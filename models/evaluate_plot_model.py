import pandas as pd
import joblib
import numpy as np
from sklearn.metrics import mean_absolute_error, r2_score
import matplotlib.pyplot as plt

# Load test dataset (use your existing or a new validation file)
rocket_df = pd.read_csv("rocket_mission_dataset_light.csv")
features = ["Time_s", "Humidity_pct", "WindSpeed_m_s"]
targets  = ["Altitude_m", "Velocity_m_s", "Accel_m_s2", "Pressure_Pa", "Temp_C"]

X = rocket_df[features]
y = rocket_df[targets]

# Load model
model = joblib.load("rocket_multioutput_model_light.pkl")

# Predict
y_pred = model.predict(X)

print("\nPerformance metrics (full set):")
for i, col in enumerate(targets):
    mae = mean_absolute_error(y.iloc[:, i], y_pred[:, i])
    r2 = r2_score(y.iloc[:, i], y_pred[:, i])
    print(f"{col:15s}: MAE={mae:.3f}, R²={r2:.4f}")

# (Optional) Plot Altitude actual vs predicted
plt.figure(figsize=(10,5))
plt.plot(y["Altitude_m"][:1000], label="Actual Altitude")
plt.plot(y_pred[:1000, 0], label="Predicted Altitude", linestyle='dashed')
plt.legend()
plt.title("First 1000 Flight Points: Actual vs Predicted Altitude")
plt.xlabel("Sample Point")
plt.ylabel("Altitude (m)")
plt.show()
