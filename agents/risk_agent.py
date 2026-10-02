"""Agent 4 - Risk Assessment. Financial values use SIMULATED assumptions from utils.config."""
import numpy as np
from utils.config import ASSUMPTIONS as A


def run(ml: dict, diagnosis: dict, trend: float = 0.0, production_rate: float = 100.0) -> dict:
    if not ml.get("valid"):
        return {"agent": "Risk Agent", "valid": False, "failure_risk": 0.0, "level": "UNKNOWN", "urgency": "Unknown",
                "downtime_hours": 0.0, "production_loss_units": 0, "financial_impact_usd": 0, "assumptions_note": "", "summary": "Risk cannot be assessed without valid data."}
    base = ml["anomaly_score"]
    risk = float(np.clip(base * 0.75 + max(trend, 0) * 0.5 + 0.05 * len(ml["affected_sensors"]), 0, 1))
    if diagnosis.get("likely_cause", "").startswith("Primary vibration sensor"):
        risk *= 0.5  # likely a measurement problem, not a mechanical one
    if ml["status"] == "NORMAL":
        risk = min(risk, 0.1)
    level = "HIGH" if risk >= 0.6 else "MEDIUM" if risk >= 0.3 else "LOW"
    urgency = {"HIGH": "Inspect within current shift", "MEDIUM": "Schedule within 24h", "LOW": "Routine monitoring"}[level]
    planned = A["planned_inspection_hours"]
    down = round(planned * (1 + 0.5 * risk), 1)
    unplanned_extra = A["unplanned_downtime_multiplier"] * planned * risk  # expected extra hours if run-to-failure
    loss_units = int(down * production_rate)
    fin = int(loss_units * A["margin_per_unit_usd"] + A["repair_cost_usd"] * (0.5 + risk))
    return {"agent": "Risk Agent", "valid": True, "failure_risk": round(risk, 2), "level": level, "urgency": urgency,
            "downtime_hours": down, "expected_unplanned_extra_hours": round(unplanned_extra, 1),
            "production_loss_units": loss_units, "financial_impact_usd": fin,
            "assumptions_note": "SIMULATED assumptions (not real factory data): margin $%.0f/unit, repair base $%.0f." % (A["margin_per_unit_usd"], A["repair_cost_usd"]),
            "summary": f"Failure risk {risk:.0%} ({level}); {urgency}; est. downtime {down} h; simulated impact ≈ ${fin:,}."}
