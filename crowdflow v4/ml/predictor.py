# ml/predictor.py  —  ML flow predictor using scikit-learn
import numpy as np
from sklearn.linear_model import LinearRegression
from sklearn.preprocessing import StandardScaler


class FlowPredictor:
    WINDOW = 5
    STEPS  = 8

    def __init__(self):
        self._m = LinearRegression()
        self._s = StandardScaler()

    def predict(self, history: list) -> dict:
        h = list(history)
        if len(h) < self.WINDOW + 5:
            return {"predictions": [], "current": 0, "confidence": 0,
                    "trend": "building", "peak_eta": None, "labels": []}
        X, y = [], []
        for i in range(len(h) - self.WINDOW):
            X.append(h[i:i+self.WINDOW]); y.append(h[i+self.WINDOW])
        if len(X) < 4:
            return {"predictions": [], "current": 0, "confidence": 0,
                    "trend": "building", "peak_eta": None, "labels": []}
        Xa, ya = np.array(X), np.array(y)
        try:
            Xs = self._s.fit_transform(Xa)
            self._m.fit(Xs, ya)
        except Exception:
            return {"predictions": [], "current": 0, "confidence": 0,
                    "trend": "error", "peak_eta": None, "labels": []}
        win = list(h[-self.WINDOW:]); preds = []
        for _ in range(self.STEPS):
            p = float(self._m.predict(self._s.transform(np.array([win])))[0])
            p += np.random.normal(0, 0.008)
            p = float(np.clip(p, 0, 1))
            preds.append(round(p, 3)); win = win[1:] + [p]
        try:
            conf = float(np.clip(self._m.score(Xs, ya), 0, 1))
        except Exception:
            conf = 0.5
        cur  = h[-1]; fa = float(np.mean(preds))
        trend = "rising" if fa > cur+0.05 else "falling" if fa < cur-0.05 else "stable"
        pv = max(preds); ps = preds.index(pv) if pv > cur else None
        return {
            "predictions": [round(p*100, 1) for p in preds],
            "current":     round(cur*100, 1),
            "confidence":  round(conf*100, 1),
            "trend":       trend,
            "peak_eta":    f"+{(ps+1)*30}s" if ps is not None else None,
            "labels":      [f"+{(i+1)*30}s" for i in range(self.STEPS)],
        }
