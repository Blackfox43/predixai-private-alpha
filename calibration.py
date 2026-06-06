import numpy as np
from sklearn.isotonic import IsotonicRegression


class Calibrator:
    def __init__(self):
        self.models = []

    def fit(self, probs, y):
        probs = np.asarray(probs, dtype=float)
        y = np.asarray(y)
        if probs.ndim != 2:
            raise ValueError("probs must be a 2D array")
        if len(probs) != len(y):
            raise ValueError("probs and y must have the same number of rows")

        self.models = []
        for i in range(probs.shape[1]):
            iso = IsotonicRegression(out_of_bounds="clip")
            iso.fit(probs[:, i], (y == i).astype(int))
            self.models.append(iso)
        return self

    def transform(self, probs):
        if not self.models:
            raise RuntimeError("Calibrator must be fitted before transform")

        probs = np.asarray(probs, dtype=float)
        calibrated = np.zeros_like(probs, dtype=float)
        for i, model in enumerate(self.models):
            calibrated[:, i] = model.transform(probs[:, i])

        row_sums = calibrated.sum(axis=1, keepdims=True)
        # Isotonic can return an all-zero row for pathological inputs; fall back to uniform.
        zero_rows = row_sums.squeeze() == 0
        calibrated = np.divide(calibrated, row_sums, out=np.zeros_like(calibrated), where=row_sums != 0)
        if np.any(zero_rows):
            calibrated[zero_rows] = 1.0 / calibrated.shape[1]
        return calibrated
