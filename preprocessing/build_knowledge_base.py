import json
import sqlite3
from pathlib import Path

def compute_relevance_score(inv, exp_list):
    """
    Computes a weighted 0-100 score of relevance to human spacecraft & lunar fire safety.
    """
    score = 0.0
    acronym = inv.get("acronym", "").upper()
    title = inv.get("title", "").lower()
    pillar = inv.get("pillar", "")
    
    # Pillar weights (0 - 30 pts)
    if "Prevention" in pillar:
        score += 30.0
    elif "Detection" in pillar:
        score += 26.0
    elif "Suppression" in pillar:
        score += 24.0
    else:
        score += 15.0
        
    # Crew environment & material factors (0 - 25 pts)
    # Check if materials are solids, fabrics, plastics, or emulated condensed fuels
    fuels = set(e.get("fuel_material", "") for e in exp_list if e.get("fuel_material"))
    fuels_str = " ".join([str(f).lower() for f in fuels])
    
    if any(m in fuels_str for m in ["pmma", "sibal", "cotton", "nomex", "silicone", "teflon", "kapton"]):
        score += 25.0
    elif "emulated" in fuels_str or "bre" in acronym.lower():
        score += 25.0
    elif any(m in fuels_str for m in ["methanol", "heptane", "octane", "decane"]):
        score += 15.0
    else:
        score += 10.0
        
    # Oxygen Range Coverage (0 - 25 pts) - Crucial for Moon Base / spacesuit environments
    o2_levels = [e.get("o2_concentration_pct") for e in exp_list if e.get("o2_concentration_pct") is not None]
    max_o2 = max(o2_levels) if o2_levels else 21.0
    has_elevated_o2 = any(o > 25.0 for o in o2_levels)
    
    if has_elevated_o2:
        score += 25.0  # ACME BRE, CFI-G, etc.
    elif any(o >= 21.0 for o in o2_levels):
        score += 15.0
    else:
        score += 10.0
        
    # Realistic hardware or large-scale vehicle tests (0 - 15 pts)
    if "saffire" in acronym.lower():
        score += 15.0  # Uncrewed vehicle actual spacecraft fire!
    elif "bass" in acronym.lower() or "same" in acronym.lower():
        score += 12.0
    elif "acme" in acronym.lower() or "flex" in acronym.lower():
        score += 10.0
    else:
        score += 5.0
        
    # Publication & validation maturity (0 - 5 pts)
    pub_count = len(inv.get("publications", []))
    score += min(5.0, pub_count * 0.5)
    
    return round(min(100.0, score), 1)

def main():
    processed_dir = Path(r"d:\FireOrbit\FireOrbit\data_processed")
    meta_path = processed_dir / "investigations_metadata.json"
    exp_path = processed_dir / "experiments_normalized.json"
    pdf_path = processed_dir / "extracted_pdf_reports.json"
    kb_out = processed_dir / "knowledge_base.json"
    db_out = processed_dir / "investigations.db"
    
    with open(meta_path, "r", encoding="utf-8") as f:
        metadata = json.load(f)
        
    with open(exp_path, "r", encoding="utf-8") as f:
        experiments = json.load(f)
        
    with open(pdf_path, "r", encoding="utf-8") as f:
        pdfs = json.load(f)
        
    # Group experiments by psi_id and acronym
    exp_by_inv = {}
    for exp in experiments:
        psi = exp.get("investigation_id", "")
        acro = exp.get("investigation_acronym", "")
        for key in [psi, acro]:
            if key:
                if key not in exp_by_inv:
                    exp_by_inv[key] = []
                exp_by_inv[key].append(exp)
                
    master_investigations = []
    
    for key, inv in metadata.items():
        psi_id = inv.get("psi_id") or key
        acronym = inv.get("acronym", "")
        
        # Correlate experiments
        matched_exps = exp_by_inv.get(psi_id, exp_by_inv.get(acronym, []))
        
        # Correlate reports
        matched_reports = []
        for pdf_key, report_data in pdfs.items():
            if acronym.lower().replace("-", "") in pdf_key.lower().replace("-", "") or (psi_id and psi_id.lower() in pdf_key.lower()):
                matched_reports.append(report_data)
                
        # Calculate O2 range & fuels
        o2_vals = [e.get("o2_concentration_pct") for e in matched_exps if e.get("o2_concentration_pct") is not None]
        o2_min = min(o2_vals) if o2_vals else 21.0
        o2_max = max(o2_vals) if o2_vals else 21.0
        
        fuels = list(set([e.get("fuel_material") for e in matched_exps if e.get("fuel_material")]))
        
        relevance_score = compute_relevance_score(inv, matched_exps)
        
        # Moon base applicability flag
        moon_base_applicable = (o2_max >= 26.5) or ("solid" in inv.get("pillar", "").lower()) or any(f in str(fuels).lower() for f in ["pmma", "sibal", "teflon", "kapton"])
        
        record = {
            "psi_id": psi_id,
            "acronym": acronym,
            "title": inv.get("title"),
            "pillar": inv.get("pillar"),
            "relevance_score": relevance_score,
            "moon_base_applicable": moon_base_applicable,
            "hardware": inv.get("hardware"),
            "flight_platform": inv.get("flight_platform"),
            "managing_center": inv.get("managing_center"),
            "start_date": inv.get("start_date"),
            "end_date": inv.get("end_date"),
            "doi": inv.get("doi"),
            "objective": inv.get("objective"),
            "hypothesis": inv.get("hypothesis"),
            "approach": inv.get("approach"),
            "research_impacts": inv.get("research_impacts"),
            "descriptors": inv.get("descriptors", []),
            "publications": inv.get("publications", []),
            "tested_fuels": fuels,
            "o2_range": {"min": o2_min, "max": o2_max},
            "experiment_count": len(matched_exps),
            "reports_count": len(matched_reports),
            "sample_experiments": matched_exps[:15] # Top representative tests
        }
        master_investigations.append(record)
        
    # Sort by relevance score descending
    master_investigations.sort(key=lambda x: x["relevance_score"], reverse=True)
    
    # Save Knowledge Base JSON
    with open(kb_out, "w", encoding="utf-8") as f:
        json.dump({
            "generated_at": "2026-11-13",
            "total_investigations": len(master_investigations),
            "total_normalized_datapoints": len(experiments),
            "investigations": master_investigations
        }, f, indent=2, ensure_ascii=False)
        
    print(f"Master Knowledge Base saved to: {kb_out}")
    
    # Build SQLite DB for ultra-fast SQL analytical queries in backend
    conn = sqlite3.connect(db_out)
    cur = conn.cursor()
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS investigations (
        psi_id TEXT PRIMARY KEY,
        acronym TEXT,
        title TEXT,
        pillar TEXT,
        relevance_score REAL,
        moon_base_applicable INTEGER,
        hardware TEXT,
        o2_min REAL,
        o2_max REAL,
        experiment_count INTEGER,
        objective TEXT,
        research_impacts TEXT
    )
    """)
    
    cur.execute("""
    CREATE TABLE IF NOT EXISTS experiments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        investigation_id TEXT,
        investigation_acronym TEXT,
        test_id TEXT,
        fuel_material TEXT,
        fuel_phase TEXT,
        fuel_geometry TEXT,
        o2_concentration_pct REAL,
        flow_velocity_cm_s REAL,
        flow_direction TEXT,
        pressure_atm REAL,
        burn_time_s REAL,
        outcome TEXT
    )
    """)
    
    cur.execute("DELETE FROM investigations")
    cur.execute("DELETE FROM experiments")
    
    for inv in master_investigations:
        cur.execute("""
        INSERT INTO investigations VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            inv["psi_id"], inv["acronym"], inv["title"], inv["pillar"],
            inv["relevance_score"], 1 if inv["moon_base_applicable"] else 0,
            inv["hardware"], inv["o2_range"]["min"], inv["o2_range"]["max"],
            inv["experiment_count"], inv["objective"], inv["research_impacts"]
        ))
        
    for exp in experiments:
        cur.execute("""
        INSERT INTO experiments (investigation_id, investigation_acronym, test_id, fuel_material, fuel_phase, fuel_geometry, o2_concentration_pct, flow_velocity_cm_s, flow_direction, pressure_atm, burn_time_s, outcome)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            exp.get("investigation_id"), exp.get("investigation_acronym"),
            exp.get("test_id"), exp.get("fuel_material"), exp.get("fuel_phase"),
            exp.get("fuel_geometry"), exp.get("o2_concentration_pct"),
            exp.get("flow_velocity_cm_s"), exp.get("flow_direction"),
            exp.get("pressure_atm"), exp.get("burn_time_s"), exp.get("outcome")
        ))
        
    conn.commit()
    conn.close()
    print(f"SQLite database generated at: {db_out}")

if __name__ == "__main__":
    main()

