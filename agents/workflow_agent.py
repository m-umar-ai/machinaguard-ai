from workflows.maintenance_workflow import generate_workflow


def run(decision, gate, risk, machine="M-04"):
    t = generate_workflow(decision, gate, risk, machine)
    if t is None:
        return {"agent": "Workflow Agent", "ticket": None, "state": gate.state,
                "summary": {"PENDING": "Waiting for human approval.", "REJECTED": "Rejected - sent for human review; no workflow generated.",
                            "NOT_REQUIRED": "No action required."}.get(gate.state, "Idle")}
    return {"agent": "Workflow Agent", "ticket": t, "state": gate.state, "summary": f"SIMULATED workflow {t['ticket_id']} generated."}
