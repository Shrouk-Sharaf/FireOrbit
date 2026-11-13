"""Build eval_set.json from chunks.json with ground truth computed from the data.
Usage: python eval/make_eval_set.py --chunks chunking/chunks.json --out eval/eval_set.json"""
import argparse, json, re

def parse_record(text):
    d = {}
    for line in text.split("\n"):
        if ": " in line:
            k, v = line.split(": ", 1); d[k.strip()] = v.strip()
    return d

def num(x):
    try: return float(x)
    except (TypeError, ValueError): return None

def is_reference(t):
    t = t.lower()
    return t.count("et al") >= 2 or len(re.findall(r"\[\d+\]", t)) >= 3 or t.count("doi") >= 2 \
        or t.count("proceedings") >= 2 or t.count("j. fluid") + t.count("combust. flame") >= 2

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--chunks", default="chunking/chunks.json"); ap.add_argument("--out", default="eval/eval_set.json")
    a = ap.parse_args()
    cs = json.load(open(a.chunks, encoding="utf-8"))
    M = lambda c: c["metadata"]
    exp = [(c["chunk_id"], parse_record(c["text"]), M(c)) for c in cs if M(c)["document_type"] == "experiment_record"]
    inv = [c for c in cs if M(c)["document_type"] == "investigation_metadata"]
    rep = [c for c in cs if M(c)["document_type"] == "report" and not is_reference(c["text"])]
    Q = []
    def add(cat, q, ids, doc_type, psi=None, label="exact", note=""):
        ids = sorted(set(ids))
        if not ids:
            print("SKIP (no matches):", q); return
        Q.append({"id": f"q{len(Q)+1:02d}", "category": cat, "question": q, "answerable": True,
                  "expected_document_type": doc_type, "expected_psi_ids": psi or [],
                  "label_quality": label, "n_relevant": len(ids), "relevant_chunk_ids": ids[:300], "note": note})
    def E(pred): return [i for i, d, m in exp if pred(d, m)]
    o2 = lambda d: num(d.get("O2 Concentration Pct"))
    fuel = lambda d: (d.get("Fuel Material Normalized") or "").lower()
    out = lambda d: d.get("Outcome Category")

    # ---- numeric / structured (exact labels from the record fields)
    add("numeric", "which test reached 85% oxygen", E(lambda d, m: o2(d) == 85), "experiment_record", ["PSI-159"], note="known failure case")
    add("numeric", "experiments run at 85% O2 with ethane fuel", E(lambda d, m: o2(d) == 85 and fuel(d) == "ethane"), "experiment_record", ["PSI-159"])
    add("numeric", "tests with oxygen concentration above 60 percent", E(lambda d, m: (o2(d) or 0) > 60), "experiment_record", note="aggregation; ideal for metadata filter")
    add("numeric", "tests run at 30% oxygen", E(lambda d, m: o2(d) == 30), "experiment_record")
    add("numeric", "experiments with 50% O2 concentration", E(lambda d, m: o2(d) == 50), "experiment_record")
    add("numeric", "tests at 17% oxygen", E(lambda d, m: o2(d) == 17), "experiment_record")
    add("numeric", "tests at 34 percent oxygen", E(lambda d, m: o2(d) == 34), "experiment_record")
    add("numeric", "which experiments burned for the longest time", E(lambda d, m: (num(d.get("Burn Time S")) or 0) >= 400), "experiment_record", label="weak", note="threshold >=400 s")

    # ---- structured combos (fuel / outcome / investigation)
    add("structured", "methanol experiments that ended in extinction", E(lambda d, m: fuel(d) == "methanol" and out(d) == "extinction"), "experiment_record")
    add("structured", "propane tests where the flame self-extinguished", E(lambda d, m: fuel(d) == "propane" and out(d) == "self_extinction"), "experiment_record")
    add("structured", "PMMA tests that failed to ignite", E(lambda d, m: fuel(d) == "pmma" and out(d) == "no_ignition"), "experiment_record")
    add("structured", "Kapton experiments", E(lambda d, m: fuel(d) == "kapton"), "experiment_record")
    add("structured", "SIBAL fabric burn tests", E(lambda d, m: fuel(d) == "sibal"), "experiment_record")
    add("structured", "tests that resulted in a sustained burn", E(lambda d, m: out(d) == "sustained_burn"), "experiment_record")
    add("structured", "SAFFIRE fire experiments records", E(lambda d, m: "saffire" in (m.get("acronym") or "").lower()), "experiment_record", ["PSI-98", "PSI-99", "PSI-100"])
    add("structured", "heptane tests in the SPICE or BASS experiments", E(lambda d, m: fuel(d) == "heptane"), "experiment_record")
    add("structured", "ethylene flame experiments", E(lambda d, m: fuel(d) == "ethylene"), "experiment_record")

    # ---- investigation metadata (objective/title)
    titles = [("PSI-107", "what is the objective of the Smoke Point In Co-flow Experiment SPICE"),
              ("PSI-102", "what was the objective of the Smoke and Aerosol Measurement Experiment SAME"),
              ("PSI-101", "what is the SAMER smoke aerosol reflight investigation about"),
              ("PSI-25", "what is the objective of Burning and Suppression of Solids II BASS-II"),
              ("PSI-26", "what are the two main objectives of BASS Burning and Suppression of Solids"),
              ("PSI-20", "what is the Burning Rate Emulator BRE investigation for"),
              ("PSI-159", "what is the Cool Flames Investigation with Gases objective"),
              ("PSI-22", "what does the electric field effects on laminar diffusion flames investigation study"),
              ("PSI-106", "what is the Structure and Liftoff In Combustion Experiment SLICE"),
              ("PSI-100", "what were the objectives of the Spacecraft Fire Experiment III Saffire-III")]
    for psi, q in titles:
        add("investigation", q, [c["chunk_id"] for c in inv if M(c)["psi_id"] == psi and c["chunk_id"].endswith("chunk-0001")],
            "investigation_metadata", [psi])

    # ---- report content (keyword-labeled, references excluded)
    def R(psi, kws, src=None):
        return [c["chunk_id"] for c in rep if (psi is None or M(c).get("psi_id") == psi)
                and (src is None or M(c).get("source_type") == src) and all(k in c["text"].lower() for k in kws)]
    add("report", "what is the smoke point of a flame in microgravity", R("PSI-107", ["smoke point"]), "report", ["PSI-107"], "weak")
    add("report", "how did smoke detectors respond to microgravity smoke in the SAME experiment", R("PSI-102", ["smoke detector"]), "report", ["PSI-102"], "weak")
    add("report", "smoke detector performance in the reflight SAMER tests", R("PSI-101", ["smoke detector"]), "report", ["PSI-101"], "weak")
    add("report", "radiation fraction of the burner flames", R("PSI-20", ["radiation fraction"]), "report", ["PSI-20"], "weak")
    add("report", "flame spread over thick solid fuels", R("PSI-25", ["flame spread", "thick"]), "report", ["PSI-25"], "weak")
    add("report", "quenching limits for flame spread in low flow", R("PSI-25", ["quench"]), "report", ["PSI-25"], "weak")
    add("report", "cool flame behavior and extinction in microgravity", R("PSI-159", ["cool flame"]), "report", ["PSI-159"], "weak")
    add("report", "effect of an electric field on flame shape", R("PSI-22", ["electric field"]), "report", ["PSI-22"], "weak")
    add("report", "soot formation measurements in the CFI report", R("PSI-39", ["soot"]), "report", ["PSI-39"], "weak")
    add("report", "how does oxygen concentration affect flame spread", R(None, ["flame spread", "oxygen"], "global_guide"), "report", [], "weak")
    add("report", "what is quenching in microgravity combustion", R(None, ["quench"], "global_guide"), "report", [], "weak")

    # ---- unanswerable (verified absent from structured data where possible)
    un = [("which test reached 250% oxygen", "max O2 in data is 85"),
          ("experiments that burned gasoline", "no gasoline in fuel list"),
          ("price of a Falcon 9 launch", ""), ("how do I bake sourdough bread", ""), ("who won the 2022 football world cup", "")]
    assert not E(lambda d, m: (o2(d) or 0) > 100) and not E(lambda d, m: "gasoline" in fuel(d))
    for q, n in un:
        Q.append({"id": f"q{len(Q)+1:02d}", "category": "unanswerable", "question": q, "answerable": False,
                  "expected_document_type": None, "expected_psi_ids": [], "label_quality": "exact",
                  "n_relevant": 0, "relevant_chunk_ids": [], "note": n})
    json.dump({"version": 2, "n_chunks": len(cs), "questions": Q}, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(f"wrote {len(Q)} questions -> {a.out}")
    for q in Q: print(q["id"], q["category"], q["n_relevant"], q["question"][:70])

if __name__ == "__main__": main()
