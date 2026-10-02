import numpy as np
def test_normal(detector, frames):
    assert detector.detect(frames["normal"])["status"] == "NORMAL"

def test_degradation_detected_with_sensors(detector, frames):
    r = detector.detect(frames["degrade"])
    assert r["status"] in ("WARNING", "CRITICAL") and r["anomaly_score"] > 0.4
    assert "vibration" in r["affected_sensors"] and "temperature" in r["affected_sensors"]
    assert r["evidence"] and r["timestamp"]

def test_sensor_fault_flags_disagreement(detector, frames):
    r = detector.detect(frames["fault"])
    assert r["status"] != "NORMAL" and "vib_disagreement" in r["affected_sensors"]

def test_missing_values_and_garbage(detector, frames):
    df = frames["normal"].copy(); df.loc[df.index[-3:], "temperature"] = np.nan
    assert detector.detect(df)["valid"]
    assert detector.detect(df.drop(columns=["pressure"]))["valid"]
    bad = detector.detect(None); assert bad["valid"] is False and bad["status"] == "UNKNOWN"
    assert detector.detect(frames["normal"].iloc[0:0])["valid"] is False

def test_score_monotone_with_severity(detector, frames):
    assert detector.detect(frames["degrade"])["anomaly_score"] > detector.detect(frames["normal"])["anomaly_score"]
