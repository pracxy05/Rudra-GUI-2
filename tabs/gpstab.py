# C:\MERN_TT\tabs\gpstab.py
import os, time, math
import numpy as np
import pandas as pd

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import QTimer, QUrl, Slot, QThread
try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except Exception:
    QWebEngineView = None

# Workers (prediction + folium rendering)
try:
    from tabs.gps_ml_workers import LandingPredictWorker, FoliumRenderWorker
except Exception:
    from .gps_ml_workers import LandingPredictWorker, FoliumRenderWorker

def _to_float(x):
    try:
        if x is None: return None
        return float(x)
    except Exception:
        return None

class GPSTab(QWidget):
    def __init__(self, csv_path: str = None, logger=None, sender=None, receiver=None):
        super().__init__()
        self.csv_path = csv_path
        self.logger = logger
        self.sender = sender     # (lat, lon) or None
        self.receiver = receiver # (lat, lon) or None

        self.lat = []
        self.lon = []
        self.alt = []
        self._last_render = 0.0
        self._predict_thread = None
        self._predict_worker = None
        self._render_thread = None
        self._render_worker = None
        self._throttle_s = 2.0
        self._pending_render = False

        layout = QVBoxLayout(self)
        self.label = QLabel("GPS Tracking with Landing Prediction")
        layout.addWidget(self.label)

        if QWebEngineView is not None:
            self.webview = QWebEngineView()
            layout.addWidget(self.webview, stretch=1)
        else:
            self.webview = None
            layout.addWidget(QLabel("QWebEngine not available — install PySide6-WebEngine to enable map"))

        self.setLayout(layout)

        # CSV fallback polling
        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self._periodic_update)
        self.timer.start()

    # Allow setting sender/receiver later
    def set_references(self, sender=None, receiver=None):
        self.sender = sender or self.sender
        self.receiver = receiver or self.receiver

    @Slot(dict)
    def append_live_data(self, row: dict):
        try:
            la = row.get("gps_lat") or row.get("gps_lat_R")
            lo = row.get("gps_lon") or row.get("gps_lon_R")
            altv = row.get("gps_alt") or row.get("bmp_alt") or row.get("Altitude_m")
            la = _to_float(la); lo = _to_float(lo); altv = _to_float(altv)
            if la is None or lo is None:
                return
            self.lat.append(la); self.lon.append(lo); self.alt.append(altv if altv is not None else 0.0)
            if len(self.lat) > 1000:
                self.lat = self.lat[-1000:]; self.lon = self.lon[-1000:]; self.alt = self.alt[-1000:]
            self._schedule()
        except Exception as e:
            print("[GPSTab] append_live_data error:", e)

    def _periodic_update(self):
        if not self.csv_path or not os.path.exists(self.csv_path):
            return
        try:
            df = pd.read_csv(self.csv_path)
            if "gps_lat" in df.columns and "gps_lon" in df.columns:
                la = df["gps_lat"].dropna().tolist()
                lo = df["gps_lon"].dropna().tolist()
                alt = df.get("gps_alt", df.get("bmp_alt", pd.Series([0]*len(df)))).fillna(0).tolist()
                n = min(len(la), len(lo), len(alt))
                if n > 0:
                    self.lat = la[-n:]; self.lon = lo[-n:]; self.alt = alt[-n:]
                    self._schedule()
        except Exception as e:
            print("[GPSTab] CSV read error:", e)
            if self.logger: self.logger.add_log("ERROR", "GPSTab CSV", str(e))

    def _schedule(self):
        now = time.time()
        if self.webview is None:
            return
        if (now - self._last_render) < self._throttle_s or self._pending_render:
            return
        self._pending_render = True
        self._last_render = now

        # Snapshot latest
        if not self.lat or not self.lon:
            self._pending_render = False
            return
        lat0 = self.lat[-1]; lon0 = self.lon[-1]; alt0 = (self.alt[-1] if self.alt else 0.0)

        # Start prediction worker (wind unknown -> 0; you can wire live wind if available)
        self._predict_thread = QThread()
        self._predict_worker = LandingPredictWorker(lat0, lon0, alt0, 0.0, 0.0)
        self._predict_worker.moveToThread(self._predict_thread)
        self._predict_worker.finished.connect(self._on_predicted)
        self._predict_worker.error.connect(self._on_predict_error)
        self._predict_worker.finished.connect(self._predict_thread.quit)
        self._predict_worker.error.connect(self._predict_thread.quit)
        self._predict_thread.started.connect(self._predict_worker.run)
        self._predict_thread.finished.connect(self._predict_worker.deleteLater)
        self._predict_thread.start()

    @Slot(dict)
    def _on_predicted(self, result: dict):
        try:
            center = result.get("center")
            radius_m = float(result.get("radius_m", 150.0))
            path = result.get("path", [])

            # Build ellipse polygon points
            from tabs.gps_ml_workers import _ellipse
            ellipse = _ellipse(center[0], center[1], radius_m, points=64)

            # Render worker
            self._render_thread = QThread()
            self._render_worker = FoliumRenderWorker(
                self.lat, self.lon,
                center=center,
                ellipse_pts=ellipse,
                sender=self.sender,
                receiver=self.receiver,
                current=(self.lat[-1], self.lon[-1]),
                path=path,
                zoom=13
            )
            self._render_worker.moveToThread(self._render_thread)
            self._render_worker.finished.connect(self._on_rendered)
            self._render_worker.error.connect(self._on_render_error)
            self._render_worker.finished.connect(self._render_thread.quit)
            self._render_worker.error.connect(self._render_thread.quit)
            self._render_thread.started.connect(self._render_worker.run)
            self._render_thread.finished.connect(self._render_worker.deleteLater)
            self._render_thread.start()
        except Exception as e:
            print("[GPSTab] on_predicted error:", e)
            self._pending_render = False

    @Slot(str)
    def _on_rendered(self, html_path: str):
        try:
            if html_path and self.webview is not None:
                from PySide6.QtCore import QUrl
                self.webview.setUrl(QUrl.fromLocalFile(html_path))
        finally:
            self._pending_render = False

    @Slot(str)
    def _on_predict_error(self, msg: str):
        print("[GPSTab] prediction error:", msg)
        self._pending_render = False

    @Slot(str)
    def _on_render_error(self, msg: str):
        print("[GPSTab] render error:", msg)
        self._pending_render = False
