"""'Ask the Machine' - natural-language assistant over live telemetry + manuals.
LLM mode: tool-using agent (same loop/tools as the Investigator). Offline mode: intent router over the same tools + grounded RAG."""
from __future__ import annotations
import re
from agents import anomaly_agent, diagnosis_agent
from agents.agent_loop import LLMPolicy, run_agent
from agents.tools import ToolBox
from rag.answer import answer as rag_answer, NO_EVIDENCE
from utils import config as _cfg
from utils.config import llm_available, llm_name

SCHEMA = '{"answer": "short answer for a plant manager, facts only from tool results", "citations": [passage ids returned by search_manuals]}'


def _toolbox(df, detector, kb, trend=0.0):
    ml = detector.detect(df)
    dg = diagnosis_agent.run(anomaly_agent.run(ml), ml)
    return ToolBox(df, detector, kb, ml, dg, trend), ml


def ask(question: str, df, detector, kb, trend: float = 0.0, llm=None) -> dict:
    q = (question or "").strip()
    if not q:
        return {"answer": "Ask me about machine health, sensors, risk or maintenance procedures.", "method": "none", "trace": [], "citations": []}
    tb, ml = _toolbox(df, detector, kb, trend)
    if llm is not None or llm_available():
        kw = {"llm": llm} if llm is not None else {}
        res = run_agent(f"Answer the plant manager's question using tools. Question: {q}", tb, LLMPolicy(tb, SCHEMA, **kw), max_steps=6)
        f = res["final"] if res["ok"] else None
        if isinstance(f, dict) and isinstance(f.get("answer"), str) and f["answer"].strip():
            cites = [tb.retrieved[c] for c in (f.get("citations") or []) if c in tb.retrieved]
            return {"answer": f["answer"][:900], "method": f"LLM tool-agent ({llm_name()})", "trace": res["trace"], "citations": cites}
    out = _offline(q, tb, ml, kb)
    if llm is None and llm_available():  # LLM was tried but failed -> tell the user why
        out["llm_error"] = _cfg.LAST_LLM_ERROR or "LLM returned an unusable reply (not valid JSON)"
    return out


def _offline(q, tb, ml, kb):
    ql, trace = q.lower(), []

    def use(tool, **args):
        obs = tb.call(tool, args)
        trace.append({"step": len(trace) + 1, "thought": "intent router", "tool": tool, "args": args, "observation": obs})
        return obs

    if re.search(r"\b(cost|risk|downtime|loss|money|impact|urgent|urgency)\b", ql):
        r = use("run_anomaly_model"); k = use("estimate_risk")
        ans = (f"Status {r['status']}. Failure risk {k['failure_risk']:.0%} ({k['level']}); {k['urgency']}; est. downtime {k['downtime_hours']} h; "
               f"simulated impact ≈ ${k['financial_impact_usd']:,}. {k['assumptions_note']}")
        return {"answer": ans, "method": "offline router", "trace": trace, "citations": []}
    if re.search(r"\b(sensor|trust|faulty|fault|redundant|disagree|reading)\b", ql) and not re.search(r"\b(how (do|to|can)|procedure|steps)\b", ql):
        c = use("compare_vibration_sensors")
        verdict = ("Sensors A and B disagree strongly - suspect a sensor problem before any mechanical work." if c["z_disagreement"] >= 4
                   else "Sensors A and B agree - the vibration reading looks trustworthy.")
        return {"answer": f"{verdict} (A={c['mean_A']} mm/s, B={c['mean_B']} mm/s, gap {c['mean_gap']}, correlation {c['correlation']}).", "method": "offline router", "trace": trace, "citations": []}
    if re.search(r"\b(status|health|how is|state|ok|normal|anomal\w*|what.?s wrong|happening)\b", ql):
        r = use("run_anomaly_model"); s = use("get_sensor_snapshot")
        aff = ", ".join(f"{k} (z={v})" for k, v in r["affected"].items()) or "none"
        return {"answer": f"Machine status: {r['status']} (anomaly score {r['score']}). Sensors outside baseline: {aff}. Latest values: " +
                ", ".join(f"{k} {v}" for k, v in s.items()) + ".", "method": "offline router", "trace": trace, "citations": []}
    res = rag_answer(q, kb, llm=None)
    trace.append({"step": 1, "thought": "intent router -> grounded RAG", "tool": "search_manuals", "args": {"query": q}, "observation": {"abstained": res["abstained"], "method": res["method"]}})
    return {"answer": res["answer"], "method": "offline grounded RAG" + (" (abstained)" if res["abstained"] else ""), "trace": trace, "citations": res["citations"]}
