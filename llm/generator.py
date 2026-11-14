
"""Generate grounded answers from a question and already-retrieved chunks."""
from __future__ import annotations

from typing import Any, Dict, Iterable, Optional

from .llm_client import DEFAULT_MODEL, GeminiClient
from .prompt import SYSTEM_PROMPT, build_prompt, normalize_chunk
from .response_formatter import format_response, insufficient_response

NO_CONTEXT_MESSAGE = (
    "The retrieved context is insufficient to answer this question: no relevant "
    "passages were retrieved."
)


def generate_answer(
    question: str,
    retrieved_chunks: Iterable[Any],
    client: Optional[GeminiClient] = None,
    total_matches: Optional[int] = None,
    match_summary: Optional[Dict[str, Dict[str, int]]] = None,
) -> Dict[str, Any]:
    """Return {"answer": str, "sources": list[dict], "model": str}.

    `retrieved_chunks` is the existing retrieval output (the final ranked list).
    Single-turn only: no history is kept.
    `total_matches` is how many records the retrieval filter matched in total.
    """
    if not question or not question.strip():
        raise ValueError("question must be a non-empty string")

    chunks = [c for c in map(normalize_chunk, retrieved_chunks) if c["text"]]

    if not chunks:
        result = insufficient_response(
            client.model if client is not None else DEFAULT_MODEL,
            NO_CONTEXT_MESSAGE,
        )
        if total_matches is not None:
            result["total_matches"], result["shown"] = total_matches, 0
        return result

    client = client or GeminiClient()

    raw = client.generate(
        build_prompt(question, chunks, total_matches, match_summary),
        SYSTEM_PROMPT,
    )

    result = format_response(raw, chunks, client.model)

    if total_matches is not None:
        result["total_matches"], result["shown"] = total_matches, len(chunks)

    return result
