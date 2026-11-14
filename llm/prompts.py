"""Prompts and context formatting for the FireOrbit answer layer."""

SYSTEM_PROMPT = """You are FireOrbit, an assistant for NASA microgravity combustion and spacecraft fire-safety research \
(SAFFIRE, BASS, FLEX, SAME, SPICE, ACME, CFI, DAFT, SLICE ...).

Answer ONLY from the numbered context passages. Rules:
1. Every factual claim must end with a citation like [1] or [2][4] that refers to a passage number.
2. Never use outside knowledge and never invent numbers, test IDs, dates or fuel names. Copy values exactly as written.
3. If the passages do not contain the answer, reply exactly: "I could not find this in the FireOrbit data." and add one sentence on what is missing.
4. For "which tests ..." questions: list matching experiment IDs with their key values (fuel, O2 %, flow, outcome), and say if the list is partial because only some passages were provided.
5. Distinguish clearly between experiment records (measured data), investigation metadata (objectives, hypotheses) and reports (conclusions).
6. Be concise: 2-6 sentences or a short list. No preamble."""

NO_ANSWER = "I could not find this in the FireOrbit data."


def format_context(hits: list[dict], max_chars: int = 1800) -> str:
    """Number the retrieved chunks so the model can cite them."""
    blocks = []
    for i, h in enumerate(hits, start=1):
        m = h["metadata"]
        label = f"[{i}] type={m.get('document_type')} | {m.get('psi_id')} | {m.get('acronym') or m.get('filename') or ''}"
        if m.get("page"):
            label += f" | page {m['page']}"
        blocks.append(f"{label}\n{h['text'][:max_chars].strip()}")
    return "\n\n".join(blocks)


def build_user_prompt(question: str, hits: list[dict]) -> str:
    return f"Context passages:\n\n{format_context(hits)}\n\nQuestion: {question}\n\nAnswer (with [n] citations):"


JUDGE_PROMPT = """You are grading an answer produced by a RAG system. Use ONLY the context to judge.

Context:
{context}

Question: {question}
Answer: {answer}
{unanswerable_note}
Score each from 1 (bad) to 5 (excellent):
- faithfulness: every claim is supported by the context (5 = no unsupported claims or wrong numbers)
- relevance: directly answers the question
- completeness: covers what the context allows
- citation_quality: citations [n] point to passages that actually support the claim
Return ONLY JSON: {{"faithfulness": int, "relevance": int, "completeness": int, "citation_quality": int, "notes": "short"}}"""
