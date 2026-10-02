"""Critic Agent - challenges the other agents. Output: Evidence -> Finding -> Concern -> Recommendation."""
import json
from agents.agent_loop import parse_json
from utils.config import llm_available, llm_text
SENSOR_FAULT = "Primary vibration sensor fault / drift"


def llm_concerns(ml, diagnosis, investigation, llm=None):
    """Adversarial second opinion from a language model. It can ADD concerns (never remove deterministic ones)."""
    fn = llm or (llm_text if llm_available() else None)
    if fn is None:
        return []
    ev = [f'{e["sensor"]} z={e["z_score"]}' for e in ml.get("evidence", [])][:6]
    prompt = ("You are an adversarial reviewer of a maintenance diagnosis. Find up to 2 genuine weaknesses (missing evidence, contradictions, "
              "alternative explanations). Reply JSON only: {\"concerns\":[{\"evidence\":str,\"finding\":str,\"concern\":str,\"recommendation\":str}]}.\n"
              f"Evidence: {ev}\nLeading cause: {diagnosis.get('likely_cause')} (conf {diagnosis.get('confidence')})\n"
              f"Investigator summary: {(investigation or {}).get('summary')}")
    msg = parse_json(fn(prompt, "You are a skeptical reliability engineer."))
    out = []
    for c in (msg or {}).get("concerns", [])[:2] if isinstance((msg or {}).get("concerns"), list) else []:
        if isinstance(c, dict) and all(isinstance(c.get(k), str) and c.get(k) for k in ("evidence", "finding", "concern", "recommendation")):
            out.append({**{k: c[k][:200] for k in ("evidence", "finding", "concern", "recommendation")}, "severity": "medium", "source": "LLM critic"})
    return out


def run(ml: dict, anomaly: dict, diagnosis: dict, rag: dict, risk: dict, investigation: dict | None = None, llm=None) -> dict:
    items = []
    penalty = 0.0
    if ml.get("status") == "NORMAL":
        return {"agent": "Critic Agent", "verdict": "SUPPORTS", "items": [], "confidence_penalty": 0.0,
                "summary": "Critic: nothing to challenge - machine within baseline."}
    z = ml.get("z_scores", {}) if ml.get("valid") else {}
    cause = diagnosis.get("likely_cause", "")

    def add(ev, finding, concern, rec, sev="medium"):
        items.append({"evidence": ev, "finding": finding, "concern": concern, "recommendation": rec, "severity": sev})

    if not ml.get("valid"):
        add("No valid sensor data", "ML result unavailable", "Any conclusion would be unsupported", "Restore data feed before acting", "high")
        return {"agent": "Critic Agent", "verdict": "CHALLENGES", "items": items, "confidence_penalty": 0.5,
                "summary": "Critic: no valid data; all conclusions unsupported."}
    # 1. contradictory evidence: redundant sensors disagree
    dis = z.get("vib_disagreement", 0)
    if dis >= 4:
        add(f"Vibration sensor A and B disagree (z={dis:.1f})", "Conflicting readings from redundant sensors",
            "Mechanical diagnosis may rest on a faulty measurement", "Verify/calibrate vibration sensors before maintenance escalation", "high")
        penalty += 0.30
    # 2. expected pattern inconsistent
    if cause == "Bearing degradation":
        if z.get("vibration", 0) > 4 and z.get("temperature", 0) < 2:
            add(f'Vibration z={z.get("vibration",0):.1f} but temperature z={z.get("temperature",0):.1f}',
                "Expected thermal signature of bearing wear is absent", "Diagnosis is only partially consistent with bearing wear",
                "Treat as early-stage or re-check sensors; collect vibration spectrum", "medium")
            penalty += 0.15
        if z.get("energy", 0) < 2:
            add("Energy draw still near baseline", "No energy increase yet", "Wear may be early; severity not yet established",
                "Keep monitoring trend; plan inspection rather than emergency stop", "low")
            penalty += 0.05
    # 3. unsupported assumptions
    if diagnosis.get("missing_information"):
        add("Missing: " + "; ".join(diagnosis["missing_information"][:2]), "Diagnosis lacks physical confirmation",
            "Cause is a hypothesis, not a fact", "Confirm via inspection before part replacement", "medium")
        penalty += 0.05
    # 4. alternative explanations
    close = [a for a in diagnosis.get("alternatives", []) if a["weight"] >= 0.2]
    if close:
        add("Alternative causes score close to the leading cause: " + ", ".join(a["cause"] for a in close),
            "Diagnosis is not uniquely identified", "Risk of fixing the wrong component", "Check alternatives during inspection", "medium")
        penalty += 0.05
    # 5. retrieval support
    if not rag.get("results"):
        add("No maintenance passages retrieved", "Recommendation lacks documented procedure support", "Cannot cite maintenance guidance",
            "Escalate to a human technician for procedure selection", "medium")
        penalty += 0.1
    elif rag["results"][0]["relevance"] < 0.12:
        add(f'Best retrieval relevance only {rag["results"][0]["relevance"]}', "Weak documentary support", "Knowledge match is loose",
            "Treat retrieved guidance as general reference", "low")
        penalty += 0.05
    # 5b. independent agents disagree: tool-using investigator vs deterministic signature matcher
    inv_top = (investigation or {}).get("top_cause")
    if inv_top and inv_top != cause and inv_top not in [a["cause"] for a in diagnosis.get("alternatives", [])[:1]]:
        add(f"Investigator Agent ranks '{inv_top}' first; signature matcher ranks '{cause}' first", "Independent agents disagree on the cause",
            "Either the evidence is ambiguous or one method is miscalibrated", "Treat the cause as unresolved; inspect both candidates", "medium")
        penalty += 0.10
    for c in llm_concerns(ml, diagnosis, investigation, llm):
        items.append(c)
        penalty += 0.05
    # 6. safety
    if risk.get("level") == "HIGH" and cause != SENSOR_FAULT:
        add("High risk rating", "Urgent action suggested", "Automated action would be unsafe", "Human approval and lockout-tagout required; no auto-shutdown", "high")
    verdict = "CHALLENGES" if penalty >= 0.25 else "PARTIALLY SUPPORTS" if items else "SUPPORTS"
    return {"agent": "Critic Agent", "verdict": verdict, "items": items, "confidence_penalty": round(penalty, 2),
            "summary": f"Critic {verdict.lower()} the diagnosis: {len(items)} concern(s), confidence penalty {penalty:.0%}."}
