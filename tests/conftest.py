import sys
from pathlib import Path
import pytest
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ml.anomaly_detector import AnomalyDetector
from rag.knowledge_base import KnowledgeBase
from simulation.sensor_engine import SensorEngine, generate_dataset


@pytest.fixture(autouse=True)
def _no_real_llm(monkeypatch):
    """Tests never use your real API keys: every test starts in offline mode."""
    for k in ("GEMINI_API_KEY", "OPENAI_API_KEY", "LLM_PROVIDER"):
        monkeypatch.delenv(k, raising=False)


@pytest.fixture(scope="session")
def detector():
    df = generate_dataset()
    return AnomalyDetector().fit(df.iloc[:3000])


@pytest.fixture(scope="session")
def kb():
    return KnowledgeBase()


def make(mode, seed=3):
    e = SensorEngine(seed=seed)
    for _ in range(40):
        e.step()
    if mode == "degrade":
        e.start_degradation(60)
        for _ in range(45):
            e.step()
    elif mode == "fault":
        e.inject_fault(True)
        for _ in range(12):
            e.step()
    return e.frame()


@pytest.fixture
def frames():
    return {m: make(m) for m in ("normal", "degrade", "fault")}
