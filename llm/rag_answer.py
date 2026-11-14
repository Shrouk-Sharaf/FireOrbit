"""retrieve -> prompt -> Gemini -> cited answer.

    python llm/rag_answer.py "which test reached 85% oxygen" --model gemini-3-flash-preview
"""
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "llm"))
sys.path.insert(0, str(ROOT / "embedding"))  # retrieval.py does `from build_index import ...`

from gemini_client import GeminiClient, DEFAULT_MODEL  # noqa: E402
from prompts import SYSTEM_PROMPT, NO_ANSWER, build_user_prompt  # noqa: E402


def cited_numbers(answer: str) -> list[int]:
    return sorted({int(n) for n in re.findall(r"\[(\d+)\]", answer)})


class FireOrbitRAG:
    def __init__(self, retriever, llm: GeminiClient, top_k: int = 6):
        self.retriever, self.llm, self.top_k = retriever, llm, top_k

    def ask(self, question: str) -> dict:
        hits = self.retriever.search(question, top_k=self.top_k)
        route = getattr(self.retriever, "last_route", {})
        if not hits:  # retriever's no-answer gate fired: do not spend an LLM call
            return {"question": question, "answer": NO_ANSWER, "sources": [], "route": route,
                    "model": self.llm.model, "latency_s": 0.0, "skipped_llm": True}
        res = self.llm.generate(build_user_prompt(question, hits), system=SYSTEM_PROMPT)
        cites = cited_numbers(res.text)
        return {
            "question": question, "answer": res.text.strip(), "route": route, "model": res.model,
            "latency_s": round(res.latency_s, 2), "prompt_tokens": res.prompt_tokens,
            "output_tokens": res.output_tokens, "skipped_llm": False,
            "invalid_citations": [c for c in cites if not 1 <= c <= len(hits)],
            "sources": [{"n": i, "chunk_id": h["chunk_id"], "psi_id": h["metadata"].get("psi_id"),
                         "document_type": h["metadata"].get("document_type"), "page": h["metadata"].get("page"),
                         "cited": i in cites} for i, h in enumerate(hits, start=1)],
            "_hits": hits,
        }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("question")
    ap.add_argument("--model", default=DEFAULT_MODEL)
    ap.add_argument("--top-k", type=int, default=6)
    ap.add_argument("--db-dir", type=Path)
    a = ap.parse_args()
    from retrieval import Retriever
    retr = Retriever(a.db_dir) if a.db_dir else Retriever()
    out = FireOrbitRAG(retr, GeminiClient(a.model), a.top_k).ask(a.question)
    out.pop("_hits", None)
    print(out["answer"], "\n")
    for s in out["sources"]:
        print(f"  [{s['n']}]{'*' if s['cited'] else ' '} {s['chunk_id']}")
    print(f"\n{out['model']} | {out['latency_s']}s | route={out['route']}")


if __name__ == "__main__":
    main()
