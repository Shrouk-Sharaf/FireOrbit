import json
from pathlib import Path

kb = json.load(open(r"data_processed/knowledge_base.json", encoding="utf-8"))
print("global docs", len(kb.get("global_documents") or []))
for d in kb.get("global_documents") or []:
    print(
        " GLOBAL",
        d.get("filename"),
        "err",
        d.get("extraction_error"),
        "len",
        d.get("full_text_length"),
        "pages",
        d.get("total_pages"),
    )

print("--- investigations reports ---")
for inv in kb["investigations"]:
    reps = inv.get("reports") or []
    print(
        inv["psi_id"],
        inv["acronym"],
        "reports",
        inv.get("reports_count"),
        "invalid_exp",
        inv.get("invalid_experiment_count"),
        "assumed",
        inv.get("assumed_experiment_count"),
    )
    for r in reps:
        secs = r.get("sections") or {}
        nonempty = [k for k, v in secs.items() if (v or "").strip()]
        preview = (r.get("text_preview") or "")[:120].replace("\n", " ")
        print(
            "  ",
            r.get("filename"),
            "pages",
            r.get("total_pages"),
            "chars",
            r.get("full_text_length"),
            "err",
            r.get("extraction_error"),
            "sections",
            nonempty,
        )
        print("   preview:", preview)

# also look for needs_verification
exps = json.load(open(r"data_processed/experiments_normalized.json", encoding="utf-8"))
print("--- needs_verification", sum(1 for e in exps if e.get("needs_verification")))
print("--- solver excluded reasons ---")
from collections import Counter
c = Counter((e.get("solver_exclude_reason") or "included") for e in exps)
for k, v in c.most_common():
    print(v, k)
