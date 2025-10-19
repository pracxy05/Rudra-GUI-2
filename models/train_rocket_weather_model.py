import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.multioutput import MultiOutputRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_absolute_error, r2_score
import joblib

# -- 1. Load Dataset --
df = pd.read_csv("rocket_mission_dataset_light.csv")

# -- 2. Redundancy Repair (again, just in case) --
for base in ["Altitudem", "Velocityms", "Accelms2", "PressurePa", "TempC", "Humiditypct", "WindSpeedms"]:
    prim = base
    red = f"{base}REDUNDANT"
    if prim in df.columns and red in df.columns:
        df[prim] = df[prim].where(
            (df[prim] != 0) & (~df[prim].isna()),
            df[red]
        )

# -- 3. Feature Engineering --
# Times as seconds since first timestamp
if pd.api.types.is_datetime64_any_dtype(df["Times"]):
    time_series = pd.to_datetime(df["Times"])
else:
    time_series = pd.to_datetime(df["Times"], errors="coerce")
df["Times"] = (time_series - time_series.min()).dt.total_seconds()

# -- 4. Feature and Target Columns --
features = ["Times", "Humiditypct", "WindSpeedms"]
targets = ["Altitudem", "Velocityms", "Accelms2", "PressurePa", "TempC"]

X = df[features].copy()
y = df[targets].copy()

# -- 5. Split --
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.25, random_state=42)

# -- 6. Model Training --
base_model = RandomForestRegressor(
    n_estimators=80,
    max_depth=12,
    min_samples_split=10,
    random_state=42,
    n_jobs=-1
)
model = MultiOutputRegressor(base_model)
model.fit(X_train, y_train)

# -- 7. Evaluate --
y_pred = model.predict(X_test)
for i, col in enumerate(targets):
    mae = mean_absolute_error(y_test.iloc[:, i], y_pred[:, i])
    r2 = r2_score(y_test.iloc[:, i], y_pred[:, i])
    print(f"{col:15s} MAE={mae:.3f}, R2={r2:.4f}")

# -- 8. Save Model --
joblib.dump(model, "rocketmultioutputmodellight.pkl")
print("✅ Model saved as rocketmultioutputmodellight.pkl")
