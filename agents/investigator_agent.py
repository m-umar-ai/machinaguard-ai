"""Agent 3b - Investigator: a tool-using agent that gathers evidence and proposes ranked hypotheses.
LLM-driven when a key is available; deterministic RulePolicy offline; automatic fallback if the LLM output is unusable.
It can only RECOMMEND - the Critic, Decision Agent and human gate still sit downstream."""
from __future__ import annotations
from agents.agent_loop import LLMPolicy, run_agent
from agents.diagnosis_agent import HYPOTHESES
from agents.tools import ToolBox
from utils.config import llm_available, llm_name

CAUSES = list(HYPOTHESES)
SCHEMA = ('{"hypotheses":[{"cause": one of %s, "likelihood": 0-1, "evidence": [str]}], '
          '"recommended_checks":[str], "citations":[passage ids from search_manuals], "summary": "2 sentences, no certainty claims"}' % CAUSES)
GOAL = ("Investigate the current machine anomaly. Use tools to check the anomaly model, whether redundant vibration sensors agree, "
        "trends, the deterministic diagnosis and the maintenance manuals. Then rank the possible causes.")


class RulePolicy:
    """Deterministic planner: fixed investigation playbook, reasons from observations already in the trace."""
    name = "offline-rules"

    def __init__(self, toolbox):
        self.tb = toolbox

    def _seen(self, trace, tool, **kw):
        return any(t["tool"] == tool and all(t["args"].get(k) == v for k, v in kw.items()) for t in trace)

    def _obs(self, trace, tool):
        return next((t["observation"] for t in trace if t["tool"] == tool), {})

    def next(self, goal, trace, force_final=False):
        steps = [("run_anomaly_model", {}, "Start with what the ML model says changed."),
                 ("compare_vibration_sensors", {}, "Check whether redundant vibration sensors agree before trusting the reading."),
                 ("get_trend", {"sensor": "vibration", "window": 30}, "Is vibration drifting gradually (wear) or jumping (sensor/looseness)?"),
                 ("get_trend", {"sensor": "temperature", "window": 30}, "Bearing wear should eventually show a thermal signature."),
                 ("get_baseline_diagnosis", {}, "Get the signature-matcher scores for every hypothesis."),
                 ("estimate_risk", {}, "Quantify urgency and simulated impact.")]
        for tool, args, why in steps:
            if not self._seen(trace, tool, **args):
                return {"thought": why, "tool": tool, "args": args}
        base = self._obs(trace, "get_baseline_diagnosis")
        cause = base.get("likely_cause", "")
        if not self._seen(trace, "search_manuals"):
            q = {"Bearing degradation": "bearing degradation vibration temperature inspection replacement",
                 "Primary vibration sensor fault / drift": "verify vibration sensor redundant disagree calibration"}.get(cause, f"{cause} inspection procedure")
            return {"thought": f"Retrieve documented procedure for '{cause}'.", "tool": "search_manuals", "args": {"query": q, "k": 3}}
        return {"final": self._final(trace, base)}

    def _final(self, trace, base):
        cmp_, vt = self._obs(trace, "compare_vibration_sensors"), None
        scores = dict(base.get("scores") or {})
        sensor_fault = cmp_.get("z_disagreement", 0) >= 4
        hyps = []
        if sensor_fault:
            scores["Primary vibration sensor fault / drift"] = max(scores.get("Primary vibration sensor fault / drift", 0), 0.6)
        total = sum(scores.values()) or 1.0
        for c, s in sorted(scores.items(), key=lambda kv: -kv[1])[:3]:
            ev = [f"signature match {s / total:.0%}"]
            if c.startswith("Primary vibration") and sensor_fault:
                ev.append(f"vibration A/B gap {cmp_.get('mean_gap')} mm/s, z={cmp_.get('z_disagreement')}")
            hyps.append({"cause": c, "likelihood": round(s / total, 2), "evidence": ev})
        passages = next((t["observation"].get("passages", []) for t in trace if t["tool"] == "search_manuals"), [])
        checks = (["Verify vibration sensors A/B against a handheld meter", "Inspect sensor mounting and cable"] if sensor_fault
                  else ["Collect vibration spectrum (bearing defect frequencies)", "Check lubricant condition and maintenance history"])
        top = hyps[0]["cause"] if hyps else "no fault indicated"
        return {"hypotheses": hyps, "recommended_checks": checks, "citations": [p["cid"] for p in passages],
                "summary": f"Evidence points most to '{top}' (hypothesis, not confirmed). Physical inspection is needed to confirm."}


def validate_final(final, toolbox):
    """Return a cleaned final answer or None if unusable. Citations are limited to passages actually retrieved."""
    if not isinstance(final, dict):
        return None
    hyps = []
    for h in final.get("hypotheses", []) if isinstance(final.get("hypotheses"), list) else []:
        if isinstance(h, dict) and h.get("cause") in CAUSES:
            try:
                p = float(h.get("likelihood", 0))
            except Exception:
                continue
            hyps.append({"cause": h["cause"], "likelihood": round(min(max(p, 0.0), 1.0), 2), "evidence": [str(e)[:160] for e in (h.get("evidence") or [])][:4]})
    if not hyps or not isinstance(final.get("summary"), str):
        return None
    cites = [c for c in (final.get("citations") or []) if c in toolbox.retrieved]
    return {"hypotheses": hyps[:4], "recommended_checks": [str(x)[:140] for x in (final.get("recommended_checks") or [])][:4],
            "citations": cites, "summary": final["summary"][:400]}


def run(ml, df, diagnosis, rag, detector, kb, trend=0.0, llm=None) -> dict:
    if not ml.get("valid") or ml.get("status") in ("NORMAL", "UNKNOWN"):
        return {"agent": "Investigator Agent", "valid": True, "mode": "idle", "trace": [], "final": None, "top_cause": None,
                "summary": "No investigation needed - machine within baseline."}
    mode, res, final = "offline-rules", None, None
    if llm is not None or llm_available():
        tb = ToolBox(df, detector, kb, ml, diagnosis, trend)
        kw = {"llm": llm} if llm is not None else {}
        res = run_agent(GOAL, tb, LLMPolicy(tb, SCHEMA, **kw))
        final = validate_final(res["final"], tb) if res["ok"] else None
        mode = f"llm ({llm_name()})" if final else "offline-rules (LLM unusable - fell back)"
    if final is None:
        tb = ToolBox(df, detector, kb, ml, diagnosis, trend)
        res = run_agent(GOAL, tb, RulePolicy(tb))
        final = validate_final(res["final"], tb) if res["ok"] else None
    if final is None:
        return {"agent": "Investigator Agent", "valid": False, "mode": mode, "trace": res["trace"] if res else [], "final": None, "top_cause": None,
                "summary": "Investigation failed; deterministic agents continue."}
    top = max(final["hypotheses"], key=lambda h: h["likelihood"])
    return {"agent": "Investigator Agent", "valid": True, "mode": mode, "trace": res["trace"], "final": final, "top_cause": top["cause"],
            "summary": f"[{mode}] {len(res['trace'])} tool calls -> top hypothesis '{top['cause']}' ({top['likelihood']:.0%}); {len(final['citations'])} citation(s)."}
