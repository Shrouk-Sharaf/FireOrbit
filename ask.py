"""Ask FireOrbit a question: retrieve chunks, then answer from them with the LLM.

Run from the repository root:
    python ask.py "which test reached 85% oxygen"
    python ask.py "what was the objective of SPICE" --top-k 6 --show-chunks
    python ask.py "..." --dry-run          # retrieve and print the prompt, do NOT call the LLM
    python ask.py --verify-model           # check that the configured Gemini model is reachable
    python ask.py "..." --json

Needs GEMINI_API_KEY (and optionally GEMINI_MODEL) in the environment or in a .env file.
Use the same --model / --mode as the index was built and evaluated with."""
import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "embedding"))  

from llm import GeminiClient, LLMError, generate_answer  # noqa: E402
from llm.prompt import SYSTEM_PROMPT, build_prompt, normalize_chunk  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser(description="Ask FireOrbit a question.")
    ap.add_argument("question", nargs="?")
    ap.add_argument("--top-k", type=int, default=6)
    ap.add_argument("--mode", choices=["hybrid", "dense", "bm25"], default="hybrid")
    ap.add_argument("--model", default="BAAI/bge-small-en-v1.5", help="embedding model (same as build_index.py)")
    ap.add_argument("--show-chunks", action="store_true", help="also print the retrieved passages")
    ap.add_argument("--dry-run", action="store_true", help="print the prompt instead of calling the LLM")
    ap.add_argument("--verify-model", action="store_true", help="check the Gemini model is reachable, then exit")
    ap.add_argument("--json", action="store_true")
    a = ap.parse_args()

    try:
        if a.verify_model:
            client = GeminiClient()
            client.verify_model()
            print(f"OK: model '{client.model}' is reachable with this API key.")
            return
        if not a.question:
            ap.error("question is required (or use --verify-model)")

        from retrieval import Retriever  # imported late: loads the embedding model

        retriever = Retriever(model_name=a.model, mode=a.mode)
        hits = retriever.search(a.question, top_k=a.top_k)
        total = retriever.last_route.get("total_matches")
        summary = retriever.last_route.get("match_summary")

        if a.dry_run:
            chunks = [c for c in map(normalize_chunk, hits) if c["text"]]
            print(f"route: {retriever.last_route or 'none'}\n")
            print("=== SYSTEM ===\n" + SYSTEM_PROMPT + "\n\n=== PROMPT ===\n" + (build_prompt(a.question, chunks, total, summary)    if chunks
                  else "(no passages retrieved -> the LLM would not be called)"))
            return

        result = generate_answer(a.question, hits, total_matches=total, match_summary=summary)
    except LLMError as exc:
        sys.exit(f"LLM error: {exc}")

    if a.json:
        print(json.dumps({"route": retriever.last_route, **result}, ensure_ascii=False, indent=2))
        return
    print(f"\n{result['answer']}\n")
    if "total_matches" in result and result["total_matches"] > result["shown"]:
        print(f"(retrieval matched {result['total_matches']} records; {result['shown']} were given to the model)\n")
    if result.get("warning"):
        print(f"WARNING: {result['warning']}\n")
    for s in result["sources"]:
        page = f" p.{s['page']}" if s["page"] is not None else ""
        print(f"  {s['ids']} {s['source']}{page}    [{s['psi_id']}]  {', '.join(s['chunk_ids'])}")
    if a.show_chunks:
        print("\n--- retrieved passages ---")
        for i, h in enumerate(hits, 1):
            print(f"[{i}] {h['chunk_id']}\n    " + h["text"][:300].replace("\n", " "))


if __name__ == "__main__":
    main()
