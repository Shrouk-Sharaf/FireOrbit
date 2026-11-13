"""Retrieve relevant FireOrbit chunks from the ChromaDB index.

Setup (same as the index, plus BM25 for hybrid search):
    pip install chromadb sentence-transformers rank-bm25

Usage from the repository root:
    python indexing/retrieval.py "flame spread at low oxygen"
    python indexing/retrieval.py "burn time of SIBAL fabric" --doc-type experiment_record
    python indexing/retrieval.py "SAFFIRE-I results" --psi-id PSI-98 --top-k 8
    python indexing/retrieval.py "PSI-98-S1-R1 outcome" --mode dense     # dense only
    python indexing/retrieval.py "..." --json                           # machine-readable

Modes:
    hybrid (default)  dense embeddings + BM25 keyword search, merged with
                      reciprocal rank fusion. Good for this data because experiment
                      records and reports contain exact IDs and material names
                      (PSI-98, SIBAL, SAFFIRE-I) that keyword search matches better.
    dense             embeddings only.
    bm25              keywords only.

Use the SAME --model that build_index.py used.
"""

import argparse
import json
import re
from pathlib import Path
from typing import Any

import chromadb
from sentence_transformers import SentenceTransformer

from build_index import COLLECTION, DEFAULT_DB_DIR, prefixes

RRF_K = 60          # standard reciprocal-rank-fusion constant
CANDIDATE_MULT = 4  # fetch this many x top_k from each retriever before fusing


def tokenize(text: str) -> list[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


class Retriever:
    def __init__(self, db_dir: Path = DEFAULT_DB_DIR,
                 model_name: str = "BAAI/bge-small-en-v1.5", mode: str = "hybrid"):
        if mode not in {"hybrid", "dense", "bm25"}:
            raise ValueError("mode must be hybrid, dense or bm25")
        self.mode = mode
        self.collection = chromadb.PersistentClient(path=str(db_dir)).get_collection(COLLECTION)
        self.model = SentenceTransformer(model_name) if mode != "bm25" else None
        self.query_prefix = prefixes(model_name)[1]

        # Keyword index is built in memory from the same collection, so ids always match.
        self.bm25 = None
        if mode != "dense":
            from rank_bm25 import BM25Okapi

            data = self.collection.get(include=["documents", "metadatas"])
            self.ids = data["ids"]
            self.docs = data["documents"]
            self.metas = data["metadatas"]
            self.bm25 = BM25Okapi([tokenize(d) for d in self.docs])

    @staticmethod
    def _where(doc_type: str | None, psi_id: str | None) -> dict | None:
        clauses = []
        if doc_type:
            clauses.append({"document_type": doc_type})
        if psi_id:
            clauses.append({"psi_id": psi_id})
        if not clauses:
            return None
        return clauses[0] if len(clauses) == 1 else {"$and": clauses}

    def _dense(self, query: str, n: int, where: dict | None) -> list[dict[str, Any]]:
        embedding = self.model.encode([self.query_prefix + query], normalize_embeddings=True)
        res = self.collection.query(query_embeddings=embedding.tolist(), n_results=n, where=where)
        return [
            {"chunk_id": i, "text": d, "metadata": m, "dense_score": 1 - dist}
            for i, d, m, dist in zip(res["ids"][0], res["documents"][0],
                                     res["metadatas"][0], res["distances"][0])
        ]

    def _keyword(self, query: str, n: int, doc_type: str | None,
                 psi_id: str | None) -> list[dict[str, Any]]:
        scores = self.bm25.get_scores(tokenize(query))
        order = sorted(range(len(scores)), key=lambda i: scores[i], reverse=True)
        out = []
        for i in order:
            if scores[i] <= 0:
                break
            meta = self.metas[i]
            if doc_type and meta.get("document_type") != doc_type:
                continue
            if psi_id and meta.get("psi_id") != psi_id:
                continue
            out.append({"chunk_id": self.ids[i], "text": self.docs[i],
                        "metadata": meta, "bm25_score": float(scores[i])})
            if len(out) == n:
                break
        return out

    def search(self, query: str, top_k: int = 5, doc_type: str | None = None,
               psi_id: str | None = None) -> list[dict[str, Any]]:
        n = top_k * CANDIDATE_MULT
        where = self._where(doc_type, psi_id)

        if self.mode == "dense":
            return self._dense(query, top_k, where)
        if self.mode == "bm25":
            return self._keyword(query, top_k, doc_type, psi_id)

        # Hybrid: reciprocal rank fusion of the two ranked lists.
        merged: dict[str, dict[str, Any]] = {}
        for ranked in (self._dense(query, n, where), self._keyword(query, n, doc_type, psi_id)):
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
    parser.add_argument("--json", action="store_true", help="Print results as JSON.")
    args = parser.parse_args()

    retriever = Retriever(args.db_dir, args.model, args.mode)
    hits = retriever.search(args.query, args.top_k, args.doc_type, args.psi_id)

    if args.json:
        print(json.dumps(hits, ensure_ascii=False, indent=2))
        return
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
