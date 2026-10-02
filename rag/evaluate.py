"""Retrieval evaluation: python -m rag.evaluate   (hit@1, hit@3, MRR per mode + abstention on off-topic queries)."""
import json
from pathlib import Path
from rag.knowledge_base import KnowledgeBase

def evaluate(kb=None, path=Path(__file__).parent / "eval_set.json") -> dict:
    kb = kb or KnowledgeBase()
    data = json.loads(path.read_text(encoding="utf-8"))
    out = {"n_questions": len(data["questions"]), "n_chunks": len(kb.chunks), "n_docs": len({c["file"] for c in kb.chunks}), "modes": {}}
    for mode in ("tfidf", "bm25", "hybrid"):
        h1 = h3 = rr = 0.0
        for q, gold in data["questions"]:
            res = kb.search(q, k=5, min_score=0.0, mode=mode)
            files = [r["file"] for r in res]
            h1 += files[:1] == [gold]
            h3 += gold in files[:3]
            rr += 1 / (files.index(gold) + 1) if gold in files else 0
        n = len(data["questions"])
        out["modes"][mode] = {"hit@1": round(h1 / n, 3), "hit@3": round(h3 / n, 3), "mrr": round(rr / n, 3)}
    ok = sum(1 for q in data["off_topic"] if not kb.retrieve(q, k=1))
    out["abstain_rate_off_topic"] = round(ok / len(data["off_topic"]), 3)
    on_topic_answered = sum(1 for q, _ in data["questions"] if kb.retrieve(q, k=1))
    out["answer_rate_on_topic"] = round(on_topic_answered / len(data["questions"]), 3)
    return out


if __name__ == "__main__":
    print(json.dumps(evaluate(), indent=2))
