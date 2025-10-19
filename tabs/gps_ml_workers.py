# C:\MERN_TT\tabs\gps_ml_workers.py
from PySide6.QtCore import QObject, Signal, Slot
import os, math, tempfile
import numpy as np

MODEL_CANDIDATES = [
    os.path.join("models", "landing_predictor.pkl"),
    os.path.join(os.getcwd(), "landing_predictor.pkl"),
    os.path.join(os.getcwd(), "models", "landing_predictor.pkl"),
    r"C:\MERN_TT\models\landing_predictor.pkl",
]

def _find_model():
    for p in MODEL_CANDIDATES:
        try:
            if os.path.exists(p):
                return p
        except Exception:
            pass
    return None

def _deg_offsets(lat_deg, dx_m, dy_m):
    # dy -> lat, dx -> lon
    m_to_deg_lat = 1.0 / 111000.0
    m_to_deg_lon = m_to_deg_lat / max(1e-6, math.cos(math.radians(lat_deg)))
    return dy_m * m_to_deg_lat, dx_m * m_to_deg_lon

def _ellipse(center_lat, center_lon, radius_m, points=64):
    lat, lon = center_lat, center_lon
    m_to_deg_lat = 1.0 / 111000.0
    m_to_deg_lon = m_to_deg_lat / max(1e-6, math.cos(math.radians(lat)))
    a = radius_m
    b = radius_m * 0.75  # slightly elliptical
    out = []
    for t in np.linspace(0, 2*math.pi, points):
        dx = a * math.cos(t)
        dy = b * math.sin(t)
        dlat, dlon = _deg_offsets(lat, dx, dy)
        out.append((lat + dlat, lon + dlon))
    return out

class LandingPredictWorker(QObject):
    finished = Signal(dict)   # {center:(lat,lon), radius_m:float, path:list}
    error = Signal(str)

    def __init__(self, last_lat, last_lon, last_alt, wind_u=0.0, wind_v=0.0):
        super().__init__()
        self.last_lat = float(last_lat)
        self.last_lon = float(last_lon)
        self.last_alt = float(last_alt) if last_alt is not None else 0.0
        self.wind_u = float(wind_u)
        self.wind_v = float(wind_v)

    @Slot()
    def run(self):
        try:
            # Try ML model; fallback to parametric drift if unavailable
            center_lat, center_lon, radius_m = self._predict_center()
            # Create a simple magenta path from current to predicted landing
            path = [(self.last_lat, self.last_lon), (center_lat, center_lon)]
            self.finished.emit({"center": (center_lat, center_lon), "radius_m": radius_m, "path": path})
        except Exception as e:
            self.error.emit(str(e))

    def _predict_center(self):
        model = None
        try:
            import joblib
            mp = _find_model()
            if mp:
                model = joblib.load(mp)
        except Exception:
            model = None

        if model is not None:
            X = np.array([[self.last_alt, self.wind_u, self.wind_v]], dtype=float)
            dlat_deg, dlon_deg, radius_m = model.predict(X)[0]
            lat = self.last_lat + float(dlat_deg)
            lon = self.last_lon + float(dlon_deg)
            radius_m = float(max(50.0, radius_m))
            return lat, lon, radius_m

        # Fallback: simple drift
        speed = math.hypot(self.wind_u, self.wind_v)
        drift_m = 60.0 + 0.15 * self.last_alt + 10.0 * speed
        heading = math.atan2(self.wind_v, self.wind_u)
        dx = drift_m * math.cos(heading)
        dy = drift_m * math.sin(heading)
        dlat, dlon = _deg_offsets(self.last_lat, dx, dy)
        lat = self.last_lat + dlat
        lon = self.last_lon + dlon
        radius_m = 180.0 + 0.18 * self.last_alt + 1.2 * speed
        return lat, lon, radius_m

class FoliumRenderWorker(QObject):
    finished = Signal(str)    # html file path
    error = Signal(str)

    def __init__(self, track_lat, track_lon, center, ellipse_pts, sender=None, receiver=None, current=None, path=None, zoom=13):
        super().__init__()
        self.track_lat = list(track_lat or [])
        self.track_lon = list(track_lon or [])
        self.center = center
        self.ellipse = ellipse_pts or []
        self.sender = sender
        self.receiver = receiver
        self.current = current
        self.path = path or []
        self.zoom = zoom

    @Slot()
    def run(self):
        try:
            import folium, tempfile
            if not self.track_lat or not self.track_lon:
                self.finished.emit("")
                return

            n = min(len(self.track_lat), len(self.track_lon))
            lat = self.track_lat[-n:]
            lon = self.track_lon[-n:]
            center = self.center if self.center else (lat[-1], lon[-1])
            m = folium.Map(location=center, zoom_start=self.zoom, tiles="OpenStreetMap")

            # Track
            folium.PolyLine(list(zip(lat, lon)), color="blue", weight=2).add_to(m)

            # Current
            if self.current:
                folium.Marker(self.current, icon=folium.Icon(color="green"), tooltip="Current").add_to(m)

            # Sender/Receiver
            if self.sender:
                folium.Marker(self.sender, icon=folium.Icon(color="purple"), tooltip="Sender").add_to(m)
            if self.receiver:
                folium.Marker(self.receiver, icon=folium.Icon(color="darkred"), tooltip="Receiver").add_to(m)

            # Predicted landing center + ellipse
            if self.center:
                folium.Marker(self.center, icon=folium.Icon(color="red"), tooltip="Predicted Landing").add_to(m)
            if self.ellipse and len(self.ellipse) > 3:
                folium.Polygon(self.ellipse, color="red", fill=True, fill_opacity=0.20).add_to(m)

            # Path line
            if self.path and len(self.path) > 1:
                folium.PolyLine(self.path, color="magenta", weight=2, opacity=0.85).add_to(m)

            # Distances popup (if we have points)
            def haversine_km(a, b):
                import math
                R = 6371.0
                lat1, lon1 = map(math.radians, a)
                lat2, lon2 = map(math.radians, b)
                dlat = lat2 - lat1
                dlon = lon2 - lon1
                h = math.sin(dlat/2)**2 + math.cos(lat1)*math.cos(lat2)*math.sin(dlon/2)**2
                return 2*R*math.asin(math.sqrt(h))

            if self.center:
                lines = []
                if self.current:
                    lines.append(f"Current→Landing: {haversine_km(self.current, self.center):.2f} km")
                if self.sender:
                    lines.append(f"Sender→Landing: {haversine_km(self.sender, self.center):.2f} km")
                if self.receiver:
                    lines.append(f"Receiver→Landing: {haversine_km(self.receiver, self.center):.2f} km")
                if lines:
                    folium.map.Marker(
                        self.center,
                        icon=folium.DivIcon(html=f\"\"\"<div style='font-size:12px;color:#222;background:#fff;padding:4px;border-radius:6px;border:1px solid #999'>{'<br/>'.join(lines)}</div>\"\"\")
                    ).add_to(m)

            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".html")
            m.save(tmp.name); tmp.close()
            self.finished.emit(tmp.name)
        except Exception as e:
            self.error.emit(str(e))
