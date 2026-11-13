import os
import pandas as pd
import json

def generate_final_experiments():
    # 1. Load Phase 1 Metadata
    with open("phase1_metadata.json", "r", encoding='utf-8') as f:
        metadata = json.load(f)

    data_dir = "./Experimentaltables"
    final_records = []

    # Helper to safely clean values and avoid "nan" ghost rows from Excel exports
    def is_ghost(val):
        return pd.isna(val) or str(val).strip().lower() == 'nan' or str(val).strip() == ''

    def safe_float(val, multiplier=1.0):
        if is_ghost(val): 
            return None
        try:
            return round(float(val) * multiplier, 2)
        except (ValueError, TypeError):
            return None

    def add_record(psi_id, test_id, fuel, o2, press, flow):
        if is_ghost(test_id): 
            return # Skip the ghost rows instantly
        
        meta = metadata.get(psi_id, {})
        final_records.append({
            "id": f"{psi_id}_{test_id}",
            "title": meta.get("title", f"Experiment {psi_id}"),
            "type": "flight",
            "gravity": "microgravity",
            "summary": meta.get("objective", ""),
            "source_link": f"https://psi.nasa.gov/investigation/{psi_id}",
            "fuel_type": str(fuel) if not is_ghost(fuel) else None,
            "oxygen_pct": safe_float(o2),
            "pressure_kpa": safe_float(press),
            "airflow_cm_s": safe_float(flow)
        })

    # Loop through all files in the directory
    for file in os.listdir(data_dir):
        if not file.endswith(".csv"): 
            continue
        
        filepath = os.path.join(data_dir, file)
        try:
            df = pd.read_csv(filepath, encoding='utf-8')
        except UnicodeDecodeError:
            df = pd.read_csv(filepath, encoding='cp1252')

        # --- 1. BASS-II (PSI-25) ---
        if "BASS-II" in file:
            for _, row in df.iterrows():
                add_record("PSI-25", row.get('Test #'), row.get('Fuel Sample Material'), row.get('Calibrated  initial O2 % by vol '), 101.3, row.get('Air display'))
                
        # --- 2. BASS (PSI-26) ---
        elif "BASS" in file and "BASS-II" not in file:
            for _, row in df.iterrows():
                add_record("PSI-26", row.get('Test #'), row.get('Fuel Sample Material'), 21.0, 101.3, None)

        # --- 3. CFI (PSI-39) ---
        elif "CFI" in file and "CFI-G" not in file:
            for _, row in df.iterrows():
                press_kpa = safe_float(row.get('Pressure'), 101.325) # atm to kPa
                add_record("PSI-39", row.get('Flex Number'), row.get('Fuel '), row.get('Oxygen'), press_kpa, None)

        # --- 4. DAFT (PSI-47) ---
        elif "DAFT" in file:
            for _, row in df.iterrows():
                add_record("PSI-47", row.get('Session Name'), row.get('Sample Material'), None, 101.3, None)

        # --- 5. FLEX-2 (PSI-68) ---
        elif "Flex2" in file:
            for _, row in df.iterrows():
                o2_pct = safe_float(row.get('Oxygen Mole Fraction'), 100.0)
                press_kpa = safe_float(row.get('Ambient Pressure (atm)'), 101.325)
                add_record("PSI-68", row.get('Sample (Fuel Type)'), row.get('Sample (Fuel Type)'), o2_pct, press_kpa, row.get('Flow Velocity (cm/s)'))

        # --- 6. FLEX (PSI-69) ---
        elif "FLEX" in file and "Flex2" not in file:
            for _, row in df.iterrows():
                o2_pct = safe_float(row.get('O initial ambient composition; mole fraction'), 100.0)
                press_kpa = safe_float(row.get('Ambient pressure; mmHg'), 0.133322) # mmHg to kPa
                add_record("PSI-69", row.get('FLEX Test #'), row.get('Fuel'), o2_pct, press_kpa, None)

        # --- 7. SAFFIRE Series (PSI-98, PSI-99, PSI-100) ---
        elif "SAFFIRE" in file:
            psi_id = "PSI-98" if "SAFFIRE-1" in file else ("PSI-99" if "SAFFIRE-2" in file else "PSI-100")
            test_col = 'Sample Number ' if 'Sample Number ' in df.columns else 'Sample Number'
            o2_col = 'Percent O2' if 'Percent O2' in df.columns else ('Percent O2 (Note 1)' if 'Percent O2 (Note 1)' in df.columns else None)
            flow_col = 'Air Flow (cm/s)' if 'Air Flow (cm/s)' in df.columns else ('Air Flow ' if 'Air Flow ' in df.columns else None)
            for _, row in df.iterrows():
                o2_val = row.get(o2_col) if o2_col else None
                flow_val = row.get(flow_col) if flow_col else None
                add_record(psi_id, row.get(test_col), row.get('Material'), o2_val, 101.3, flow_val)

        # --- 8. ACME BRE (PSI-20) ---
        elif "ACME BRE" in file:
            o2_col = 'Oxygen Conc (percent)' if 'Oxygen Conc (percent)' in df.columns else 'Fuel Conc'
            for _, row in df.iterrows():
                add_record("PSI-20", row.get('Date'), row.get('Fuel Bottle'), row.get(o2_col), 101.3, 0)

        # --- 9. ACME E-FIELD (PSI-22) ---
        elif "E-FIELD" in file:
            for _, row in df.iterrows():
                add_record("PSI-22", row.get('Date'), row.get('Fuel Bottle'), None, 101.3, None)

        # --- 10. ACME CFI-G (PSI-159) ---
        elif "CFI-G" in file:
            o2_col = 'XO2' if 'XO2' in df.columns else ' XO2 before test'
            for _, row in df.iterrows():
                o2_pct = safe_float(row.get(o2_col), 100.0) # fraction to pct
                press_kpa = safe_float(row.get('approx p (bar)'), 100.0) # bar to kPa
                add_record("PSI-159", row.get('Test'), row.get('Fuel'), o2_pct, press_kpa, None)

        # --- 11. SPICE (PSI-107) ---
        elif "Spice" in file:
            for _, row in df.iterrows():
                add_record("PSI-107", row.get('GMT date'), row.get('Fuel'), 21.0, 101.3, row.get('Air Rate (cm/s)'))

        # --- 12. SLICE (PSI-106) ---
        elif "Slice" in file:
            for _, row in df.iterrows():
                add_record("PSI-106", row.get('Test Date'), row.get('Fuel Type'), 21.0, 101.3, None)

        # --- 13. SAME (PSI-102) ---
        elif "SAME" in file and "SAME-R" not in file:
            for _, row in df.iterrows():
                add_record("PSI-102", row.get('Sample #'), row.get('Sample Material  '), None, 101.3, row.get('Air Flow (cm/s)'))

        # --- 14. SAME-R (PSI-101) ---
        elif "SAME-R" in file:
            for _, row in df.iterrows():
                add_record("PSI-101", row.get('SAME Test #'), row.get('Sample Type'), None, 101.3, row.get('Inlet velocity (cm/s)'))

    output_file = "experiments.json"
    with open(output_file, "w", encoding='utf-8') as f:
        json.dump(final_records, f, indent=4)
        
    print(f"✅ Successfully processed {len(final_records)} valid records across all datasets into {output_file}.")

if __name__ == "__main__":
    generate_final_experiments()