"""Agent 2 - Diagnosis: scores competing fault hypotheses against the observed z-score signature."""
import numpy as np

# expected direction/weight per hypothesis (domain knowledge); weights say how diagnostic each sensor is
HYPOTHESES = {
    "Bearing degradation": {"vibration": 1.0, "temperature": 0.8, "energy": 0.6, "vib_disagreement": -0.8, "rpm": -0.1},
    "Primary vibration sensor fault / drift": {"vibration": 1.0, "vib_disagreement": 1.0, "temperature": -0.7, "energy": -0.7},
    "Lubrication breakdown": {"temperature": 1.0, "vibration": 0.4, "energy": 0.3, "vib_disagreement": -0.5},
    "Shaft misalignment / imbalance": {"vibration": 1.0, "energy": 0.4, "temperature": 0.2, "vib_disagreement": -0.5},
    "Motor electrical overload": {"energy": 1.0, "rpm": -0.7, "temperature": 0.4, "vibration": 0.1},
    "Pressure / process fault": {"pressure": 1.0, "production_rate": 0.7, "vibration": 0.0},
}
MISSING_INFO = {
    "Bearing degradation": ["Vibration frequency spectrum (bearing defect frequencies)", "Lubricant condition", "Maintenance history"],
    "Primary vibration sensor fault / drift": ["Redundant sensor calibration record", "Mounting / cable inspection"],
    "Lubrication breakdown": ["Lubricant quantity and age"],
    "Shaft misalignment / imbalance": ["Axial vibration data", "Coupling alignment check"],
    "Motor electrical overload": ["Phase current balance", "Supply voltage"],
    "Pressure / process fault": ["Upstream process data"],
}


def run(anomaly: dict, ml: dict) -> dict:
    if not anomaly.get("valid") or ml.get("status") in ("NORMAL", "UNKNOWN") or not anomaly.get("changes"):
        return {"agent": "Diagnosis Agent", "valid": anomaly.get("valid", False), "likely_cause": "No fault indicated",
                "confidence": 0.0 if not anomaly.get("valid") else 0.9, "alternatives": [], "supporting_evidence": [],
                "missing_information": [] if anomaly.get("valid") else ["Valid sensor data"], "scores": {}, "is_confirmed": False,
                "summary": "No diagnosis required - machine within baseline." if anomaly.get("valid") else "Cannot diagnose: sensor data invalid."}
    z = ml["z_scores"]
    zc = {k: float(np.tanh(v / 6.0)) for k, v in z.items()}  # saturating, so one noisy-tight sensor can't dominate
    obs = np.array([zc.get(k, 0.0) for k in ["vibration", "temperature", "energy", "rpm", "pressure", "production_rate", "vib_disagreement"]])
    order = ["vibration", "temperature", "energy", "rpm", "pressure", "production_rate", "vib_disagreement"]
    raw = {}
    for h, sig in HYPOTHESES.items():
        v = np.array([sig.get(k, 0.0) for k in order])
        cos = float(obs @ v / ((np.linalg.norm(obs) + 1e-9) * (np.linalg.norm(v) + 1e-9)))  # pattern similarity
        raw[h] = max(cos, 0.0) ** 3
    total = sum(raw.values()) or 1.0
    probs = {h: v / total for h, v in raw.items()}
    ranked = sorted(probs.items(), key=lambda kv: -kv[1])
    top, top_p = ranked[0]
    margin = top_p - ranked[1][1]
    strength = min(1.0, abs(z.get("vibration", 0)) / 8 + 0.2 * len(ml["affected_sensors"]) / 4)
    confidence = round(float(np.clip(0.35 + 0.35 * strength + 0.3 * margin, 0.2, 0.92)), 2)
    ev = [f'{c["label"]} {c["direction"]} ({c["value"]} {c["unit"]} vs baseline {c["baseline"]}, z={c["z"]})' for c in anomaly["changes"][:4]]
    alts = [{"cause": h, "weight": round(p, 2)} for h, p in ranked[1:4] if p > 0.03]
    return {"agent": "Diagnosis Agent", "valid": True, "likely_cause": top, "confidence": confidence, "alternatives": alts,
            "supporting_evidence": ev, "missing_information": MISSING_INFO.get(top, []), "scores": {h: round(p, 3) for h, p in ranked},
            "is_confirmed": False,
            "summary": f"Possible {top.lower()} (confidence {confidence:.0%}, NOT confirmed). Alternatives: " + ", ".join(a["cause"] for a in alts[:2])}
