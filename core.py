"""MachineSession: everything the UI needs, with no Streamlit dependency (so it is unit-testable)."""
from __future__ import annotations
import os
from datetime import datetime
from ml.anomaly_detector import AnomalyDetector
from ml.train_model import train
from rag.knowledge_base import KnowledgeBase
from simulation.sensor_engine import SensorEngine
from agents.pipeline import run_pipeline
from agents import workflow_agent
from workflows.maintenance_workflow import ApprovalGate
from utils.config import MODEL_PATH, llm_available

# "need" = number of pipeline events that must be revealed (event order: ML, Anomaly, Diagnosis, RAG, Investigator, Risk, Critic, Decision, Gate)
STAGES = [("Sensor Data", 1), ("Anomaly", 2), ("Diagnosis", 3), ("RAG Evidence", 4), ("Agentic Investigation", 5), ("Risk", 6),
          ("Critic", 7), ("Decision", 8), ("Human Approval", 9), ("Process Automation", 10)]
AGENTS = [("Anomaly Agent", 2), ("Diagnosis Agent", 3), ("RAG Agent", 4), ("Investigator Agent", 5), ("Risk Agent", 6), ("Critic Agent", 7),
          ("Decision Agent", 8), ("Workflow Agent", 10)]


def load_detector() -> AnomalyDetector:
    try:
        return AnomalyDetector.load()
    except Exception:
        det, _ = train()
        return det


class MachineSession:
    def __init__(self, seed: int = 42, detector=None, kb=None):
        self.detector = detector or load_detector()
        self.kb = kb or KnowledgeBase()
        self.seed = seed
        self.engine = SensorEngine(seed)
        self.running = False
        self.demo = False
        self.reset(keep_running=False)
        for _ in range(60):  # pre-fill so charts aren't empty
            self.engine.step()
        self.ml = self.detector.detect(self.engine.frame())

    # --- lifecycle ----------------------------------------------------------
    def reset(self, keep_running=False):
        self.engine.reset()
        self.tick_n = 0
        self.scores: list[float] = []
        self.incident = None
        self.timeline: list[dict] = []
        self.demo = False
        self.demo_marks: dict = {}
        self.running = keep_running
        self.ml = {"status": "NORMAL", "anomaly_score": 0.0, "evidence": [], "affected_sensors": [], "valid": True}
        for _ in range(60):
            self.engine.step()

    @property
    def offline(self) -> bool:
        return not llm_available()

    def log(self, agent, text):
        self.timeline.append({"time": datetime.now().strftime("%H:%M:%S"), "agent": agent, "text": text})

    # --- user actions -----------------------------------------------------------
    def simulate_failure(self):
        self.engine.start_degradation(55)
        self.log("Operator", "Developing failure simulation started")

    def inject_fault(self):
        self.engine.inject_fault(True)
        self.log("Operator", "Sensor fault injected (vibration sensor A)")

    def start_demo(self):
        self.reset()
        self.demo, self.running = True, True
        self.log("Demo", "Demo mode started - healthy machine")

    def approve(self, by="human"):
        if self.incident and self.incident["gate"].state == "PENDING":
            self.incident["gate"].approve()
            self.incident["approved_tick"] = self.tick_n
            self._update_workflow()
            self.log("Human" if by == "human" else "Demo operator (simulated human)", "Action APPROVED" if by == "human" else "Action APPROVED by scripted demo operator")
            self.log("Workflow Agent", self.incident["workflow"]["summary"])
           

    def reject(self):
        if self.incident and self.incident["gate"].state == "PENDING":
            self.incident["gate"].reject()
            self._update_workflow()
            self.log("Human", "Action REJECTED - sent for review")

    def complete_maintenance(self):
        self.engine.perform_maintenance()
        if self.incident:
            self.incident["closed"] = True
        self.log("Maintenance", "Maintenance complete (simulated) - monitoring resumes")

    def _update_workflow(self):
        i = self.incident
        i["workflow"] = workflow_agent.run(i["result"]["decision"], i["gate"], i["result"]["risk"])

    def calibrate(self, min_ticks=200):
        """Commissioning step: learn THIS machine's healthy baseline (see validation: generic model false-alarms on noisier plants)."""
        df = self.engine.frame()
        if self.incident or len(df) < min_ticks or self.ml.get("status") != "NORMAL":
            return False
        from ml.anomaly_detector import AnomalyDetector
        self.detector = AnomalyDetector().fit(df)
        self.log("Calibration", f"Detector re-fitted on {len(df)} healthy ticks of this machine")
        return True

    # --- main loop ------------------------------------------------------------------
    def tick(self):
        self.tick_n += 1
        self._demo_script()
        row = self.engine.step()
        df = self.engine.frame(120)
        self.ml = self.detector.detect(df)
        self.scores.append(self.ml["anomaly_score"])
        inc = self.incident
        if inc and inc.get("closed") and self.ml["status"] == "NORMAL":
            self.incident = inc = None
        if self.ml["status"] in ("WARNING", "CRITICAL") and inc is None:
            trend = self._trend()
            res = run_pipeline(df, self.detector, self.kb, trend)
            gate = ApprovalGate(res["decision"])
            self.incident = {"result": res, "gate": gate, "reveal": 0, "start_tick": self.tick_n, "closed": False, "workflow": None, "stable_tick": self.tick_n}
            self._update_workflow()
            self.log("ML Detector", f'Anomaly detected ({self.ml["status"]})')
        elif inc and not inc["closed"]:
            n_events = len(inc["result"]["events"])
            if inc["reveal"] < n_events:
                ev = inc["result"]["events"][inc["reveal"]]
                self.timeline.append(ev)
                inc["reveal"] += 1
            elif inc["gate"].state == "PENDING" and self.tick_n % 6 == 0:
                # keep monitoring: refresh the recommendation while waiting for the human
                res = run_pipeline(df, self.detector, self.kb, self._trend(), investigation=inc["result"].get("investigation"))
                inc["result"] = res
                inc["gate"].decision = res["decision"]
                self._update_workflow()
        return row

    def _trend(self):
        s = self.scores[-10:]
        return max(0.0, (s[-1] - s[0]) / 10) * 5 if len(s) >= 2 else 0.0

    def _demo_script(self):
        if not self.demo:
            return
        t, inc = self.tick_n, self.incident
        if t == 12:
            self.engine.start_degradation(50)
            self.log("Demo", "Gradual degradation begins")
        if inc and not inc["closed"]:
            n = len(inc["result"]["events"])
            if inc["reveal"] >= n and inc["gate"].state == "PENDING":
                self.demo_marks.setdefault("pending", self.tick_n)
                if self.tick_n - self.demo_marks["pending"] >= 6:
                    self.approve(by="demo")
            if inc["gate"].state == "APPROVED" and self.tick_n - inc.get("approved_tick", self.tick_n) >= 8:
                self.complete_maintenance()
        if self.incident is None and t > 20 and self.demo_marks.get("pending") and self.ml["status"] == "NORMAL":
            self.log("Demo", "Machine healthy again - monitoring continues")
            self.demo = False

    # --- helpers for UI ---------------------------------------------------------------
    def stage_states(self):
        r = self.incident["reveal"] if self.incident else 0
        st = self.incident["gate"].state if self.incident else None
        out = []
        for name, need in STAGES:
            if name == "Sensor Data":
                out.append((name, "done"))
            elif name == "Human Approval":
                out.append((name, "done" if st in ("APPROVED", "REJECTED") else "active" if r >= 9 and st == "PENDING" else "pending"))
            elif name == "Process Automation":
                out.append((name, "done" if st == "APPROVED" else "pending"))
            else:
                out.append((name, "done" if r >= need else "active" if r == need - 1 and r > 0 else "pending"))
        return out

    def agent_states(self):
        r = self.incident["reveal"] if self.incident else 0
        cr = self.incident["result"]["critic"]["verdict"] if self.incident else "SUPPORTS"
        st = self.incident["gate"].state if self.incident else None
        out = []
        for name, need in AGENTS:
            if name == "Workflow Agent":
                s = "🟢" if st == "APPROVED" else "⚪"
            elif not self.incident or r < need:
                s = "⚪" if self.incident else "🟢"
            else:
                s = "🟡" if name == "Critic Agent" and cr != "SUPPORTS" else "🟢"
            out.append((name, s))
        return out
