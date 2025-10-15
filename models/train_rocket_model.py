# train_rocket_model.py  (place in C:\MERN_TT\models)
import os, argparse, numpy as np, pandas as pd

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--csv", type=str, default="simulated_flight.csv")
    ap.add_argument("--model_out", type=str, default="plot_predictor.pkl")
    ap.add_argument("--n_estimators", type=int, default=120)
    args = ap.parse_args()

    csv_path = os.path.abspath(args.csv)
    if not os.path.exists(csv_path):
        raise SystemExit(f"CSV not found: {csv_path}")

    df = pd.read_csv(csv_path)

    X = np.column_stack([
        df["Time_s"].values.astype(float),
        df.get("Velocity_m_s", pd.Series(np.zeros(len(df)))).values.astype(float),
        df.get("Accel_m_s2", pd.Series(np.zeros(len(df)))).values.astype(float),
        df.get("Pressure_Pa", pd.Series(np.full(len(df), 101325))).values.astype(float),
    ])
    y = df.get("Altitude_m", pd.Series(np.zeros(len(df)))).values.astype(float)

    try:
        from sklearn.ensemble import RandomForestRegressor
        from sklearn.model_selection import train_test_split
        import joblib
    except Exception as e:
        raise SystemExit(f"Please install scikit-learn and joblib: {e}")

    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.12, random_state=42)
    model = RandomForestRegressor(n_estimators=args.n_estimators, n_jobs=-1, random_state=42)
    model.fit(Xtr, ytr)
    mse = np.mean((model.predict(Xte) - yte) ** 2)
    print(f"Validation MSE: {mse:.2f}")

    out_path = os.path.abspath(args.model_out)
    os.makedirs(os.path.dirname(out_path) or ".", exist_ok=True)
    joblib.dump(model, out_path)
    print(f"Saved model to {out_path}")

if __name__ == "__main__":
    main()
