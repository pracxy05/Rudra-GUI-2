# generate_rocket_dataset.py  (place in C:\MERN_TT\models)
import os, math, argparse, json
import numpy as np
import pandas as pd
import requests

DEF_PARAMS = {
    "apogee_m": 1076.0,
    "burnout_t": 3.81,
    "apogee_t": 15.74,
    "descent_rate_m_s": 4.36,
    "burnout_alt": 350.0,
    "max_vel_m_s": 148.0,
    "max_acc_m_s2": 102.0,
    "flight_time_s": 249.0,
}

def fetch_weather(lat, lon, start_date, end_date):
    try:
        url = "https://archive-api.open-meteo.com/v1/archive"
        params = {
            "latitude": lat, "longitude": lon,
            "start_date": start_date, "end_date": end_date,
            "hourly": "temperature_2m,pressure_msl,wind_speed_10m",
            "timezone": "UTC",
        }
        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()
        h = r.json().get("hourly", {})
        temp_C = float(h.get("temperature_2m", [20])[0])
        pressure0 = float(h.get("pressure_msl", [101325])[0])
        wind = float(h.get("wind_speed_10m", [2])[0])
        return temp_C, pressure0, wind
    except Exception:
        return 20.0, 101325.0, 2.0

def generate_trajectory(params, t_max=180.0, dt=0.25):
    t = np.arange(0.0, t_max + 1e-9, dt)
    burnout_t = params["burnout_t"]; apogee_t = params["apogee_t"]
    burnout_alt = params["burnout_alt"]; apogee = params["apogee_m"]
    descent_rate = params["descent_rate_m_s"]
    max_acc = params["max_acc_m_s2"]; max_vel = params["max_vel_m_s"]

    def hermite(ti, t0, t1, y0, y1, v0, v1):
        s = np.clip((ti - t0) / (t1 - t0), 0.0, 1.0)
        h00 = (2*s**3 - 3*s**2 + 1); h10 = (s**3 - 2*s**2 + s)
        h01 = (-2*s**3 + 3*s**2);    h11 = (s**3 - s**2)
        return h00*y0 + h10*(t1-t0)*v0 + h01*y1 + h11*(t1-t0)*v1

    a_est = (2 * burnout_alt) / max(burnout_t, 1e-6)**2
    a_used = min(a_est, max_acc); v_burn = min(a_used * burnout_t, max_vel)

    alt = np.zeros_like(t); vel = np.zeros_like(t); acc = np.zeros_like(t)
    for i, ti in enumerate(t):
        if ti <= burnout_t:
            alt[i] = 0.5 * a_used * (ti**2); vel[i] = a_used * ti; acc[i] = a_used
        elif ti <= apogee_t:
            alt[i] = hermite(ti, burnout_t, apogee_t, burnout_alt, apogee, v_burn, 0.0)
            dt_small = 1e-3
            alt_plus = hermite(ti + dt_small, burnout_t, apogee_t, burnout_alt, apogee, v_burn, 0.0)
            alt_minus = hermite(ti - dt_small, burnout_t, apogee_t, burnout_alt, apogee, v_burn, 0.0)
            vel[i] = (alt_plus - alt[i]) / dt_small
            acc[i] = (alt_plus - 2*alt[i] + alt_minus) / (dt_small**2)
        else:
            down_t = ti - apogee_t
            alt[i] = max(apogee - descent_rate * down_t, 0.0); vel[i] = -descent_rate; acc[i] = 0.0
    return t, alt, vel, acc

def barometric_pressure(alt_m, p0=101325.0, H=8000.0):
    return p0 * np.exp(-np.asarray(alt_m) / H)

def add_sensor_noise(acc_true, gyro_true, pres_true, accel_std=6e-4, gyro_std=2e-5, pres_std=0.5):
    accel_meas = acc_true + np.random.normal(0, accel_std, size=len(acc_true))
    gyro_meas = gyro_true + np.random.normal(0, gyro_std, size=len(gyro_true))
    pres_meas = pres_true + np.random.normal(0, pres_std, size=len(pres_true))
    return accel_meas, gyro_meas, pres_meas

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--lat", type=float, default=26.720333)
    ap.add_argument("--lon", type=float, default=84.303806)
    ap.add_argument("--start", type=str, default="2025-10-23")
    ap.add_argument("--end", type=str, default="2025-11-03")
    ap.add_argument("--out_csv", type=str, default="simulated_flight.csv")
    ap.add_argument("--params_json", type=str, default="")
    args = ap.parse_args()

    temp_C, p0, wind = fetch_weather(args.lat, args.lon, args.start, args.end)
    params = dict(DEF_PARAMS)
    if args.params_json and os.path.exists(args.params_json):
        params.update(json.load(open(args.params_json, "r")))

    t, alt, vel, acc = generate_trajectory(params, t_max=params["flight_time_s"], dt=0.25)
    pres = barometric_pressure(alt, p0=p0, H=8000.0)
    gyro_true = np.zeros_like(t)
    acc_m, gyro_m, pres_m = add_sensor_noise(acc, gyro_true, pres)

    df = pd.DataFrame({
        "Time_s": t,
        "Altitude_m": alt,
        "Velocity_m_s": vel,
        "Accel_m_s2": acc_m,
        "Gyro_rad_s": gyro_m,
        "Pressure_Pa": pres_m,
        "AmbientTemp_C": np.full_like(t, temp_C, dtype=float),
        "Wind10m_m_s": np.full_like(t, wind, dtype=float),
    })
    out_path = os.path.abspath(args.out_csv)
    df.to_csv(out_path, index=False)
    print(f"Wrote dataset to {out_path} with {len(df)} rows")

if __name__ == "__main__":
    main()
