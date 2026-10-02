"""Human-in-the-loop gate + SIMULATED maintenance workflow generation."""
from datetime import datetime


class ApprovalGate:
    def __init__(self, decision: dict):
        self.decision = decision
        self.state = "PENDING" if decision.get("requires_approval") else "NOT_REQUIRED"
        self.decided_at = None

    def approve(self):
        if self.state == "PENDING":
            self.state, self.decided_at = "APPROVED", datetime.now().isoformat(timespec="seconds")

    def reject(self):
        if self.state == "PENDING":
            self.state, self.decided_at = "REJECTED", datetime.now().isoformat(timespec="seconds")


def generate_workflow(decision: dict, gate: ApprovalGate, risk: dict, machine: str = "M-04"):
    """Returns None unless a human approved. Everything is SIMULATED."""
    if gate.state != "APPROVED":
        return None
    sensor = decision.get("action_type") == "VERIFY_SENSOR"
    checklist = (["Notify supervisor", "Compare vibration sensor A against redundant sensor B / handheld meter", "Inspect sensor mounting and cabling",
                  "Calibrate or replace faulty sensor", "Record findings", "Confirm readings return to baseline"] if sensor else
                 ["Isolate machine (lockout-tagout)", "Follow industrial safety procedure", "Inspect bearing assembly",
                  "Record findings", "Replace bearing if required", "Perform post-maintenance test"])
    ticket = {"label": "SIMULATED WORKFLOW", "ticket_id": "SIM-" + datetime.now().strftime("%Y%m%d-%H%M%S"), "machine": machine,
              "priority": decision.get("priority", "MEDIUM"), "issue": decision.get("problem"),
              "recommended_inspection": "Vibration sensors A/B" if sensor else "Bearing assembly",
              "estimated_downtime_hours": 0.5 if sensor else risk.get("downtime_hours", 2.5),
              "required_parts": ["Replacement accelerometer (example)"] if sensor else ["Example bearing assembly + seals + grease"],
              "technician_checklist": checklist, "approved_at": gate.decided_at,
              "reference_documents": decision.get("evidence_docs", [])}
    from workflows.process_engine import run_process
    ticket["process"] = run_process(decision, gate, risk, machine)
    ticket["escalation_message"] = (f"[SIMULATED] Machine {machine}: {decision.get('problem')}. Recommended: {decision.get('recommended_action')}. "
                                    f"Priority {ticket['priority']}, est. downtime {ticket['estimated_downtime_hours']} h. Human-approved at {gate.decided_at}. "
                                    "No real ticket or email was created.")
    return ticket
