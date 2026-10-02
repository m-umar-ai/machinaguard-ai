"""GenAI communication layer: WhatsApp-style alerts and shift reports in English and Urdu.
LLM (if configured) polishes/translates; otherwise deterministic bilingual templates are used (labelled)."""
from __future__ import annotations
from datetime import datetime
from utils.config import llm_text, llm_available

PRIO_UR = {"HIGH": "فوری", "MEDIUM": "درمیانی", "LOW": "کم", "NONE": "—"}
CAUSE_UR = {"Bearing degradation": "بیئرنگ کی خرابی / گھساؤ", "Primary vibration sensor fault / drift": "پرائمری وائبریشن سینسر کی خرابی",
            "Lubrication breakdown": "چکنائی کا ناکافی ہونا", "Shaft misalignment / imbalance": "شافٹ کی غلط ترتیب / عدم توازن",
            "Motor electrical overload": "موٹر پر برقی اوورلوڈ", "Pressure / process fault": "پریشر / پراسیس کی خرابی"}
ACTION_UR = {"INSPECT": "لاک آؤٹ ٹیگ آؤٹ کے ساتھ معائنہ کیا جائے", "VERIFY_SENSOR": "مکینیکل مرمت سے پہلے وائبریشن سینسر A/B کی جانچ اور کیلیبریشن کی جائے",
             "MONITOR": "نگرانی جاری رکھی جائے"}


def _cause(decision):
    return (decision.get("possible_causes") or ["Unknown"])[0]


def whatsapp_alert(decision: dict, risk: dict | None = None, lang: str = "en", machine: str = "M-04", polish=None) -> dict:
    risk = risk or {}
    conf, prio = decision.get("confidence", 0), decision.get("priority", "MEDIUM")
    if lang == "ur":
        if decision.get("action_type") == "MONITOR":
            body = f"✅ مشین {machine}: کوئی مسئلہ نہیں۔ نگرانی جاری ہے۔"
        else:
            body = (f"⚠️ مشین {machine}: {CAUSE_UR.get(_cause(decision), 'غیر معمولی رجحان')} کا امکان\n"
                    f"تجویز: {ACTION_UR.get(decision.get('action_type'), 'معائنہ')}\n"
                    f"ترجیح: {PRIO_UR.get(prio, prio)} | اعتماد: {conf:.0%} (تصدیق شدہ نہیں)\n"
                    f"منظوری درکار ہے — منظوری کے بغیر کوئی کارروائی نہیں ہوگی۔\n[سمولیشن]")
        method = "bilingual template"
    else:
        body = (f"✅ Machine {machine}: no problem, monitoring continues." if decision.get("action_type") == "MONITOR" else
                f"⚠️ Machine {machine}: {decision.get('problem')}\nRecommended: {decision.get('recommended_action')}\n"
                f"Priority: {prio} | Confidence: {conf:.0%} (hypothesis, not confirmed)\n"
                f"{risk.get('urgency', '')}\nApproval required - no action without human approval.\n[SIMULATED]")
        method = "template"
    txt = None if polish is False else (polish or (llm_text if llm_available() else None))
    if txt:
        out = txt(f"Rewrite this factory alert as a short clear WhatsApp message in {'Urdu' if lang == 'ur' else 'English'}. "
                  f"Keep every fact, number and the words SIMULATED/approval. Output the message only.\n\n{body}", None)
        if out and len(out) > 20:
            body, method = out, "LLM"
    return {"lang": lang, "text": body, "method": method}


def shift_report(timeline: list[dict], incident: dict | None, ml: dict, lang: str = "en", machine: str = "M-04", polish=None) -> dict:
    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    if incident:
        d, rk = incident["result"]["decision"], incident["result"]["risk"]
        state = incident["gate"].state
        if lang == "ur":
            body = (f"شفٹ رپورٹ — مشین {machine} — {now}\nحالت: {ml.get('status')} (اینومیلی اسکور {ml.get('anomaly_score', 0):.2f})\n"
                    f"ممکنہ وجہ: {CAUSE_UR.get(_cause(d), _cause(d))} — اعتماد {d['confidence']:.0%} (تصدیق شدہ نہیں)\n"
                    f"تجویز: {ACTION_UR.get(d.get('action_type'), '')}\nخطرہ: {rk.get('level')} ({rk.get('failure_risk', 0):.0%}) — تخمینی نقصان (سمولیشن) ≈ ${rk.get('financial_impact_usd', 0):,}\n"
                    f"منظوری کی حالت: {state}\nشواہد: {len(d.get('evidence_docs', []))} مینول حوالہ جات")
        else:
            body = (f"SHIFT REPORT - Machine {machine} - {now}\nStatus: {ml.get('status')} (anomaly score {ml.get('anomaly_score', 0):.2f})\n"
                    f"Problem: {d['problem']}\nLikely cause: {_cause(d)} - confidence {d['confidence']:.0%} (not confirmed)\n"
                    f"Recommended: {d['recommended_action']}\nRisk: {rk.get('summary')}\nApproval state: {state}\n"
                    f"Evidence: {'; '.join(d.get('evidence_docs', [])) or 'none retrieved'}\nCritic: {d.get('critic_verdict')}")
    else:
        body = (f"شفٹ رپورٹ — مشین {machine} — {now}\nمشین معمول کی حد میں ہے۔ کوئی کارروائی درکار نہیں۔" if lang == "ur" else
                f"SHIFT REPORT - Machine {machine} - {now}\nMachine within baseline. No action required.")
    method = "bilingual template"
    fn = None if polish is False else (polish or (llm_text if llm_available() else None))
    if fn and incident:
        out = fn(f"Write a concise, professional shift handover report in {'Urdu' if lang == 'ur' else 'English'} from these facts. Add nothing new; keep all numbers.\n\n{body}", None)
        if out and len(out) > 40:
            body, method = out, "LLM"
    return {"lang": lang, "text": body, "method": method}
