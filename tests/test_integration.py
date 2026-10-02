from core import MachineSession
from agents.pipeline import run_pipeline

def test_full_pipeline_sensor_to_workflow(detector, kb):
    s = MachineSession(detector=detector, kb=kb)
    s.simulate_failure()
    for _ in range(120):
        s.tick()
        if s.incident and s.incident["reveal"] >= len(s.incident["result"]["events"]): break
    inc = s.incident
    assert inc, "ML never raised an incident"
    names = [e["agent"] for e in inc["result"]["events"]]
    for a in ("ML Detector", "Anomaly Agent", "Diagnosis Agent", "RAG Agent", "Risk Agent", "Critic Agent", "Decision Agent", "Human Gate"):
        assert a in names
    assert inc["workflow"]["ticket"] is None and inc["gate"].state == "PENDING"
    s.approve()
    assert inc["workflow"]["ticket"]["label"] == "SIMULATED WORKFLOW"
    s.complete_maintenance()
    for _ in range(15): s.tick()
    assert s.ml["status"] == "NORMAL" and s.incident is None  # monitoring resumes

def test_sensor_fault_flow_reduces_confidence(detector, kb):
    s = MachineSession(detector=detector, kb=kb); s.inject_fault()
    for _ in range(40):
        s.tick()
        if s.incident: break
    r = s.incident["result"]
    assert r["decision"]["action_type"] == "VERIFY_SENSOR" and r["critic"]["verdict"] == "CHALLENGES"

def test_demo_mode_is_deterministic_and_completes(detector, kb):
    def run():
        s = MachineSession(detector=detector, kb=kb); s.start_demo(); seq = []
        for _ in range(150):
            s.tick(); seq.append((s.ml["status"], s.incident["gate"].state if s.incident else None))
            if not s.demo and s.tick_n > 30: break
        return s.tick_n, [x for i, x in enumerate(seq) if i == 0 or x != seq[i - 1]]
    a, b = run(), run()
    assert a == b and any(x[1] == "APPROVED" for x in a[1]) and a[1][-1] == ("NORMAL", None)

def test_agent_failure_is_survived(detector, kb, frames, monkeypatch):
    from agents import critic_agent
    monkeypatch.setattr(critic_agent, "run", lambda *a, **k: 1 / 0)
    r = run_pipeline(frames["degrade"], detector, kb)
    assert r["critic"]["verdict"] == "CHALLENGES" and r["decision"]["requires_approval"]

def test_offline_mode_without_key(monkeypatch, detector, kb):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    s = MachineSession(detector=detector, kb=kb); assert s.offline
    r = run_pipeline(make_deg(), detector, kb); assert r["decision"]["llm_used"] is False

def test_llm_failure_falls_back(monkeypatch, detector, kb):
    monkeypatch.setenv("GEMINI_API_KEY", "invalid")
    import utils.config as c; monkeypatch.setattr(c.urllib.request, "urlopen", lambda *a, **k: (_ for _ in ()).throw(OSError("down")))
    r = run_pipeline(make_deg(), detector, kb); assert r["decision"]["llm_used"] is False and r["decision"]["executive_summary"]

def make_deg():
    from tests.conftest import make
    return make("degrade")
