"""Sensor simulation: smooth AR(1) noise + physically-motivated degradation coupling."""
from __future__ import annotations
import numpy as np, pandas as pd
from datetime import datetime, timedelta

BASE = {"temperature": 65.0, "vibration": 2.0, "pressure": 6.0, "rpm": 1500.0,
        "energy": 45.0, "production_rate": 100.0}
NOISE = {"temperature": 0.35, "vibration": 0.06, "pressure": 0.04, "rpm": 5.0,
         "energy": 0.5, "production_rate": 0.8}


class SensorEngine:
    """severity 0..1 models developing bearing degradation; fault_active models a
    misbehaving primary vibration sensor while the redundant one (vibration_b) stays physical."""

    def __init__(self, seed: int = 42, start: datetime | None = None, noise_scale: float = 1.0):
        self.seed = seed
        self.noise_scale = noise_scale  # >1 = noisier plant than the one the detector was trained on
        self.reset(start)

    def reset(self, start: datetime | None = None):
        self.rng = np.random.default_rng(self.seed)
        self.t = start or datetime(2026, 1, 1, 8, 0, 0)
        self.severity = 0.0
        self.target_severity = 0.0
        self.ramp_rate = 0.0
        self.fault_active = False
        self.noise = {k: 0.0 for k in list(BASE) + ["vibration_b"]}
        self.history: list[dict] = []

    def start_degradation(self, ticks_to_critical: int = 60):
        self.target_severity, self.ramp_rate = 1.0, 1.0 / max(ticks_to_critical, 1)

    def inject_fault(self, on: bool = True):
        self.fault_active = on

    def perform_maintenance(self):
        """Recovery: bearing replaced, degradation removed."""
        self.severity = self.target_severity = self.ramp_rate = 0.0
        self.fault_active = False

    def _ar(self, k, scale):
        self.noise[k] = 0.8 * self.noise[k] + self.rng.normal(0, scale * self.noise_scale)
        return self.noise[k]

    def step(self) -> dict:
        if self.severity < self.target_severity:
            self.severity = min(self.target_severity, self.severity + self.ramp_rate)
        s = self.severity
        vib_up = 6.0 * s ** 1.4                                    # vibration first
        temp_up = 20.0 * max(0.0, (s - 0.25) / 0.75) ** 1.2        # then temperature
        energy_up = 9.0 * max(0.0, (s - 0.45) / 0.55)              # then energy
        prod_dn = 12.0 * max(0.0, (s - 0.5) / 0.5) ** 1.5
        press_dn = 0.5 * max(0.0, (s - 0.6) / 0.4)
        true_vib = BASE["vibration"] + vib_up
        row = {
            "temperature": BASE["temperature"] + temp_up + self._ar("temperature", NOISE["temperature"]),
            "vibration": true_vib + self._ar("vibration", NOISE["vibration"]),
            "pressure": BASE["pressure"] - press_dn + self._ar("pressure", NOISE["pressure"]),
            "rpm": BASE["rpm"] - 20 * s + self._ar("rpm", NOISE["rpm"]),
            "energy": BASE["energy"] + energy_up + self._ar("energy", NOISE["energy"]),
            "production_rate": BASE["production_rate"] - prod_dn + self._ar("production_rate", NOISE["production_rate"]),
            "vibration_b": true_vib + self._ar("vibration_b", 0.05),  # redundant accelerometer
        }
        if self.fault_active:  # primary vibration sensor reads high; redundant sensor + others stay normal
            row["vibration"] = true_vib + 4.8 + 1.2 * np.sin(len(self.history) / 3.0) + self.rng.normal(0, 0.4)
        row["timestamp"] = self.t
        row["severity_truth"] = round(s, 3)
        row["fault_truth"] = self.fault_active
        self.t += timedelta(seconds=1)
        self.history.append(row)
        return row

    def frame(self, n: int | None = None) -> pd.DataFrame:
        df = pd.DataFrame(self.history)
        return df.tail(n) if n else df


def generate_dataset(n_normal=3000, seed=7) -> pd.DataFrame:
    """Synthetic history: normal -> gradual degradation -> maintenance recovery -> sensor fault -> normal."""
    e = SensorEngine(seed=seed)
    for _ in range(n_normal):
        e.step()
    e.start_degradation(300)
    for _ in range(320):
        e.step()
    e.perform_maintenance()
    for _ in range(200):
        e.step()
    e.inject_fault(True)
    for _ in range(150):
        e.step()
    e.inject_fault(False)
    for _ in range(300):
        e.step()
    return e.frame()
