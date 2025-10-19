from PySide6.QtCore import QObject, Signal, Slot
import numpy as np
import pandas as pd

class PlotPredictWorker(QObject):
    finished = Signal(dict)   # emits dict of predicted arrays
    error = Signal(str)

    def __init__(self, model, x, df_features):
        super().__init__()
        self.model = model
        self.x = np.asarray(x)
        self.df = df_features.copy()

    @Slot()
    def run(self):
        try:
            # Names must match features used for model training
            t_feat = self.x  # This should match "Times" (seconds since start)
            hum = self.df.get("Humiditypct", pd.Series([50]*len(self.x))).fillna(50).values
            wind = self.df.get("WindSpeedms", pd.Series([3]*len(self.x))).fillna(3).values
            Xp = np.vstack([t_feat, hum, wind]).T
            y_pred = self.model.predict(Xp)
            predictions = {
                "Altitudem": y_pred[:, 0].astype(float),
                "Velocityms": y_pred[:, 1].astype(float),
                "Accelms2": y_pred[:, 2].astype(float),
                "PressurePa": y_pred[:, 3].astype(float),
                "TempC": y_pred[:, 4].astype(float),
            }
            self.finished.emit(predictions)
        except Exception as e:
            self.error.emit(str(e))
