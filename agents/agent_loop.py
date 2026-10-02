"""Generic tool-using agent loop (ReAct-style, JSON protocol, provider-agnostic).

A *policy* decides the next step from the goal and the trace so far:
  * LLMPolicy  - asks a language model (Gemini / OpenAI-compatible) to choose a tool or give a final answer
  * RulePolicy - deterministic offline planner (used when no key is set, or as fallback if the LLM fails)
The loop enforces a tool whitelist, a step budget, JSON recovery and records a full trace for the UI.
"""
from __future__ import annotations
import json, re
from utils.config import llm_text

SYSTEM = ("You are an industrial maintenance investigator agent. You may call tools to gather evidence, then give a final answer. "
          "Reply with ONE JSON object only. To call a tool: {\"thought\": str, \"tool\": name, \"args\": {...}}. "
          "To finish: {\"final\": {...}}. Never invent sensor values or citations; cite only passage ids returned by search_manuals. "
          "You cannot execute actions; a human approves everything.")


def parse_json(raw):
    if not isinstance(raw, str):
        return None
    raw = re.sub(r"^```(?:json)?|```$", "", raw.strip(), flags=re.M).strip()
    for cand in (raw, raw[raw.find("{"): raw.rfind("}") + 1] if "{" in raw else ""):
        try:
            v = json.loads(cand)
            return v if isinstance(v, dict) else None
        except Exception:
            continue
    return None


def _short(obs, n=700):
    s = json.dumps(obs, default=str)
    return s if len(s) <= n else s[:n] + "...(truncated)"


class LLMPolicy:
    name = "llm"

    def __init__(self, toolbox, final_schema: str, llm=llm_text):
        self.tb, self.schema, self.llm = toolbox, final_schema, llm

    def next(self, goal, trace, force_final=False):
        hist = "\n".join(f"Step {t['step']}: called {t['tool']}({json.dumps(t['args'])}) -> {_short(t['observation'])}" for t in trace) or "(no tool calls yet)"
        prompt = (f"GOAL: {goal}\n\nTOOLS:\n{self.tb.describe()}\n\nFINAL ANSWER JSON SCHEMA: {self.schema}\n\nHISTORY:\n{hist}\n\n"
                  + ("You must give the final answer now." if force_final else "Next step (JSON only):"))
        for attempt in range(2):
            msg = parse_json(self.llm(prompt + ("\nYour previous reply was not valid JSON. Reply with JSON only." if attempt else ""), SYSTEM))
            if msg:
                return msg
        return None


def run_agent(goal, toolbox, policy, max_steps=10):
    trace, ok = [], False
    for step in range(1, max_steps + 1):
        msg = policy.next(goal, trace, force_final=(step == max_steps))
        if msg is None:
            return {"ok": False, "final": None, "trace": trace, "policy": policy.name, "error": "policy returned no valid JSON"}
        if "final" in msg and isinstance(msg["final"], dict):
            return {"ok": True, "final": msg["final"], "trace": trace, "policy": policy.name, "error": None}
        tool, args = msg.get("tool"), msg.get("args") or {}
        try:
            obs = toolbox.call(tool, args)
        except Exception as e:  # a tool crash is an observation, not an app crash
            obs = {"error": f"{type(e).__name__}: {e}"}
        trace.append({"step": step, "thought": str(msg.get("thought", ""))[:300], "tool": tool, "args": args, "observation": obs})
    return {"ok": False, "final": None, "trace": trace, "policy": policy.name, "error": "step budget exhausted"}
