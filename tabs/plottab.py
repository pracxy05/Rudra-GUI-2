import os, time
from collections import deque
from typing import Optional
import numpy as np
import pandas as pd
import pyqtgraph as pg

from PySide6.QtCore import QTimer, Slot, QThread, Qt
from PySide6.QtWidgets import QWidget, QGridLayout, QPushButton, QHBoxLayout
from PySide6.QtGui import QColor

# Optional WebEngine mini-view
try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except Exception:
    QWebEngineView = None

# Optional joblib for model loading
try:
    import joblib
except Exception:
    joblib = None

# Import worker (ensure tabs/ml_workers.py exists)
try:
    # When imported as package
    from tabs.ml_workers import PlotPredictWorker
except Exception:
    try:
        # When using relative package import
        from .ml_workers import PlotPredictWorker
    except Exception:
        PlotPredictWorker = None

# Plot configuration
PRIMARY_REDUNDANT = {
    "Altitude_m": ("Altitude_m", None),
    "Temp_C": ("Temp_C", None),
    "Pressure_Pa": ("Pressure_Pa", None),
    "Velocity_m_s": ("Velocity_m_s", None),
    "Accel_m_s2": ("Accel_m_s2", None),
    "Battery_pct": ("Battery_pct", None),
}

PLOT_CONFIGS = [
    ("Altitude_m", "Altitude (m)", QColor(20, 100, 220)),
    ("Temp_C", "Temp (°C)", QColor(255, 69, 0)),
    ("Pressure_Pa", "Pressure (Pa)", QColor(0, 191, 255)),
    ("Velocity_m_s", "Velocity (m/s)", QColor(50, 205, 50)),
    ("Accel_m_s2", "Accel (m/s²)", QColor(255, 160, 0)),
    ("Battery_pct", "Battery (%)", QColor(128, 0, 255)),
]

# Model search order (adds your absolute path)
MODEL_CANDIDATES = [
    os.path.join("models", "plot_predictor.pkl"),                                   # project-root/models
    os.path.join(os.getcwd(), "plot_predictor.pkl"),                                 # CWD
    os.path.join(os.getcwd(), "models", "plot_predictor.pkl"),                       # CWD/models
    os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "models", "plot_predictor.pkl")),  # tabs/../models
    r"C:\MERN_TT\models\plot_predictor.pkl",                                         # your explicit path
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

        # ML state
        self.model = None
        self._ml_thread: Optional[QThread] = None
        self._ml_worker = None
        self._ml_busy = False
        self._ml_enabled = False
        self._ml_last_ts = 0.0

        self._build_ui()

        self.timer = QTimer(self)
        self.timer.timeout.connect(self._on_timer)
        self.timer.start(160)  # ~6 FPS

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

        self.plots, self.curves, self.curves_ml = [], [], []
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
            main_curve = plot.plot(pen=pen_main, name="Measured")
            ml_curve = plot.plot(pen=pen_ml, name="Predicted")
            ml_curve.hide()
            plot.addLegend()
            self.plots.append(plot)
            self.curves.append(main_curve)
            self.curves_ml.append(ml_curve)
            self.layout.addWidget(plot, start_row + i // 3, i % 3)

        # Optional mini map spot (unused if QWebEngineView missing)
        if QWebEngineView is not None:
            self.gps_view = QWebEngineView()
            self.gps_view.setMinimumSize(320, 240)
            self.layout.addWidget(self.gps_view, start_row + 1, 2)
        else:
            self.gps_view = None

        self.setLayout(self.layout)

    # ------------- Public API -------------
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

    # ------------- Internals --------------
    def _normalize_row(self, row: dict) -> dict:
        out = {}
        # Time
        t = None
        for k in ("Time_s", "time", "time_s", "Time"):
            if k in row and row.get(k) is not None:
                try:
                    t = float(row.get(k))
                    break
                except Exception:
                    t = None
        if t is None:
            t = (self.buffer[-1]["Time_s"] + 1) if self.buffer else 0.0
        out["Time_s"] = t

        # Altitude
        alt = None
        for k in ("Altitude_m", "gps_alt", "bmp_alt"):
            if k in row and row.get(k) not in (None, "", "nan"):
                try:
                    alt = float(row.get(k))
                    break
                except Exception:
                    alt = None
        out["Altitude_m"] = alt if alt is not None else float("nan")

        # Other channels
        out["Temp_C"] = _safe_float(row.get("bme_temp")) or float("nan")
        out["Pressure_Pa"] = _safe_float(row.get("bme_p")) or _safe_float(row.get("Pressure_Pa")) or float("nan")
        out["Battery_pct"] = _safe_float(row.get("Battery_pct")) or float("nan")

        out["Velocity_m_s"] = _safe_float(row.get("Velocity_m_s")) or float("nan")
        out["Accel_m_s2"] = _safe_float(row.get("Accel_m_s2")) or float("nan")
        return out

    def _on_timer(self):
        # Optional CSV tailing
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

        # Redraw throttle
        now = time.time()
        if self._need_draw or (now - self._last_draw) > 0.5:
            try:
                self._redraw()
            finally:
                self._last_draw = now
                self._need_draw = False

        # ML throttle (~2 Hz)
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
            prim_key, _ = PRIMARY_REDUNDANT.get(sensor, (sensor, None))
            y = df.get(prim_key, pd.Series([np.nan] * len(x))).values
            try:
                self.curves[i].setData(x, y)
            except Exception as e:
                print("[PlotTab] setData error:", e)

    # --------- ML handling ----------
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
        if joblib is None:
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
        self._ml_worker = PlotPredictWorker(self.model, x, df)  # keep strong reference
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

    def _apply_ml(self, y_pred_alt: np.ndarray):
        try:
            df = pd.DataFrame(list(self.buffer))
            x = df.get("Time_s", pd.Series(np.arange(len(df)))).fillna(method="ffill").fillna(0).values
            for i, (sensor, _, _) in enumerate(PLOT_CONFIGS):
                if sensor == "Altitude_m":
                    self.curves_ml[i].setData(x, y_pred_alt.tolist())
                    self.curves_ml[i].show()
                elif sensor == "Velocity_m_s":
                    velpred = np.gradient(y_pred_alt, x)
                    self.curves_ml[i].setData(x, velpred.tolist())
                    self.curves_ml[i].show()
                elif sensor == "Accel_m_s2":
                    accelpred = np.gradient(np.gradient(y_pred_alt, x), x)
                    self.curves_ml[i].setData(x, accelpred.tolist())
                    self.curves_ml[i].show()
                elif sensor == "Temp_C":
                    temppred = 20.0 - 0.0065 * y_pred_alt
                    self.curves_ml[i].setData(x, temppred.tolist())
                    self.curves_ml[i].show()
                elif sensor == "Pressure_Pa":
                    prespred = 101325.0 * np.exp(-y_pred_alt / 8000.0)
                    self.curves_ml[i].setData(x, prespred.tolist())
                    self.curves_ml[i].show()
                else:
                    self.curves_ml[i].hide()
        finally:
            self._ml_busy = False

    def _ml_error(self, msg: str):
        print("[PlotTab] ML error:", msg)
        self._ml_busy = False
