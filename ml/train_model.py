"""Generate synthetic history, train on the first healthy period only, save model + CSV."""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from simulation.sensor_engine import generate_dataset
from ml.anomaly_detector import AnomalyDetector
from utils.config import SENSOR_CSV


def train(save: bool = True):
    df = generate_dataset()
    SENSOR_CSV.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(SENSOR_CSV, index=False)
    healthy = df.iloc[:3000]
    det = AnomalyDetector().fit(healthy)
    if save:
        det.save()
    return det, df


if __name__ == "__main__":
    det, df = train()
    print(f"trained; warn_thr={det.warn_thr:.3f} crit_thr={det.crit_thr:.3f}; rows={len(df)}")
