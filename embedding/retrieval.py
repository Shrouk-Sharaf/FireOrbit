"""Retrieve relevant FireOrbit chunks from the ChromaDB index (hybrid + query routing).

Usage from the repository root:
    python indexing/retrieval.py "which test reached 85% oxygen"
    python indexing/retrieval.py "methanol experiments that ended in extinction" --top-k 8
    python indexing/retrieval.py "..." --no-route        # disable automatic filters
    python indexing/retrieval.py "..." --mode dense|bm25|hybrid --json

Query routing (rule-based) turns parts of the question into metadata filters:
    "85% oxygen", "oxygen above 60 percent"  -> o2_pct filter  (needs enrich_metadata.py + rebuilt index)
    fuel names (ethane, PMMA, ...)            -> fuel filter    (only together with "tests/experiments/...")
    "self-extinguished", "failed to ignite"   -> outcome filter
    "objective/purpose/goal"                  -> document_type=investigation_metadata
    the word "report"                         -> document_type=report
    "PSI-98"                                  -> psi_id filter
Explicit --doc-type / --psi-id always win. Use the SAME --model that build_index.py used."""

import argparse
import json
import re
from pathlib import Path
from typing import Any

import chromadb

from build_index import COLLECTION, DEFAULT_DB_DIR, prefixes

RRF_K = 60
CANDIDATE_MULT = 4

CMP_WORDS = {
    "$gt": ["above", "over", "more than", "greater than", "exceeding", "higher than", "higher", "greater"],
    "$gte": ["at least", "no less than", "not less than"],
    "$lt": ["below", "under", "less than", "lower than", "lower", "fewer than"],
    "$lte": ["at most", "up to", "no more than", "not more than"],
}
_CMP_LOOKUP = {w: op for op, ws in CMP_WORDS.items() for w in ws}
_CMP = "|".join(sorted(_CMP_LOOKUP, key=len, reverse=True))
_NUM = r"\d+(?:\.\d+)?"
O2_A = re.compile(rf"(?:(?P<cmp>{_CMP})\s+)?(?P<num>{_NUM})\s*(?:%|percent|pct)\s*(?:of\s+)?(?:o2|oxygen)\b", re.I)
O2_B = re.compile(rf"\b(?:o2|oxygen)(?:\s+(?:concentration|level|content|fraction))?\s*(?:(?P<cmp>{_CMP})\s+)?"
                  rf"(?:of\s+|at\s+|=\s*|:\s*)?(?P<num>{_NUM})\s*(?:%|percent|pct)?", re.I)
OUTCOMES = [
    ("self_extinction", re.compile(r"self[- ]?extinguish|self[- ]?extinction", re.I)),
    ("no_ignition", re.compile(r"fail(?:ed|s)? to ignite|did(?:n't| not) ignite|not ignite|no[- ]ignition", re.I)),
    ("sustained_burn", re.compile(r"sustained[- ]burn", re.I)),
    ("extinction", re.compile(r"extinguish|extinction", re.I)),
    ("disruption", re.compile(r"disrupt", re.I)),
]
RECORD_WORDS = re.compile(r"\b(tests?|experiments|runs|records?|trials)\b", re.I)
OBJECTIVE_WORDS = re.compile(r"\b(objectives?|purpose|goals?|aims?)\b", re.I)
REPORT_WORD = re.compile(r"\breports?\b", re.I)
PSI_RE = re.compile(r"\bPSI-\d+\b", re.I)


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def route_query(query: str, fuels: list[str]) -> dict[str, Any]:
    """Return {"clauses": [...chroma where clauses...], "notes": {...}}."""
    q = query.lower()
    notes: dict[str, Any] = {}
    o2 = None
    for pat in (O2_A, O2_B):
        m = pat.search(query)
        if m:
            op = _CMP_LOOKUP.get((m.group("cmp") or "").lower())
            val = float(m.group("num")); o2 = {"$eq": val} if op is None else {op: val}
            break
    fuel_hits = [f for f in fuels if re.search(rf"(?<![a-z0-9]){re.escape(f)}(?![a-z0-9])", q)]
    outcome = next((name for name, pat in OUTCOMES if pat.search(query)), None)
    has_record_words = bool(RECORD_WORDS.search(query))

    doc_type = None
    if OBJECTIVE_WORDS.search(query):
        doc_type = "investigation_metadata"
    elif REPORT_WORD.search(query):
        doc_type = "report"
    elif o2 is not None or ((fuel_hits or outcome) and has_record_words):
        doc_type = "experiment_record"

    clauses: list[dict] = []
    if doc_type:
        clauses.append({"document_type": doc_type}); notes["document_type"] = doc_type
    if doc_type == "experiment_record":
        if o2 is not None:
            clauses.append({"o2_pct": o2}); notes["o2_pct"] = o2
        if fuel_hits:
            clauses.append({"fuel": fuel_hits[0] if len(fuel_hits) == 1 else {"$in": fuel_hits}}); notes["fuel"] = fuel_hits
        if outcome:
            clauses.append({"outcome": outcome}); notes["outcome"] = outcome
    psi = PSI_RE.search(query)
    if psi:
        clauses.append({"psi_id": psi.group(0).upper()}); notes["psi_id"] = psi.group(0).upper()
    return {"clauses": clauses, "notes": notes}


def build_where(clauses: list[dict]) -> dict | None:
    if not clauses:
        return None
    return clauses[0] if len(clauses) == 1 else {"$and": clauses}


def matches(meta: dict, where: dict | None) -> bool:
    """Evaluate a Chroma-style where dict in Python (used by the BM25 side)."""
    if not where:
        return True
    if "$and" in where:
        return all(matches(meta, w) for w in where["$and"])
    for key, cond in where.items():
        val = meta.get(key)
        if isinstance(cond, dict):
            for op, ref in cond.items():
                if val is None:
                    return False
                if op == "$eq" and not val == ref: return False
                if op == "$ne" and not val != ref: return False
                if op == "$gt" and not val > ref: return False
                if op == "$gte" and not val >= ref: return False
                if op == "$lt" and not val < ref: return False
                if op == "$lte" and not val <= ref: return False
                if op == "$in" and val not in ref: return False
        elif val != cond:
            return False
    return True


class Retriever:
    def __init__(self, db_dir: Path = DEFAULT_DB_DIR,
                 model_name: str = "BAAI/bge-small-en-v1.5", mode: str = "hybrid"):
        if mode not in {"hybrid", "dense", "bm25"}:
            raise ValueError("mode must be hybrid, dense or bm25")
        self.mode = mode
        self.collection = chromadb.PersistentClient(path=str(db_dir)).get_collection(COLLECTION)
        self.model = None
        if mode != "bm25":
            from sentence_transformers import SentenceTransformer
            self.model = SentenceTransformer(model_name)
        self.query_prefix = prefixes(model_name)[1]

        data = self.collection.get(include=["documents", "metadatas"])
        self.ids, self.docs, self.metas = data["ids"], data["documents"], data["metadatas"]
        self.fuels = sorted({m["fuel"] for m in self.metas if m.get("fuel") and re.fullmatch(r"[a-z][a-z \-]+", m["fuel"])},
                            key=len, reverse=True)
        self.has_numeric_meta = any("o2_pct" in m for m in self.metas)
        self.bm25 = None
        if mode != "dense":
            from rank_bm25 import BM25Okapi
            self.bm25 = BM25Okapi([tokenize(d) for d in self.docs])
        self.last_route: dict[str, Any] = {}

    def _dense(self, query: str, n: int, where: dict | None) -> list[dict[str, Any]]:
        embedding = self.model.encode([self.query_prefix + query], normalize_embeddings=True)
        res = self.collection.query(query_embeddings=embedding.tolist(), n_results=n, where=where)
        return [{"chunk_id": i, "text": d, "metadata": m, "dense_score": 1 - dist}
                for i, d, m, dist in zip(res["ids"][0], res["documents"][0], res["metadatas"][0], res["distances"][0])]

    def _keyword(self, query: str, n: int, where: dict | None) -> list[dict[str, Any]]:
        scores = self.bm25.get_scores(tokenize(query))
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        out = []
        for i in order:
            if scores[i] <= 0:
                break
            if not matches(self.metas[i], where):
                continue
            out.append({"chunk_id": self.ids[i], "text": self.docs[i], "metadata": self.metas[i],
                        "bm25_score": float(scores[i])})
            if len(out) == n:
                break
        return out

    def search(self, query: str, top_k: int = 5, doc_type: str | None = None,
               psi_id: str | None = None, route: bool = True) -> list[dict[str, Any]]:
        clauses: list[dict] = []
        self.last_route = {}
        if route:
            r = route_query(query, self.fuels)
            clauses = [c for c in r["clauses"]
                       if not (doc_type and "document_type" in c) and not (psi_id and "psi_id" in c)]
            if not self.has_numeric_meta:  # index built before enrich_metadata.py: skip structured filters
                clauses = [c for c in clauses if not set(c) & {"o2_pct", "fuel", "outcome"}]
            self.last_route = {k: v for k, v in r["notes"].items()}
        if doc_type:
            clauses.append({"document_type": doc_type})
        if psi_id:
            clauses.append({"psi_id": psi_id})
        where = build_where(clauses)
        n = top_k * CANDIDATE_MULT

        if self.mode == "dense":
            return self._dense(query, top_k, where)
        if self.mode == "bm25":
            return self._keyword(query, top_k, where)

        merged: dict[str, dict[str, Any]] = {}
        for ranked in (self._dense(query, n, where), self._keyword(query, n, where)):
            for rank, hit in enumerate(ranked, start=1):
                entry = merged.setdefault(hit["chunk_id"], {**hit, "rrf_score": 0.0})
                entry.update({k: v for k, v in hit.items() if k.endswith("_score")})
                entry["rrf_score"] += 1.0 / (RRF_K + rank)
        return sorted(merged.values(), key=lambda h: h["rrf_score"], reverse=True)[:top_k]


def main() -> None:
    parser = argparse.ArgumentParser(description="Search the FireOrbit index.")
    parser.add_argument("query")
    parser.add_argument("--db-dir", type=Path, default=DEFAULT_DB_DIR)
    parser.add_argument("--model", default="BAAI/bge-small-en-v1.5")
    parser.add_argument("--mode", choices=["hybrid", "dense", "bm25"], default="hybrid")
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument("--doc-type", choices=["report", "experiment_record", "investigation_metadata"])
    parser.add_argument("--psi-id", help="Only search one investigation, e.g. PSI-98.")
    parser.add_argument("--no-route", action="store_true", help="Disable automatic query-to-filter routing.")
    parser.add_argument("--json", action="store_true", help="Print results as JSON.")
    args = parser.parse_args()

    retriever = Retriever(args.db_dir, args.model, args.mode)
    hits = retriever.search(args.query, args.top_k, args.doc_type, args.psi_id, route=not args.no_route)

    if args.json:
        print(json.dumps({"route": retriever.last_route, "hits": hits}, ensure_ascii=False, indent=2))
        return
    print(f"route: {retriever.last_route or 'none'}")
    if not hits:
        print("No results.")
    for rank, hit in enumerate(hits, start=1):
        meta = hit["metadata"]
        scores = "  ".join(f"{k}={v:.3f}" for k, v in hit.items() if k.endswith("_score"))
        print(f"\n#{rank}  {scores}\n    {hit['chunk_id']}")
        print(f"    type={meta.get('document_type')}  psi_id={meta.get('psi_id')}  page={meta.get('page')}")
        print("    " + hit["text"][:300].replace("\n", " "))


if __name__ == "__main__":
    main()
