"""Synthetic-but-fair benchmark: python -m validation.benchmark [n_runs]
Detector is trained ONCE on healthy data at noise scale 1.0 (seed 7). Test runs use DIFFERENT seeds, DIFFERENT degradation speeds
and NOISIER plants (1.0x/1.5x/2.0x), so it is not a replay of the training data. Still synthetic: see README 'Known limitations'.
Baseline = fixed alarm 'vibration > 4.5 mm/s' (what a plain threshold system would do)."""
from __future__ import annotations
import json, sys
from pathlib import Path
import numpy as np
from agents.pipeline import run_pipeline
from ml.anomaly_detector import AnomalyDetector
from rag.knowledge_base import KnowledgeBase
from simulation.sensor_engine import SensorEngine, generate_dataset

BASE_ALARM = 4.5
OUT = Path(__file__).parent / "results.json"


CAL_TICKS = 400


def _setup(seed, noise, det, calibrate):
    """Engine warmed up; if calibrate, a per-machine detector is fitted on that machine's first healthy ticks (commissioning step)."""
    e = SensorEngine(seed=seed, noise_scale=noise)
    if calibrate:
        for _ in range(CAL_TICKS):
            e.step()
        return e, AnomalyDetector().fit(e.frame())
    for _ in range(60):
        e.step()
    return e, det


def _alarm(det, df):
    return det.detect(df)["status"] in ("WARNING", "CRITICAL")


def degradation_runs(det, n, calibrate):
    rows = []
    for i in range(n):
        speed, noise = [40, 60, 90, 120][i % 4], [1.0, 1.5, 2.0][i % 3]
        e, det_i = _setup(1000 + i, noise, det, calibrate)
        e.start_degradation(speed)
        first_ml = first_base = pre_false = None
        for t in range(speed + 10):
            e.step()
            df = e.frame(120)
            sev = df["severity_truth"].iloc[-1]
            if first_ml is None and _alarm(det_i, df):
                first_ml = t
                if sev < 0.05:
                    pre_false = True
            if first_base is None and df["vibration"].tail(3).mean() > BASE_ALARM:
                first_base = t
        rows.append({"speed": speed, "noise": noise, "ml_alarm_tick": first_ml, "base_alarm_tick": first_base, "fail_tick": speed,
                     "ml_detected": first_ml is not None, "base_detected": first_base is not None})
    return rows


def healthy_runs(det, n, calibrate, ticks=500):
    alarms = base_alarms = total = 0
    for i in range(n):
        e, det_i = _setup(2000 + i, [1.0, 1.5, 2.0][i % 3], det, calibrate)
        for t in range(ticks):
            e.step()
            if t >= 0:
                df = e.frame(120); total += 1
                alarms += _alarm(det_i, df)
                base_alarms += df["vibration"].tail(3).mean() > BASE_ALARM
    return {"ticks": total, "ml_false_alarms_per_1000": round(1000 * alarms / total, 1), "baseline_false_alarms_per_1000": round(1000 * base_alarms / total, 1)}


def sensor_fault_runs(det, kb, n, calibrate):
    ml_right = base_wrong = 0
    for i in range(n):
        e, det_i = _setup(3000 + i, [1.0, 1.5][i % 2], det, calibrate)
        e.inject_fault(True)
        decided = None
        for _ in range(30):
            e.step(); df = e.frame(120)
            if _alarm(det_i, df):
                decided = run_pipeline(df, det_i, kb)["decision"]["action_type"]; break
        ml_right += decided == "VERIFY_SENSOR"
        base_wrong += df["vibration"].tail(3).mean() > BASE_ALARM  # a threshold system raises a MECHANICAL alarm
    return {"runs": n, "system_recommends_sensor_check": ml_right, "baseline_raises_mechanical_alarm": int(base_wrong)}


def _summary(det, kb, n, calibrate):
    d = degradation_runs(det, n, calibrate)
    hit = [r for r in d if r["ml_detected"]]
    lead = [r["fail_tick"] - r["ml_alarm_tick"] for r in hit]
    base = [r for r in d if r["base_detected"]]
    base_lead = [r["fail_tick"] - r["base_alarm_tick"] for r in base]
    return {"degradation": {"detection_rate": round(len(hit) / n, 2), "median_lead_ticks": float(np.median(lead)) if lead else None,
                            "median_lead_fraction_of_life": round(float(np.median([l / r["fail_tick"] for l, r in zip(lead, hit)])), 2) if lead else None,
                            "baseline_detection_rate": round(len(base) / n, 2), "baseline_median_lead_ticks": float(np.median(base_lead)) if base_lead else None},
            "healthy": healthy_runs(det, max(6, n // 4), calibrate), "sensor_fault": sensor_fault_runs(det, kb, max(8, n // 2), calibrate)}


def run(n=24) -> dict:
    det = AnomalyDetector().fit(generate_dataset().iloc[:3000])
    kb = KnowledgeBase()
    res = {"n_degradation_runs": n, "per_machine_calibrated": _summary(det, kb, n, True), "generic_pretrained_no_calibration": _summary(det, kb, n, False)}
    OUT.write_text(json.dumps(res, indent=2))
    return res


if __name__ == "__main__":
    print(json.dumps(run(int(sys.argv[1]) if len(sys.argv) > 1 else 24), indent=2))
