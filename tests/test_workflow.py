from agents.pipeline import run_pipeline
from agents import workflow_agent
from workflows.maintenance_workflow import ApprovalGate, generate_workflow

def _res(detector, kb, frames, m="degrade"):
    return run_pipeline(frames[m], detector, kb)

def test_approval_required(detector, kb, frames):
    r = _res(detector, kb, frames); g = ApprovalGate(r["decision"])
    assert g.state == "PENDING" and generate_workflow(r["decision"], g, r["risk"]) is None

def test_rejected_does_not_proceed(detector, kb, frames):
    r = _res(detector, kb, frames); g = ApprovalGate(r["decision"]); g.reject()
    assert g.state == "REJECTED" and workflow_agent.run(r["decision"], g, r["risk"])["ticket"] is None
    g.approve(); assert g.state == "REJECTED"  # cannot flip after decision

def test_approved_generates(detector, kb, frames):
    r = _res(detector, kb, frames); g = ApprovalGate(r["decision"]); g.approve()
    t = workflow_agent.run(r["decision"], g, r["risk"])["ticket"]
    assert t["label"] == "SIMULATED WORKFLOW" and len(t["technician_checklist"]) == 6
    assert "Bearing" in t["recommended_inspection"] and "No real ticket" in t["escalation_message"]

def test_sensor_fault_workflow_differs(detector, kb, frames):
    r = _res(detector, kb, frames, "fault"); g = ApprovalGate(r["decision"]); g.approve()
    assert "sensor" in generate_workflow(r["decision"], g, r["risk"])["recommended_inspection"].lower()
