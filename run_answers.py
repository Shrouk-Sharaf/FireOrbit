"""End-to-end check: run eval questions through retrieval + LLM and write answers for manual review.

  python run_answers.py                       # all questions (one LLM call per answerable question)
  python run_answers.py --only q01,q17,q38    # just these
  python run_answers.py --dry-run             # no LLM calls: only checks that retrieval feeds the prompt

Writes embedding/answers.md (read it!) and embedding/answers.json. Automatic checks are rough:
  answerable   -> did the answer cite at least one chunk from relevant_chunk_ids?
  unanswerable -> did the system refuse (no sources)?"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "embedding"))

from llm import GeminiClient, LLMError, generate_answer  # noqa: E402
from llm.prompt import normalize_chunk  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval", default=str(ROOT / "embedding" / "eval_set.json"))
    ap.add_argument("--only", help="comma-separated question ids")
    ap.add_argument("--top-k", type=int, default=6)
    ap.add_argument("--mode", choices=["hybrid", "dense", "bm25"], default="hybrid")
    ap.add_argument("--model", default="BAAI/bge-small-en-v1.5")
    ap.add_argument("--sleep", type=float, default=1.0, help="seconds between LLM calls (rate limits)")
    ap.add_argument("--dry-run", action="store_true")
    a = ap.parse_args()

    from retrieval import Retriever

    qs = json.load(open(a.eval, encoding="utf-8"))["questions"]
    if a.only:
        wanted = set(a.only.split(",")); qs = [q for q in qs if q["id"] in wanted]
    retriever = Retriever(model_name=a.model, mode=a.mode)
    client = None if a.dry_run else GeminiClient()
    rows, md = [], ["# FireOrbit answers (review manually)\n"]
    stats = {"ans_n": 0, "ans_cited_relevant": 0, "ans_no_cite": 0, "una_n": 0, "una_refused": 0, "errors": 0}

    for q in qs:
        hits = retriever.search(q["question"], top_k=a.top_k)
        total = retriever.last_route.get("total_matches")
        if a.dry_run:
            res = {"answer": f"(dry run) {len(hits)} passages retrieved", "sources": [], "model": "-"}
        else:
            try:
                res = generate_answer(q["question"], hits, client=client, total_matches=total)
            except LLMError as exc:
                stats["errors"] += 1
                res = {"answer": f"LLM ERROR: {exc}", "sources": [], "model": "-"}
            time.sleep(a.sleep)
        chunks = [c for c in map(normalize_chunk, hits) if c["text"]]
        cited = [hits[i - 1]["chunk_id"] for s in res["sources"] for i in s["ids"] if i - 1 < len(hits)]
        if q["answerable"]:
            stats["ans_n"] += 1
            ok = bool(set(cited) & set(q["relevant_chunk_ids"]))
            stats["ans_cited_relevant"] += ok
            stats["ans_no_cite"] += bool(res.get("warning"))
        else:
            stats["una_n"] += 1
            ok = not res["sources"]
            stats["una_refused"] += ok
        rows.append({"id": q["id"], "question": q["question"], "answerable": q["answerable"], "auto_ok": ok,
                     "total_matches": total, "retrieved": [h["chunk_id"] for h in hits], "result": res})
        flag = "OK" if ok else "CHECK"
        md += [f"## {q['id']} [{flag}] {q['question']}", f"*answerable={q['answerable']}, retrieved={len(chunks)}, "
               f"total_matches={total}*\n", res["answer"], ""]
        for s in res["sources"]:
            md.append(f"- {s['ids']} {s['source']} (page {s['page']}) - `{s['chunk_id']}`")
        if res.get("warning"):
            md.append(f"- WARNING: {res['warning']}")
        md.append("")
        print(f"{q['id']} {flag}")

    (ROOT / "embedding" / "answers.md").write_text("\n".join(md), encoding="utf-8")
    json.dump(rows, open(ROOT / "embedding" / "answers.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    if a.dry_run:
        print("\ndry run: no LLM was called, so the statistics are not meaningful. Retrieval and prompts work.")
        return
    print(f"\nanswerable: cited a relevant chunk {stats['ans_cited_relevant']}/{stats['ans_n']} "
          f"(answers with no citation: {stats['ans_no_cite']})")
    print(f"unanswerable: refused {stats['una_refused']}/{stats['una_n']}   LLM errors: {stats['errors']}")
    print("Now read embedding/answers.md: the automatic checks cannot tell whether an answer is actually correct.")


if __name__ == "__main__":
    main()
