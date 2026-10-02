import json
from agents import anomaly_agent, diagnosis_agent, rag_agent, critic_agent, risk_agent, investigator_agent
from agents.agent_loop import run_agent, LLMPolicy, parse_json
from agents.tools import ToolBox


def setup(detector, kb, frames, mode="degrade"):
    df = frames[mode]; ml = detector.detect(df); an = anomaly_agent.run(ml); dg = diagnosis_agent.run(an, ml); rg = rag_agent.run(dg, kb)
    return df, ml, an, dg, rg


def scripted(*replies):
    it = iter(replies)
    return lambda prompt, system=None: next(it, None)


def test_parse_json_recovers_fenced_and_noisy():
    assert parse_json('```json\n{"a": 1}\n```') == {"a": 1}
    assert parse_json('Sure! {"a": 2} hope that helps') == {"a": 2}
    assert parse_json("not json") is None and parse_json(None) is None


def test_loop_tool_then_final(detector, kb, frames):
    df, ml, an, dg, rg = setup(detector, kb, frames); tb = ToolBox(df, detector, kb, ml, dg)
    llm = scripted('{"thought":"look","tool":"run_anomaly_model","args":{}}', '{"final":{"answer":"ok"}}')
    r = run_agent("g", tb, LLMPolicy(tb, "{}", llm=llm))
    assert r["ok"] and r["final"] == {"answer": "ok"} and r["trace"][0]["tool"] == "run_anomaly_model"


def test_loop_survives_bad_json_unknown_tool_and_budget(detector, kb, frames):
    df, ml, an, dg, rg = setup(detector, kb, frames); tb = ToolBox(df, detector, kb, ml, dg)
    r = run_agent("g", tb, LLMPolicy(tb, "{}", llm=scripted("garbage", '{"tool":"delete_everything","args":{}}', '{"final":{"x":1}}')))
    assert r["ok"] and "unknown tool" in r["trace"][0]["observation"]["error"]
    loop_forever = lambda p, s=None: '{"tool":"get_sensor_snapshot","args":{}}'
    r2 = run_agent("g", tb, LLMPolicy(tb, "{}", llm=loop_forever), max_steps=4)
    assert not r2["ok"] and len(r2["trace"]) == 4
    assert not run_agent("g", tb, LLMPolicy(tb, "{}", llm=lambda p, s=None: None))["ok"]


def test_draft_work_order_never_submits(detector, kb, frames):
    df, ml, an, dg, rg = setup(detector, kb, frames); tb = ToolBox(df, detector, kb, ml, dg)
    out = tb.call("draft_work_order", {"action": "x", "reason": "y", "evil": "z"})
    assert "NOT SUBMITTED" in out["status"]


def test_investigator_offline_default(detector, kb, frames, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False); monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    df, ml, an, dg, rg = setup(detector, kb, frames)
    r = investigator_agent.run(ml, df, dg, rg, detector, kb)
    assert r["valid"] and r["mode"] == "offline-rules" and len(r["trace"]) >= 6 and r["final"]["citations"]


def test_investigator_sensor_fault_detected_by_tools(detector, kb, frames, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    df, ml, an, dg, rg = setup(detector, kb, frames, "fault")
    assert investigator_agent.run(ml, df, dg, rg, detector, kb)["top_cause"] == "Primary vibration sensor fault / drift"


def test_investigator_llm_path_and_citation_filter(detector, kb, frames):
    df, ml, an, dg, rg = setup(detector, kb, frames)
    final = {"hypotheses": [{"cause": "Lubrication breakdown", "likelihood": 0.7, "evidence": ["temp"]}, {"cause": "Made up cause", "likelihood": 0.9}],
             "recommended_checks": ["check grease"], "citations": ["D99.9"], "summary": "Likely lubrication."}
    llm = scripted('{"tool":"run_anomaly_model","args":{}}',
                   '{"tool":"compare_vibration_sensors","args":{}}',
                   '{"tool":"get_baseline_diagnosis","args":{}}',
                   '{"tool":"search_manuals","args":{"query":"lubrication high temperature bearing grease"}}',
                   json.dumps({"final": final}))
    r = investigator_agent.run(ml, df, dg, rg, detector, kb, llm=llm)
    assert r["mode"].startswith("llm") and r["top_cause"] == "Lubrication breakdown"
    assert r["final"]["citations"] == [] and len(r["final"]["hypotheses"]) == 1  # hallucinated citation + unknown cause dropped


def test_investigator_falls_back_when_llm_unusable(detector, kb, frames):
    df, ml, an, dg, rg = setup(detector, kb, frames)
    r = investigator_agent.run(ml, df, dg, rg, detector, kb, llm=lambda p, s=None: "I cannot help")
    assert "fell back" in r["mode"] and r["valid"] and r["final"]


def test_critic_flags_investigator_disagreement_and_llm_concerns_only_add(detector, kb, frames):
    df, ml, an, dg, rg = setup(detector, kb, frames); rk = risk_agent.run(ml, dg)
    base = critic_agent.run(ml, an, dg, rg, rk)
    inv = {"top_cause": "Motor electrical overload", "summary": "x"}
    c = critic_agent.run(ml, an, dg, rg, rk, inv)
    assert c["confidence_penalty"] >= base["confidence_penalty"] + 0.1 and any("Investigator" in i["evidence"] for i in c["items"])
    llm = scripted(json.dumps({"concerns": [{"evidence": "e", "finding": "f", "concern": "c", "recommendation": "r"}, {"bad": 1}]}))
    c2 = critic_agent.run(ml, an, dg, rg, rk, None, llm=llm)
    assert len(c2["items"]) == len(base["items"]) + 1 and sum(i.get("source") == "LLM critic" for i in c2["items"]) == 1
    assert c2["confidence_penalty"] >= base["confidence_penalty"]
