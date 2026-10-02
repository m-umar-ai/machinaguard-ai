"""Tool box for the tool-using agents. Every tool is read-only or produces a DRAFT - nothing here can act on the plant."""
from __future__ import annotations
import numpy as np
from agents import risk_agent
from utils.config import UNITS

TOOL_SPECS = {
    "run_anomaly_model": ("Run the Isolation Forest on the latest sensor window. Returns status, score, affected sensors with z-scores.", {}),
    "get_sensor_snapshot": ("Latest mean value of every sensor over the last 5 ticks.", {}),
    "compare_vibration_sensors": ("Compare redundant vibration sensors A and B (mean gap, correlation). Large gap with normal temperature/energy suggests a sensor fault.", {}),
    "get_trend": ("Slope and total change of one sensor over a window.", {"sensor": "temperature|vibration|pressure|rpm|energy|production_rate", "window": "int, default 30"}),
    "get_baseline_diagnosis": ("Scores of the deterministic fault-signature matcher for all hypotheses.", {}),
    "search_manuals": ("Search the maintenance knowledge base (hybrid RAG). Returns passage ids you may cite.", {"query": "text", "k": "int, default 3"}),
    "estimate_risk": ("Failure risk, urgency, downtime and SIMULATED financial impact.", {}),
    "draft_work_order": ("Create a DRAFT work order text. It is NOT submitted; a human must approve.", {"action": "text", "reason": "text"}),
}


class ToolBox:
    def __init__(self, df, detector, kb, ml, diagnosis, trend=0.0):
        self.df, self.detector, self.kb, self.ml, self.diagnosis, self.trend = df, detector, kb, ml, diagnosis, trend
        self.retrieved: dict[str, dict] = {}  # cid -> passage, used to verify citations
        self.tools = {n: getattr(self, n) for n in TOOL_SPECS}

    def describe(self) -> str:
        return "\n".join(f"- {n}({', '.join(f'{k}: {v}' for k, v in a.items())}): {d}" for n, (d, a) in TOOL_SPECS.items())

    def call(self, name, args):
        if name not in self.tools:
            return {"error": f"unknown tool '{name}'"}
        args = args if isinstance(args, dict) else {}
        return self.tools[name](**{k: v for k, v in args.items() if k in TOOL_SPECS[name][1]})

    # ---- tools ----------------------------------------------------------------
    def run_anomaly_model(self):
        m = self.detector.detect(self.df)
        return {"status": m["status"], "score": m["anomaly_score"], "affected": {e["sensor"]: e["z_score"] for e in m["evidence"]}}

    def get_sensor_snapshot(self):
        t = self.df.tail(5)
        return {k: round(float(t[k].mean()), 2) for k in UNITS if k in t and k != "vib_disagreement"}

    def compare_vibration_sensors(self):
        t = self.df.tail(20)
        a, b = t["vibration"].astype(float), t["vibration_b"].astype(float)
        corr = float(np.corrcoef(a, b)[0, 1]) if a.std() > 1e-9 and b.std() > 1e-9 else 0.0
        return {"mean_A": round(float(a.mean()), 2), "mean_B": round(float(b.mean()), 2), "mean_gap": round(float((a - b).abs().mean()), 2),
                "correlation": round(corr, 2), "z_disagreement": round(float(self.ml.get("z_scores", {}).get("vib_disagreement", 0)), 1)}

    def get_trend(self, sensor="vibration", window=30):
        if sensor not in UNITS or sensor not in self.df:
            return {"error": f"unknown sensor '{sensor}'"}
        try:
            window = max(5, min(int(window), 120))
        except Exception:
            window = 30
        y = self.df[sensor].astype(float).tail(window).values
        slope = float(np.polyfit(np.arange(len(y)), y, 1)[0]) if len(y) > 2 else 0.0
        return {"sensor": sensor, "unit": UNITS[sensor], "slope_per_tick": round(slope, 4), "change": round(float(y[-1] - y[0]), 2), "window": len(y)}

    def get_baseline_diagnosis(self):
        d = self.diagnosis
        return {"likely_cause": d.get("likely_cause"), "confidence": d.get("confidence"), "scores": d.get("scores", {})}

    def search_manuals(self, query="", k=3):
        try:
            k = max(1, min(int(k), 5))
        except Exception:
            k = 3
        res = self.kb.retrieve(str(query), k=k)
        for r in res:
            self.retrieved[r["cid"]] = r
        return {"passages": [{"cid": r["cid"], "source": f'{r["document"]} - {r["section"]}', "relevance": r["relevance"], "text": r["text"][:320]} for r in res],
                "note": "" if res else "NO EVIDENCE FOUND - do not invent citations"}

    def estimate_risk(self):
        r = risk_agent.run(self.ml, self.diagnosis, self.trend)
        return {k: r[k] for k in ("failure_risk", "level", "urgency", "downtime_hours", "financial_impact_usd", "assumptions_note")}

    def draft_work_order(self, action="", reason=""):
        return {"status": "DRAFT - NOT SUBMITTED (requires human approval)", "action": str(action)[:200], "reason": str(reason)[:300]}
