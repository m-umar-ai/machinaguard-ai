def test_docs_load(kb):
    assert kb.ready and len(kb.chunks) >= 10
    assert {c["document"] for c in kb.chunks} >= {"Bearing Maintenance Guide", "Industrial Safety Procedure"}

def test_retrieval_relevant(kb):
    r = kb.search("bearing vibration temperature degradation")
    assert r and r[0]["document"] == "Bearing Maintenance Guide"
    assert all({"document", "section", "text", "relevance"} <= set(x) for x in r)

def test_sensor_query(kb):
    r = kb.search("verify redundant vibration sensor drift", k=3)
    assert any(x["document"] == "Vibration Troubleshooting Guide" for x in r)

def test_invalid_queries(kb):
    assert kb.search("") == [] and kb.search("   ") == [] and kb.search(None) == [] and kb.search(123) == []
