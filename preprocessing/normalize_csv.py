import os
import re
import glob
import pandas as pd
import json
from pathlib import Path

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

def normalize_csv_files():
    base_dir = Path(r"d:\FireOrbit\FireOrbit\DATA\nasa final data")
    out_json = Path(r"d:\FireOrbit\FireOrbit\data_processed\experiments_normalized.json")
    
    all_experiments = []
    
    # 1. SAFFIRE-1
    f_saffire1 = base_dir / "98 SAFFIRE-1" / "PSI-98_Experimental table_SAFFIRE-1.csv"
    if f_saffire1.exists():
        df = read_csv_safe(f_saffire1)
        for _, r in df.iterrows():
            if pd.isna(r.get("Sample Number ")) or "Pre-test" in str(r.get("Material", "")):
                continue
            all_experiments.append({
                "investigation_id": "PSI-98",
                "investigation_acronym": "SAFFIRE-I",
                "test_id": clean_val(r.get("Sample Number ")),
                "fuel_material": clean_val(r.get("Material")),
                "fuel_phase": "solid",
                "fuel_geometry": f"sheet ({clean_val(r.get('Sample Thickness (cm)'))}x{clean_val(r.get('Sample Width (cm)'))}x{clean_val(r.get('Sample Length (cm)'))} cm)",
                "o2_concentration_pct": parse_num(r.get("Percent O2")),
                "flow_velocity_cm_s": parse_num(r.get("Air Flow (cm/s)")),
                "flow_direction": clean_val(r.get("Flow Direction ")),
                "pressure_atm": 1.0,
                "burn_time_s": parse_num(r.get("Burn Time (s)")),
                "outcome": "sustained_burn" if parse_num(r.get("Burn Time (s)")) and parse_num(r.get("Burn Time (s)")) > 0 else "extinguished",
                "raw_details": r.dropna().to_dict()
            })

    # 2. SAFFIRE-2
    f_saffire2 = base_dir / "99 SAFFIRE-2" / "PSI-99_Experimental table_SAFFIRE-2.csv"
    if f_saffire2.exists():
        df = read_csv_safe(f_saffire2)
        for _, r in df.iterrows():
            if pd.isna(r.get("Sample Number")):
                continue
            all_experiments.append({
                "investigation_id": "PSI-99",
                "investigation_acronym": "SAFFIRE-II",
                "test_id": clean_val(r.get("Sample Number")),
                "fuel_material": clean_val(r.get("Material")),
                "fuel_phase": "solid",
                "fuel_geometry": f"sample ({clean_val(r.get('Samle Thickness '))} x {clean_val(r.get('Sample Width (cm)'))} x {clean_val(r.get('Sample Length '))} cm)",
                "o2_concentration_pct": parse_num(r.get("Percent O2 (Note 1)")),
                "flow_velocity_cm_s": parse_num(r.get("Air Flow (cm/s)")),
                "flow_direction": clean_val(r.get("Flow Direction")),
                "pressure_atm": 1.0,
                "burn_time_s": parse_num(r.get("Burn Time (s)")),
                "outcome": clean_val(r.get("Burn Time (s)")),
                "raw_details": r.dropna().to_dict()
            })

    # 3. SAFFIRE-3
    f_saffire3 = base_dir / "100 SAFFIRE-3" / "PSI-100_Experimental table_SAFFIRE-3.csv"
    if f_saffire3.exists():
        df = read_csv_safe(f_saffire3)
        for _, r in df.iterrows():
            if pd.isna(r.get("Sample Number ")):
                continue
            all_experiments.append({
                "investigation_id": "PSI-100",
                "investigation_acronym": "SAFFIRE-III",
                "test_id": clean_val(r.get("Sample Number ")),
                "fuel_material": clean_val(r.get("Material")),
                "fuel_phase": "solid",
                "fuel_geometry": f"sheet ({clean_val(r.get('Sample Thickness'))} x {clean_val(r.get('Sample Width'))} x {clean_val(r.get('Sample Length'))})",
                "o2_concentration_pct": 21.0, # Nominal ISS Cygnus atmospheric condition
                "flow_velocity_cm_s": parse_num(r.get("Air Flow ")),
                "flow_direction": clean_val(r.get("Direction")),
                "pressure_atm": 1.0,
                "burn_time_s": None,
                "outcome": "large-scale spread test",
                "raw_details": r.dropna().to_dict()
            })

    # 4. BASS
    f_bass = base_dir / "26 BASS" / "PSI-26_Experimental table_BASS.csv"
    if f_bass.exists():
        df = read_csv_safe(f_bass)
        for _, r in df.iterrows():
            if pd.isna(r.get("As Run Test #")) and pd.isna(r.get("Test #")):
                continue
            all_experiments.append({
                "investigation_id": "PSI-26",
                "investigation_acronym": "BASS",
                "test_id": f"BASS-T{clean_val(r.get('Test #'))}-S{clean_val(r.get('Sample #'))}",
                "fuel_material": clean_val(r.get("Fuel Sample Material")),
                "fuel_phase": "solid",
                "fuel_geometry": "sphere/sheet/slab",
                "o2_concentration_pct": 21.0,
                "flow_velocity_cm_s": None,
                "flow_direction": "concurrent/opposed",
                "pressure_atm": 1.0,
                "burn_time_s": None,
                "outcome": "burn_and_suppress",
                "raw_details": r.dropna().to_dict()
            })

    # 5. BASS-II
    f_bass2 = base_dir / "25 BASS-2" / "PSI-25_Experimental table_BASS-II.csv"
    if f_bass2.exists():
        df = read_csv_safe(f_bass2)
        for _, r in df.iterrows():
            if pd.isna(r.get("Test #")):
                continue
            o2_val = parse_num(r.get("Calibrated  initial O2 % by vol "))
            all_experiments.append({
                "investigation_id": "PSI-25",
                "investigation_acronym": "BASS-II",
                "test_id": clean_val(r.get("Test #")),
                "fuel_material": clean_val(r.get("Fuel Sample Material")),
                "fuel_phase": "solid",
                "fuel_geometry": "PMMA/film/slab",
                "o2_concentration_pct": o2_val,
                "flow_velocity_cm_s": parse_num(r.get("Air display")),
                "flow_direction": "opposed/concurrent",
                "pressure_atm": 1.0,
                "burn_time_s": None,
                "outcome": "completed",
                "raw_details": r.dropna().to_dict()
            })

    # 6. ACME BRE
    f_bre = base_dir / "20 ACME BRE" / "PSI-20_Experimental table_ACME BRE.csv"
    if f_bre.exists():
        df = read_csv_safe(f_bre)
        for _, r in df.iterrows():
            if pd.isna(r.get("Date")) or pd.isna(r.get("Fuel Bottle")):
                continue
            o2_str = str(r.get("Oxygen Conc (percent)", ""))
            # May list multiple e.g. "21; 26.5; 40"
            for o2_item in o2_str.split(";"):
                o2_val = parse_num(o2_item)
                all_experiments.append({
                    "investigation_id": "PSI-20",
                    "investigation_acronym": "ACME BRE",
                    "test_id": f"BRE-{r.get('Month')}{r.get('Date')}-O2_{o2_item.strip()}",
                    "fuel_material": clean_val(r.get("Fuel Bottle")),
                    "fuel_phase": "solid-emulated (gas burner)",
                    "fuel_geometry": f"porous burner {clean_val(r.get('Burner Size (mm)'))} mm",
                    "o2_concentration_pct": o2_val,
                    "flow_velocity_cm_s": 0.0, # Quiescent!
                    "flow_direction": "quiescent",
                    "pressure_atm": 1.0 if o2_val == 21.0 else (0.69 if o2_val == 26.5 else 0.56),
                    "burn_time_s": None,
                    "outcome": f"{clean_val(r.get('Flames Ignited'))} flames ignited",
                    "raw_details": r.dropna().to_dict()
                })

    # 7. FLEX (PSI-69)
    f_flex = base_dir / "69 FLEX" / "PSI-69_Experimental table_FLEX.csv"
    if f_flex.exists():
        df = read_csv_safe(f_flex)
        for _, r in df.iterrows():
            if pd.isna(r.get("FLEX Test #")):
                continue
            o2_mol = parse_num(r.get("O initial ambient composition; mole fraction"))
            p_mmhg = parse_num(r.get("Ambient pressure; mmHg"))
            p_atm = (p_mmhg / 760.0) if p_mmhg else 1.0
            all_experiments.append({
                "investigation_id": "PSI-69",
                "investigation_acronym": "FLEX",
                "test_id": f"FLEX-{clean_val(r.get('FLEX Test #'))}",
                "fuel_material": clean_val(r.get("Fuel")),
                "fuel_phase": "liquid",
                "fuel_geometry": f"droplet (d0={clean_val(r.get('Droplet initial diameter; mm'))} mm)",
                "o2_concentration_pct": (o2_mol * 100.0) if o2_mol else 21.0,
                "flow_velocity_cm_s": 0.0,
                "flow_direction": "quiescent",
                "pressure_atm": round(p_atm, 3),
                "burn_time_s": parse_num(r.get("Burn time; s")),
                "outcome": clean_val(r.get("Test end")),
                "raw_details": r.dropna().to_dict()
            })

    # 8. CFI (PSI-39)
    f_cfi = base_dir / "39 CFI" / "PSI-39_Experimental table_CFI.csv"
    if f_cfi.exists():
        df = read_csv_safe(f_cfi)
        for _, r in df.iterrows():
            if pd.isna(r.get("Flex Number")):
                continue
            o2_val = parse_num(r.get("Oxygen"))
            all_experiments.append({
                "investigation_id": "PSI-39",
                "investigation_acronym": "CFI",
                "test_id": f"CFI-{clean_val(r.get('Flex Number'))}",
                "fuel_material": clean_val(r.get("Fuel ")),
                "fuel_phase": "liquid",
                "fuel_geometry": "droplet with fiber support",
                "o2_concentration_pct": (o2_val * 100.0) if o2_val and o2_val <= 1.0 else o2_val,
                "flow_velocity_cm_s": 0.0,
                "flow_direction": "quiescent",
                "pressure_atm": 1.0,
                "burn_time_s": None,
                "outcome": "cool_flame_observed",
                "raw_details": r.dropna().to_dict()
            })

    # 9. CFI-G Inverse Flames
    f_cfig_inv = base_dir / "159 ACME-CFI-G" / "expirement table" / "PSI-159_Experimental table_CFI-G_Inverse Flames.csv"
    if f_cfig_inv.exists():
        df = read_csv_safe(f_cfig_inv)
        for _, r in df.iterrows():
            if pd.isna(r.get("Test")):
                continue
            o2_val = parse_num(r.get("XO2"))
            all_experiments.append({
                "investigation_id": "PSI-159",
                "investigation_acronym": "ACME CFI-G",
                "test_id": f"CFIG-Inv-{clean_val(r.get('Test'))}",
                "fuel_material": clean_val(r.get("Fuel")),
                "fuel_phase": "gas",
                "fuel_geometry": "inverse spherical burner",
                "o2_concentration_pct": (o2_val * 100.0) if o2_val and o2_val <= 1.0 else o2_val,
                "flow_velocity_cm_s": None,
                "flow_direction": "inverse flow",
                "pressure_atm": parse_num(r.get("approx p (bar)")),
                "burn_time_s": parse_num(r.get("burn time (sec)")),
                "outcome": "ignited" if str(r.get("Hot ignition", "")).lower() == "yes" else "failed_ignition",
                "raw_details": r.dropna().to_dict()
            })

    # 10. SPICE (PSI-107)
    f_spice = base_dir / "107 SPICE" / "exp" / "PSI-107_Experimental table_Spice.csv"
    if f_spice.exists():
        df = read_csv_safe(f_spice)
        for idx, r in df.head(100).iterrows(): # sample key data points from the 500+ records
            if pd.isna(r.get("Fuel")):
                continue
            all_experiments.append({
                "investigation_id": "PSI-107",
                "investigation_acronym": "SPICE",
                "test_id": f"SPICE-GMT{clean_val(r.get('GMT date'))}-{idx}",
                "fuel_material": clean_val(r.get("Fuel")),
                "fuel_phase": "gas",
                "fuel_geometry": f"co-flow nozzle ({clean_val(r.get('Nozzle (mm)'))} mm)",
                "o2_concentration_pct": 21.0,
                "flow_velocity_cm_s": parse_num(r.get("Air Rate (cm/s)")),
                "flow_direction": "coflow",
                "pressure_atm": 1.0,
                "burn_time_s": None,
                "outcome": "laminar_smoke_point_test",
                "raw_details": r.dropna().to_dict()
            })

    # 11. SAME (PSI-102) & SAME-R (PSI-101)
    f_same = base_dir / "102 SAME" / "PSI-102_Experimental table_SAME.csv"
    if f_same.exists():
        df = read_csv_safe(f_same)
        for _, r in df.iterrows():
            if pd.isna(r.get("Sample #")):
                continue
            all_experiments.append({
                "investigation_id": "PSI-102",
                "investigation_acronym": "SAME",
                "test_id": f"SAME-S{clean_val(r.get('Sample #'))}",
                "fuel_material": clean_val(r.get("Sample Material  ")),
                "fuel_phase": "aerosol/pyrolysis smoke",
                "fuel_geometry": "smoldering source",
                "o2_concentration_pct": 21.0,
                "flow_velocity_cm_s": parse_num(r.get("Air Flow (cm/s)")),
                "flow_direction": "duct flow",
                "pressure_atm": 1.0,
                "burn_time_s": None,
                "outcome": "smoke_detection_measured",
                "raw_details": r.dropna().to_dict()
            })

    f_samer = base_dir / "101 SAME-R" / "PSI-101_Experimental table_SAME-R.csv"
    if f_samer.exists():
        df = read_csv_safe(f_samer)
        for _, r in df.iterrows():
            if pd.isna(r.get("SAME Test #")):
                continue
            all_experiments.append({
                "investigation_id": "PSI-101",
                "investigation_acronym": "SAME-R",
                "test_id": f"SAMER-T{clean_val(r.get('SAME Test #'))}",
                "fuel_material": clean_val(r.get("Sample Type")),
                "fuel_phase": "aerosol/pyrolysis smoke",
                "fuel_geometry": "smoldering wire/foam",
                "o2_concentration_pct": 21.0,
                "flow_velocity_cm_s": parse_num(r.get("Inlet velocity (cm/s)")),
                "flow_direction": "duct flow",
                "pressure_atm": 1.0,
                "burn_time_s": parse_num(r.get("Duration (sec)")),
                "outcome": "aerosol_size_measured",
                "raw_details": r.dropna().to_dict()
            })

    print(f"Total normalized experimental points: {len(all_experiments)}")
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(all_experiments, f, indent=2, ensure_ascii=False)
    print(f"Saved normalized experiments to {out_json}")

if __name__ == "__main__":
    normalize_csv_files()
