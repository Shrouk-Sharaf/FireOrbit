"""Compare Gemini models on the FireOrbit eval questions and write a report.

    python llm/compare_models.py --models gemini-3-flash-preview gemini-2.5-flash \
        --judge-model gemini-2.5-pro --limit 41 --out llm/results

Retrieval runs ONCE per question and is shared, so differences come only from the LLM.
Outputs: results.json, results.csv, report.md
"""
import argparse
import csv
import json
import re
import statistics as st
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "llm"))
sys.path.insert(0, str(ROOT / "embedding"))

from gemini_client import GeminiClient  # noqa: E402
from prompts import SYSTEM_PROMPT, NO_ANSWER, JUDGE_PROMPT, build_user_prompt, format_context  # noqa: E402
from rag_answer import cited_numbers  # noqa: E402

NUM = re.compile(r"\d+(?:\.\d+)?")


def refused(answer: str) -> bool:
    return "could not find" in answer.lower()


def unsupported_numbers(answer: str, context: str) -> list[str]:
    """Numbers in the answer (outside [n] citations) that never appear in the context."""
    body = re.sub(r"\[\d+\]", "", answer)
    ctx = set(NUM.findall(context))
    return sorted({n for n in NUM.findall(body) if n not in ctx and float(n) not in {float(c) for c in ctx}})


def judge(judge_llm, question, answer, context, answerable):
    note = "" if answerable else "NOTE: this question is unanswerable from the data; a correct answer declines.\n"
    p = JUDGE_PROMPT.format(context=context, question=question, answer=answer, unanswerable_note=note)
    try:
        return json.loads(judge_llm.generate(p, json_output=True).text)
    except Exception as e:
        return {"error": str(e)}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--judge-model", help="Model used as grader (use a different/stronger one than the candidates).")
    ap.add_argument("--eval", type=Path, default=ROOT / "embedding" / "eval_set.json")
    ap.add_argument("--top-k", type=int, default=6)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--out", type=Path, default=ROOT / "llm" / "results")
    a = ap.parse_args()
    a.out.mkdir(parents=True, exist_ok=True)

    from retrieval import Retriever
    retr = Retriever()
    llms = {m: GeminiClient(m) for m in a.models}
    judge_llm = GeminiClient(a.judge_model, temperature=0) if a.judge_model else None
    qs = json.load(open(a.eval, encoding="utf-8"))["questions"][: a.limit]

    rows = []
    for q in qs:
        hits = retr.search(q["question"], top_k=a.top_k)
        ctx = format_context(hits) if hits else ""
        for m, llm in llms.items():
            if hits:
                r = llm.generate(build_user_prompt(q["question"], hits), system=SYSTEM_PROMPT)
                ans, lat, pt, ot = r.text.strip(), r.latency_s, r.prompt_tokens, r.output_tokens
            else:
                ans, lat, pt, ot = NO_ANSWER, 0.0, 0, 0
            cites = cited_numbers(ans)
            row = {"id": q["id"], "category": q["category"], "answerable": q["answerable"], "model": m,
                   "question": q["question"], "answer": ans, "retrieved": len(hits),
                   "latency_s": round(lat, 2), "prompt_tokens": pt, "output_tokens": ot,
                   "refused": refused(ans),
                   "correct_refusal": refused(ans) == (not q["answerable"]),
                   "has_citation": bool(cites),
                   "invalid_citations": len([c for c in cites if not 1 <= c <= len(hits)]),
                   "unsupported_numbers": unsupported_numbers(ans, ctx) if hits else []}
            if judge_llm and hits:
                row["judge"] = judge(judge_llm, q["question"], ans, ctx, q["answerable"])
            rows.append(row)
            print(f"{q['id']} {m}: {'REFUSED' if row['refused'] else 'answered'} {row['latency_s']}s")

    json.dump(rows, open(a.out / "results.json", "w", encoding="utf-8"), indent=2, ensure_ascii=False)
    flat = [{**r, "unsupported_numbers": ";".join(r["unsupported_numbers"]),
             **{f"judge_{k}": v for k, v in r.get("judge", {}).items()}} for r in rows]
    for r in flat:
        r.pop("judge", None)
    keys = sorted({k for r in flat for k in r}, key=lambda k: list(flat[0]).index(k) if k in flat[0] else 99)
    with open(a.out / "results.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=keys); w.writeheader(); w.writerows(flat)

    lines = ["# Gemini model comparison\n", f"Questions: {len(qs)}  |  top_k={a.top_k}  |  judge={a.judge_model or 'none'}\n",
             "| model | correct refusal | answered w/ citation | invalid cites | answers w/ unsupported numbers | median latency (s) | avg out tokens |"
             + (" faithfulness | relevance | completeness | citation_q |" if judge_llm else ""),
             "|---|---|---|---|---|---|---|" + ("---|---|---|---|" if judge_llm else "")]
    for m in a.models:
        R = [r for r in rows if r["model"] == m]
        ans = [r for r in R if r["answerable"] and r["retrieved"]]
        j = [r["judge"] for r in R if r.get("judge") and "error" not in r["judge"]]
        avg = lambda k: f"{st.mean(x[k] for x in j):.2f}" if j else "-"
        line = (f"| {m} | {sum(r['correct_refusal'] for r in R)}/{len(R)} | "
                f"{sum(r['has_citation'] for r in ans)}/{len(ans)} | {sum(r['invalid_citations'] for r in R)} | "
                f"{sum(bool(r['unsupported_numbers']) for r in R)} | "
                f"{st.median([r['latency_s'] for r in R if r['retrieved']] or [0]):.2f} | "
                f"{st.mean([r['output_tokens'] or 0 for r in R]):.0f} |")
        if judge_llm:
            line += f" {avg('faithfulness')} | {avg('relevance')} | {avg('completeness')} | {avg('citation_quality')} |"
        lines.append(line)
    lines += ["\nLower is better for: invalid cites, unsupported numbers, latency.",
              "Higher is better for: correct refusal, citation coverage, judge scores (1-5).",
              "\nRead `results.csv` side by side for the questions where models disagree before choosing."]
    (a.out / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
