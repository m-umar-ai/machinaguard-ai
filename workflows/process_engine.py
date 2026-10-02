"""AI-powered business-process automation: approved decision -> end-to-end maintenance process (SIMULATED).
States: APPROVED -> PARTS_CHECK -> (PURCHASE_REQUEST) -> TECHNICIAN_ASSIGNED -> SCHEDULED -> NOTIFIED -> READY_FOR_EXECUTION.
Nothing runs unless a human approved; every step is written to an audit log; no external system is touched."""
from __future__ import annotations
import json
from datetime import datetime, timedelta
from pathlib import Path
from genai.reports import whatsapp_alert

DATA = Path(__file__).resolve().parent.parent / "data"
SLA_HOURS = {"HIGH": 4, "MEDIUM": 24, "LOW": 72, "NONE": 72}
PARTS_FOR = {"INSPECT": ["bearing_set", "seal_kit", "grease"], "VERIFY_SENSOR": ["accelerometer"]}
SKILL_FOR = {"INSPECT": "bearing", "VERIFY_SENSOR": "vibration"}


def _load(name):
    try:
        return json.loads((DATA / name).read_text(encoding="utf-8"))
    except Exception:
        return {}


def run_process(decision: dict, gate, risk: dict, machine: str = "M-04", now: datetime | None = None, inventory=None, roster=None) -> dict | None:
    if gate.state != "APPROVED":
        return None  # hard rule: no process without human approval
    now = now or datetime.now()
    inv = (inventory or _load("inventory.json")).get("parts", {})
    techs = (roster or _load("technicians.json")).get("technicians", [])
    at = decision.get("action_type", "INSPECT")
    log = [{"t": now.isoformat(timespec="seconds"), "step": "APPROVED", "detail": f"Human approved: {decision.get('recommended_action')}"}]

    needed = PARTS_FOR.get(at, [])
    parts, purchase = [], None
    for pid in needed:
        p = inv.get(pid, {"name": pid, "qty": 0, "lead_time_days": 7})
        ok = p.get("qty", 0) > 0
        parts.append({"part": p["name"], "in_stock": ok, "lead_time_days": 0 if ok else p.get("lead_time_days", 7)})
    log.append({"t": now.isoformat(timespec="seconds"), "step": "PARTS_CHECK", "detail": f"{sum(p['in_stock'] for p in parts)}/{len(parts)} parts in stock"})
    missing = [p for p in parts if not p["in_stock"]]
    delay_days = max([p["lead_time_days"] for p in missing], default=0)
    if missing:
        purchase = {"status": "DRAFT PURCHASE REQUEST (not sent)", "items": [p["part"] for p in missing], "expected_lead_time_days": delay_days}
        log.append({"t": now.isoformat(timespec="seconds"), "step": "PURCHASE_REQUEST", "detail": f"Draft raised for {', '.join(purchase['items'])}"})

    skill = SKILL_FOR.get(at, "mechanical")
    tech = next((t for t in techs if t.get("available") and skill in t.get("skills", [])), None)
    log.append({"t": now.isoformat(timespec="seconds"), "step": "TECHNICIAN_ASSIGNED", "detail": tech["name"] if tech else "No matching technician - escalate to supervisor"})

    sla = SLA_HOURS.get(decision.get("priority", "MEDIUM"), 24)
    due = now + timedelta(hours=sla)
    start = now + timedelta(days=delay_days) if delay_days and at == "INSPECT" else now + timedelta(hours=min(sla, 2))
    log.append({"t": now.isoformat(timespec="seconds"), "step": "SCHEDULED", "detail": f"Start {start:%Y-%m-%d %H:%M}, SLA due {due:%Y-%m-%d %H:%M} ({sla} h)"})
    notes = [whatsapp_alert(decision, risk, "en", machine, polish=False), whatsapp_alert(decision, risk, "ur", machine, polish=False)]
    log.append({"t": now.isoformat(timespec="seconds"), "step": "NOTIFIED", "detail": "Supervisor + technician messages drafted (EN/UR), NOT sent"})
    ready = tech is not None and not (missing and at == "INSPECT" and delay_days > 0)
    return {"label": "SIMULATED PROCESS", "machine": machine, "state": "READY_FOR_EXECUTION" if ready else "BLOCKED - needs supervisor",
            "parts": parts, "purchase_request": purchase, "technician": tech["name"] if tech else None, "sla_hours": sla,
            "scheduled_start": start.isoformat(timespec="minutes"), "sla_due": due.isoformat(timespec="minutes"),
            "notifications": notes, "audit_log": log}
