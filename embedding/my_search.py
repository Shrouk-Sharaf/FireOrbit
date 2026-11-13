"""Adapter between eval/run_eval.py and indexing/retrieval.py.

Run from the repository root:
    python eval/run_eval.py --search-fn my_search:search --k 5 --threshold 0.5 --verbose

Env vars (optional): EVAL_MODE=hybrid|dense|bm25   EVAL_MODEL=<same model as build_index.py>
                     EVAL_ROUTE=1|0  (query routing on/off, default on)
"""
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "indexing"))  # retrieval.py does `from build_index import ...`

from retrieval import Retriever  # noqa: E402

_retriever = Retriever(
    model_name=os.environ.get("EVAL_MODEL", "BAAI/bge-small-en-v1.5"),
    mode=os.environ.get("EVAL_MODE", "hybrid"),
)


def search(question, k):
    hits = _retriever.search(question, top_k=k, route=os.environ.get("EVAL_ROUTE", "1") == "1")
    out = []
    for h in hits:
        # Ranking stays as the retriever returns it. The "score" is only used to decide
        # whether an unanswerable question was correctly rejected, so it must be an
        # absolute relevance signal. RRF scores (~0.03 max) are rank-based, not absolute,
        # so use the dense cosine similarity when available, then BM25 as a fallback.
        score = h.get("dense_score")
        if score is None:
            score = h.get("bm25_score", 0.0)
        out.append({"chunk_id": h["chunk_id"], "score": float(score)})
    return out
