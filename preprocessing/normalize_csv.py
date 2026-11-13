import re
from collections import defaultdict

import pandas as pd

from utils import (
    BASE_DIR,
    OUTPUT_DIR,
    STUDY_LEVEL_CONDITIONS,
    classify_outcome,
    clean_val,
    dump_json,
    ensure_output_dir,
    finalize_experiment_record,
    infer_geometry_from_material,
    jsonable,
    normalize_fuel_name,
    parse_num,
    parse_num_list,
    row_to_dict,
)


def read_csv_safe(file_path):
    last_err: Exception | None = None
    for enc in ["utf-8-sig", "utf-8", "latin1", "cp1252", "iso-8859-1"]:
        try:
            df = pd.read_csv(file_path, encoding=enc)
            df.columns = [str(c).replace("\ufeff", "").strip() for c in df.columns]
            return df
        except Exception as exc:
            last_err = exc
            continue
    if last_err is not None:
        raise last_err
    raise RuntimeError(f"Failed to read CSV at {file_path}")


def col_lookup(columns, *needles_groups):
    cols = list(columns)
    lowered = {c: c.lower() for c in cols}
    for needles in needles_groups:
        if isinstance(needles, str):
            needles = (needles,)
        for c, low in lowered.items():
            if all(n.lower() in low for n in needles):
                return c
    return None


def getv(row, *needles_groups):
    name = col_lookup(row.index, *needles_groups)
    if name is None:
        return None
    return row.get(name)


def mole_frac_to_pct(val):
    num = parse_num(val)
    if num is None:
        return None
    if num <= 1.0:
        return round(num * 100.0, 2)
    if num > 100:
        while num > 100:
            num = num / 100.0
        return round(num, 2)
    return round(num, 2)


def make_experiment_record(
    investigation_id,
    investigation_acronym,
    source_test_id,
    replicate_tracker,
    source_row_index,
    fuel_material,
    fuel_phase,
    fuel_geometry,
    o2_pct,
    o2_source,
    o2_is_assumed,
    pressure_atm,
    pressure_source,
    pressure_is_assumed,
    flow_velocity_cm_s,
    flow_velocity_source,
    flow_direction,
    burn_time_s,
    outcome,
    experiment_context,
    raw_dict,
    **extra,
):
    key = (investigation_id, source_test_id)
    replicate_tracker[key] += 1
    replicate = replicate_tracker[key]
    safe_test_id = re.sub(r"[^A-Za-z0-9_.-]+", "_", str(source_test_id).strip())
    experiment_id = f"{investigation_id}-{safe_test_id}-R{replicate}"

    rec = {
        "experiment_id": experiment_id,
        "investigation_id": investigation_id,
        "investigation_acronym": investigation_acronym,
        "source_test_id": str(source_test_id),
        "replicate": replicate,
        "source_row_index": int(source_row_index),
        "fuel_material": fuel_material,
        "fuel_material_normalized": extra.pop(
            "fuel_material_normalized", normalize_fuel_name(fuel_material)
        ),
        "fuel_phase": fuel_phase,
        "fuel_geometry": fuel_geometry,
        "o2_concentration_pct": o2_pct,
        "o2_values": extra.pop("o2_values", [o2_pct] if o2_pct is not None else []),
        "o2_source": o2_source,
        "o2_is_assumed": o2_is_assumed,
        "pressure_atm": pressure_atm,
        "pressure_values": extra.pop(
            "pressure_values", [pressure_atm] if pressure_atm is not None else []
        ),
        "pressure_source": pressure_source,
        "pressure_is_assumed": pressure_is_assumed,
        "flow_velocity_cm_s": flow_velocity_cm_s,
        "flow_values": extra.pop(
            "flow_values",
            [flow_velocity_cm_s] if flow_velocity_cm_s is not None else [],
        ),
        "flow_velocity_source": flow_velocity_source,
        "flow_direction": flow_direction,
        "flow_is_assumed": extra.pop("flow_is_assumed", False),
        "burn_time_s": burn_time_s,
        "outcome": outcome,
        "outcome_category": extra.pop("outcome_category", classify_outcome(outcome)),
        "experiment_context": experiment_context,
        "gravity_level": extra.pop("gravity_level", "microgravity"),
        "diluent": extra.pop("diluent", None),
        "raw_details": jsonable(raw_dict),
    }
    rec.update(extra)
    return finalize_experiment_record(rec)


def normalize_csv_files():
    ensure_output_dir()
    all_experiments = []
    replicate_tracker = defaultdict(int)
    base_dir = BASE_DIR

    # 1. SAFFIRE-1
    f = base_dir / "98 SAFFIRE-1" / "PSI-98_Experimental table_SAFFIRE-1.csv"
    if f.exists():
        df = read_csv_safe(f)
        for idx, r in df.iterrows():
            sample_num = clean_val(getv(r, "Sample Number"))
            material = clean_val(getv(r, "Material"))
            if not sample_num or (material and "pre-test" in material.lower()):
                continue
            o2_vals = parse_num_list(getv(r, "Percent O2"))
            o2_val = sum(o2_vals) / len(o2_vals) if o2_vals else parse_num(getv(r, "Percent O2"))
            thick = clean_val(getv(r, "Sample Thickness"))
            length = clean_val(getv(r, "Sample Length"))
            width = clean_val(getv(r, "Sample Width"))
            all_experiments.append(make_experiment_record(
                "PSI-98", "SAFFIRE-I", sample_num, replicate_tracker, idx,
                material, "solid",
                f"sheet ({thick} cm thick x {length} cm x {width} cm)",
                o2_val, "reported in experimental table under 'Percent O2'", False,
                None, "not reported in source data", False,
                parse_num(getv(r, "Air Flow")), "reported in experimental table under 'Air Flow (cm/s)'",
                clean_val(getv(r, "Flow Direction")),
                parse_num(getv(r, "Burn Time")),
                f"Burned for {parse_num(getv(r, 'Burn Time'))} s" if parse_num(getv(r, "Burn Time")) is not None else None,
                "large-scale vehicle fire test",
                row_to_dict(r),
                ignition_power_w=parse_num(getv(r, "Ignition Power")),
                ignition_time_s=parse_num(getv(r, "Ignition Time")),
                o2_values=o2_vals or ([o2_val] if o2_val is not None else []),
            ))

    # 2. SAFFIRE-2
    f = base_dir / "99 SAFFIRE-2" / "PSI-99_Experimental table_SAFFIRE-2.csv"
    if f.exists():
        df = read_csv_safe(f)
        ug_burn = col_lookup(df.columns, ("-g Burn Length",), ("? -g Burn",))
        ug_spread = col_lookup(df.columns, ("-g Spread Length",))
        g1_burn = col_lookup(df.columns, ("1-g Burn Length",))
        g1_spread = col_lookup(df.columns, ("1-g Spread Rate",))
        thick_col = col_lookup(df.columns, ("Samle Thickness",), ("Sample Thickness",))
        for idx, r in df.iterrows():
            sample_num = clean_val(getv(r, "Sample Number"))
            if not sample_num:
                continue
            burn_raw = clean_val(getv(r, "Burn Time"))
            all_experiments.append(make_experiment_record(
                "PSI-99", "SAFFIRE-II", sample_num, replicate_tracker, idx,
                clean_val(getv(r, "Material")), "solid",
                f"sample ({clean_val(r.get(thick_col) if thick_col else None)} x {clean_val(getv(r, 'Sample Width'))} x {clean_val(getv(r, 'Sample Length'))})",
                parse_num(getv(r, "Percent O2")), "reported in experimental table under 'Percent O2 (Note 1)'", False,
                None, "not reported in source data", False,
                parse_num(getv(r, "Air Flow")), "reported in experimental table under 'Air Flow (cm/s)'",
                clean_val(getv(r, "Flow Direction")),
                parse_num(burn_raw), burn_raw,
                "material flammability screening test",
                row_to_dict(r),
                gravity_level="microgravity (with 1-g comparison)",
                ignition_power_w=parse_num(getv(r, "Ignition Power")),
                ignition_time_s=parse_num(getv(r, "Ignition Time")),
                microg_burn_length=clean_val(r.get(ug_burn) if ug_burn else None),
                microg_spread_length=clean_val(r.get(ug_spread) if ug_spread else None),
                normalg_burn_length=clean_val(r.get(g1_burn) if g1_burn else None),
                normalg_spread_rate=clean_val(r.get(g1_spread) if g1_spread else None),
            ))

    # 3. SAFFIRE-3
    f = base_dir / "100 SAFFIRE-3" / "PSI-100_Experimental table_SAFFIRE-3.csv"
    if f.exists():
        df = read_csv_safe(f)
        for idx, r in df.iterrows():
            sample_num = clean_val(getv(r, "Sample Number"))
            if not sample_num:
                continue
            all_experiments.append(make_experiment_record(
                "PSI-100", "SAFFIRE-III", sample_num, replicate_tracker, idx,
                clean_val(getv(r, "Material")), "solid",
                f"sheet ({clean_val(getv(r, 'Sample Thickness'))} x {clean_val(getv(r, 'Sample Width'))} x {clean_val(getv(r, 'Sample Length'))})",
                None, "not reported in experimental table (O2 sensors were used in flight; values not in this CSV)", False,
                None, "not reported in source data", False,
                parse_num(getv(r, "Air Flow")), "reported in experimental table under 'Air Flow'",
                clean_val(getv(r, "Direction")),
                None, None,
                "large-scale flame spread test",
                row_to_dict(r),
            ))

    # 4. BASS
    f = base_dir / "26 BASS" / "PSI-26_Experimental table_BASS.csv"
    if f.exists():
        df = read_csv_safe(f)
        for idx, r in df.iterrows():
            test_num = clean_val(getv(r, "Test #"))
            sample_num = clean_val(getv(r, "Sample #"))
            as_run = clean_val(getv(r, "As Run Test #"))
            if not test_num and not as_run:
                continue
            material = clean_val(getv(r, "Fuel Sample Material"))
            source_id = f"BASS-T{test_num}-S{sample_num}" if test_num else f"BASS-Run{as_run}"
            flow_dir = None
            low = (material or "").lower()
            if "oppos" in low:
                flow_dir = "opposed"
            elif "concurr" in low:
                flow_dir = "concurrent"
            elif "wake" in low:
                flow_dir = "wake"
            all_experiments.append(make_experiment_record(
                "PSI-26", "BASS", source_id, replicate_tracker, idx,
                material, "solid",
                infer_geometry_from_material(material, "solid sample"),
                None, "not reported in experimental table; ISA-Tab notes airflow up to 40 cm/s and N2 suppressant", False,
                None, "not reported in source data", False,
                None, "not reported in experimental table",
                flow_dir, None, None,
                "microgravity solid burning and suppression test",
                row_to_dict(r),
            ))

    # 5. BASS-II
    f = base_dir / "25 BASS-2" / "PSI-25_Experimental table_BASS-II.csv"
    if f.exists():
        df = read_csv_safe(f)
        for idx, r in df.iterrows():
            test_num = clean_val(getv(r, "Test #"))
            if not test_num:
                continue
            material = clean_val(getv(r, "Fuel Sample Material"))
            flow_dir = None
            low = (material or "").lower()
            if "oppos" in low:
                flow_dir = "opposed"
            elif "concurr" in low:
                flow_dir = "concurrent"
            all_experiments.append(make_experiment_record(
                "PSI-25", "BASS-II", f"BASS2-{test_num}", replicate_tracker, idx,
                material, "solid",
                infer_geometry_from_material(material, "PMMA/film/slab"),
                parse_num(getv(r, "Calibrated  initial O2", "initial O2")),
                "reported in experimental table under 'Calibrated initial O2 % by vol'", False,
                None, "not reported in source data", False,
                parse_num(getv(r, "Air display")),
                "reported in experimental table under 'Air display' (fan-driven duct; not labeled cm/s)",
                flow_dir, None, None,
                "opposed/concurrent flame spread & extinction test",
                row_to_dict(r),
                investigator=clean_val(getv(r, "PI")),
                o2_final_pct=parse_num(getv(r, "Calibrated final O2", "final O2 %")),
                co2_initial_pct=parse_num(getv(r, "Initial CO2")),
                co2_final_pct=parse_num(getv(r, "Final CO2")),
                co_initial_ppm=parse_num(getv(r, "Initial CO (ppm)", "Initial CO (")),
                co_final_ppm=parse_num(getv(r, "Final CO (ppm)", "Final CO (")),
                radiometer_gain=clean_val(getv(r, "Radiometer")),
                flow_direction_note="opposed and concurrent both used; direction not a CSV column",
            ))

    # 6. ACME BRE
    f = base_dir / "20 ACME BRE" / "PSI-20_Experimental table_ACME BRE.csv"
    if f.exists():
        df = read_csv_safe(f)
        for idx, r in df.iterrows():
            if pd.isna(getv(r, "Date")) or pd.isna(getv(r, "Fuel Bottle")):
                continue
            month_str = clean_val(getv(r, "Month")) or ""
            date_str = clean_val(getv(r, "Date")) or ""
            flames_ignited = clean_val(getv(r, "Flames Ignited"))
            burner_size = clean_val(getv(r, "Burner Size"))
            o2_tokens = parse_num_list(getv(r, "Oxygen Conc"))
            if not o2_tokens:
                o2_tokens = [None]
            study_p = STUDY_LEVEL_CONDITIONS["PSI-20"]
            for tok in o2_tokens:
                val = tok
                if val is not None and val > 100:
                    val = val / 100.0
                source_test_id = f"BRE-{month_str}{date_str}-O2_{val if val is not None else 'NA'}"
                all_experiments.append(make_experiment_record(
                    "PSI-20", "ACME BRE", source_test_id, replicate_tracker, idx,
                    clean_val(getv(r, "Fuel Bottle")), "solid-emulated (gas burner)",
                    f"porous burner {burner_size} mm",
                    val, "reported in experimental table under 'Oxygen Conc (percent)'", False,
                    None,
                    study_p["pressure_source"],
                    True,
                    0.0, "quiescent chamber environment (inferred; airflow not reported in CSV)",
                    "quiescent", None,
                    f"{flames_ignited} flames ignited that day (day total, not per O2 condition)",
                    "burning rate emulation in quiescent ambient",
                    row_to_dict(r),
                    pressure_values=list(study_p["pressure_atm_values"]),
                    pressure_condition_level="study",
                    pressure_status=study_p["pressure_status"],
                    condition_level="mixed",
                    flow_is_assumed=True,
                    diluent="N2",
                    day_flames_ignited=parse_num(flames_ignited),
                ))

    # 7. FLEX
    f = base_dir / "69 FLEX" / "PSI-69_Experimental table_FLEX.csv"
    if f.exists():
        df = read_csv_safe(f)
        for idx, r in df.iterrows():
            flex_test_num = clean_val(getv(r, "FLEX Test #"))
            if not flex_test_num:
                continue
            o2_mol = parse_num(getv(r, "O initial ambient"))
            o2_pct = round(o2_mol * 100.0, 2) if o2_mol is not None else None
            p_mmhg = parse_num(getv(r, "Ambient pressure"))
            p_atm = round(p_mmhg / 760.0, 4) if p_mmhg is not None else None
            n_mol = parse_num(getv(r, "N initial"))
            co_mol = parse_num(getv(r, "CO initial"))
            he_mol = parse_num(getv(r, "He initial"))
            dil_parts = []
            if n_mol:
                dil_parts.append(f"N2={n_mol}")
            if co_mol:
                dil_parts.append(f"CO2={co_mol} (source column labeled CO)")
            if he_mol:
                dil_parts.append(f"He={he_mol}")
            outcome = clean_val(getv(r, "Test end"))
            all_experiments.append(make_experiment_record(
                "PSI-69", "FLEX", f"FLEX-{flex_test_num}", replicate_tracker, idx,
                clean_val(getv(r, "Fuel")), "liquid",
                f"droplet (d0={clean_val(getv(r, 'Droplet initial diameter'))} mm)",
                o2_pct, "converted from reported 'O initial ambient composition; mole fraction'", False,
                p_atm,
                f"converted from reported pressure of {p_mmhg} mmHg (1 atm = 760 mmHg)" if p_mmhg is not None else "not reported",
                False,
                0.0, "quiescent chamber environment (inferred; airflow not reported in CSV)", "quiescent",
                parse_num(getv(r, "Burn time")), outcome,
                "droplet combustion and extinction test",
                row_to_dict(r),
                flow_is_assumed=True,
                diluent="; ".join(dil_parts) if dil_parts else None,
                n2_mole_fraction=n_mol,
                co2_mole_fraction=co_mol,
                he_mole_fraction=he_mol,
                extinction_diameter_mm=parse_num(getv(r, "extinction diameter")),
                burning_rate=parse_num(getv(r, "Burning rate")),
            ))

    # 8. CFI
    f = base_dir / "39 CFI" / "PSI-39_Experimental table_CFI.csv"
    if f.exists():
        df = read_csv_safe(f).drop_duplicates().reset_index(drop=True)
        for idx, r in df.iterrows():
            flex_num = clean_val(getv(r, "Flex Number"))
            if not flex_num:
                continue
            o2_raw = parse_num(getv(r, "Oxygen"))
            o2_pct = round(o2_raw * 100.0, 2) if (o2_raw is not None and o2_raw <= 1.0) else o2_raw
            p_str = clean_val(getv(r, "Pressure"))
            he_mol = parse_num(getv(r, "Helium"))
            n_mol = parse_num(getv(r, "Nitrogen"))
            fiber = clean_val(getv(r, "Fiber"))
            dil_parts = []
            if n_mol:
                dil_parts.append(f"N2={n_mol}")
            if he_mol:
                dil_parts.append(f"He={he_mol}")
            all_experiments.append(make_experiment_record(
                "PSI-39", "CFI", f"CFI-{flex_num}", replicate_tracker, idx,
                clean_val(getv(r, "Fuel")), "liquid",
                "droplet with fiber support" if (fiber or "").lower() == "yes" else "free droplet",
                o2_pct, "converted from reported mole fraction under 'Oxygen'", False,
                parse_num(p_str),
                f"reported in experimental table under 'Pressure' as '{p_str}'" if p_str else "not reported",
                False,
                0.0, "quiescent chamber environment (inferred; airflow not reported in CSV)", "quiescent",
                None, None,
                "cool flames investigation with liquid droplets",
                row_to_dict(r),
                flow_is_assumed=True,
                diluent="; ".join(dil_parts) if dil_parts else None,
            ))

    # 9. CFI-G Normal
    f = base_dir / "159 ACME-CFI-G" / "expirement table" / "PSI-159_Experimental table_CFI-G_Normal Flames.csv"
    if f.exists():
        df = read_csv_safe(f)
        for idx, r in df.iterrows():
            test_id = clean_val(getv(r, "Test"))
            if not test_id:
                continue
            xo2_raw = getv(r, "XO2 before")
            if xo2_raw is None or pd.isna(xo2_raw):
                xo2_raw = getv(r, "XO2  after", "XO2 after")
            o2_pct = mole_frac_to_pct(xo2_raw)
            p_bar = parse_num(getv(r, "approx p"))
            p_atm = round(p_bar * 0.986923, 4) if p_bar is not None else None
            hot_ign = clean_val(getv(r, "Hot ignition"))
            self_ext = clean_val(getv(r, "Self-ext"))
            parts = []
            if hot_ign:
                parts.append(f"Hot ignition: {hot_ign}")
            if self_ext:
                parts.append(f"Extinction: {self_ext}")
            all_experiments.append(make_experiment_record(
                "PSI-159", "ACME CFI-G", f"CFIG-Norm-{test_id}", replicate_tracker, idx,
                clean_val(getv(r, "Fuel")), "gas", "normal spherical burner",
                o2_pct, "converted from reported 'XO2' mole fraction (Normal Flames, before-test preferred)", False,
                p_atm,
                f"converted from reported {p_bar} bar (1 bar = 0.986923 atm)" if p_bar is not None else "not reported",
                False, None, "not reported in experimental table", "normal flow",
                parse_num(getv(r, "burn time")), "; ".join(parts) if parts else None,
                "spherical normal cool diffusion flame test",
                row_to_dict(r),
                flame_type="normal",
                o2_role="chamber_or_reactant",
                cool_flame=clean_val(getv(r, "Cool flame")),
                zst=parse_num(getv(r, "Zst")),
            ))

    # 10. CFI-G Inverse
    f = base_dir / "159 ACME-CFI-G" / "expirement table" / "PSI-159_Experimental table_CFI-G_Inverse Flames.csv"
    if f.exists():
        df = read_csv_safe(f)
        for idx, r in df.iterrows():
            test_id = clean_val(getv(r, "Test"))
            if not test_id:
                continue
            o2_pct = mole_frac_to_pct(getv(r, "XO2"))
            p_bar = parse_num(getv(r, "approx p"))
            p_atm = round(p_bar * 0.986923, 4) if p_bar is not None else None
            hot_ign = clean_val(getv(r, "Hot ignition"))
            self_ext = clean_val(getv(r, "Self -ext", "Self-ext"))
            comments = clean_val(getv(r, "Comments"))
            parts = []
            if hot_ign:
                parts.append(f"Hot ignition: {hot_ign}")
            if self_ext and self_ext != "-":
                parts.append(f"Extinction: {self_ext}")
            if comments:
                parts.append(comments)
            all_experiments.append(make_experiment_record(
                "PSI-159", "ACME CFI-G", f"CFIG-Inv-{test_id}", replicate_tracker, idx,
                clean_val(getv(r, "Fuel")), "gas", "inverse spherical burner",
                o2_pct, "converted from reported 'XO2' mole fraction (Inverse Flames; oxidizer-stream O2, not cabin air)", False,
                p_atm,
                f"converted from reported {p_bar} bar (1 bar = 0.986923 atm)" if p_bar is not None else "not reported",
                False, None, "not reported in experimental table", "inverse flow",
                parse_num(getv(r, "burn time")), "; ".join(parts) if parts else None,
                "spherical inverse cool diffusion flame test",
                row_to_dict(r),
                flame_type="inverse",
                o2_role="oxidizer_stream",
                o2_cabin_comparable=False,
                o2_report_note=(
                    "CFI-G final report Table 2 confirms inverse-flame fluent bottles of 85% O2 with N2; "
                    "this is oxidizer-stream oxygen, not cabin air, and must not be used as a habitat O2 match."
                ),
                zst=parse_num(getv(r, "Zst")),
            ))

    # 11. SPICE
    f = base_dir / "107 SPICE" / "exp" / "PSI-107_Experimental table_Spice.csv"
    if f.exists():
        df = read_csv_safe(f)
        # GMT times are written both as 14:37:08 and 14.37.08; unify before dropping duplicates
        for col in df.columns:
            if "GMT" in col:
                df[col] = df[col].map(
                    lambda v: re.sub(r"[.]", ":", v) if isinstance(v, str) else v
                )
        df = df.drop_duplicates().reset_index(drop=True)
        for idx, r in df.iterrows():
            fuel = clean_val(getv(r, "Fuel"))
            if not fuel:
                continue
            gmt_date = clean_val(getv(r, "GMT date")) or ""
            gmt_ign = clean_val(getv(r, "GMT ignition")) or ""
            nozzle = clean_val(getv(r, "Nozzle"))
            source_id = f"SPICE-GMT{gmt_date}-{gmt_ign}" if gmt_ign else f"SPICE-Row{idx}"
            all_experiments.append(make_experiment_record(
                "PSI-107", "SPICE", source_id, replicate_tracker, idx,
                fuel, "gas", f"co-flow nozzle ({nozzle} mm)",
                None, "not reported in experimental table", False,
                None, "not reported in source data", False,
                parse_num(getv(r, "Air Rate")), "reported in experimental table under 'Air Rate (cm/s)'",
                "coflow", None, None,
                "laminar smoke point and flame length test in coflow",
                row_to_dict(r),
                fuel_rate_sccm=parse_num(getv(r, "Fuel Rate (sccm)")),
            ))

    # 12. SAME
    f = base_dir / "102 SAME" / "PSI-102_Experimental table_SAME.csv"
    if f.exists():
        df = read_csv_safe(f)
        for idx, r in df.iterrows():
            sample_num = clean_val(getv(r, "Sample #"))
            if not sample_num:
                continue
            loss_rate = clean_val(getv(r, "Weight loss"))
            aging_dur = clean_val(getv(r, "Aging Duration"))
            parts = []
            if loss_rate:
                parts.append(f"Weight loss rate: {loss_rate} mg/min")
            if aging_dur:
                parts.append(f"Aging: {aging_dur} min")
            all_experiments.append(make_experiment_record(
                "PSI-102", "SAME", f"SAME-S{sample_num}", replicate_tracker, idx,
                clean_val(getv(r, "Sample Material")), "aerosol/pyrolysis smoke",
                "smoldering source",
                None, "not reported in experimental table", False,
                None, "not reported in source data", False,
                parse_num(getv(r, "Air Flow")),
                "reported in experimental table under 'Air Flow (cm/s)'" if parse_num(getv(r, "Air Flow")) is not None else "not reported",
                "duct flow", None, "; ".join(parts) if parts else None,
                "smoke particle size and detector response test",
                row_to_dict(r),
                measurement_type="smoke_particle_size",
            ))

    # 13. SAME-R
    f = base_dir / "101 SAME-R" / "PSI-101_Experimental table_SAME-R.csv"
    if f.exists():
        df = read_csv_safe(f)
        for idx, r in df.iterrows():
            test_num = clean_val(getv(r, "SAME Test #"))
            sample_type = clean_val(getv(r, "Sample Type"))
            if not test_num:
                continue
            source_id = f"SAMER-{sample_type}-T{test_num}" if sample_type else f"SAMER-T{test_num}"
            all_experiments.append(make_experiment_record(
                "PSI-101", "SAME-R", source_id, replicate_tracker, idx,
                sample_type, "aerosol/pyrolysis smoke", "smoldering wire/foam",
                None, "not reported in experimental table", False,
                None, "not reported in source data", False,
                parse_num(getv(r, "Inlet velocity")), "reported in experimental table under 'Inlet velocity (cm/s)'",
                "duct flow", parse_num(getv(r, "Duration")), clean_val(getv(r, "Description")),
                "smoke particle size reflight measurement",
                row_to_dict(r),
                measurement_type="smoke_particle_size",
            ))

    # 14. SLICE
    f = base_dir / "106 SLICE" / "PSI-106_Experimental table_Slice.csv"
    if f.exists():
        df = read_csv_safe(f)
        for idx, r in df.iterrows():
            fuel_raw = clean_val(getv(r, "Fuel Type"))
            test_date = clean_val(getv(r, "Test Date"))
            if not fuel_raw and not test_date:
                continue
            comment = None
            fuel = fuel_raw
            if fuel_raw and "including" in fuel_raw.lower():
                bits = re.split(r"\sincluding\s", fuel_raw, maxsplit=1, flags=re.I)
                fuel = bits[0].strip()
                comment = bits[1].strip() if len(bits) > 1 else None
            all_experiments.append(make_experiment_record(
                "PSI-106", "SLICE", f"SLICE-Row{idx}", replicate_tracker, idx,
                fuel, "gas", "coflow burner",
                None, "not reported in experimental table", False,
                None, "not reported in source data", False,
                None, "not reported in experimental table", "coflow",
                None, comment,
                "laminar diffusion flame structure and liftoff test",
                row_to_dict(r),
            ))

    # 15. E-FIELD
    f = base_dir / "22 ACME E-FIELD Flames" / "PSI-22_Experimental table_ACME E-FIELD Flames.csv"
    if f.exists():
        df = read_csv_safe(f)
        for idx, r in df.iterrows():
            date_val = clean_val(getv(r, "Date"))
            test_day = clean_val(getv(r, "Test Day"))
            fuel_bottle = clean_val(getv(r, "Fuel Bottle"))
            if not date_val and not fuel_bottle:
                continue
            flames = clean_val(getv(r, "Flames Ignited"))
            burner_type = clean_val(getv(r, "Test Type"))
            polarity = clean_val(getv(r, "Mesh Polarity"))
            source_id = f"EFIELD-Day{test_day}-Row{idx}" if test_day else f"EFIELD-Row{idx}"
            all_experiments.append(make_experiment_record(
                "PSI-22", "ACME E-FIELD Flames", source_id, replicate_tracker, idx,
                fuel_bottle, "gas",
                f"{burner_type} (polarity: {polarity})",
                None, "not reported in experimental table", False,
                None, "not reported in source data", False,
                None, "not reported in experimental table", "coflow/jet",
                None, f"{flames} flames ignited" if flames else None,
                "electric-field effect on laminar diffusion flame; partial-gravity proxy via ion-driven convection",
                row_to_dict(r),
                gravity_level="partial-emulated (electric field)",
                fuel_concentration=clean_val(getv(r, "Fuel Conc")),
                electric_field_polarity=polarity,
                partial_g_proxy=True,
            ))

    # 16. FLEX-2 parameter matrix — keep one row per fuel, store ranges
    f = base_dir / "68 FLEX-2" / "PSI-68_Experimental table_Flex2.csv"
    if f.exists():
        df = read_csv_safe(f)
        for idx, r in df.iterrows():
            fuel = clean_val(getv(r, "Sample (Fuel Type)", "Fuel Type"))
            if not fuel:
                continue
            study = STUDY_LEVEL_CONDITIONS["PSI-68"]
            o2_mols = parse_num_list(getv(r, "Oxygen Mole Fraction"))
            o2_pcts = [round(x * 100.0, 2) if x <= 1.5 else round(x, 2) for x in o2_mols] or list(study["o2_pct_values"])
            p_vals = parse_num_list(getv(r, "Ambient Pressure")) or list(study["pressure_atm_values"])
            flow_vals = parse_num_list(getv(r, "Flow Velocity")) or list(study["flow_values"])
            gas_mix = clean_val(getv(r, "Ambient Gas Mixture"))
            drop_diam = clean_val(getv(r, "Initial Droplet Diameter"))
            all_experiments.append(make_experiment_record(
                "PSI-68", "FLEX-2", f"FLEX2-{fuel.replace(' ', '_')}", replicate_tracker, idx,
                fuel, "liquid",
                f"droplet (d0 range: {drop_diam} mm, gas: {gas_mix})",
                None,
                study["o2_source"],
                False,
                None,
                study["pressure_source"],
                False,
                None,
                study["flow_source"],
                "forced flow",
                None, None,
                "droplet combustion parameter test matrix (not one executed test per cell)",
                row_to_dict(r),
                o2_values=o2_pcts,
                pressure_values=p_vals,
                flow_values=flow_vals,
                diluent=gas_mix,
                is_parameter_matrix=True,
                condition_level="study",
                o2_condition_level="study",
                pressure_condition_level="study",
                pressure_status=study["pressure_status"],
                o2_status=study["o2_status"],
            ))

    # 17. DAFT
    f = base_dir / "47 DAFT _ DAFT-2" / "PSI-47_Experimental table_DAFT.csv"
    if f.exists():
        df = read_csv_safe(f)
        for idx, r in df.iterrows():
            session = clean_val(getv(r, "Session Name"))
            if not session:
                continue
            material = clean_val(getv(r, "Sample Material"))
            location = clean_val(getv(r, "Sampled Location"))
            hardware = clean_val(getv(r, "Hardware Description"))
            all_experiments.append(make_experiment_record(
                "PSI-47", "DAFT / DAFT-2", f"DAFT-{session}", replicate_tracker, idx,
                material, "aerosol/dust",
                f"{hardware}; sampled at: {location}",
                None, "not reported in experimental table", False,
                None, "not reported in source data", False,
                None, "not reported in experimental table", None,
                None, f"Sampled at {location}",
                "dust and aerosol measurement feasibility test (P-Trak/DustTrak reused from smoke-detection lineage)",
                row_to_dict(r),
                measurement_type="dust_aerosol",
                related_hardware_note="instrument lineage shared with SAME / SAME-R smoke diagnostics",
            ))

    print(f"\nTotal normalized experimental records: {len(all_experiments)}")
    assumed_n = sum(1 for e in all_experiments if e.get("is_assumed"))
    invalid_n = sum(1 for e in all_experiments if e.get("has_invalid_values"))
    excluded_n = sum(1 for e in all_experiments if not e.get("include_in_atmosphere_solver"))
    print(f"Assumed rows: {assumed_n}; invalid-value rows: {invalid_n}; excluded from solver: {excluded_n}")
    seen_ids = set()
    duplicate_ids = []
    for exp in all_experiments:
        eid = exp["experiment_id"]
        if eid in seen_ids:
            duplicate_ids.append(eid)
        seen_ids.add(eid)
    if duplicate_ids:
        raise ValueError(f"VALIDATION ERROR: Found {len(duplicate_ids)} duplicate experiment_id(s): {duplicate_ids[:10]}")
    print("VALIDATION PASSED: All experiment_id values are strictly unique and reproducible.")

    out_json = OUTPUT_DIR / "experiments_normalized.json"
    dump_json(out_json, all_experiments)
    print(f"Saved normalized experiments to {out_json}")


if __name__ == "__main__":
    normalize_csv_files()
