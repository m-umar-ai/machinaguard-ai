"""Agent 1 - Anomaly Analysis: turns raw ML output into 'what changed, how much'."""
SENSOR_LABEL = {"temperature": "Temperature", "vibration": "Vibration (primary)", "pressure": "Pressure", "rpm": "RPM",
                "energy": "Energy", "production_rate": "Production rate", "vib_disagreement": "Vibration A/B disagreement"}


def run(ml: dict) -> dict:
    if not ml.get("valid", False):
        return {"agent": "Anomaly Agent", "valid": False, "summary": "No valid ML result (sensor data missing or malformed).",
                "changes": [], "significance": "unknown", "pattern": {}}
    changes = []
    for e in ml["evidence"]:
        mag = abs(e["z_score"])
        changes.append({"sensor": e["sensor"], "label": SENSOR_LABEL.get(e["sensor"], e["sensor"]), "direction": e["direction"],
                        "value": e["value"], "baseline": e["baseline"], "unit": e["unit"], "z": e["z_score"],
                        "significance": "major" if mag >= 8 else "moderate" if mag >= 4 else "minor"})
    pattern = {c["sensor"]: c["direction"] for c in changes}
    sig = {"NORMAL": "none", "WARNING": "moderate", "CRITICAL": "high"}.get(ml["status"], "unknown")
    names = ", ".join(f'{c["label"]} {c["direction"]}' for c in changes) or "no sensor outside baseline"
    return {"agent": "Anomaly Agent", "valid": True, "significance": sig, "changes": changes, "pattern": pattern,
            "summary": f'Anomaly score {ml["anomaly_score"]:.2f} ({ml["status"]}). Changed: {names}.'}
