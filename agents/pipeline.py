"""Orchestrator: SENSE -> DETECT -> INVESTIGATE -> RETRIEVE -> CRITIQUE -> DECIDE -> (human) -> ACT.
Plain sequential orchestration with typed hand-offs (LangGraph deliberately not used: no benefit for a linear flow)."""
from datetime import datetime
from agents import anomaly_agent, diagnosis_agent, rag_agent, risk_agent, critic_agent, decision_agent, investigator_agent


def _safe(name, fn, fallback, events):
    try:
        return fn()
    except Exception as e:  # an agent failing must never crash the app
        events.append({"time": datetime.now().strftime("%H:%M:%S"), "agent": name, "text": f"{name} failed ({type(e).__name__}); fallback used"})
        return fallback


def run_pipeline(df, detector, kb, trend=0.0, investigation=None) -> dict:
    ev: list = []
    t = lambda a, s: ev.append({"time": datetime.now().strftime("%H:%M:%S"), "agent": a, "text": s})
    ml = detector.detect(df)
    t("ML Detector", f'Anomaly {ml["status"]} (score {ml["anomaly_score"]:.2f})')
    an = _safe("Anomaly Agent", lambda: anomaly_agent.run(ml), {"agent": "Anomaly Agent", "valid": False, "changes": [], "summary": "failed"}, ev)
    t("Anomaly Agent", an["summary"])
    dg = _safe("Diagnosis Agent", lambda: diagnosis_agent.run(an, ml), {"agent": "Diagnosis Agent", "valid": False, "likely_cause": "Unknown", "confidence": 0, "alternatives": [], "missing_information": [], "summary": "failed"}, ev)
    t("Diagnosis Agent", dg["summary"])
    rg = _safe("RAG Agent", lambda: rag_agent.run(dg, kb), {"agent": "RAG Agent", "valid": False, "results": [], "query": "", "summary": "failed"}, ev)
    t("RAG Agent", rg["summary"])
    if investigation is None:  # tool-using agent; callers refreshing an open incident pass the cached investigation to avoid repeat LLM calls
        investigation = _safe("Investigator Agent", lambda: investigator_agent.run(ml, df, dg, rg, detector, kb, trend),
                              {"agent": "Investigator Agent", "valid": False, "mode": "failed", "trace": [], "final": None, "top_cause": None, "summary": "failed"}, ev)
    t("Investigator Agent", investigation["summary"])
    rk = _safe("Risk Agent", lambda: risk_agent.run(ml, dg, trend), {"agent": "Risk Agent", "valid": False, "failure_risk": 0, "level": "UNKNOWN", "summary": "failed", "downtime_hours": 0, "financial_impact_usd": 0, "production_loss_units": 0, "urgency": "", "assumptions_note": ""}, ev)
    t("Risk Agent", rk["summary"])
    cr = _safe("Critic Agent", lambda: critic_agent.run(ml, an, dg, rg, rk, investigation), {"agent": "Critic Agent", "verdict": "CHALLENGES", "items": [], "confidence_penalty": 0.3, "summary": "failed"}, ev)
    t("Critic Agent", cr["summary"])
    dc = _safe("Decision Agent", lambda: decision_agent.run(ml, an, dg, rg, rk, cr, investigation), {"agent": "Decision Agent", "valid": False, "status": "UNKNOWN", "problem": "Decision unavailable", "recommended_action": "Escalate to human", "requires_approval": True, "action_type": "INSPECT", "priority": "MEDIUM", "confidence": 0.1, "evidence_docs": [], "executive_summary": "Decision unavailable", "observed_data": [], "alternative_causes": [], "possible_causes": [], "missing_information": [], "reason": "agent failure", "ai_interpretation": "", "risk": "", "critic_verdict": "n/a"}, ev)
    t("Decision Agent", f'{dc["problem"]} → {dc["recommended_action"]}')
    if dc.get("requires_approval"):
        t("Human Gate", "Human approval required")
    return {"ml": ml, "investigation": investigation, "anomaly": an, "diagnosis": dg, "rag": rg, "risk": rk, "critic": cr, "decision": dc, "events": ev}
