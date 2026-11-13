import os
import re
import glob
from collections import defaultdict
import pandas as pd
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_DIR = PROJECT_ROOT / "DATA" / "nasa final data"
OUTPUT_DIR = PROJECT_ROOT / "data_processed"

def clean_val(v):
    if pd.isna(v):
        return None
    s = str(v).strip()
    return s if s else None

def parse_num(v):
    if pd.isna(v) or v is None:
        return None
    s = str(v).replace("~", "").replace("atm", "").replace("bar", "").replace("cm/s", "").replace("s", "").replace("W", "").replace("mm", "").replace("cm", "").strip()
    try:
        if "-" in s and len(s.split("-")) == 2:
            parts = [float(p.strip()) for p in s.split("-") if p.strip()]
            if len(parts) == 2:
                return sum(parts) / 2.0
        return float(s)
    except:
        return None

def read_csv_safe(file_path):
    for enc in ['utf-8', 'latin1', 'cp1252', 'iso-8859-1']:
        try:
            return pd.read_csv(file_path, encoding=enc)
        except:
            continue
    return pd.read_csv(file_path, encoding='latin1')

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
    raw_dict
):
    key = (investigation_id, source_test_id)
    replicate_tracker[key] += 1
    replicate = replicate_tracker[key]
    
    # Deterministic clean experiment_id
    safe_test_id = re.sub(r'[^A-Za-z0-9_.-]+', '_', str(source_test_id).strip())
    experiment_id = f"{investigation_id}-{safe_test_id}-R{replicate}"
    
    return {
        "experiment_id": experiment_id,
        "investigation_id": investigation_id,
        "investigation_acronym": investigation_acronym,
        "source_test_id": str(source_test_id),
        "replicate": replicate,
        "source_row_index": int(source_row_index),
        "fuel_material": fuel_material,
        "fuel_phase": fuel_phase,
        "fuel_geometry": fuel_geometry,
        "o2_concentration_pct": o2_pct,
        "o2_source": o2_source,
        "o2_is_assumed": o2_is_assumed,
        "pressure_atm": pressure_atm,
        "pressure_source": pressure_source,
        "pressure_is_assumed": pressure_is_assumed,
        "flow_velocity_cm_s": flow_velocity_cm_s,
        "flow_velocity_source": flow_velocity_source,
        "flow_direction": flow_direction,
        "burn_time_s": burn_time_s,
        "outcome": outcome,
        "experiment_context": experiment_context,
        "raw_details": raw_dict
    }

def normalize_csv_files():
    base_dir = BASE_DIR
    out_json = OUTPUT_DIR / "experiments_normalized.json"
    
    all_experiments = []
    replicate_tracker = defaultdict(int)
    
    # -------------------------------------------------------------
    # 1. SAFFIRE-1 (PSI-98)
    # -------------------------------------------------------------
    f_saffire1 = base_dir / "98 SAFFIRE-1" / "PSI-98_Experimental table_SAFFIRE-1.csv"
    if f_saffire1.exists():
        df = read_csv_safe(f_saffire1)
        for idx, r in df.iterrows():
            sample_num = clean_val(r.get("Sample Number "))
            material = clean_val(r.get("Material"))
            if not sample_num or "pre-test" in str(material).lower():
                continue
            
            o2_val = parse_num(r.get("Percent O2"))
            burn_time = parse_num(r.get("Burn Time (s)"))
            flow_vel = parse_num(r.get("Air Flow (cm/s)"))
            
            all_experiments.append(make_experiment_record(
                investigation_id="PSI-98",
                investigation_acronym="SAFFIRE-I",
                source_test_id=sample_num,
                replicate_tracker=replicate_tracker,
                source_row_index=idx,
                fuel_material=material,
                fuel_phase="solid",
                fuel_geometry=f"sheet ({clean_val(r.get('Sample Thickness (cm)'))}x{clean_val(r.get('Sample Width (cm)'))}x{clean_val(r.get('Sample Length (cm)'))} cm)",
                o2_pct=o2_val,
                o2_source="reported in experimental table under 'Percent O2'",
                o2_is_assumed=False,
                pressure_atm=None,
                pressure_source="not reported in source data",
                pressure_is_assumed=False,
                flow_velocity_cm_s=flow_vel,
                flow_velocity_source="reported in experimental table under 'Air Flow (cm/s)'",
                flow_direction=clean_val(r.get("Flow Direction ")),
                burn_time_s=burn_time,
                outcome=f"Burned for {burn_time} s" if burn_time is not None else None,
                experiment_context="large-scale vehicle fire test",
                raw_dict=r.dropna().to_dict()
            ))

    # -------------------------------------------------------------
    # 2. SAFFIRE-2 (PSI-99)
    # -------------------------------------------------------------
    f_saffire2 = base_dir / "99 SAFFIRE-2" / "PSI-99_Experimental table_SAFFIRE-2.csv"
    if f_saffire2.exists():
        df = read_csv_safe(f_saffire2)
        for idx, r in df.iterrows():
            sample_num = clean_val(r.get("Sample Number"))
            if not sample_num:
                continue
            
            o2_val = parse_num(r.get("Percent O2 (Note 1)"))
            burn_time_raw = clean_val(r.get("Burn Time (s)"))
            burn_time_num = parse_num(burn_time_raw)
            flow_vel = parse_num(r.get("Air Flow (cm/s)"))
            
            all_experiments.append(make_experiment_record(
                investigation_id="PSI-99",
                investigation_acronym="SAFFIRE-II",
                source_test_id=sample_num,
                replicate_tracker=replicate_tracker,
                source_row_index=idx,
                fuel_material=clean_val(r.get("Material")),
                fuel_phase="solid",
                fuel_geometry=f"sample ({clean_val(r.get('Samle Thickness '))} x {clean_val(r.get('Sample Width (cm)'))} x {clean_val(r.get('Sample Length '))} cm)",
                o2_pct=o2_val,
                o2_source="reported in experimental table under 'Percent O2 (Note 1)'",
                o2_is_assumed=False,
                pressure_atm=None,
                pressure_source="not reported in source data",
                pressure_is_assumed=False,
                flow_velocity_cm_s=flow_vel,
                flow_velocity_source="reported in experimental table under 'Air Flow (cm/s)'",
                flow_direction=clean_val(r.get("Flow Direction")),
                burn_time_s=burn_time_num,
                outcome=burn_time_raw,
                experiment_context="material flammability screening test",
                raw_dict=r.dropna().to_dict()
            ))

    # -------------------------------------------------------------
    # 3. SAFFIRE-3 (PSI-100)
    # -------------------------------------------------------------
    f_saffire3 = base_dir / "100 SAFFIRE-3" / "PSI-100_Experimental table_SAFFIRE-3.csv"
    if f_saffire3.exists():
        df = read_csv_safe(f_saffire3)
        for idx, r in df.iterrows():
            sample_num = clean_val(r.get("Sample Number "))
            if not sample_num:
                continue
            
            flow_vel = parse_num(r.get("Air Flow "))
            
            all_experiments.append(make_experiment_record(
                investigation_id="PSI-100",
                investigation_acronym="SAFFIRE-III",
                source_test_id=sample_num,
                replicate_tracker=replicate_tracker,
                source_row_index=idx,
                fuel_material=clean_val(r.get("Material")),
                fuel_phase="solid",
                fuel_geometry=f"sheet ({clean_val(r.get('Sample Thickness'))} x {clean_val(r.get('Sample Width'))} x {clean_val(r.get('Sample Length'))})",
                o2_pct=None,
                o2_source="not reported in experimental table",
                o2_is_assumed=False,
                pressure_atm=None,
                pressure_source="not reported in source data",
                pressure_is_assumed=False,
                flow_velocity_cm_s=flow_vel,
                flow_velocity_source="reported in experimental table under 'Air Flow '",
                flow_direction=clean_val(r.get("Direction")),
                burn_time_s=None,
                outcome=None,
                experiment_context="large-scale flame spread test",
                raw_dict=r.dropna().to_dict()
            ))

    # -------------------------------------------------------------
    # 4. BASS (PSI-26)
    # -------------------------------------------------------------
    f_bass = base_dir / "26 BASS" / "PSI-26_Experimental table_BASS.csv"
    if f_bass.exists():
        df = read_csv_safe(f_bass)
        for idx, r in df.iterrows():
            test_num = clean_val(r.get("Test #"))
            sample_num = clean_val(r.get("Sample #"))
            as_run = clean_val(r.get("As Run Test #"))
            
            if not test_num and not as_run:
                continue
            
            source_id = f"BASS-T{test_num}-S{sample_num}" if test_num else f"BASS-Run{as_run}"
            
            all_experiments.append(make_experiment_record(
                investigation_id="PSI-26",
                investigation_acronym="BASS",
                source_test_id=source_id,
                replicate_tracker=replicate_tracker,
                source_row_index=idx,
                fuel_material=clean_val(r.get("Fuel Sample Material")),
                fuel_phase="solid",
                fuel_geometry="sphere/sheet/slab",
                o2_pct=None,
                o2_source="not reported in experimental table",
                o2_is_assumed=False,
                pressure_atm=None,
                pressure_source="not reported in source data",
                pressure_is_assumed=False,
                flow_velocity_cm_s=None,
                flow_velocity_source="not reported in experimental table",
                flow_direction=None,
                burn_time_s=None,
                outcome=None,
                experiment_context="microgravity solid burning and suppression test",
                raw_dict=r.dropna().to_dict()
            ))

    # -------------------------------------------------------------
    # 5. BASS-II (PSI-25)
    # -------------------------------------------------------------
    f_bass2 = base_dir / "25 BASS-2" / "PSI-25_Experimental table_BASS-II.csv"
    if f_bass2.exists():
        df = read_csv_safe(f_bass2)
        for idx, r in df.iterrows():
            test_num = clean_val(r.get("Test #"))
            if not test_num:
                continue
            
            o2_val = parse_num(r.get("Calibrated  initial O2 % by vol "))
            flow_vel = parse_num(r.get("Air display"))
            
            all_experiments.append(make_experiment_record(
                investigation_id="PSI-25",
                investigation_acronym="BASS-II",
                source_test_id=f"BASS2-{test_num}",
                replicate_tracker=replicate_tracker,
                source_row_index=idx,
                fuel_material=clean_val(r.get("Fuel Sample Material")),
                fuel_phase="solid",
                fuel_geometry="PMMA/film/slab",
                o2_pct=o2_val,
                o2_source="reported in experimental table under 'Calibrated  initial O2 % by vol '",
                o2_is_assumed=False,
                pressure_atm=None,
                pressure_source="not reported in source data",
                pressure_is_assumed=False,
                flow_velocity_cm_s=flow_vel,
                flow_velocity_source="reported in experimental table under 'Air display'",
                flow_direction=None,
                burn_time_s=None,
                outcome=None,
                experiment_context="opposed/concurrent flame spread & extinction test",
                raw_dict=r.dropna().to_dict()
            ))

    # -------------------------------------------------------------
    # 6. ACME BRE (PSI-20)
    # -------------------------------------------------------------
    f_bre = base_dir / "20 ACME BRE" / "PSI-20_Experimental table_ACME BRE.csv"
    if f_bre.exists():
        df = read_csv_safe(f_bre)
        for idx, r in df.iterrows():
            if pd.isna(r.get("Date")) or pd.isna(r.get("Fuel Bottle")):
                continue
            
            month_str = clean_val(r.get("Month")) or ""
            date_str = clean_val(r.get("Date")) or ""
            flames_ignited = clean_val(r.get("Flames Ignited"))
            burner_size = clean_val(r.get("Burner Size (mm)"))
            o2_str = str(r.get("Oxygen Conc (percent)", ""))
            
            raw_tokens = [tok.strip().replace("%", "") for tok in o2_str.split(";") if tok.strip()]
            for sub_i, tok in enumerate(raw_tokens):
                val = parse_num(tok)
                if val is not None and val > 100.0:
                    val = val / 100.0
                    
                source_test_id = f"BRE-{month_str}{date_str}-O2_{tok}"
                
                all_experiments.append(make_experiment_record(
                    investigation_id="PSI-20",
                    investigation_acronym="ACME BRE",
                    source_test_id=source_test_id,
                    replicate_tracker=replicate_tracker,
                    source_row_index=idx,
                    fuel_material=clean_val(r.get("Fuel Bottle")),
                    fuel_phase="solid-emulated (gas burner)",
                    fuel_geometry=f"porous burner {burner_size} mm",
                    o2_pct=val,
                    o2_source="reported in experimental table under 'Oxygen Conc (percent)'",
                    o2_is_assumed=False,
                    pressure_atm=None,
                    pressure_source="not reported in source table (chamber pressures were varied per note)",
                    pressure_is_assumed=False,
                    flow_velocity_cm_s=0.0,
                    flow_velocity_source="quiescent microgravity ambient per investigation protocol",
                    flow_direction="quiescent",
                    burn_time_s=None,
                    outcome=f"{flames_ignited} flames ignited",
                    experiment_context="burning rate emulation in quiescent ambient",
                    raw_dict=r.dropna().to_dict()
                ))

    # -------------------------------------------------------------
    # 7. FLEX (PSI-69)
    # -------------------------------------------------------------
    f_flex = base_dir / "69 FLEX" / "PSI-69_Experimental table_FLEX.csv"
    if f_flex.exists():
        df = read_csv_safe(f_flex)
        for idx, r in df.iterrows():
            flex_test_num = clean_val(r.get("FLEX Test #"))
            if not flex_test_num:
                continue
            
            o2_mol = parse_num(r.get("O initial ambient composition; mole fraction"))
            o2_pct = round(o2_mol * 100.0, 2) if o2_mol is not None else None
            
            p_mmhg = parse_num(r.get("Ambient pressure; mmHg"))
            p_atm = round(p_mmhg / 760.0, 4) if p_mmhg is not None else None
            
            all_experiments.append(make_experiment_record(
                investigation_id="PSI-69",
                investigation_acronym="FLEX",
                source_test_id=f"FLEX-{flex_test_num}",
                replicate_tracker=replicate_tracker,
                source_row_index=idx,
                fuel_material=clean_val(r.get("Fuel")),
                fuel_phase="liquid",
                fuel_geometry=f"droplet (d0={clean_val(r.get('Droplet initial diameter; mm'))} mm)",
                o2_pct=o2_pct,
                o2_source="converted from reported 'O initial ambient composition; mole fraction' in experimental table",
                o2_is_assumed=False,
                pressure_atm=p_atm,
                pressure_source=f"converted from reported pressure of {p_mmhg} mmHg (1 atm = 760 mmHg)" if p_mmhg is not None else "not reported in source data",
                pressure_is_assumed=False,
                flow_velocity_cm_s=0.0,
                flow_velocity_source="quiescent chamber environment",
                flow_direction="quiescent",
                burn_time_s=parse_num(r.get("Burn time; s")),
                outcome=clean_val(r.get("Test end")),
                experiment_context="droplet combustion and extinction test",
                raw_dict=r.dropna().to_dict()
            ))

    # -------------------------------------------------------------
    # 8. CFI (PSI-39)
    # -------------------------------------------------------------
    f_cfi = base_dir / "39 CFI" / "PSI-39_Experimental table_CFI.csv"
    if f_cfi.exists():
        df = read_csv_safe(f_cfi)
        df_clean = df.drop_duplicates().reset_index(drop=True)
        for idx, r in df_clean.iterrows():
            flex_num = clean_val(r.get("Flex Number"))
            if not flex_num:
                continue
            
            o2_raw = parse_num(r.get("Oxygen"))
            o2_pct = round(o2_raw * 100.0, 2) if (o2_raw is not None and o2_raw <= 1.0) else o2_raw
            
            p_str = clean_val(r.get("Pressure"))
            p_atm = parse_num(p_str)
            
            all_experiments.append(make_experiment_record(
                investigation_id="PSI-39",
                investigation_acronym="CFI",
                source_test_id=f"CFI-{flex_num}",
                replicate_tracker=replicate_tracker,
                source_row_index=idx,
                fuel_material=clean_val(r.get("Fuel ")),
                fuel_phase="liquid",
                fuel_geometry="droplet with fiber support" if str(r.get("Fiber")).strip().lower() == "yes" else "free droplet",
                o2_pct=o2_pct,
                o2_source="converted from reported mole fraction under 'Oxygen' in experimental table",
                o2_is_assumed=False,
                pressure_atm=p_atm,
                pressure_source=f"reported in experimental table under 'Pressure' as '{p_str}'" if p_atm is not None else "not reported in source data",
                pressure_is_assumed=False,
                flow_velocity_cm_s=0.0,
                flow_velocity_source="quiescent chamber environment",
                flow_direction="quiescent",
                burn_time_s=None,
                outcome=None,
                experiment_context="cool flames investigation with liquid droplets",
                raw_dict=r.dropna().to_dict()
            ))

    # -------------------------------------------------------------
    # 9. ACME CFI-G (PSI-159) - Normal Flames
    # -------------------------------------------------------------
    f_cfig_norm = base_dir / "159 ACME-CFI-G" / "expirement table" / "PSI-159_Experimental table_CFI-G_Normal Flames.csv"
    if f_cfig_norm.exists():
        df = read_csv_safe(f_cfig_norm)
        for idx, r in df.iterrows():
            test_id = clean_val(r.get("Test"))
            if not test_id:
                continue
            
            xo2_raw = r.get(" XO2 before test")
            if pd.isna(xo2_raw):
                xo2_raw = r.get("XO2  after test")
            xo2_num = parse_num(xo2_raw)
            o2_pct = round(xo2_num * 100.0, 2) if xo2_num is not None else None
            
            p_bar = parse_num(r.get("approx p (bar)"))
            p_atm = round(p_bar * 0.986923, 4) if p_bar is not None else None
            
            burn_time = parse_num(r.get("burn time (sec)"))
            hot_ign = clean_val(r.get("Hot ignition"))
            self_ext = clean_val(r.get("Self-ext or flow term"))
            
            outcome_parts = []
            if hot_ign:
                outcome_parts.append(f"Hot ignition: {hot_ign}")
            if self_ext:
                outcome_parts.append(f"Extinction: {self_ext}")
            outcome_str = "; ".join(outcome_parts) if outcome_parts else None
            
            all_experiments.append(make_experiment_record(
                investigation_id="PSI-159",
                investigation_acronym="ACME CFI-G",
                source_test_id=f"CFIG-Norm-{test_id}",
                replicate_tracker=replicate_tracker,
                source_row_index=idx,
                fuel_material=clean_val(r.get("Fuel")),
                fuel_phase="gas",
                fuel_geometry="normal spherical burner",
                o2_pct=o2_pct,
                o2_source="converted from reported 'XO2' mole fraction in experimental table (Normal Flames)",
                o2_is_assumed=False,
                pressure_atm=p_atm,
                pressure_source=f"converted from reported {p_bar} bar (1 bar = 0.986923 atm)" if p_bar is not None else "not reported in source data",
                pressure_is_assumed=False,
                flow_velocity_cm_s=None,
                flow_velocity_source="not reported in experimental table",
                flow_direction="normal flow",
                burn_time_s=burn_time,
                outcome=outcome_str,
                experiment_context="spherical normal cool diffusion flame test",
                raw_dict=r.dropna().to_dict()
            ))

    # -------------------------------------------------------------
    # 10. ACME CFI-G (PSI-159) - Inverse Flames
    # -------------------------------------------------------------
    f_cfig_inv = base_dir / "159 ACME-CFI-G" / "expirement table" / "PSI-159_Experimental table_CFI-G_Inverse Flames.csv"
    if f_cfig_inv.exists():
        df = read_csv_safe(f_cfig_inv)
        for idx, r in df.iterrows():
            test_id = clean_val(r.get("Test"))
            if not test_id:
                continue
            
            xo2_num = parse_num(r.get("XO2"))
            o2_pct = round(xo2_num * 100.0, 2) if xo2_num is not None else None
            
            p_bar = parse_num(r.get("approx p (bar)"))
            p_atm = round(p_bar * 0.986923, 4) if p_bar is not None else None
            
            burn_time = parse_num(r.get("burn time (sec)"))
            hot_ign = clean_val(r.get("Hot ignition"))
            self_ext = clean_val(r.get("Self -ext or flow term"))
            comments = clean_val(r.get("Comments"))
            
            outcome_parts = []
            if hot_ign:
                outcome_parts.append(f"Hot ignition: {hot_ign}")
            if self_ext and self_ext != "-":
                outcome_parts.append(f"Extinction: {self_ext}")
            if comments:
                outcome_parts.append(comments)
            outcome_str = "; ".join(outcome_parts) if outcome_parts else None
            
            all_experiments.append(make_experiment_record(
                investigation_id="PSI-159",
                investigation_acronym="ACME CFI-G",
                source_test_id=f"CFIG-Inv-{test_id}",
                replicate_tracker=replicate_tracker,
                source_row_index=idx,
                fuel_material=clean_val(r.get("Fuel")),
                fuel_phase="gas",
                fuel_geometry="inverse spherical burner",
                o2_pct=o2_pct,
                o2_source="converted from reported 'XO2' mole fraction in experimental table (Inverse Flames)",
                o2_is_assumed=False,
                pressure_atm=p_atm,
                pressure_source=f"converted from reported {p_bar} bar (1 bar = 0.986923 atm)" if p_bar is not None else "not reported in source data",
                pressure_is_assumed=False,
                flow_velocity_cm_s=None,
                flow_velocity_source="not reported in experimental table",
                flow_direction="inverse flow",
                burn_time_s=burn_time,
                outcome=outcome_str,
                experiment_context="spherical inverse cool diffusion flame test",
                raw_dict=r.dropna().to_dict()
            ))

    # -------------------------------------------------------------
    # 11. SPICE (PSI-107)
    # -------------------------------------------------------------
    f_spice = base_dir / "107 SPICE" / "exp" / "PSI-107_Experimental table_Spice.csv"
    if f_spice.exists():
        df = read_csv_safe(f_spice)
        for idx, r in df.iterrows():
            fuel = clean_val(r.get("Fuel"))
            if not fuel:
                continue
            
            gmt_date = clean_val(r.get("GMT date")) or ""
            gmt_ign = clean_val(r.get("GMT ignition")) or ""
            flow_vel = parse_num(r.get("Air Rate (cm/s)"))
            nozzle = clean_val(r.get("Nozzle (mm)"))
            
            source_id = f"SPICE-GMT{gmt_date}-{gmt_ign}" if gmt_ign else f"SPICE-Row{idx}"
            
            all_experiments.append(make_experiment_record(
                investigation_id="PSI-107",
                investigation_acronym="SPICE",
                source_test_id=source_id,
                replicate_tracker=replicate_tracker,
                source_row_index=idx,
                fuel_material=fuel,
                fuel_phase="gas",
                fuel_geometry=f"co-flow nozzle ({nozzle} mm)",
                o2_pct=None,
                o2_source="not reported in experimental table",
                o2_is_assumed=False,
                pressure_atm=None,
                pressure_source="not reported in source data",
                pressure_is_assumed=False,
                flow_velocity_cm_s=flow_vel,
                flow_velocity_source="reported in experimental table under 'Air Rate (cm/s)'",
                flow_direction="coflow",
                burn_time_s=None,
                outcome=None,
                experiment_context="laminar smoke point and flame length test in coflow",
                raw_dict=r.dropna().to_dict()
            ))

    # -------------------------------------------------------------
    # 12. SAME (PSI-102)
    # -------------------------------------------------------------
    f_same = base_dir / "102 SAME" / "PSI-102_Experimental table_SAME.csv"
    if f_same.exists():
        df = read_csv_safe(f_same)
        for idx, r in df.iterrows():
            sample_num = clean_val(r.get("Sample #"))
            if not sample_num:
                continue
            
            flow_vel = parse_num(r.get("Air Flow (cm/s)"))
            loss_rate = clean_val(r.get("Weight loss rate (mg/min)"))
            aging_dur = clean_val(r.get("Aging Duration (minutes)"))
            
            outcome_parts = []
            if loss_rate:
                outcome_parts.append(f"Weight loss rate: {loss_rate} mg/min")
            if aging_dur:
                outcome_parts.append(f"Aging: {aging_dur} min")
            outcome_str = "; ".join(outcome_parts) if outcome_parts else None
            
            all_experiments.append(make_experiment_record(
                investigation_id="PSI-102",
                investigation_acronym="SAME",
                source_test_id=f"SAME-S{sample_num}",
                replicate_tracker=replicate_tracker,
                source_row_index=idx,
                fuel_material=clean_val(r.get("Sample Material  ")),
                fuel_phase="aerosol/pyrolysis smoke",
                fuel_geometry="smoldering source",
                o2_pct=None,
                o2_source="not reported in experimental table",
                o2_is_assumed=False,
                pressure_atm=None,
                pressure_source="not reported in source data",
                pressure_is_assumed=False,
                flow_velocity_cm_s=flow_vel,
                flow_velocity_source="reported in experimental table under 'Air Flow (cm/s)'" if flow_vel is not None else "not reported in experimental table",
                flow_direction="duct flow",
                burn_time_s=None,
                outcome=outcome_str,
                experiment_context="smoke particle size and detector response test",
                raw_dict=r.dropna().to_dict()
            ))

    # -------------------------------------------------------------
    # 13. SAME-R (PSI-101)
    # -------------------------------------------------------------
    f_samer = base_dir / "101 SAME-R" / "PSI-101_Experimental table_SAME-R.csv"
    if f_samer.exists():
        df = read_csv_safe(f_samer)
        for idx, r in df.iterrows():
            test_num = clean_val(r.get("SAME Test #"))
            sample_type = clean_val(r.get("Sample Type"))
            if not test_num:
                continue
            
            flow_vel = parse_num(r.get("Inlet velocity (cm/s)"))
            duration = parse_num(r.get("Duration (sec)"))
            desc = clean_val(r.get("Description"))
            
            source_id = f"SAMER-{sample_type}-T{test_num}" if sample_type else f"SAMER-T{test_num}"
            
            all_experiments.append(make_experiment_record(
                investigation_id="PSI-101",
                investigation_acronym="SAME-R",
                source_test_id=source_id,
                replicate_tracker=replicate_tracker,
                source_row_index=idx,
                fuel_material=sample_type,
                fuel_phase="aerosol/pyrolysis smoke",
                fuel_geometry="smoldering wire/foam",
                o2_pct=None,
                o2_source="not reported in experimental table",
                o2_is_assumed=False,
                pressure_atm=None,
                pressure_source="not reported in source data",
                pressure_is_assumed=False,
                flow_velocity_cm_s=flow_vel,
                flow_velocity_source="reported in experimental table under 'Inlet velocity (cm/s)'",
                flow_direction="duct flow",
                burn_time_s=duration,
                outcome=desc,
                experiment_context="smoke particle size reflight measurement",
                raw_dict=r.dropna().to_dict()
            ))

    # -------------------------------------------------------------
    # 14. SLICE (PSI-106)
    # -------------------------------------------------------------
    f_slice = base_dir / "106 SLICE" / "PSI-106_Experimental table_Slice.csv"
    if f_slice.exists():
        df = read_csv_safe(f_slice)
        for idx, r in df.iterrows():
            fuel = clean_val(r.get("Fuel Type"))
            test_date = clean_val(r.get("Test Date"))
            if not fuel and not test_date:
                continue
            
            all_experiments.append(make_experiment_record(
                investigation_id="PSI-106",
                investigation_acronym="SLICE",
                source_test_id=f"SLICE-Row{idx}",
                replicate_tracker=replicate_tracker,
                source_row_index=idx,
                fuel_material=fuel,
                fuel_phase="gas",
                fuel_geometry="coflow burner",
                o2_pct=None,
                o2_source="not reported in experimental table",
                o2_is_assumed=False,
                pressure_atm=None,
                pressure_source="not reported in source data",
                pressure_is_assumed=False,
                flow_velocity_cm_s=None,
                flow_velocity_source="not reported in experimental table",
                flow_direction="coflow",
                burn_time_s=None,
                outcome=None,
                experiment_context="laminar diffusion flame structure and liftoff test",
                raw_dict=r.dropna().to_dict()
            ))

    # -------------------------------------------------------------
    # 15. ACME E-FIELD Flames (PSI-22)
    # -------------------------------------------------------------
    f_efield = base_dir / "22 ACME E-FIELD Flames" / "PSI-22_Experimental table_ACME E-FIELD Flames.csv"
    if f_efield.exists():
        df = read_csv_safe(f_efield)
        for idx, r in df.iterrows():
            date_val = clean_val(r.get("Date"))
            test_day = clean_val(r.get("Test Day"))
            fuel_bottle = clean_val(r.get("Fuel Bottle"))
            if not date_val and not fuel_bottle:
                continue
            
            flames = clean_val(r.get("Flames Ignited"))
            burner_type = clean_val(r.get("Test Type"))
            polarity = clean_val(r.get("Mesh Polarity"))
            
            source_id = f"EFIELD-Day{test_day}-Row{idx}" if test_day else f"EFIELD-Row{idx}"
            
            all_experiments.append(make_experiment_record(
                investigation_id="PSI-22",
                investigation_acronym="ACME E-FIELD Flames",
                source_test_id=source_id,
                replicate_tracker=replicate_tracker,
                source_row_index=idx,
                fuel_material=fuel_bottle,
                fuel_phase="gas",
                fuel_geometry=f"{burner_type} (polarity: {polarity})",
                o2_pct=None,
                o2_source="not reported in experimental table",
                o2_is_assumed=False,
                pressure_atm=None,
                pressure_source="not reported in source data",
                pressure_is_assumed=False,
                flow_velocity_cm_s=None,
                flow_velocity_source="not reported in experimental table",
                flow_direction="coflow/jet",
                burn_time_s=None,
                outcome=f"{flames} flames ignited" if flames else None,
                experiment_context="electric-field effect on laminar diffusion flame",
                raw_dict=r.dropna().to_dict()
            ))

    # -------------------------------------------------------------
    # 16. FLEX-2 (PSI-68)
    # -------------------------------------------------------------
    f_flex2 = base_dir / "68 FLEX-2" / "PSI-68_Experimental table_Flex2.csv"
    if f_flex2.exists():
        df = read_csv_safe(f_flex2)
        for idx, r in df.iterrows():
            fuel = clean_val(r.get("Sample (Fuel Type)"))
            if not fuel:
                continue
            
            drop_diam = clean_val(r.get("Initial Droplet Diameter (mm)"))
            gas_mix = clean_val(r.get("Ambient Gas Mixture "))
            o2_str = clean_val(r.get("Oxygen Mole Fraction"))
            p_str = clean_val(r.get("Ambient Pressure (atm)"))
            flow_str = clean_val(r.get("Flow Velocity (cm/s)"))
            
            all_experiments.append(make_experiment_record(
                investigation_id="PSI-68",
                investigation_acronym="FLEX-2",
                source_test_id=f"FLEX2-{fuel.replace(' ', '_')}",
                replicate_tracker=replicate_tracker,
                source_row_index=idx,
                fuel_material=fuel,
                fuel_phase="liquid",
                fuel_geometry=f"droplet (d0 range: {drop_diam} mm, gas: {gas_mix})",
                o2_pct=None,
                o2_source=f"reported as parameter matrix range: '{o2_str}' in experimental table",
                o2_is_assumed=False,
                pressure_atm=None,
                pressure_source=f"reported as parameter matrix range: '{p_str}' in experimental table",
                pressure_is_assumed=False,
                flow_velocity_cm_s=None,
                flow_velocity_source=f"reported as parameter matrix range: '{flow_str}' in experimental table",
                flow_direction="forced flow",
                burn_time_s=None,
                outcome=None,
                experiment_context="droplet combustion parameter test matrix",
                raw_dict=r.dropna().to_dict()
            ))

    # -------------------------------------------------------------
    # 17. DAFT / DAFT-2 (PSI-47)
    # -------------------------------------------------------------
    f_daft = base_dir / "47 DAFT _ DAFT-2" / "PSI-47_Experimental table_DAFT.csv"
    if f_daft.exists():
        df = read_csv_safe(f_daft)
        for idx, r in df.iterrows():
            session = clean_val(r.get("Session Name"))
            if not session:
                continue
            
            material = clean_val(r.get("Sample Material"))
            location = clean_val(r.get("Sampled Location"))
            hardware = clean_val(r.get("Hardware Description"))
            
            all_experiments.append(make_experiment_record(
                investigation_id="PSI-47",
                investigation_acronym="DAFT",
                source_test_id=f"DAFT-{session}",
                replicate_tracker=replicate_tracker,
                source_row_index=idx,
                fuel_material=material,
                fuel_phase="aerosol/dust",
                fuel_geometry=f"{hardware}; sampled at: {location}",
                o2_pct=None,
                o2_source="not reported in experimental table",
                o2_is_assumed=False,
                pressure_atm=None,
                pressure_source="not reported in source data",
                pressure_is_assumed=False,
                flow_velocity_cm_s=None,
                flow_velocity_source="not reported in experimental table",
                flow_direction=None,
                burn_time_s=None,
                outcome=f"Sampled at {location}",
                experiment_context="dust and aerosol measurement feasibility test",
                raw_dict=r.dropna().to_dict()
            ))

    # -------------------------------------------------------------
    # VALIDATION STEP: Verify 100% uniqueness of experiment_id
    # -------------------------------------------------------------
    print(f"\nTotal normalized experimental records: {len(all_experiments)}")
    
    seen_ids = set()
    duplicate_ids = []
    for exp in all_experiments:
        eid = exp["experiment_id"]
        if eid in seen_ids:
            duplicate_ids.append(eid)
        seen_ids.add(eid)
        
    if duplicate_ids:
        err_msg = f"VALIDATION ERROR: Found {len(duplicate_ids)} duplicate experiment_id(s): {duplicate_ids[:10]}"
        print(err_msg)
        raise ValueError(err_msg)
    else:
        print("VALIDATION PASSED: All experiment_id values are strictly unique and reproducible.")
        
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(all_experiments, f, indent=2, ensure_ascii=False)
    print(f"Saved normalized experiments to {out_json}")

if __name__ == "__main__":
    normalize_csv_files()
