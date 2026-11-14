"""Format the model output into {answer, sources, model}.

Sources are built from the chunks that were actually retrieved, never from model text,
so a source can't be invented.
"""
from __future__ import annotations

import re
from typing import Any, Dict, List

from .prompt import INSUFFICIENT_TAG

# Matches [1], [1][2], [1, 2] and [1-3] (ranges and lists inside one bracket).
_CITATION = re.compile(r"\[(\d+(?:\s*[,\-\u2013]\s*\d+)*)\]")

NO_CITATION_WARNING = (
    "The model did not cite any passage, so no sources are listed. "
    "Treat this answer as unverified and check it against the retrieved passages."
)


def _cited_indices(answer: str, n_chunks: int) -> List[int]:
    seen: List[int] = []
    for match in _CITATION.finditer(answer):
        for part in re.split(r"\s*,\s*", match.group(1)):
            bounds = [int(x) for x in re.split(r"\s*[-\u2013]\s*", part)]
            nums = range(bounds[0], bounds[-1] + 1) if len(bounds) == 2 else bounds[:1]
            for idx in nums:
                if 1 <= idx <= n_chunks and idx not in seen:
                    seen.append(idx)
    return seen


def build_sources(indices: List[int], chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """One entry per distinct (source, page).

    `ids` lists every [n] citation that maps to it; `chunk_ids` lists every retrieved chunk behind
    it (several chunks of one document can share a source and page, e.g. investigation metadata).
    `chunk_id` (the first one) is kept for backward compatibility.
    """
    by_key: Dict[Any, Dict[str, Any]] = {}
    for idx in indices:
        c = chunks[idx - 1]
        key = (c["source"], c["page"])
        if key in by_key:
            by_key[key]["ids"].append(idx)
            if c["chunk_id"] not in by_key[key]["chunk_ids"]:
                by_key[key]["chunk_ids"].append(c["chunk_id"])
            continue
        by_key[key] = {
            "ids": [idx],
            "source": c["source"],
            "page": c["page"],
            "psi_id": c["psi_id"],
            "document_type": c["document_type"],
            "chunk_id": c["chunk_id"],
            "chunk_ids": [c["chunk_id"]],
        }
    return list(by_key.values())

def format_response(raw_answer: str, chunks: List[Dict[str, Any]], model: str) -> Dict[str, Any]:
    answer = raw_answer.strip()

    if answer.startswith(INSUFFICIENT_TAG):
        answer = answer[len(INSUFFICIENT_TAG):].strip() or (
            "The retrieved context is insufficient to answer this question."
        )
        return {"answer": answer, "sources": [], "model": model}

    cited = _cited_indices(answer, len(chunks))
    if not cited:
        # Do not claim sources the model did not actually use: flag the answer instead.
        return {"answer": answer, "sources": [], "model": model, "warning": NO_CITATION_WARNING}
    return {"answer": answer, "sources": build_sources(cited, chunks), "model": model}


def insufficient_response(model: str, reason: str) -> Dict[str, Any]:
    return {"answer": reason, "sources": [], "model": model}
