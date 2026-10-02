"""Decision Agent - merges ML, diagnosis, RAG, risk and critic into one structured recommendation."""
from utils.config import llm_text
SENSOR_FAULT = "Primary vibration sensor fault / drift"


def run(ml, anomaly, diagnosis, rag, risk, critic, investigation=None) -> dict:
    status = ml.get("status", "UNKNOWN")
    conf = round(max(0.05, diagnosis.get("confidence", 0) - critic.get("confidence_penalty", 0)), 2)
    cause = diagnosis.get("likely_cause", "Unknown")
    obs = [f'{c["label"]} {c["direction"]} {c["value"]} {c["unit"]} (baseline {c["baseline"]})' for c in anomaly.get("changes", [])]
    base = {"agent": "Decision Agent", "valid": True, "observed_data": obs,
            "ai_interpretation": diagnosis.get("summary", ""), "risk": risk.get("summary", ""),
            "possible_causes": [cause], "alternative_causes": [a["cause"] for a in diagnosis.get("alternatives", [])],
            "confidence": conf, "missing_information": diagnosis.get("missing_information", []),
            "evidence_docs": [f'{r["document"]} - {r["section"]}' for r in rag.get("results", [])],
            "critic_verdict": critic.get("verdict"), "status": status}
    if status in ("NORMAL", "UNKNOWN"):
        action, reason, req, prio = "Continue monitoring", "No anomaly above baseline." if status == "NORMAL" else "Sensor data invalid; restore feed.", False, "NONE"
        problem = "No problem detected" if status == "NORMAL" else "Data quality problem"
        action_type = "MONITOR"
    elif cause == SENSOR_FAULT or critic["verdict"] == "CHALLENGES" and any("disagree" in i["evidence"] for i in critic["items"]):
        problem, action_type, prio, req = "Conflicting vibration readings (possible sensor fault)", "VERIFY_SENSOR", "MEDIUM", True
        action = "Verify and calibrate vibration sensors A/B before any mechanical maintenance"
        reason = "Redundant sensors disagree while temperature, energy and RPM are normal; mechanical failure is not supported."
    else:
        problem, action_type = "Abnormal multi-sensor pattern: " + cause.lower(), "INSPECT"
        prio = "HIGH" if risk.get("level") == "HIGH" else "MEDIUM"
        req = True
        action = "Schedule bearing assembly inspection under lockout-tagout" if "Bearing" in cause else f"Schedule inspection for: {cause}"
        reason = "ML anomaly confirmed by multiple correlated sensors; documented procedures support planned inspection. Human approval required."
    base.update({"problem": problem, "recommended_action": action, "action_type": action_type, "priority": prio,
                 "reason": reason, "requires_approval": req})
    prompt = (f"In 2 sentences, executive summary for a plant manager. Problem: {problem}. Action: {action}. "
              f"Confidence {conf:.0%}. Critic: {critic.get('verdict')}. Investigator: {(investigation or {}).get('summary', 'n/a')}. Do not claim certainty.")
    txt = llm_text(prompt) if req else None
    base["executive_summary"] = txt or f"{problem}. Recommended: {action}. Confidence {conf:.0%} (critic: {critic.get('verdict')})."
    base["llm_used"] = txt is not None
    base["investigation_mode"] = (investigation or {}).get("mode")
    return base
