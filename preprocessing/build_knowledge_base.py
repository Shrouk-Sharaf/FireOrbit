import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from utils import (
    HARDWARE_GROUPS,
    OUTPUT_DIR,
    RELATED_INVESTIGATIONS,
    dump_json,
    ensure_output_dir,
    extract_sensors,
)


def all_o2_values(exp):
    vals = []
    if exp.get("o2_concentration_pct") is not None:
        vals.append(exp["o2_concentration_pct"])
    for v in exp.get("o2_values") or []:
        if v is not None:
            vals.append(v)
    return vals


def all_pressure_values(exp):
    vals = []
    if exp.get("pressure_atm") is not None:
        vals.append(exp["pressure_atm"])
    for v in exp.get("pressure_values") or []:
        if v is not None:
            vals.append(v)
    return vals


def earth_application_flag(text):
    blob = (text or "").lower()
    keywords = [
        "earth", "terrestrial", "submarine", "aircraft", "mine", "firefighter",
        "wildfire", "building fire", "smoke detector", "protective clothing",
        "engine", "pollution",
    ]
    return any(k in blob for k in keywords)


def compute_relevance_score(inv, exp_list):
    score = 0.0
    acronym = (inv.get("acronym") or "").upper()
    pillar = inv.get("pillar") or ""
    sub = (inv.get("subresearch_area") or "").lower()
    descriptors = " ".join(inv.get("descriptors") or []).lower()
    impacts = inv.get("research_impacts") or ""

    if "spacecraft fire safety" in sub or "fire safety" in descriptors:
        score += 20.0
    elif "Prevention" in pillar or "Detection" in pillar or "Suppression" in pillar:
        score += 12.0
    else:
        score += 6.0

    fuels = " ".join(
        str(e.get("fuel_material_normalized") or e.get("fuel_material") or "").lower()
        for e in exp_list
    )
    crew_materials = any(
        m in fuels
        for m in ["pmma", "sibal", "cotton", "nomex", "silicone", "teflon", "kapton", "ultem", "pyrell"]
    )
    phases = {e.get("fuel_phase") for e in exp_list}
    if crew_materials or "emulated" in fuels or "BRE" in acronym:
        score += 20.0
    elif "solid" in phases or "aerosol" in "".join(str(p) for p in phases):
        score += 14.0
    else:
        score += 8.0

    o2_levels = [v for e in exp_list for v in all_o2_values(e)]
    if any(o >= 26.5 for o in o2_levels):
        score += 15.0
    elif o2_levels:
        score += 8.0
    else:
        score += 3.0

    if any((e.get("fuel_phase") or "").startswith("solid") for e in exp_list) or crew_materials:
        score += 15.0
    elif "BRE" in acronym:
        score += 15.0
    else:
        score += 5.0

    if "Suppression" in pillar or any(e.get("co2_mole_fraction") or e.get("he_mole_fraction") for e in exp_list):
        score += 10.0
    if "Detection" in pillar or any(e.get("measurement_type") for e in exp_list):
        score += 10.0

    score += min(5.0, 0.5 * len(inv.get("publications") or []))
    if earth_application_flag(impacts):
        score += 5.0

    if any(e.get("partial_g_proxy") or "partial-emulated" in str(e.get("gravity_level")) for e in exp_list):
        score += 4.0

    return round(min(100.0, score), 1)


def match_reports(pdfs, psi_id, folder):
    matched = []
    for key, report in pdfs.items():
        if report.get("source_type") == "global_guide":
            continue
        if report.get("psi_id") and psi_id and report["psi_id"] == psi_id:
            matched.append(report)
            continue
        if folder and report.get("investigation_folder") == folder:
            matched.append(report)
    return matched


def report_stub(report):
    return {
        "filename": report.get("filename"),
        "relative_path": report.get("relative_path"),
        "psi_id": report.get("psi_id"),
        "total_pages": report.get("total_pages"),
        "full_text_length": report.get("full_text_length"),
        "sections": report.get("sections") or {},
        "text_preview": report.get("text_preview") or "",
        "extraction_error": report.get("extraction_error"),
    }


def main():
    ensure_output_dir()
    processed_dir = OUTPUT_DIR
    with open(processed_dir / "investigations_metadata.json", encoding="utf-8") as f:
        metadata = json.load(f)
    with open(processed_dir / "experiments_normalized.json", encoding="utf-8") as f:
        experiments = json.load(f)
    with open(processed_dir / "extracted_pdf_reports.json", encoding="utf-8") as f:
        pdfs = json.load(f)

    exp_by_psi = {}
    for exp in experiments:
        psi = exp.get("investigation_id")
        if psi:
            exp_by_psi.setdefault(psi, []).append(exp)

    global_docs = [
        report_stub(r) for r in pdfs.values() if r.get("source_type") == "global_guide"
    ]

    master_investigations = []
    for key, inv in metadata.items():
        psi_id = inv.get("psi_id") or key
        matched_exps = exp_by_psi.get(psi_id, [])
        matched_reports = match_reports(pdfs, psi_id, inv.get("folder"))

        habitat_o2 = []
        inverse_o2 = []
        pressures = []
        for e in matched_exps:
            o2s = all_o2_values(e)
            pressures.extend(all_pressure_values(e))
            if e.get("o2_role") == "oxidizer_stream" or e.get("flame_type") == "inverse":
                inverse_o2.extend(o2s)
            else:
                habitat_o2.extend(o2s)

        fuels = sorted({
            e.get("fuel_material_normalized") or e.get("fuel_material")
            for e in matched_exps
            if e.get("fuel_material_normalized") or e.get("fuel_material")
        })
        phases = sorted({e.get("fuel_phase") for e in matched_exps if e.get("fuel_phase")})

        o2_for_score = habitat_o2 + inverse_o2
        o2_min = min(o2_for_score) if o2_for_score else None
        o2_max = max(o2_for_score) if o2_for_score else None
        habitat_max = max(habitat_o2) if habitat_o2 else None
        p_min = min(pressures) if pressures else None
        p_max = max(pressures) if pressures else None

        covers_elevated_o2 = any(o >= 26.5 for o in o2_for_score)
        covers_moon_cabin_o2 = any(o >= 26.5 for o in habitat_o2)
        covers_reduced_pressure = any(p is not None and p <= 0.70 for p in pressures)
        crew_materials = any(
            m in " ".join(str(f).lower() for f in fuels)
            for m in ["pmma", "sibal", "cotton", "nomex", "silicone", "teflon", "kapton", "ultem", "pyrell"]
        )
        partial_g_proxy = any(
            e.get("partial_g_proxy") or "partial-emulated" in str(e.get("gravity_level"))
            for e in matched_exps
        )
        moon_base_applicable = bool(
            covers_moon_cabin_o2 or covers_elevated_o2 or crew_materials or covers_reduced_pressure
        )

        sensors = sorted(set((inv.get("sensors") or []) + extract_sensors(
            inv.get("approach"), inv.get("objective"), *(r.get("text_preview") or "" for r in matched_reports[:3])
        )))

        record = {
            "psi_id": psi_id,
            "acronym": inv.get("acronym"),
            "title": inv.get("title"),
            "pillar": inv.get("pillar"),
            "subresearch_area": inv.get("subresearch_area"),
            "research_area": inv.get("research_area"),
            "hardware": inv.get("hardware"),
            "hardware_group": HARDWARE_GROUPS.get(psi_id, inv.get("hardware")),
            "related_investigations": RELATED_INVESTIGATIONS.get(psi_id, []),
            "relevance_score": compute_relevance_score(inv, matched_exps),
            "moon_base_applicable": moon_base_applicable,
            "covers_elevated_o2": covers_elevated_o2,
            "covers_moon_cabin_o2": covers_moon_cabin_o2,
            "covers_reduced_pressure": covers_reduced_pressure,
            "crew_materials": crew_materials,
            "partial_g_proxy": partial_g_proxy,
            "earth_application": earth_application_flag(inv.get("research_impacts")),
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
            "contacts": inv.get("contacts", []),
            "sensors": sensors,
            "tested_fuels": fuels,
            "fuel_phases": phases,
            "o2_range": {"min": o2_min, "max": o2_max},
            "o2_range_habitat": {
                "min": min(habitat_o2) if habitat_o2 else None,
                "max": habitat_max,
            },
            "o2_range_oxidizer_stream": {
                "min": min(inverse_o2) if inverse_o2 else None,
                "max": max(inverse_o2) if inverse_o2 else None,
            },
            "pressure_range_atm": {"min": p_min, "max": p_max},
            "experiment_count": len(matched_exps),
            "reports_count": len(matched_reports),
            "reports": [report_stub(r) for r in matched_reports],
            "sample_experiments": matched_exps[:15],
        }
        master_investigations.append(record)

    master_investigations.sort(key=lambda x: x["relevance_score"], reverse=True)

    knowledge_gaps = [
        {
            "id": "partial-gravity",
            "title": "No partial-gravity combustion data in PSI",
            "detail": "Moon (1/6 g) and Mars (3/8 g) flame behavior is not directly measured in the current PSI set. Microgravity and 1-g results can only bound intermediate gravity.",
            "upcoming": ["LUCI (Lunar-g Combustion Investigation)", "FM2 (Flammability of Materials on the Moon)"],
            "current_proxy": "ACME E-FIELD Flames mimics body-force effects via electric fields on flame ions.",
        },
        {
            "id": "moon-cabin-atmosphere",
            "title": "Sparse data at Moon Base cabin conditions",
            "detail": "Planned habitat atmospheres are ~30% O2 at 10.2 psi or less. Few investigations report both elevated oxygen and reduced pressure together.",
        },
    ]

    kb = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "total_investigations": len(master_investigations),
        "total_normalized_datapoints": len(experiments),
        "global_documents": global_docs,
        "knowledge_gaps": knowledge_gaps,
        "investigations": master_investigations,
    }
    dump_json(processed_dir / "knowledge_base.json", kb)
    print(f"Master Knowledge Base saved to: {processed_dir / 'knowledge_base.json'}")

    db_out = processed_dir / "investigations.db"
    conn = sqlite3.connect(db_out)
    cur = conn.cursor()
    cur.execute("DROP TABLE IF EXISTS investigations")
    cur.execute("DROP TABLE IF EXISTS experiments")
    cur.execute("""
    CREATE TABLE investigations (
        psi_id TEXT PRIMARY KEY,
        acronym TEXT,
        title TEXT,
        pillar TEXT,
        subresearch_area TEXT,
        hardware TEXT,
        hardware_group TEXT,
        relevance_score REAL,
        moon_base_applicable INTEGER,
        covers_elevated_o2 INTEGER,
        covers_moon_cabin_o2 INTEGER,
        covers_reduced_pressure INTEGER,
        partial_g_proxy INTEGER,
        earth_application INTEGER,
        o2_min REAL,
        o2_max REAL,
        pressure_min_atm REAL,
        pressure_max_atm REAL,
        experiment_count INTEGER,
        objective TEXT,
        research_impacts TEXT
    )
    """)
    cur.execute("""
    CREATE TABLE experiments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        experiment_id TEXT UNIQUE,
        investigation_id TEXT,
        investigation_acronym TEXT,
        source_test_id TEXT,
        replicate INTEGER,
        source_row_index INTEGER,
        fuel_material TEXT,
        fuel_material_normalized TEXT,
        fuel_phase TEXT,
        fuel_geometry TEXT,
        o2_concentration_pct REAL,
        o2_source TEXT,
        o2_is_assumed INTEGER,
        pressure_atm REAL,
        pressure_source TEXT,
        pressure_is_assumed INTEGER,
        flow_velocity_cm_s REAL,
        flow_velocity_source TEXT,
        flow_direction TEXT,
        flow_is_assumed INTEGER,
        burn_time_s REAL,
        outcome TEXT,
        outcome_category TEXT,
        experiment_context TEXT,
        gravity_level TEXT,
        diluent TEXT,
        flame_type TEXT
    )
    """)
    for inv in master_investigations:
        cur.execute(
            """INSERT INTO investigations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                inv["psi_id"], inv["acronym"], inv["title"], inv["pillar"],
                inv.get("subresearch_area"), inv["hardware"], inv["hardware_group"],
                inv["relevance_score"], int(inv["moon_base_applicable"]),
                int(inv["covers_elevated_o2"]), int(inv["covers_moon_cabin_o2"]),
                int(inv["covers_reduced_pressure"]), int(inv["partial_g_proxy"]),
                int(inv["earth_application"]),
                inv["o2_range"]["min"], inv["o2_range"]["max"],
                inv["pressure_range_atm"]["min"], inv["pressure_range_atm"]["max"],
                inv["experiment_count"], inv["objective"], inv["research_impacts"],
            ),
        )
    for exp in experiments:
        cur.execute(
            """INSERT INTO experiments (
                experiment_id, investigation_id, investigation_acronym, source_test_id, replicate, source_row_index,
                fuel_material, fuel_material_normalized, fuel_phase, fuel_geometry, o2_concentration_pct, o2_source,
                o2_is_assumed, pressure_atm, pressure_source, pressure_is_assumed, flow_velocity_cm_s,
                flow_velocity_source, flow_direction, flow_is_assumed, burn_time_s, outcome, outcome_category,
                experiment_context, gravity_level, diluent, flame_type
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                exp.get("experiment_id"), exp.get("investigation_id"), exp.get("investigation_acronym"),
                exp.get("source_test_id"), exp.get("replicate"), exp.get("source_row_index"),
                exp.get("fuel_material"), exp.get("fuel_material_normalized"), exp.get("fuel_phase"),
                exp.get("fuel_geometry"), exp.get("o2_concentration_pct"), exp.get("o2_source"),
                int(bool(exp.get("o2_is_assumed"))), exp.get("pressure_atm"), exp.get("pressure_source"),
                int(bool(exp.get("pressure_is_assumed"))), exp.get("flow_velocity_cm_s"),
                exp.get("flow_velocity_source"), exp.get("flow_direction"),
                int(bool(exp.get("flow_is_assumed"))), exp.get("burn_time_s"), exp.get("outcome"),
                exp.get("outcome_category"), exp.get("experiment_context"), exp.get("gravity_level"),
                exp.get("diluent"), exp.get("flame_type"),
            ),
        )
    conn.commit()
    conn.close()
    print(f"SQLite database generated at: {db_out}")


if __name__ == "__main__":
    main()
