"""Agent 3 - RAG Maintenance Knowledge Agent. Only returns real retrieved chunks - never invents citations."""
QUERY = {
    "Bearing degradation": "bearing degradation vibration temperature energy rising inspection replacement",
    "Primary vibration sensor fault / drift": "verify vibration sensor redundant accelerometer disagree drift calibration",
    "Lubrication breakdown": "lubrication high temperature bearing grease",
    "Shaft misalignment / imbalance": "misalignment imbalance vibration coupling alignment",
    "Motor electrical overload": "energy consumption rpm overload motor current",
    "Pressure / process fault": "pressure process fault",
}


def run(diagnosis: dict, kb) -> dict:
    cause = diagnosis.get("likely_cause", "")
    if not diagnosis.get("valid") or cause not in QUERY:
        return {"agent": "RAG Agent", "valid": True, "query": "", "results": [], "summary": "No retrieval needed."}
    q = QUERY[cause]
    res = kb.search(q + " safety procedure", k=3) if cause != "Primary vibration sensor fault / drift" else kb.search(q, k=3)
    if not res:
        return {"agent": "RAG Agent", "valid": False, "query": q, "results": [],
                "summary": "Knowledge retrieval unavailable or returned nothing - proceeding without maintenance evidence."}
    return {"agent": "RAG Agent", "valid": True, "query": q, "results": res,
            "summary": f"Retrieved {len(res)} passages; best: {res[0]['document']} - {res[0]['section']} (relevance {res[0]['relevance']})."}
