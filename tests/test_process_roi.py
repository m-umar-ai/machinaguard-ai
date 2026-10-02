from datetime import datetime
from workflows.maintenance_workflow import ApprovalGate
from workflows.process_engine import run_process
from business.roi import roi, sensitivity


def dec(at="INSPECT", prio="HIGH"):
    return {"requires_approval": True, "action_type": at, "priority": prio, "problem": "p", "recommended_action": "a", "possible_causes": ["Bearing degradation"], "confidence": .5, "evidence_docs": []}


def approved(d):
    g = ApprovalGate(d); g.approve(); return g


def test_no_process_without_approval():
    d = dec(); g = ApprovalGate(d)
    assert run_process(d, g, {}) is None
    g.reject(); assert run_process(d, g, {}) is None


def test_process_parts_sla_and_audit():
    d = dec("INSPECT", "HIGH"); now = datetime(2026, 10, 1, 9, 0)
    inv = {"parts": {"bearing_set": {"name": "B", "qty": 0, "lead_time_days": 6}, "seal_kit": {"name": "S", "qty": 2}, "grease": {"name": "G", "qty": 2}}}
    p = run_process(d, approved(d), {}, now=now, inventory=inv)
    assert p["sla_hours"] == 4 and p["purchase_request"]["items"] == ["B"] and p["state"].startswith("BLOCKED")
    assert [x["step"] for x in p["audit_log"]][:2] == ["APPROVED", "PARTS_CHECK"] and "NOT sent" in p["audit_log"][-1]["detail"]
    assert {n["lang"] for n in p["notifications"]} == {"en", "ur"}
    p2 = run_process(dec("INSPECT", "LOW"), approved(d), {}, now=now)
    assert p2["sla_hours"] == 72 and p2["technician"]


def test_roi_math_and_monotonic():
    r = roi(machines=10, failures_per_machine_year=1, unplanned_downtime_hours=10, planned_downtime_hours=2, cost_per_downtime_hour_usd=1000,
            detection_rate=0.5, avoidable_fraction=1.0, price_per_machine_month_usd=50, setup_fee_usd=1000)
    assert r["gross_savings_usd"] == 40000 and r["subscription_usd"] == 6000 and r["year1_net_usd"] == 33000
    s = sensitivity()
    assert s[0]["$300/h"] < s[-1]["$300/h"] and roi(detection_rate=0.0)["year1_net_usd"] < 0
