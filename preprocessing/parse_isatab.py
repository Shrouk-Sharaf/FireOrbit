import os
import re
import json
from pathlib import Path

def parse_isatab_file(filepath):
    """
    Parses an ISA-Tab i_Investigation*.txt file into structured key-values.
    Handles multi-column tab-separated entries such as study descriptors,
    publications, and comments.
    """
    data = {
        "raw_fields": {},
        "publications": [],
        "design_descriptors": []
    }
    
    with open(filepath, "r", encoding="utf-8", errors="replace") as f:
        lines = f.readlines()
        
    pub_keys = {}
    
    for line in lines:
        line_clean = line.strip("\r\n")
        if not line_clean:
            continue
        parts = [p.strip() for p in line_clean.split("\t")]
        key = parts[0]
        vals = [p for p in parts[1:] if p]
        
        # Publications handling
        if key.startswith("Study Publication") or key.startswith("Investigation Publication"):
            pub_keys[key] = vals
            continue
            
        if key == "Study Design Type":
            data["design_descriptors"].extend(vals)
            continue
            
        # Comments & standard fields
        # E.g. Comment[Approach], Comment[Objective], Study Title, etc.
        m = re.match(r"Comment\[(.*?)\]", key)
        if m:
            clean_key = m.group(1).lower().replace(" ", "_")
            data["raw_fields"][clean_key] = " ".join(vals) if vals else ""
        else:
            clean_key = key.lower().replace(" ", "_")
            data["raw_fields"][clean_key] = " ".join(vals) if vals else ""

    # Align publication columns if found
    pub_titles = pub_keys.get("Study Publication Title", pub_keys.get("Investigation Publication Title", []))
    pub_dois = pub_keys.get("Study Publication DOI", pub_keys.get("Investigation Publication DOI", []))
    pub_authors = pub_keys.get("Study Publication Author List", pub_keys.get("Investigation Publication Author List", []))
    pub_links = pub_keys.get("Comment[Study Publication Link]", [])

    max_pubs = max(len(pub_titles), len(pub_dois), len(pub_authors), 0)
    for i in range(max_pubs):
        pub = {
            "title": pub_titles[i] if i < len(pub_titles) else "",
            "doi": pub_dois[i] if i < len(pub_dois) else "",
            "authors": pub_authors[i] if i < len(pub_authors) else "",
            "link": pub_links[i] if i < len(pub_links) else ""
        }
        if pub["title"] or pub["doi"]:
            data["publications"].append(pub)
            
    return data

def main():
    base_dir = Path(r"d:\FireOrbit\FireOrbit\DATA\nasa final data")
    out_file = Path(r"d:\FireOrbit\FireOrbit\data_processed\investigations_metadata.json")
    
    results = {}
    
    # Scan subdirectories
    for item in sorted(base_dir.iterdir()):
        if not item.is_dir():
            continue
        
        # Look for i_Investigation*.txt
        inv_files = list(item.glob("i_Investigation*.txt"))
        if not inv_files:
            continue
            
        inv_path = inv_files[0]
        parsed = parse_isatab_file(inv_path)
        
        raw = parsed["raw_fields"]
        folder_name = item.name
        
        # Extract standardized identifier and acronym
        study_id = raw.get("study_identifier", "")
        acronym = raw.get("investigation_acronym", folder_name)
        title = raw.get("study_title", raw.get("investigation_title", folder_name))
        
        # Map pillar
        sub_area = raw.get("subresearch_area", "")
        research_area = raw.get("research_area", "")
        descriptors = " ".join(parsed["design_descriptors"]).lower()
        
        # Classify Fire Safety Pillar
        pillar = "Fundamental Combustion"
        if any(w in acronym.lower() for w in ["bass", "saffire", "bre", "cfi-g"]):
            pillar = "Prevention (Flammability)"
        elif any(w in acronym.lower() for w in ["same", "daft"]):
            pillar = "Detection (Smoke/Aerosol)"
        elif any(w in acronym.lower() for w in ["flex", "cfi"]):
            pillar = "Suppression (Extinction)"
        elif "fire safety" in sub_area.lower() or "fire safety" in descriptors:
            pillar = "Prevention (Flammability)"

        inv_record = {
            "folder": folder_name,
            "psi_id": study_id,
            "acronym": acronym,
            "title": title,
            "pillar": pillar,
            "hardware": raw.get("experiment_hardware", ""),
            "flight_platform": raw.get("flight_platform", "ISS"),
            "managing_center": raw.get("managing_nasa_center", "GRC"),
            "start_date": raw.get("investigation_start_date", ""),
            "end_date": raw.get("investigation_end_date", ""),
            "doi": raw.get("doi", ""),
            "objective": raw.get("objective", ""),
            "hypothesis": raw.get("hypothesis", ""),
            "approach": raw.get("approach", ""),
            "research_impacts": raw.get("research_impacts", ""),
            "descriptors": list(set(parsed["design_descriptors"])),
            "publications": parsed["publications"]
        }
        
        key = study_id if study_id else folder_name
        results[key] = inv_record
        print(f"Parsed {folder_name} -> {inv_record['acronym']} ({inv_record['pillar']})")

    with open(out_file, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
        
    print(f"\nSaved metadata for {len(results)} investigations to: {out_file}")

if __name__ == "__main__":
    main()

