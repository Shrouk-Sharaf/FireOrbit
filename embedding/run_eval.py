"""Usage (from repo root):
  python eval/run_eval.py --search-fn my_search:search --k 5 --threshold 0.1
`search(question, k)` must return a ranked list of dicts: {"chunk_id": str, "score": float}.
For hybrid/rerank pipelines, return the final reranker score as "score" (used for the unanswerable test)."""
import argparse, importlib, json, sys, collections

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--eval", default="eval_set.json"); ap.add_argument("--search-fn", required=True)
    ap.add_argument("--k", type=int, default=5); ap.add_argument("--threshold", type=float, default=0.1)
    ap.add_argument("--verbose", action="store_true"); ap.add_argument("--out", default="last_run.json")
    a = ap.parse_args()
    sys.path.insert(0, "."); sys.path.insert(0, "embedding")
    mod, fn = a.search_fn.split(":"); search = getattr(importlib.import_module(mod), fn)
    ev = json.load(open(a.eval, encoding="utf-8"))
    cat = collections.defaultdict(lambda: {"n": 0, "hit": 0, "rr": 0.0, "prec": 0.0, "rej": 0})
    rows = []
    for q in ev["questions"]:
        res = search(q["question"], a.k)[: a.k]; ids = [r["chunk_id"] for r in res]
        c = cat[q["category"]]; c["n"] += 1
        if not q["answerable"]:
            ok = not res or res[0]["score"] < a.threshold; c["rej"] += ok
            rows.append({"id": q["id"], "ok": ok, "top_score": res[0]["score"] if res else None}); continue
        rel = set(q["relevant_chunk_ids"]); rank = next((i + 1 for i, x in enumerate(ids) if x in rel), None)
        c["hit"] += rank is not None; c["rr"] += 1 / rank if rank else 0; c["prec"] += sum(x in rel for x in ids) / a.k
        rows.append({"id": q["id"], "ok": rank is not None, "rank": rank, "top": ids[:3]})
        if a.verbose and rank is None: print("MISS", q["id"], q["question"], "->", ids[:3])
    tot = {"n": 0, "hit": 0, "rr": 0.0, "prec": 0.0}
    print(f"{'category':14}{'n':>4}{'Hit@k':>8}{'MRR':>8}{'P@k':>8}")
    for k, c in cat.items():
        if k == "unanswerable": print(f"{k:14}{c['n']:>4}  rejected correctly: {c['rej']}/{c['n']}"); continue
        print(f"{k:14}{c['n']:>4}{c['hit']/c['n']:>8.2f}{c['rr']/c['n']:>8.2f}{c['prec']/c['n']:>8.2f}")
        for t in tot: tot[t] += c[t]
    print(f"{'ALL answerable':14}{tot['n']:>4}{tot['hit']/tot['n']:>8.2f}{tot['rr']/tot['n']:>8.2f}{tot['prec']/tot['n']:>8.2f}")
    json.dump(rows, open(a.out, "w"), indent=1)

if __name__ == "__main__": main()
