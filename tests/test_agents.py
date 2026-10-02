from agents import anomaly_agent, diagnosis_agent, rag_agent, risk_agent, critic_agent, decision_agent

def chain(ml, kb):
    an = anomaly_agent.run(ml); dg = diagnosis_agent.run(an, ml); rg = rag_agent.run(dg, kb)
    rk = risk_agent.run(ml, dg); cr = critic_agent.run(ml, an, dg, rg, rk)
    return an, dg, rg, rk, cr, decision_agent.run(ml, an, dg, rg, rk, cr)

def test_diagnosis_bearing_not_confirmed(detector, frames, kb):
    ml = detector.detect(frames["degrade"]); an, dg, *_ = chain(ml, kb)
    assert dg["likely_cause"] == "Bearing degradation" and dg["is_confirmed"] is False
    assert 0 < dg["confidence"] < 1 and dg["alternatives"] and dg["missing_information"]

def test_risk_structured(detector, frames, kb):
    ml = detector.detect(frames["degrade"]); *_, rk, cr, dc = chain(ml, kb)
    assert rk["level"] in ("LOW", "MEDIUM", "HIGH") and 0 <= rk["failure_risk"] <= 1
    assert "SIMULATED" in rk["assumptions_note"] and rk["downtime_hours"] > 0

def test_critic_identifies_contradiction(detector, frames, kb):
    ml = detector.detect(frames["fault"]); an, dg, rg, rk, cr, dc = chain(ml, kb)
    assert any("disagree" in i["evidence"] for i in cr["items"]) and cr["confidence_penalty"] >= 0.25
    assert dc["action_type"] == "VERIFY_SENSOR"
    assert dc["confidence"] < dg["confidence"]

def test_critic_all_items_have_four_fields(detector, frames, kb):
    ml = detector.detect(frames["degrade"]); *_, cr, dc = chain(ml, kb)
    for i in cr["items"]: assert all(i[k] for k in ("evidence", "finding", "concern", "recommendation"))

def test_decision_incomplete_evidence(detector, kb):
    ml = detector.detect(None); an, dg, rg, rk, cr, dc = chain(ml, kb)
    assert dc["action_type"] == "MONITOR" and not dc["requires_approval"] and dc["valid"]

def test_decision_normal_no_approval(detector, frames, kb):
    *_, dc = chain(detector.detect(frames["normal"]), kb)
    assert dc["action_type"] == "MONITOR" and dc["requires_approval"] is False

def test_decision_without_rag(detector, frames):
    class Dead:
        ready = False
        def search(self, *a, **k): return []
    ml = detector.detect(frames["degrade"]); *_, cr, dc = chain(ml, Dead())
    assert any("No maintenance passages" in i["evidence"] for i in cr["items"]) and dc["requires_approval"]
