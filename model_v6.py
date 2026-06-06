import numpy as np
import xgboost as xgb
from sklearn.calibration import CalibratedClassifierCV


class V6Model:
    def __init__(self, random_state: int = 42):
        self.random_state = random_state
        self.model = None
        self.trained = False

    def _base_model(self):
        return xgb.XGBClassifier(
            n_estimators=300,
            max_depth=5,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            objective="multi:softprob",
            num_class=3,
            eval_metric="mlogloss",
            n_jobs=-1,
            random_state=self.random_state,
        )

    def train(self, X, y):
        X_arr = np.asarray(X, dtype=float)
        y_arr = np.asarray(y, dtype=int)
        if X_arr.ndim != 2:
            raise ValueError("X must be a 2D numeric matrix")
        if len(X_arr) != len(y_arr):
            raise ValueError("X and y must have the same number of rows")
        if len(np.unique(y_arr)) < 2:
            raise ValueError("training data must contain at least two classes")

        base = self._base_model()
        _, counts = np.unique(y_arr, return_counts=True)
        cv = int(min(3, counts.min()))

        # Calibration is useful, but sklearn requires every class to appear in every fold.
        self.model = CalibratedClassifierCV(base, method="isotonic", cv=cv) if cv >= 2 else base
        self.model.fit(X_arr, y_arr)
        self.trained = True
        return self

    def predict_proba(self, X):
        if not self.trained or self.model is None:
            raise RuntimeError("model must be trained before predict_proba")
        probs = np.asarray(self.model.predict_proba(np.asarray(X, dtype=float)), dtype=float)
        probs = np.clip(probs, 1e-9, 1.0)
        probs = np.power(probs, 1.15)
        return probs / probs.sum(axis=1, keepdims=True)
