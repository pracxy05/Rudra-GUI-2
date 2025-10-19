import os, time
from collections import deque
from typing import Optional
import numpy as np
import pandas as pd
import pyqtgraph as pg

from PySide6.QtCore import QTimer, Slot, QThread, Qt
from PySide6.QtWidgets import QWidget, QGridLayout, QPushButton, QHBoxLayout
from PySide6.QtGui import QColor

try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except Exception:
    QWebEngineView = None

try:
    from tabs.ml_workers import PlotPredictWorker
except Exception:
    try:
        from .ml_workers import PlotPredictWorker
    except Exception:
        PlotPredictWorker = None

PRIMARY_REDUNDANT = {
    "Altitudem": ("Altitudem", "AltitudemREDUNDANT"),
    "TempC": ("TempC", "TempCREDUNDANT"),
    "PressurePa": ("PressurePa", "PressurePaREDUNDANT"),
    "Velocityms": ("Velocityms", "VelocitymsREDUNDANT"),
    "Accelms2": ("Accelms2", "Accelms2REDUNDANT"),
    "Batterypct": ("Batterypct", None),
}

PLOT_CONFIGS = [
    ("Altitudem", "Altitude (m)", QColor(20, 100, 220)),
    ("TempC", "Temp (°C)", QColor(255, 69, 0)),
    ("PressurePa", "Pressure (Pa)", QColor(0, 191, 255)),
    ("Velocityms", "Velocity (m/s)", QColor(50, 205, 50)),
    ("Accelms2", "Accel (m/s²)", QColor(255, 160, 0)),
    ("Batterypct", "Battery (%)", QColor(128, 0, 255)),
]

MODEL_CANDIDATES = [
    os.path.join("models", "rocketmultioutputmodellight.pkl"),
    os.path.join(os.getcwd(), "rocketmultioutputmodellight.pkl"),
    os.path.join(os.getcwd(), "models", "rocketmultioutputmodellight.pkl"),
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models", "rocketmultioutputmodellight.pkl")),
    r"C:\MERN_TT\models\rocketmultioutputmodellight.pkl",
]

def _find_model_file():
    for p in MODEL_CANDIDATES:
        try:
            if os.path.exists(p):
                return p
        except Exception:
            pass
    return None

def _safe_float(x):
    try:
        if x is None:
            return None
        return float(x)
    except Exception:
        return None

class PlotTab(QWidget):
    def __init__(self, csv_path: Optional[str] = None, logger=None, buffer_size: int = 800):
        super().__init__()
        self.csv_path = csv_path
        self.logger = logger
        self.buffer_size = buffer_size
        self.buffer = deque(maxlen=self.buffer_size)
        self._last_draw = 0.0
        self._need_draw = False

        self.model = None
        self._ml_thread: Optional[QThread] = None
        self._ml_worker = None
        self._ml_busy = False
        self._ml_enabled = False
        self._ml_last_ts = 0.0

        self._build_ui()
        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_timer)
        self.timer.start(160)
        self._csv_mtime = None

    def _build_ui(self):
        self.layout = QGridLayout()
        self.layout.setSpacing(12)

        self.ml_button = QPushButton("SHOW PREDICTED (ML)")
        self.ml_button.setCheckable(True)
        self.ml_button.setChecked(False)
        self.ml_button.toggled.connect(self._on_ml_toggled)

        topbar = QHBoxLayout()
        topbar.addStretch()
        topbar.addWidget(self.ml_button)
        self.layout.addLayout(topbar, 0, 0, 1, 3)

        self.plots, self.curves, self.curves_ml, self.curves_red = [], [], [], []
        start_row = 1
        for i, (sensor, ylabel, color) in enumerate(PLOT_CONFIGS):
            plot = pg.PlotWidget(title=ylabel)
            plot.setBackground("w")
            plot.showGrid(x=True, y=True, alpha=0.25)
            plot.setLabel("left", ylabel)
            plot.setLabel("bottom", "Time", units="s")
            plot.setDownsampling(auto=True, mode="peak")
            plot.setClipToView(True)
            pen_main = pg.mkPen(color, width=2)
            pen_ml = pg.mkPen("magenta", width=2, style=Qt.DotLine)
            pen_red = pg.mkPen((255, 204, 0), width=2, style=Qt.DashLine)
            main_curve = plot.plot(pen=pen_main, name="Measured")
            ml_curve = plot.plot(pen=pen_ml, name="Predicted")
            ml_curve.hide()
            red_curve = plot.plot(pen=pen_red, name="Redundant")
            red_curve.hide()
            plot.addLegend()
            self.plots.append(plot)
            self.curves.append(main_curve)
            self.curves_ml.append(ml_curve)
            self.curves_red.append(red_curve)
            self.layout.addWidget(plot, start_row + i // 3, i % 3)

        if QWebEngineView is not None:
            self.gps_view = QWebEngineView()
            self.gps_view.setMinimumSize(320, 240)
            self.layout.addWidget(self.gps_view, start_row + 1, 2)
        else:
            self.gps_view = None
        self.setLayout(self.layout)

    @Slot(dict)
    def update_plot_data(self, row: dict):
        try:
            norm = self._normalize_row(row)
            self.buffer.append(norm)
            self._need_draw = True
        except Exception as e:
            print("[PlotTab] update error:", e)
            if self.logger:
                self.logger.add_log("ERROR", "PlotTab.update", str(e))

    def _normalize_row(self, row: dict) -> dict:
        out = {}
        t = None
        for k in ("Time_s", "time", "time_s", "Times"):
            if k in row and row.get(k) is not None:
                try:
                    t = float(row.get(k))
                    break
                except Exception:
                    t = None
        if t is None:
            t = (self.buffer[-1]["Time_s"] + 1) if self.buffer else 0.0
        out["Time_s"] = t
        out["Altitudem"] = _safe_float(row.get("Altitudem")) or float("nan")
        out["AltitudemREDUNDANT"] = _safe_float(row.get("AltitudemREDUNDANT")) or float("nan")
        out["TempC"] = _safe_float(row.get("TempC")) or float("nan")
        out["TempCREDUNDANT"] = _safe_float(row.get("TempCREDUNDANT")) or float("nan")
        out["PressurePa"] = _safe_float(row.get("PressurePa")) or float("nan")
        out["PressurePaREDUNDANT"] = _safe_float(row.get("PressurePaREDUNDANT")) or float("nan")
        out["Batterypct"] = _safe_float(row.get("Batterypct")) or float("nan")
        out["Velocityms"] = _safe_float(row.get("Velocityms")) or float("nan")
        out["VelocitymsREDUNDANT"] = _safe_float(row.get("VelocitymsREDUNDANT")) or float("nan")
        out["Accelms2"] = _safe_float(row.get("Accelms2")) or float("nan")
        out["Accelms2REDUNDANT"] = _safe_float(row.get("Accelms2REDUNDANT")) or float("nan")
        out["Humiditypct"] = _safe_float(row.get("Humiditypct")) or float("nan")
        out["HumiditypctREDUNDANT"] = _safe_float(row.get("HumiditypctREDUNDANT")) or float("nan")
        out["WindSpeedms"] = _safe_float(row.get("WindSpeedms")) or float("nan")
        out["WindSpeedmsREDUNDANT"] = _safe_float(row.get("WindSpeedmsREDUNDANT")) or float("nan")
        return out

    def _on_timer(self):
        if self.csv_path and os.path.exists(self.csv_path):
            try:
                mtime = os.path.getmtime(self.csv_path)
                if self._csv_mtime is None or mtime != self._csv_mtime:
                    self._csv_mtime = mtime
                    df = pd.read_csv(self.csv_path)
                    for r in df.tail(self.buffer_size).to_dict(orient="records"):
                        norm = self._normalize_row(r)
                        self.buffer.append(norm)
                        self._need_draw = True
            except Exception as e:
                print("[PlotTab] CSV read error:", e)
        now = time.time()
        if self._need_draw or (now - self._last_draw) > 0.5:
            try:
                self._redraw()
            finally:
                self._last_draw = now
                self._need_draw = False
        if self._ml_enabled and (now - self._ml_last_ts) > 0.5:
            self._schedule_ml()
            self._ml_last_ts = now

    def _redraw(self):
        if not self.buffer:
            return
        df = pd.DataFrame(list(self.buffer))
        if "Time_s" in df.columns:
            x = df["Time_s"].fillna(method="ffill").fillna(0).values
        else:
            x = np.arange(len(df))
        for i, (sensor, _, _) in enumerate(PLOT_CONFIGS):
            prim_key, red_key = PRIMARY_REDUNDANT.get(sensor, (sensor, None))
            y = df.get(prim_key, pd.Series([np.nan] * len(x))).values
            self.curves[i].setData(x, y)
            # Redundant visual line
            if red_key and red_key in df.columns:
                y_red = df.get(red_key, pd.Series([np.nan] * len(x))).values
                self.curves_red[i].setData(x, y_red)
                self.curves_red[i].show()
            else:
                self.curves_red[i].hide()

    def _on_ml_toggled(self, on: bool):
        self._ml_enabled = on
        self.ml_button.setText("HIDE PREDICTED (ML)" if on else "SHOW PREDICTED (ML)")
        if not on:
            for c in self.curves_ml:
                c.hide()
            return
        if self.model is None:
            self._load_model()
        else:
            self._schedule_ml()

    def _load_model(self):
        try:
            import joblib
        except Exception:
            print("[PlotTab] joblib not installed; ML disabled.")
            self.ml_button.setChecked(False)
            return
        try:
            model_path = _find_model_file()
            if model_path:
                self.model = joblib.load(model_path)
                print(f"[PlotTab] Loaded model: {model_path}")
                self._schedule_ml()
            else:
                print("[PlotTab] Model not found in expected locations.")
                self.ml_button.setChecked(False)
        except Exception as e:
            print("[PlotTab] model load error:", e)
            self.ml_button.setChecked(False)

    def _schedule_ml(self):
        if not self._ml_enabled or self._ml_busy or self.model is None or PlotPredictWorker is None or not self.buffer:
            return
        self._ml_busy = True
        df = pd.DataFrame(list(self.buffer))
        x = df.get("Time_s", pd.Series(np.arange(len(df)))).fillna(method="ffill").fillna(0).values
        self._ml_thread = QThread()
        self._ml_worker = PlotPredictWorker(self.model, x, df)
        self._ml_worker.moveToThread(self._ml_thread)
        self._ml_worker.finished.connect(self._apply_ml)
        self._ml_worker.error.connect(self._ml_error)
        self._ml_worker.finished.connect(self._ml_thread.quit)
        self._ml_worker.error.connect(self._ml_thread.quit)
        self._ml_thread.started.connect(self._ml_worker.run)
        self._ml_thread.finished.connect(self._clear_worker)
        self._ml_thread.start()

    @Slot()
    def _clear_worker(self):
        try:
            if self._ml_worker is not None:
                self._ml_worker.deleteLater()
        except Exception:
            pass
        self._ml_worker = None
        self._ml_thread = None

    def _apply_ml(self, predictions: dict):
        try:
            df = pd.DataFrame(list(self.buffer))
            x = df.get("Time_s", pd.Series(np.arange(len(df)))).fillna(method="ffill").fillna(0).values
            for i, (sensor, _, _) in enumerate(PLOT_CONFIGS):
                if sensor in predictions:
                    y_pred = predictions[sensor]
                    self.curves_ml[i].setData(x, y_pred.tolist())
                    self.curves_ml[i].show()
                elif sensor == "Batterypct":
                    battery_pred = np.maximum(0.0, 100.0 - 0.02 * x)
                    self.curves_ml[i].setData(x, battery_pred.tolist())
                    self.curves_ml[i].show()
                else:
                    self.curves_ml[i].hide()
        finally:
            self._ml_busy = False

    def _ml_error(self, msg: str):
        print("[PlotTab] ML error:", msg)
        self._ml_busy = False
