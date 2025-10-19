import pandas as pd
import numpy as np
import glob

# -- Parameters --
EVENT_START_DAY = 26
EVENT_END_DAY = 30
HOUR_START = 7
HOUR_END = 19

# -- 1. Load & Filter Weather Data --
files = glob.glob("weather_launch_location_*.csv")
df_list = [pd.read_csv(f) for f in files]

weather_df = pd.concat(df_list, ignore_index=True)
weather_df = weather_df.rename(columns={
    "temperature_2m": "TempC",
    "pressure_msl": "PressurePa",
    "relative_humidity_2m": "Humiditypct",
    "wind_speed_10m": "WindSpeedms",
    "wind_direction_10m": "WindDirdeg",
    "time": "Times"
})

weather_df["Times"] = pd.to_datetime(weather_df["Times"])
mask = (
    (weather_df["Times"].dt.month == 10) &
    (weather_df["Times"].dt.day >= EVENT_START_DAY) &
    (weather_df["Times"].dt.day <= EVENT_END_DAY) &
    (weather_df["Times"].dt.hour >= HOUR_START) &
    (weather_df["Times"].dt.hour <= HOUR_END)
)
weather_selected = weather_df.loc[mask].reset_index(drop=True)
print(f"🎯 Filtered weather records: {len(weather_selected)}")

# -- 2. Flight Simulator --
def simulate_flight(temp, pressure, humidity, windspeed):
    total_time = 160
    dt = 0.1
    t = np.arange(0, total_time + dt, dt)
    apogee = 1076.0
    burn_time = 3.81
    coast_time = 15.74
    descent_rate = 4.36
    g = 9.81

    alt, vel, acc, pres, temp_series = [], [], [], [], []
    for time_val in t:
        if time_val <= burn_time:
            a = 102.0 + np.random.normal(0, 0.5)
            v = a * time_val
            h = 0.5 * a * time_val**2
        elif time_val <= coast_time:
            a = -g + np.random.normal(0, 0.1)
            v = 148 - 9.81 * (time_val - burn_time)
            h = 350 + (v * (time_val - burn_time)) - (0.5 * g * (time_val - burn_time)**2)
        else:
            a = 0.0
            v = -descent_rate + np.random.normal(0, 0.05)
            h = max(apogee - descent_rate * (time_val - coast_time), 0)
        pres_val = pressure * np.exp(-h / 8400.0)
        temp_val = temp - 0.0065 * h / 1000 + np.random.normal(0, 0.1)

        alt.append(h)
        vel.append(v)
        acc.append(a)
        pres.append(pres_val)
        temp_series.append(temp_val)
    return pd.DataFrame({
        "Times": t,
        "Velocityms": vel,
        "Accelms2": acc,
        "PressurePa": pres,
        "TempC": temp_series,
        "Humiditypct": humidity,
        "WindSpeedms": windspeed,
        "Altitudem": alt
    })

# -- 3. Assemble Dataset --
flight_datasets = []
for i in range(0, len(weather_selected), max(1, len(weather_selected)//40)):
    row = weather_selected.iloc[i]
    df_flight = simulate_flight(
        row["TempC"],
        row["PressurePa"],
        row["Humiditypct"],
        row["WindSpeedms"]
    )
    # Add redundant columns for demonstration, e.g., copy primary to REDUNDANT
    for col in ["Altitudem", "Velocityms", "Accelms2", "PressurePa", "TempC", "Humiditypct", "WindSpeedms"]:
        red_col = f"{col}REDUNDANT"
        df_flight[red_col] = df_flight[col]
        # Optionally, introduce some 0 values in the primary (simulate failure)
        df_flight.loc[df_flight.index[-10:], col] = 0
    flight_datasets.append(df_flight)

rocket_df = pd.concat(flight_datasets, ignore_index=True)

# -- 4. Redundancy Repair --
for base in ["Altitudem", "Velocityms", "Accelms2", "PressurePa", "TempC", "Humiditypct", "WindSpeedms"]:
    prim = base
    red = f"{base}REDUNDANT"
    if prim in rocket_df.columns and red in rocket_df.columns:
        rocket_df[prim] = rocket_df[prim].where(
            (rocket_df[prim] != 0) & (~rocket_df[prim].isna()),
            rocket_df[red]
        )

rocket_df = rocket_df.sample(min(8000, len(rocket_df)), random_state=42)
rocket_df.to_csv("rocket_mission_dataset_light.csv", index=False)
print(f"✅ Dataset ready: {len(rocket_df)} rows")
