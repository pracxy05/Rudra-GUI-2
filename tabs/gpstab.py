# gpstab.py
import os, tempfile, math, numpy as np, pandas as pd

# Guard joblib
try:
    import joblib
except Exception:
    joblib = None

# Guard WebEngine
try:
    from PySide6.QtWebEngineWidgets import QWebEngineView
except Exception:
    QWebEngineView = None

from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel
from PySide6.QtCore import QTimer, QUrl, Slot

# Try to import ROCKET_PARAMS from plottab, else define local fallback (avoid importing WebEngine via plottab)
try:
    from plottab import ROCKET_PARAMS, generate_trajectory as _gen_traj
    def generate_trajectory(params, t_max=60.0, dt=0.1):
        return _gen_traj(params, t_max=t_max, dt=dt)
except Exception:
    ROCKET_PARAMS = {
        "apogee_m": 1076.0, "apogee_tol_m": 5.0, "descent_rate_m_s": 4.36,
        "stability_margin_cal": 2.08, "flight_time_s": 249.0,
        "max_vel_m_s": 148.0, "max_acc_m_s2": 102.0,
        "burnout_t": 3.81, "apogee_t": 15.74, "burnout_alt": 350.0,
    }
    def generate_trajectory(params, t_max=60.0, dt=0.1):
        t = np.arange(0.0, t_max + 1e-9, dt)
        burnout_t = params.get("burnout_t", 3.81)
        apogee_t = params.get("apogee_t", 15.74)
        burnout_alt = params.get("burnout_alt", 350.0)
        apogee = params.get("apogee_m", 1076.0)
        descent_rate = params.get("descent_rate_m_s", 4.36)
        max_acc = params.get("max_acc_m_s2", 102.0)
        max_vel = params.get("max_vel_m_s", 148.0)
        a_est = (2 * burnout_alt) / (burnout_t ** 2) if burnout_t > 0 else 5.0
        a_used = min(a_est, max_acc)
        v_burn = min(a_used * burnout_t, max_vel)
        def hermite(ti, t0, t1, y0, y1, v0, v1):
            s = np.clip((ti - t0) / (t1 - t0), 0.0, 1.0)
            h00 = (2*s**3 - 3*s**2 + 1); h10 = (s**3 - 2*s**2 + s)
            h01 = (-2*s**3 + 3*s**2);    h11 = (s**3 - s**2)
            return h00*y0 + h10*(t1-t0)*v0 + h01*y1 + h11*(t1-t0)*v1
        alt = np.zeros_like(t); vel = np.zeros_like(t); acc = np.zeros_like(t)
        for i, ti in enumerate(t):
            if ti <= burnout_t:
                alt[i] = 0.5 * a_used * (ti**2); vel[i] = a_used * ti; acc[i] = a_used
            elif ti <= apogee_t:
                alt[i] = hermite(ti, burnout_t, apogee_t, burnout_alt, apogee, v_burn, 0.0)
                dt_small = 1e-3
                alt_plus = hermite(ti + dt_small, burnout_t, apogee_t, burnout_alt, apogee, v_burn, 0.0)
                vel[i] = (alt_plus - alt[i]) / dt_small
                alt_minus = hermite(ti - dt_small, burnout_t, apogee_t, burnout_alt, apogee, v_burn, 0.0)
                acc[i] = (alt_plus - 2*alt[i] + alt_minus) / (dt_small**2)
            else:
                down_t = ti - apogee_t
                alt[i] = max(apogee - descent_rate * down_t, 0.0)
                vel[i] = -descent_rate; acc[i] = 0.0
        P0 = 101325.0; H = 8000.0
        pressure = P0 * np.exp(-alt / H)
        return t, alt, vel, acc, pressure

MODEL_FILE = "models/plot_predictor.pkl"
FALLBACK_MODEL = "models/plot_predictor.pkl"
os.makedirs("models", exist_ok=True)

def _to_float(x):
    try:
        if x is None: return None
        return float(x)
    except Exception:
        return None

class GPSTab(QWidget):
    def __init__(self, csv_path: str = None, logger=None):
        super().__init__()
        self.csv_path = csv_path
        self.logger = logger
        self.lat, self.lon, self.alt = [], [], []
        self.model = self._maybe_load_model()

        layout = QVBoxLayout(self)
        self.label = QLabel("🗺️ GPS Tracking with ML Landing Prediction")
        layout.addWidget(self.label)

        if QWebEngineView is not None:
            self.webview = QWebEngineView()
            layout.addWidget(self.webview, stretch=1)
        else:
            self.webview = None
            warn = QLabel("QWebEngine not available — install PySide6-WebEngine to enable map")
            layout.addWidget(warn)

        self.setLayout(layout)

        self.timer = QTimer(self)
        self.timer.setInterval(2000)
        self.timer.timeout.connect(self._periodic_update)
        self.timer.start()

    def _maybe_load_model(self):
        if not joblib:
            return None
        try:
            if os.path.exists(MODEL_FILE):
                return joblib.load(MODEL_FILE)
            elif os.path.exists(FALLBACK_MODEL):
                return joblib.load(FALLBACK_MODEL)
        except Exception as e:
            print("[GPSTab] model load error:", e)
        return None

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
            if len(self.lat) > 800:
                self.lat = self.lat[-800:]; self.lon = self.lon[-800:]; self.alt = self.alt[-800:]
            self._render_map()
        except Exception as e:
            print("[GPSTab] append_live_data error:", e)

    def _periodic_update(self):
        if self.csv_path and os.path.exists(self.csv_path):
            try:
                df = pd.read_csv(self.csv_path)
                if "gps_lat" in df.columns and "gps_lon" in df.columns:
                    la = df["gps_lat"].dropna().tolist()
                    lo = df["gps_lon"].dropna().tolist()
                    alt = df.get("gps_alt", df.get("bmp_alt", pd.Series([0]*len(df)))).fillna(0).tolist()
                    n = min(len(la), len(lo), len(alt))
                    if n > 0:
                        self.lat = la[-n:]; self.lon = lo[-n:]; self.alt = alt[-n:]
                        self._render_map()
            except Exception as e:
                print("[GPSTab] CSV read error:", e)
                if self.logger:
                    self.logger.add_log("ERROR", "GPSTab CSV", str(e))

    def _render_map(self):
        if self.webview is None:
            return  # no WebEngine — skip
        try:
            import folium
            if not self.lat or not self.lon:
                return
            n = min(len(self.lat), len(self.lon))
            lat_list = self.lat[-n:]; lon_list = self.lon[-n:]; alt_list = (self.alt[-n:] if self.alt else [0]*n)
            center = [lat_list[-1], lon_list[-1]]
            m = folium.Map(location=center, zoom_start=13, tiles="OpenStreetMap")
            folium.PolyLine(list(zip(lat_list, lon_list)), color="blue", weight=2).add_to(m)
            folium.CircleMarker(location=center, radius=6, color="red", fill=True).add_to(m)

            path, ellipse = self._predict_path_and_ellipse(center[0], center[1], alt_list[-1] if alt_list else 0.0)
            if path and len(path) > 1:
                folium.PolyLine(path, color="magenta", weight=2, opacity=0.8).add_to(m)
            if ellipse and len(ellipse) > 3:
                folium.Polygon(ellipse, color="red", fill=True, fill_opacity=0.2).add_to(m)

            tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".html")
            m.save(tmp.name); tmp.close()
            self.webview.setUrl(QUrl.fromLocalFile(tmp.name))
        except Exception as e:
            print("[GPSTab] render error:", e)

    def _predict_path_and_ellipse(self, lat0, lon0, alt0):
        try:
            times = np.linspace(0, 40, 25)
            if self.model is not None:
                Xp = np.vstack([times, np.zeros_like(times), np.zeros_like(times), np.full_like(times, 101325)]).T
                alt_preds = self.model.predict(Xp)
            else:
                _, alt_preds, _, _, _ = generate_trajectory(ROCKET_PARAMS, t_max=40.0, dt=40.0/len(times))
            path = []
            for i, a in enumerate(alt_preds):
                drift_m = max(5.0, (i+1)**1.2) + max(0.0, (alt0 - a) * 0.05)
                drift_deg = drift_m / 111000.0
                new_lat = lat0 - drift_deg * 0.6
                new_lon = lon0 + drift_deg * 1.0
                path.append((new_lat, new_lon))
                if a <= 0:
                    break
            r_m = 300.0 + 0.2 * alt0
            r_deg_lat = r_m / 111000.0
            r_deg_lon = r_deg_lat * 1.3
            angles = np.linspace(0, 2*math.pi, 48)
            ellipse = [(lat0 + r_deg_lat * math.cos(a), lon0 + r_deg_lon * math.sin(a)) for a in angles]
            return path, ellipse
        except Exception as e:
            print("[GPSTab] predict error:", e)
            return [(lat0, lon0)], []
