import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from utils import (
    ATMOSPHERE_SOLVER_EXCLUDE,
    HARDWARE_GROUPS,
    MOON_BASE_TARGET,
    OUTPUT_DIR,
    RELATED_INVESTIGATIONS,
    STUDY_LEVEL_CONDITIONS,
    dump_json,
    ensure_output_dir,
    extract_sensors,
)


def all_o2_values(exp, habitat_only=False):
    if habitat_only and (
        exp.get("o2_role") == "oxidizer_stream"
        or exp.get("flame_type") == "inverse"
        or exp.get("o2_cabin_comparable") is False
    ):
        return []
    vals = []
    if "o2_concentration_pct" not in (exp.get("invalid_fields") or []):
        if exp.get("o2_concentration_pct") is not None:
            vals.append(exp["o2_concentration_pct"])
    for v in exp.get("o2_values") or []:
        if v is not None:
            vals.append(v)
    return vals


def all_pressure_values(exp):
    vals = []
    invalid = set(exp.get("invalid_fields") or [])
    if "pressure_atm" not in invalid and exp.get("pressure_atm") is not None:
        if exp["pressure_atm"] > 0:
            vals.append(exp["pressure_atm"])
    for v in exp.get("pressure_values") or []:
        if v is not None and v > 0:
            vals.append(v)
    return vals


def study_level_for(psi_id):
    return STUDY_LEVEL_CONDITIONS.get(psi_id) or {}


def merge_unique(nums):
    out = []
    seen = set()
    for v in nums:
        if v is None:
            continue
        key = round(float(v), 6)
        if key not in seen:
            seen.add(key)
            out.append(float(v))
    return out


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

    o2_levels = [v for e in exp_list for v in all_o2_values(e, habitat_only=True)]
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


def compute_moon_base_score(inv, exp_list, habitat_o2, pressures):
    psi_id = inv.get("psi_id")
    if psi_id in ATMOSPHERE_SOLVER_EXCLUDE:
        return None, ["excluded from atmosphere solver: " + ATMOSPHERE_SOLVER_EXCLUDE[psi_id]]

    score = 0.0
    notes = []
    target = MOON_BASE_TARGET
    study = study_level_for(psi_id)

    if any(26.5 <= o <= 34.0 for o in habitat_o2):
        score += 28.0
        notes.append("habitat O2 covers the 26.5–34% Moon-cabin band")
    elif any(o >= 26.5 for o in habitat_o2):
        score += 16.0
        notes.append("habitat O2 is elevated but outside the 26.5–34% band")
    elif habitat_o2:
        score += 6.0

    if any(abs(p - target["pressure_atm"]) <= 0.03 for p in pressures):
        score += 28.0
        notes.append("pressure includes the 0.694 atm (10.2 psia) Moon-cabin anchor")
    elif any(p <= 0.70 for p in pressures):
        score += 16.0
        notes.append("pressure includes reduced-pressure points at or below 0.70 atm")
    elif pressures:
        score += 4.0

    if study.get("pressure_status") == "planned_unconfirmed":
        notes.append("pressure anchors are study-level planned, unconfirmed")
        score -= 2.0
    elif study.get("pressure_status") == "design_matrix":
        notes.append("O2/pressure come from the study-level design matrix, not one executed cell per row")

    assumed_flow = any(e.get("flow_is_assumed") for e in exp_list)
    quiescent = any(
        e.get("flow_velocity_cm_s") == 0.0 or e.get("flow_direction") == "quiescent"
        for e in exp_list
    )
    if quiescent:
        score += 12.0
        notes.append("quiescent (no-ventilation) burning is in scope")
        if assumed_flow:
            notes.append("airflow 0 is assumed from a quiescent chamber description; CSV has no airflow column")
            score -= 1.0

    fuels = " ".join(
        str(e.get("fuel_material_normalized") or e.get("fuel_material") or "").lower()
        for e in exp_list
    )
    if "emulated" in fuels or "BRE" in (inv.get("acronym") or ""):
        score += 18.0
        notes.append("burning-rate emulator maps to condensed crew-cabin materials")
    elif any(
        m in fuels
        for m in ["pmma", "sibal", "cotton", "nomex", "silicone", "teflon", "kapton", "ultem", "pyrell"]
    ):
        score += 14.0
        notes.append("crew-relevant solid materials")

    pillar = inv.get("pillar") or ""
    if "Prevention" in pillar or "fire safety" in (inv.get("subresearch_area") or "").lower():
        score += 8.0

    return round(max(0.0, min(100.0, score)), 1), notes


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
        assumed_count = 0
        invalid_count = 0
        for e in matched_exps:
            if e.get("is_assumed"):
                assumed_count += 1
            if e.get("has_invalid_values"):
                invalid_count += 1
            habitat_o2.extend(all_o2_values(e, habitat_only=True))
            if e.get("o2_role") == "oxidizer_stream" or e.get("flame_type") == "inverse":
                inverse_o2.extend(all_o2_values(e))
            pressures.extend(all_pressure_values(e))

        study = study_level_for(psi_id)
        if study.get("o2_pct_values"):
            habitat_o2.extend(study["o2_pct_values"])
        if study.get("pressure_atm_values"):
            pressures.extend(study["pressure_atm_values"])
        habitat_o2 = merge_unique(habitat_o2)
        inverse_o2 = merge_unique(inverse_o2)
        pressures = merge_unique(pressures)

        fuels = sorted({
            e.get("fuel_material_normalized") or e.get("fuel_material")
            for e in matched_exps
            if e.get("fuel_material_normalized") or e.get("fuel_material")
        })
        phases = sorted({e.get("fuel_phase") for e in matched_exps if e.get("fuel_phase")})

        o2_min = min(habitat_o2) if habitat_o2 else None
        o2_max = max(habitat_o2) if habitat_o2 else None
        habitat_max = max(habitat_o2) if habitat_o2 else None
        p_min = min(pressures) if pressures else None
        p_max = max(pressures) if pressures else None

        covers_elevated_o2 = any(o >= 26.5 for o in habitat_o2)
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
        include_in_solver = psi_id not in ATMOSPHERE_SOLVER_EXCLUDE
        moon_base_applicable = bool(
            include_in_solver
            and (covers_moon_cabin_o2 or crew_materials or covers_reduced_pressure)
        )
        moon_base_score, moon_notes = compute_moon_base_score(
            inv, matched_exps, habitat_o2, pressures
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
            "moon_base_score": moon_base_score,
            "moon_base_score_notes": moon_notes,
            "moon_base_applicable": moon_base_applicable,
            "include_in_atmosphere_solver": include_in_solver,
            "solver_exclude_reason": ATMOSPHERE_SOLVER_EXCLUDE.get(psi_id),
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
            "study_level_conditions": study or None,
            "assumed_experiment_count": assumed_count,
            "invalid_experiment_count": invalid_count,
            "experiment_count": len(matched_exps),
            "reports_count": len(matched_reports),
            "reports": [report_stub(r) for r in matched_reports],
            "sample_experiments": matched_exps[:15],
        }
        master_investigations.append(record)

    master_investigations.sort(key=lambda x: x["relevance_score"], reverse=True)
    moon_ranked = sorted(
        [inv for inv in master_investigations if inv.get("include_in_atmosphere_solver")],
        key=lambda x: (x.get("moon_base_score") is not None, x.get("moon_base_score") or 0),
        reverse=True,
    )

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
        "moon_base_ranking": [
            {
                "rank": i + 1,
                "psi_id": inv["psi_id"],
                "acronym": inv["acronym"],
                "moon_base_score": inv["moon_base_score"],
                "notes": inv.get("moon_base_score_notes") or [],
                "covers_moon_cabin_o2": inv.get("covers_moon_cabin_o2"),
                "covers_reduced_pressure": inv.get("covers_reduced_pressure"),
                "assumed_experiment_count": inv.get("assumed_experiment_count"),
                "pressure_status": (inv.get("study_level_conditions") or {}).get("pressure_status"),
            }
            for i, inv in enumerate(moon_ranked)
        ],
        "investigations": master_investigations,
    }
    dump_json(processed_dir / "knowledge_base.json", kb)
    print(f"Master Knowledge Base saved to: {processed_dir / 'knowledge_base.json'}")
    print("Moon-base ranking (atmosphere solver):")
    for row in kb["moon_base_ranking"][:8]:
        print(f"  {row['rank']}. {row['psi_id']} {row['acronym']} score={row['moon_base_score']}")

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
        moon_base_score REAL,
        moon_base_applicable INTEGER,
        include_in_atmosphere_solver INTEGER,
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
        is_assumed INTEGER,
        has_invalid_values INTEGER,
        include_in_atmosphere_solver INTEGER,
        condition_level TEXT,
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
            """INSERT INTO investigations VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                inv["psi_id"], inv["acronym"], inv["title"], inv["pillar"],
                inv.get("subresearch_area"), inv["hardware"], inv["hardware_group"],
                inv["relevance_score"], inv.get("moon_base_score"),
                int(inv["moon_base_applicable"]),
                int(inv.get("include_in_atmosphere_solver", True)),
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
                flow_velocity_source, flow_direction, flow_is_assumed, is_assumed, has_invalid_values,
                include_in_atmosphere_solver, condition_level, burn_time_s, outcome, outcome_category,
                experiment_context, gravity_level, diluent, flame_type
            ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                exp.get("experiment_id"), exp.get("investigation_id"), exp.get("investigation_acronym"),
                exp.get("source_test_id"), exp.get("replicate"), exp.get("source_row_index"),
                exp.get("fuel_material"), exp.get("fuel_material_normalized"), exp.get("fuel_phase"),
                exp.get("fuel_geometry"), exp.get("o2_concentration_pct"), exp.get("o2_source"),
                int(bool(exp.get("o2_is_assumed"))), exp.get("pressure_atm"), exp.get("pressure_source"),
                int(bool(exp.get("pressure_is_assumed"))), exp.get("flow_velocity_cm_s"),
                exp.get("flow_velocity_source"), exp.get("flow_direction"),
                int(bool(exp.get("flow_is_assumed"))), int(bool(exp.get("is_assumed"))),
                int(bool(exp.get("has_invalid_values"))),
                int(bool(exp.get("include_in_atmosphere_solver", True))),
                exp.get("condition_level"), exp.get("burn_time_s"), exp.get("outcome"),
                exp.get("outcome_category"), exp.get("experiment_context"), exp.get("gravity_level"),
                exp.get("diluent"), exp.get("flame_type"),
            ),
        )
    conn.commit()
    conn.close()
    print(f"SQLite database generated at: {db_out}")


if __name__ == "__main__":
    main()
