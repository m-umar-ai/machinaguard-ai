from rag.answer import answer, NO_EVIDENCE
from rag.evaluate import evaluate
from genai.assistant import ask
from genai.reports import whatsapp_alert, shift_report


def test_retrieval_quality_and_abstention(kb):
    e = evaluate(kb)
    assert e["n_docs"] >= 25 and e["modes"]["hybrid"]["hit@3"] >= 0.9 and e["modes"]["hybrid"]["mrr"] >= e["modes"]["tfidf"]["mrr"]
    assert e["abstain_rate_off_topic"] == 1.0 and e["answer_rate_on_topic"] >= 0.95


def test_answer_abstains_and_extractive(kb):
    assert answer("best biryani recipe", kb, llm=None)["abstained"]
    a = answer("What are the steps to lock out a machine before repair?", kb, llm=None)
    assert not a["abstained"] and a["method"] == "extractive" and a["citations"]


def test_llm_answer_citations_verified(kb):
    good = lambda p, s=None: "Use lockout-tagout isolation [D13.2]."
    bad = lambda p, s=None: "Do magic [D99.9]."
    q = "What are the steps to lock out a machine before repair?"
    top = kb.retrieve(q)[0]["cid"]
    ok = answer(q, kb, llm=lambda p, s=None: f"Isolate energy first [{top}].")
    assert ok["method"] == "llm" and ok["citations"][0]["cid"] == top
    assert answer(q, kb, llm=bad)["method"] == "extractive"  # hallucinated citation rejected
    assert answer(q, kb, llm=lambda p, s=None: "INSUFFICIENT")["abstained"]


def test_assistant_offline(detector, kb, frames, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    r = ask("Can I trust the vibration sensor?", frames["fault"], detector, kb)
    assert "disagree" in r["answer"] and r["trace"]
    assert "risk" in ask("what is the risk and cost", frames["degrade"], detector, kb)["answer"].lower()
    assert ask("best biryani in karachi", frames["normal"], detector, kb)["answer"] == NO_EVIDENCE
    assert ask("", frames["normal"], detector, kb)["method"] == "none"


def test_assistant_llm_agent_with_fake(detector, kb, frames):
    replies = iter(['{"tool":"compare_vibration_sensors","args":{}}', '{"final":{"answer":"Sensors disagree.","citations":["D99.9"]}}'])
    r = ask("sensor ok?", frames["fault"], detector, kb, llm=lambda p, s=None: next(replies))
    assert r["method"].startswith("LLM") and r["citations"] == []


def test_bilingual_alert_and_report(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    d = {"action_type": "VERIFY_SENSOR", "priority": "MEDIUM", "confidence": 0.4, "problem": "p", "recommended_action": "a", "possible_causes": ["Primary vibration sensor fault / drift"]}
    ur = whatsapp_alert(d, {}, "ur")["text"]
    assert "مشین" in ur and "منظوری" in ur and "40%" in ur
    assert "SIMULATED" in whatsapp_alert(d, {}, "en")["text"]
    assert "معمول" in shift_report([], None, {"status": "NORMAL"}, "ur")["text"]
