"""Hybrid local RAG: section-level chunks, three retrievers fused into one score.

  * BM25            - exact-term matching (part names, fault names)
  * TF-IDF cosine   - weighted phrase matching (1-2 grams) via FAISS inner-product index (numpy fallback)
  * LSA cosine      - latent semantic space (TruncatedSVD) so related words match without sharing terms
Modes: "hybrid" (default), "tfidf" (baseline), "bm25". Scores are absolute (0..1), so a low top score means
'no real evidence' and callers can abstain instead of inventing support.
"""
from __future__ import annotations
import re
import numpy as np
from sklearn.decomposition import TruncatedSVD
from sklearn.feature_extraction.text import TfidfVectorizer, ENGLISH_STOP_WORDS
from utils.config import DOCS_DIR

try:
    import faiss
except Exception:  # fallback keeps app alive
    faiss = None

_TOKEN = re.compile(r"[a-z0-9]+")


_SYN = [(r"lock[\s-]?out", "lockout"), (r"tag[\s-]?out", "tagout"), (r"\bloto\b", "lockout tagout"), (r"\bloto\b", "lockout tagout"),
        (r"\bpm\b", "preventive maintenance"), (r"\baccelerometers?\b", "accelerometer sensor"), (r"\bcmms\b", "work order"),
        (r"\bbearings?\b", "bearing"), (r"\bsag(s|ging)?\b", "sag voltage")]


def _norm(text: str) -> str:
    """Lower-case + domain synonym normalisation (lock out == lockout, LOTO == lockout tagout, ...), applied to docs AND queries."""
    t = text.lower()
    for pat, rep in _SYN:
        t = re.sub(pat, rep, t)
    return t


def _tok(text: str) -> list[str]:
    return [t for t in _TOKEN.findall(_norm(text)) if t not in ENGLISH_STOP_WORDS and len(t) > 1]


class KnowledgeBase:
    W = {"tfidf": 0.45, "bm25": 0.30, "lsa": 0.25}
    MIN_RELEVANCE = 0.25   # below this the best chunk is not real evidence
    MAX_OOV = 0.5          # more than half the query words unknown to the corpus => off-topic

    def __init__(self, docs_dir=DOCS_DIR):
        self.chunks: list[dict] = []
        self.ready = False
        try:
            self._load(docs_dir)
            self._index()
            self.ready = bool(self.chunks)
        except Exception:
            self.ready = False

    # ---- build ---------------------------------------------------------------
    def _load(self, docs_dir):
        for di, f in enumerate(sorted(docs_dir.glob("*.md"))):
            text = f.read_text(encoding="utf-8")
            title = re.search(r"^# (.+)$", text, re.M)
            title = title.group(1) if title else f.stem
            for si, sec in enumerate(re.split(r"^## ", text, flags=re.M)[1:]):
                head, _, body = sec.partition("\n")
                self.chunks.append({"cid": f"D{di + 1:02d}.{si + 1}", "document": title, "file": f.name,
                                    "section": head.strip(), "text": body.strip()})

    def _index(self):
        docs = [f'{c["section"]} {c["text"]}' for c in self.chunks]
        self.vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True, preprocessor=_norm)
        M = self.vec.fit_transform(docs).toarray().astype("float32")
        M /= (np.linalg.norm(M, axis=1, keepdims=True) + 1e-9)
        self.M = M
        self.index = None
        if faiss is not None:
            self.index = faiss.IndexFlatIP(M.shape[1])
            self.index.add(M)
        # LSA
        k = int(max(2, min(64, M.shape[0] - 1, M.shape[1] - 1)))
        self.svd = TruncatedSVD(n_components=k, random_state=0).fit(M)
        L = self.svd.transform(M)
        self.L = L / (np.linalg.norm(L, axis=1, keepdims=True) + 1e-9)
        # BM25
        self.toks = [_tok(d) for d in docs]
        self.N = len(self.toks)
        self.avgdl = float(np.mean([len(t) for t in self.toks])) or 1.0
        df_ = {}
        for t in self.toks:
            for w in set(t):
                df_[w] = df_.get(w, 0) + 1
        self.idf = {w: float(np.log(1 + (self.N - n + 0.5) / (n + 0.5))) for w, n in df_.items()}

    # ---- scoring -------------------------------------------------------------
    def _bm25(self, q_tokens, k1=1.5, b=0.75) -> np.ndarray:
        s = np.zeros(self.N, dtype="float32")
        for i, toks in enumerate(self.toks):
            if not toks:
                continue
            tf = {}
            for w in toks:
                tf[w] = tf.get(w, 0) + 1
            dl = len(toks)
            for w in set(q_tokens):
                if w in tf:
                    f = tf[w]
                    s[i] += self.idf.get(w, 0) * f * (k1 + 1) / (f + k1 * (1 - b + b * dl / self.avgdl))
        return s

    def _tfidf(self, query: str) -> np.ndarray:
        q = self.vec.transform([query]).toarray().astype("float32")
        q /= (np.linalg.norm(q) + 1e-9)
        if self.index is not None:
            scores, idx = self.index.search(q, self.N)
            out = np.zeros(self.N, dtype="float32")
            out[idx[0]] = scores[0]
            return out
        return (self.M @ q.T).ravel()

    def _lsa(self, query: str) -> np.ndarray:
        q = self.vec.transform([query]).toarray().astype("float32")
        z = self.svd.transform(q)
        z /= (np.linalg.norm(z) + 1e-9)
        return (self.L @ z.T).ravel()

    def score_all(self, query: str, mode: str = "hybrid") -> np.ndarray:
        if mode == "tfidf":
            return self._tfidf(query)
        bm = self._bm25(_tok(query))
        bm = bm / (bm + 6.0)  # squash to 0..1, absolute (not query-normalised) so weak matches stay weak
        if mode == "bm25":
            return bm
        w = self.W
        return w["tfidf"] * self._tfidf(query) + w["bm25"] * bm + w["lsa"] * np.clip(self._lsa(query), 0, 1)

    def search(self, query: str, k: int = 3, min_score: float = 0.05, mode: str = "hybrid") -> list[dict]:
        """Returns [] for empty/invalid queries or when retrieval fails."""
        try:
            if not self.ready or not isinstance(query, str) or not query.strip():
                return []
            s = self.score_all(query, mode)
            order = np.argsort(-s)[:k]
            return [{**self.chunks[i], "relevance": round(float(s[i]), 3)} for i in order if s[i] >= min_score]
        except Exception:
            return []

    def oov_ratio(self, query: str) -> float:
        t = _tok(query) if isinstance(query, str) else []
        return sum(w not in self.idf for w in t) / max(len(t), 1) if t else 1.0

    def retrieve(self, query: str, k: int = 3, mode: str = "hybrid") -> list[dict]:
        """Evidence-gated search: returns [] (abstains) when the query is off-topic or only weakly matched."""
        if not isinstance(query, str) or not query.strip() or self.oov_ratio(query) > self.MAX_OOV:
            return []
        return self.search(query, k=k, min_score=self.MIN_RELEVANCE, mode=mode)
