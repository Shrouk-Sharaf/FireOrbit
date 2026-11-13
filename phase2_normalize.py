import os
import pandas as pd
import json

def normalize_experimental_tables(data_dir):
    all_experiments = []
    
    # 1. BASS & BASS-II (Solid Fuels)
    # Assumes ISS cabin pressure (14.7 psi / 101.3 kPa)
    file_bass2 = os.path.join(data_dir, "PSI-25_Experimental table_BASS-II.csv")
    if os.path.exists(file_bass2):
        df = pd.read_csv(file_bass2, encoding='cp1252')
        for _, row in df.iterrows():
            all_experiments.append({
                "investigation_id": "PSI-25",
                "test_id": str(row.get('Test #')),
                "fuel_type": str(row.get('Fuel Sample Material')),
                "fuel_state": "solid",
                "o2_concentration": pd.to_numeric(row.get('Calibrated  initial O2 % by vol ', 21.0), errors='coerce') / 100.0,
                "pressure_kpa": 101.3,
                "flow_velocity_cm_s": pd.to_numeric(row.get('Air display', None), errors='coerce')
            })

    # 2. FLEX & FLEX-2 (Liquid Droplets)
    file_flex2 = os.path.join(data_dir, "PSI-68_Experimental table_Flex2.csv")
    if os.path.exists(file_flex2):
        df = pd.read_csv(file_flex2, encoding='cp1252')
        for _, row in df.iterrows():
            # Convert atm to kPa (1 atm = 101.325 kPa)
            pressure_atm = pd.to_numeric(row.get('Ambient Pressure (atm)'), errors='coerce')
            all_experiments.append({
                "investigation_id": "PSI-68",
                "test_id": str(row.get('Sample (Fuel Type)')),
                "fuel_type": str(row.get('Sample (Fuel Type)')),
                "fuel_state": "liquid",
                "o2_concentration": pd.to_numeric(row.get('Oxygen Mole Fraction'), errors='coerce'),
                "pressure_kpa": pressure_atm * 101.325 if pd.notna(pressure_atm) else None,
                "flow_velocity_cm_s": pd.to_numeric(row.get('Flow Velocity (cm/s)'), errors='coerce')
            })

    # 3. ACME BRE (Gaseous Fuels)
    file_bre = os.path.join(data_dir, "PSI-20_Experimental table_ACME BRE.csv")
    if os.path.exists(file_bre):
        df = pd.read_csv(file_bre, encoding='cp1252')
        for _, row in df.iterrows():
            o2_col = 'Oxygen Conc (percent)' if 'Oxygen Conc (percent)' in df.columns else 'Fuel Conc'
            o2_val = pd.to_numeric(row.get(o2_col, 21.0), errors='coerce') / 100.0
            all_experiments.append({
                "investigation_id": "PSI-20",
                "test_id": str(row.get('Date', 'N/A')),
                "fuel_type": str(row.get('Fuel Bottle')),
                "fuel_state": "gas",
                "o2_concentration": o2_val,
                "pressure_kpa": 101.3, # Assume 1 atm if unlisted in this specific ACME run
                "flow_velocity_cm_s": 0 # BRE is explicitly quiescent
            })

    # 4. ACME CFI-G (Gaseous Cool Flames)
    file_cfig = os.path.join(data_dir, "PSI-159_Experimental table_CFI-G_Inverse Flames.csv")
    if os.path.exists(file_cfig):
        df = pd.read_csv(file_cfig, encoding='cp1252')
        for _, row in df.iterrows():
            # Convert bar to kPa (1 bar = 100 kPa)
            pressure_bar = pd.to_numeric(row.get('approx p (bar)'), errors='coerce')
            all_experiments.append({
                "investigation_id": "PSI-159",
                "test_id": str(row.get('Test')),
                "fuel_type": str(row.get('Fuel')),
                "fuel_state": "gas",
                "o2_concentration": pd.to_numeric(row.get('XO2'), errors='coerce'),
                "pressure_kpa": pressure_bar * 100.0 if pd.notna(pressure_bar) else None,
                "flow_velocity_cm_s": None
            })

    clean_experiments = []
    for exp in all_experiments:
        clean_exp = {}
        for k, v in exp.items():
            if pd.isna(v):
                clean_exp[k] = None
            elif hasattr(v, 'item'): 
                clean_exp[k] = v.item() 
            else:
                clean_exp[k] = v
        clean_experiments.append(clean_exp)

    # Save to JSON
    output_file = "phase2_experiments.json"
    with open(output_file, "w", encoding='utf-8') as f:
        json.dump(clean_experiments, f, indent=4)
        
    print(f"Phase 2 Complete. Normalized {len(clean_experiments)} test runs to {output_file}.")

if __name__ == "__main__":
    normalize_experimental_tables("./Experimentaltables")