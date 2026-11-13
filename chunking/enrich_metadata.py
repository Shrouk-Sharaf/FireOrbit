"""Add structured fields (o2_pct, fuel, outcome, flow_cm_s, burn_time_s) to the metadata of
experiment_record chunks, parsed from the record text. Run before build_index.py.

  python enrich_metadata.py     (put this file next to chunks.json; or pass --chunks <path>)
Writes the result back to the same file (the original is saved as chunks.json.orig on first run).
Values that are missing/None are NOT added (ChromaDB rejects None)."""
import argparse, json, shutil
from pathlib import Path

def parse(text):
    d = {}
    for line in text.split("\n"):
        if ": " in line:
            k, v = line.split(": ", 1); d[k.strip()] = v.strip()
    return d

def num(x):
    try: return float(x)
    except (TypeError, ValueError): return None

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--chunks"); ap.add_argument("--out")
    a = ap.parse_args(); p = Path(a.chunks) if a.chunks else Path(__file__).resolve().parent / "chunks.json"; out = Path(a.out) if a.out else p
    print("using", p)
    orig = p.with_suffix(p.suffix + ".orig")
    if out == p and not orig.exists(): shutil.copy(p, orig)
    chunks = json.load(open(orig if out == p and orig.exists() else p, encoding="utf-8"))  # always start from the original
    n = 0; stats = {}
    for c in chunks:
        m = c["metadata"]
        if m.get("document_type") != "experiment_record": continue
        d = parse(c["text"]); extra = {}
        if num(d.get("O2 Concentration Pct")) is not None: extra["o2_pct"] = num(d["O2 Concentration Pct"])
        fuel = (d.get("Fuel Material Normalized") or "").strip().lower()
        if fuel and fuel != "none": extra["fuel"] = fuel
        oc = d.get("Outcome Category")
        if oc and oc != "None": extra["outcome"] = oc
        if num(d.get("Flow Velocity Cm S")) is not None: extra["flow_cm_s"] = num(d["Flow Velocity Cm S"])
        if num(d.get("Burn Time S")) is not None: extra["burn_time_s"] = num(d["Burn Time S"])
        m.update(extra); n += 1
        for k in extra: stats[k] = stats.get(k, 0) + 1
    json.dump(chunks, open(out, "w", encoding="utf-8"), ensure_ascii=False)
    print(f"enriched {n} experiment records -> {out}"); print("fields filled:", stats)

if __name__ == "__main__": main()
