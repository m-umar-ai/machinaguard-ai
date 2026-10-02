"""Grounded answer generation: answer ONLY from retrieved passages, cite passage ids, verify citations, abstain if no evidence."""
from __future__ import annotations
import re
from utils.config import llm_text

_CITE = re.compile(r"\[([A-Z]\d{2}\.\d)\]")
NO_EVIDENCE = "No supporting passage found in the maintenance knowledge base - escalate to a qualified technician."


def _extractive(passages: list[dict]) -> str:
    best = passages[0]
    sents = re.split(r"(?<=[.!?])\s+", best["text"])
    return " ".join(sents[:2]) + f" [{best['cid']}]"


def verify_citations(text: str, passages: list[dict]) -> bool:
    cited = set(_CITE.findall(text))
    return bool(cited) and cited <= {p["cid"] for p in passages}


def answer(question: str, kb, k: int = 3, llm=llm_text) -> dict:
    passages = kb.retrieve(question, k=k)
    if not passages:
        return {"question": question, "answer": NO_EVIDENCE, "abstained": True, "method": "abstain", "verified": True, "citations": []}
    ctx = "\n".join(f"[{p['cid']}] ({p['document']} - {p['section']}) {p['text']}" for p in passages)
    prompt = (f"Answer the maintenance question using ONLY the numbered passages. Cite passage ids in square brackets like [D01.2] after each claim. "
              f"If the passages do not contain the answer, reply exactly: INSUFFICIENT. Max 4 sentences.\n\nPassages:\n{ctx}\n\nQuestion: {question}")
    txt = llm(prompt, "You are a careful industrial maintenance assistant. Never use knowledge outside the passages.") if llm else None
    if txt and "INSUFFICIENT" in txt.upper() and len(txt) < 40:
        return {"question": question, "answer": NO_EVIDENCE, "abstained": True, "method": "llm", "verified": True, "citations": []}
    if txt and verify_citations(txt, passages):
        method, out = "llm", txt
    else:
        method, out = "extractive", _extractive(passages)  # LLM absent, failed, or cited something not retrieved
    used = set(_CITE.findall(out))
    return {"question": question, "answer": out, "abstained": False, "method": method, "verified": True,
            "citations": [p for p in passages if p["cid"] in used]}
