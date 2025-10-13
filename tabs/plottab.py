from PySide6.QtWidgets import QWidget, QGridLayout, QPushButton, QHBoxLayout
from PySide6.QtCore import QTimer, QUrl
from PySide6.QtGui import QColor
from PySide6.QtWebEngineWidgets import QWebEngineView
import pyqtgraph as pg
import pandas as pd
import numpy as np
import tempfile
import plotly.express as px
import plotly.graph_objects as go

PRIMARY_REDUNDANT = {
    "Temp_C": ("Temp_C", None),
    "Altitude_m": ("Altitude_m", "Altitude_R_m"),
    "Pressure_Pa": ("Pressure_Pa", None),
    "Velocity_m_s": ("Velocity_m_s", "Velocity_R_m_s"),
    "Accel_m_s2": ("Accel_m_s2", "Accel_R_m_s2"),
    "Battery_pct": ("Battery_pct", "Battery_R_pct")
}

PLOT_CONFIGS = [
    ("Altitude_m", "Altitude (m)", QColor(20, 100, 220)),
    ("Temp_C", "Temp (°C)", QColor(255, 69, 0)),
    ("Pressure_Pa", "Pressure (Pa)", QColor(0, 191, 255)),
    ("Velocity_m_s", "Velocity (m/s)", QColor(50, 205, 50)),
    ("Accel_m_s2", "Accel (m/s²)", QColor(255, 160, 0)),
    ("Battery_pct", "Battery (%)", QColor(128, 0, 255)),
]

class PlotTab(QWidget):
    def __init__(self, csv_path=None, logger=None):
        super().__init__()
        self.csv_path = csv_path or "C:\\updated\\mission_profile_telemetry.csv"
        self.logger = logger

        self.layout = QGridLayout()
        self.layout.setSpacing(12)
        self.ml_button = QPushButton("Show Predicted (ML)")
        self.ml_button.setCheckable(True)
        self.ml_button.setToolTip("Toggle ML-predicted overlay for all plots")
        self.ml_button.clicked.connect(self.update_data)
        topbar = QHBoxLayout(); topbar.addStretch(); topbar.addWidget(self.ml_button)
        self.layout.addLayout(topbar, 0, 0, 1, 3)

        self.plots, self.curves, self.curves_redundant, self.curves_ml, self.labels = [], [], [], [], []
        start_row = 1  # ML toggle on row 0
        for i, (sensor, ylabel, color) in enumerate(PLOT_CONFIGS):
            plot = pg.PlotWidget(title=ylabel)
            plot.setBackground('w'); plot.showGrid(x=True, y=True, alpha=0.3)
            plot.setLabel('left', ylabel); plot.setLabel('bottom', 'Time', units='s')
            curve = plot.plot(pen=pg.mkPen(color, width=2), name="Measured")
            redundant_curve = plot.plot(pen=pg.mkPen("red", width=2, style=pg.QtCore.Qt.DashLine), name="Redundant")
            ml_curve = plot.plot(pen=pg.mkPen("magenta", width=2, style=pg.QtCore.Qt.DotLine), name="Predicted")
            ml_curve.hide()
            plot.addLegend()
            self.plots.append(plot)
            self.curves.append(curve)
            self.curves_redundant.append(redundant_curve)
            self.curves_ml.append(ml_curve)
            self.labels.append(sensor)
            self.layout.addWidget(plot, start_row + i // 3, i % 3)

        # GPS
        self.gps_view = QWebEngineView()
        self.gps_view.setMinimumSize(320, 240)
        self.layout.addWidget(self.gps_view, start_row + 1, 2)
        self.setLayout(self.layout)
        self.timer = QTimer(); self.timer.timeout.connect(self.update_data); self.timer.start(1000)

    def update_data(self):
        if not self.csv_path: return
        try:
            df = pd.read_csv(self.csv_path)
            if df.empty or len(df) < 2: return
            df_recent = df.tail(100)
            x_values = df_recent["Time_s"].values if "Time_s" in df_recent else np.arange(len(df_recent))
            for i, (sensor, _, color) in enumerate(PLOT_CONFIGS):
                prim_col, red_col = PRIMARY_REDUNDANT[sensor]
                y_prim = df_recent[prim_col].copy() if prim_col in df_recent.columns else pd.Series([np.nan] * len(df_recent))
                if red_col and red_col in df_recent.columns:
                    y_red = df_recent[red_col].copy()
                    is_redundant = y_prim.isna() | (y_prim == 0)
                    y_display = y_prim.mask(is_redundant, y_red)
                    self.curves[i].setData(x_values, y_display.tolist())
                    y_masked_for_plot = y_display.where(is_redundant, np.nan)
                    self.curves_redundant[i].setData(x_values, y_masked_for_plot.tolist())
                else:
                    self.curves[i].setData(x_values, y_prim.tolist())
                    self.curves_redundant[i].clear()
                # ML overlay
                if self.ml_button.isChecked():
                    y_pred = self.dummy_predictor(y_prim)
                    self.curves_ml[i].setData(x_values, y_pred)
                    self.curves_ml[i].show()
                else:
                    self.curves_ml[i].hide()
            # GPS
            lat_col, lon_col = "Latitude_deg", "Longitude_deg"
            if lat_col in df_recent.columns and lon_col in df_recent.columns:
                lat = df_recent[lat_col].dropna().tolist()
                lon = df_recent[lon_col].dropna().tolist()
                if lat and lon: self._update_gps_map(lat, lon)
        except Exception as e:
            print("Plot error:", e)
            if self.logger: self.logger.add_log("ERROR", "Plot error", str(e))

    def dummy_predictor(self, y):
        y = np.array(y)
        return (y + np.random.normal(0, 0.02, size=len(y))).tolist()

    def _update_gps_map(self, lat_list, lon_list):
        try:
            fig = px.scatter_mapbox(
                lat=lat_list,
                lon=lon_list,
                zoom=12,
                mapbox_style="open-street-map",
                title="Rocket GPS Tracking"
            )
            fig.add_trace(go.Scattermapbox(
                lat=[lat_list[-1]], lon=[lon_list[-1]],
                mode='markers', marker=dict(size=15, color='red'), name='Current Position'))
            temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.html')
            fig.write_html(temp_file.name); temp_file.close()
            self.gps_view.load(QUrl.fromLocalFile(temp_file.name))
        except Exception as e:
            print("GPS map error:", e)
