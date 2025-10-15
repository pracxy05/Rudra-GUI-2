from PySide6.QtCore import QObject, Signal, Slot
import numpy as np
import pandas as pd

class PlotPredictWorker(QObject):
    finished = Signal(np.ndarray)   # emits y_pred_alt
    error = Signal(str)

    def __init__(self, model, x, df_features):
        super().__init__()
        self.model = model
        self.x = np.asarray(x)
        # Shallow copy to avoid concurrent mutation while worker runs
        self.df = df_features.copy()

    @Slot()
    def run(self):
        try:
            t_feat = self.x
            vel = self.df.get("Velocity_m_s", pd.Series([0]*len(self.x))).fillna(0).values
            acc = self.df.get("Accel_m_s2", pd.Series([0]*len(self.x))).fillna(0).values
            pres = self.df.get("Pressure_Pa", pd.Series([101325]*len(self.x))).fillna(101325).values
            Xp = np.vstack([t_feat, vel, acc, pres]).T
            y_pred = self.model.predict(Xp)
            self.finished.emit(y_pred.astype(float))
        except Exception as e:
            self.error.emit(str(e))
