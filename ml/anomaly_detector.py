"""Genuine ML anomaly detection: Isolation Forest on multivariate sensor features
(+ redundant-sensor disagreement), trained on healthy history only. Per-sensor z-scores
vs the healthy baseline provide explainable evidence."""
from __future__ import annotations
import numpy as np, pandas as pd, joblib
from datetime import datetime
from sklearn.ensemble import IsolationForest
from sklearn.preprocessing import StandardScaler
from utils.config import SENSORS, UNITS, MODEL_PATH

FEATURES = SENSORS + ["vib_disagreement"]


def featurize(df: pd.DataFrame) -> pd.DataFrame:
    X = df.copy()
    X["vib_disagreement"] = (X["vibration"] - X["vibration_b"]).abs() if "vibration_b" in X and "vibration" in X else np.nan
    for c in FEATURES:
        if c not in X:
            X[c] = np.nan
    return X[FEATURES].apply(pd.to_numeric, errors="coerce")


class AnomalyDetector:
    def __init__(self, window: int = 5):
        self.window = window
        self.model = self.scaler = None
        self.medians = self.mu = self.sd = None
        self.warn_thr = self.crit_thr = 0.0

    def fit(self, healthy: pd.DataFrame, seed: int = 0):
        X = featurize(healthy)
        self.medians = X.median()
        X = X.fillna(self.medians)
        self.mu, self.sd = X.mean(), X.std().replace(0, 1e-6)
        self.scaler = StandardScaler().fit(X)
        self.model = IsolationForest(n_estimators=200, random_state=seed).fit(self.scaler.transform(X))
        raw = pd.Series(self._raw(X)).rolling(self.window, min_periods=1).mean().values
        self.base_hi = float(raw.max())
        self.warn_thr = self.base_hi + 0.02
        self.crit_thr = self.warn_thr + 0.10
        self.base_lo = float(np.percentile(raw, 50))
        return self

    def _raw(self, X: pd.DataFrame) -> np.ndarray:
        return -self.model.score_samples(self.scaler.transform(X))  # higher = more anomalous

    def _norm(self, raw):
        return float(np.clip((raw - self.base_lo) / (self.crit_thr + 0.08 - self.base_lo), 0, 1))

    def save(self, path=MODEL_PATH):
        MODEL_PATH.parent.mkdir(parents=True, exist_ok=True)
        joblib.dump(self, path)

    @staticmethod
    def load(path=MODEL_PATH) -> "AnomalyDetector":
        return joblib.load(path)

    def detect(self, df: pd.DataFrame) -> dict:
        """Never raises on bad data: returns a degraded (status UNKNOWN) result instead."""
        ts = datetime.now().isoformat(timespec="seconds")
        try:
            if df is None or len(df) == 0:
                raise ValueError("no sensor data")
            win = df.tail(self.window)
            if "timestamp" in win.columns:
                ts = str(win["timestamp"].iloc[-1])
            X = featurize(win)
            missing = [c for c in FEATURES if X[c].isna().all() and c != "vib_disagreement"]
            X = X.fillna(self.medians)
            raw = float(np.mean(self._raw(X)))
            xm = X.mean()
            z = {k: float((xm[k] - self.mu[k]) / self.sd[k]) for k in FEATURES}
            status = "CRITICAL" if raw >= self.crit_thr else "WARNING" if raw >= self.warn_thr else "NORMAL"
            affected = [s for s in FEATURES if abs(z[s]) >= 3.0]
            evidence = [{"sensor": s, "value": round(float(xm[s]), 2), "baseline": round(float(self.mu[s]), 2),
                         "z_score": round(z[s], 1), "unit": UNITS.get(s, ""), "direction": "↑" if z[s] > 0 else "↓"}
                        for s in sorted(affected, key=lambda k: -abs(z[k]))]
            return {"timestamp": ts, "status": status, "anomaly_score": round(self._norm(raw), 3), "raw_score": round(raw, 4),
                    "severity": status, "affected_sensors": affected, "evidence": evidence, "z_scores": z,
                    "missing_sensors": missing, "valid": True, "error": None}
        except Exception as e:
            return {"timestamp": ts, "status": "UNKNOWN", "anomaly_score": 0.0, "raw_score": 0.0, "severity": "UNKNOWN",
                    "affected_sensors": [], "evidence": [], "z_scores": {}, "missing_sensors": [],
                    "valid": False, "error": str(e)}

    def score_series(self, df: pd.DataFrame) -> np.ndarray:
        X = featurize(df).fillna(self.medians)
        raw = pd.Series(self._raw(X)).rolling(self.window, min_periods=1).mean().values
        return np.array([self._norm(r) for r in raw])
