import csv
import re
from pathlib import Path

from utils import (
    BASE_DIR,
    OUTPUT_DIR,
    dump_json,
    ensure_output_dir,
    extract_sensors,
    strip_wrapping_quotes,
)

PUB_PREFIXES = ("Study Publication", "Investigation Publication")


def _read_isatab_rows(filepath):
    with open(filepath, "r", encoding="utf-8", errors="replace", newline="") as f:
        return list(csv.reader(f, delimiter="\t", quotechar='"'))


def parse_isatab_file(filepath):
    data = {
        "raw_fields": {},
        "publications": [],
        "design_descriptors": [],
        "contacts": [],
    }
    pub_keys = {}
    contact_keys = {}

    for parts in _read_isatab_rows(filepath):
        if not parts:
            continue
        key = (parts[0] or "").strip()
        if not key:
            continue
        vals = [strip_wrapping_quotes(p) if p is not None else "" for p in parts[1:]]

        if key.startswith(PUB_PREFIXES) or key == "Comment[Study Publication Link]":
            pub_keys[key] = vals
            continue
        if key.startswith("Study Person") or key.startswith("Investigation Person"):
            contact_keys[key] = vals
            continue
        if key == "Study Design Type":
            data["design_descriptors"].extend([v for v in vals if v])
            continue

        m = re.match(r"Comment\[(.*?)\]", key)
        if m:
            clean_key = m.group(1).lower().replace(" ", "_")
        else:
            clean_key = key.lower().replace(" ", "_")
        data["raw_fields"][clean_key] = " ".join(v for v in vals if v)

    titles = pub_keys.get("Study Publication Title", pub_keys.get("Investigation Publication Title", []))
    dois = pub_keys.get("Study Publication DOI", pub_keys.get("Investigation Publication DOI", []))
    authors = pub_keys.get("Study Publication Author List", pub_keys.get("Investigation Publication Author List", []))
    links = pub_keys.get("Comment[Study Publication Link]", [])
    max_pubs = max(len(titles), len(dois), len(authors), len(links), 0)

    def at(seq, i):
        return seq[i] if i < len(seq) else ""

    for i in range(max_pubs):
        pub = {
            "title": at(titles, i),
            "doi": at(dois, i),
            "authors": at(authors, i),
            "link": at(links, i),
        }
        if pub["title"] or pub["doi"]:
            data["publications"].append(pub)

    last_names = contact_keys.get("Study Person Last Name", contact_keys.get("Investigation Person Last Name", []))
    first_names = contact_keys.get("Study Person First Name", contact_keys.get("Investigation Person First Name", []))
    affiliations = contact_keys.get("Study Person Affiliation", contact_keys.get("Investigation Person Affiliation", []))
    roles = contact_keys.get("Study Person Roles", contact_keys.get("Investigation Person Roles", []))
    max_people = max(len(last_names), len(first_names), 0)
    for i in range(max_people):
        last = at(last_names, i)
        first = at(first_names, i)
        if last or first:
            data["contacts"].append({
                "name": " ".join(p for p in [first, last] if p).strip(),
                "affiliation": at(affiliations, i),
                "role": at(roles, i),
            })

    return data


def classify_pillar(acronym, sub_area, descriptors):
    acr = (acronym or "").lower()
    desc = " ".join(descriptors).lower()
    sub = (sub_area or "").lower()
    if any(w in acr for w in ["bass", "saffire", "bre"]):
        return "Prevention (Flammability)"
    if "cfi-g" in acr or "cfig" in acr.replace("-", "").replace(" ", ""):
        return "Prevention (Flammability)"
    if any(w in acr for w in ["same", "daft"]):
        return "Detection (Smoke/Aerosol)"
    if "flex" in acr or re.search(r"\bcfi\b", acr):
        return "Suppression (Extinction)"
    if "fire safety" in sub or "fire safety" in desc:
        return "Prevention (Flammability)"
    return "Fundamental Combustion"


def main():
    ensure_output_dir()
    results = {}
    base_dir = BASE_DIR

    for item in sorted(base_dir.iterdir()):
        if not item.is_dir():
            continue
        inv_files = list(item.glob("i_Investigation*.txt"))
        if not inv_files:
            continue
        parsed = parse_isatab_file(inv_files[0])
        raw = parsed["raw_fields"]
        folder_name = item.name
        study_id = raw.get("study_identifier", "")
        acronym = raw.get("investigation_acronym", folder_name)
        title = raw.get("study_title", raw.get("investigation_title", folder_name))
        sub_area = raw.get("subresearch_area", "")
        research_area = raw.get("research_area", "")
        pillar = classify_pillar(acronym, sub_area, parsed["design_descriptors"])
        objective = raw.get("objective", "")
        approach = raw.get("approach", "")
        impacts = raw.get("research_impacts", "")

        inv_record = {
            "folder": folder_name,
            "psi_id": study_id,
            "acronym": acronym,
            "title": title,
            "pillar": pillar,
            "subresearch_area": sub_area,
            "research_area": research_area,
            "hardware": raw.get("experiment_hardware", ""),
            "flight_platform": raw.get("flight_platform", "ISS"),
            "managing_center": raw.get("managing_nasa_center", "GRC"),
            "start_date": raw.get("investigation_start_date", ""),
            "end_date": raw.get("investigation_end_date", ""),
            "doi": raw.get("doi", ""),
            "objective": objective,
            "hypothesis": raw.get("hypothesis", ""),
            "approach": approach,
            "research_impacts": impacts,
            "descriptors": sorted(set(parsed["design_descriptors"])),
            "publications": parsed["publications"],
            "contacts": parsed["contacts"],
            "sensors": extract_sensors(objective, approach, impacts),
        }
        key = study_id if study_id else folder_name
        results[key] = inv_record
        print(f"Parsed {folder_name} -> {inv_record['acronym']} ({inv_record['pillar']})")

    out_file = OUTPUT_DIR / "investigations_metadata.json"
    dump_json(out_file, results)
    print(f"\nSaved metadata for {len(results)} investigations to: {out_file}")


if __name__ == "__main__":
    main()
