import json
import math
import re
from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASE_DIR = PROJECT_ROOT / "DATA" / "nasa final data"
OUTPUT_DIR = PROJECT_ROOT / "data_processed"

HARDWARE_GROUPS = {
    "PSI-26": "MSG + SPICE flow duct",
    "PSI-25": "MSG + SPICE flow duct",
    "PSI-107": "MSG + SPICE flow duct",
    "PSI-106": "MSG + SPICE flow duct",
    "PSI-20": "CIR + ACME",
    "PSI-22": "CIR + ACME",
    "PSI-159": "CIR + ACME",
    "PSI-69": "CIR + MDCA",
    "PSI-68": "CIR + MDCA",
    "PSI-39": "CIR + MDCA",
    "PSI-98": "Cygnus vehicle (Saffire)",
    "PSI-99": "Cygnus vehicle (Saffire)",
    "PSI-100": "Cygnus vehicle (Saffire)",
    "PSI-102": "MSG (smoke/aerosol)",
    "PSI-101": "MSG (smoke/aerosol)",
    "PSI-47": "MSG (smoke/aerosol)",
}

# Investigations that are not combustion-atmosphere datasets for habitat matching.
ATMOSPHERE_SOLVER_EXCLUDE = {
    "PSI-47": "DAFT/DAFT-2 is an aerosol-instrument feasibility test, not a combustion atmosphere dataset",
}

# Study-level condition anchors that are not reported per executed test row.
STUDY_LEVEL_CONDITIONS = {
    "PSI-20": {
        "pressure_atm_values": [0.558, 0.694, 1.0],
        "pressure_source": (
            "planned, unconfirmed: NASA-considered habitat atmospheres from the study objective "
            "(8.2 psia = 0.558 atm, 10.2 psia = 0.694 atm, 14.7 psia = 1.0 atm). "
            "The experimental table notes chamber pressure was varied but does not identify per-test values."
        ),
        "pressure_status": "planned_unconfirmed",
        "pressure_is_assumed": True,
        "pressure_condition_level": "study",
    },
    "PSI-68": {
        "o2_pct_values": [17.0, 21.0, 25.0, 30.0],
        "pressure_atm_values": [0.5, 1.0, 1.5, 2.0, 3.0],
        "flow_values": [0.1, 5.0],
        "o2_source": "FLEX-2 design matrix Oxygen Mole Fraction 0.17; 0.21; 0.25; 0.3 converted to percent",
        "pressure_source": "FLEX-2 design matrix Ambient Pressure (atm): 0.5; 1.0; 1.5; 2.0; 3.0",
        "flow_source": "FLEX-2 design matrix Flow Velocity (cm/s): 0.1 - 5",
        "o2_status": "design_matrix",
        "pressure_status": "design_matrix",
        "o2_is_assumed": False,
        "pressure_is_assumed": False,
        "o2_condition_level": "study",
        "pressure_condition_level": "study",
        "flow_condition_level": "study",
    },
}

MOON_BASE_TARGET = {
    "o2_pct": 30.0,
    "pressure_atm": 0.694,  # 10.2 psia
    "flow_cm_s": 0.0,
}

RELATED_INVESTIGATIONS = {
    "PSI-98": ["PSI-99", "PSI-100"],
    "PSI-99": ["PSI-98", "PSI-100"],
    "PSI-100": ["PSI-98", "PSI-99"],
    "PSI-26": ["PSI-25", "PSI-107", "PSI-106"],
    "PSI-25": ["PSI-26", "PSI-107", "PSI-106"],
    "PSI-107": ["PSI-106", "PSI-26", "PSI-25"],
    "PSI-106": ["PSI-107", "PSI-26", "PSI-25"],
    "PSI-102": ["PSI-101", "PSI-47"],
    "PSI-101": ["PSI-102", "PSI-47"],
    "PSI-47": ["PSI-102", "PSI-101"],
    "PSI-69": ["PSI-68", "PSI-39"],
    "PSI-68": ["PSI-69", "PSI-39"],
    "PSI-39": ["PSI-69", "PSI-68", "PSI-159"],
    "PSI-20": ["PSI-22", "PSI-159"],
    "PSI-22": ["PSI-20", "PSI-159"],
    "PSI-159": ["PSI-20", "PSI-22", "PSI-39"],
}

FUEL_CANONICAL = [
    ("sibal", "SIBAL"),
    ("nomex", "Nomex"),
    ("ultem", "Ultem"),
    ("pmma", "PMMA"),
    ("acrylic", "PMMA"),
    ("teflon", "Teflon"),
    ("ptfe", "Teflon"),
    ("kapton", "Kapton"),
    ("pyrell", "Pyrell"),
    ("silicone", "Silicone"),
    ("cotton", "Cotton"),
    ("cellulose", "Cellulose"),
    ("methanol", "Methanol"),
    ("ethanol", "Ethanol"),
    ("propanol", "Propanol"),
    ("isooctane", "Iso-octane"),
    ("iso-octane", "Iso-octane"),
    ("n-octane", "n-Octane"),
    ("octane", "n-Octane"),
    ("heptane", "Heptane"),
    ("decane", "Decane"),
    ("dodecane", "Dodecane"),
    ("c12h26", "Dodecane"),
    ("glycerol", "Glycerol mixture"),
    ("paraffin", "Paraffin"),
    ("parrafin", "Paraffin"),
    ("japan wax", "Japan wax"),
    ("ethylene", "Ethylene"),
    ("c2h4", "Ethylene"),
    ("methane", "Methane"),
    ("ch4", "Methane"),
    ("propane", "Propane"),
    ("c3h8", "Propane"),
    ("propylene", "Propylene"),
    ("butane", "Butane"),
    ("ethane", "Ethane"),
    ("n-butane", "Butane"),
]

SENSOR_KEYWORDS = [
    ("thermocouple", "thermocouple"),
    ("radiometer", "radiometer"),
    ("anemometer", "anemometer"),
    ("camera", "camera"),
    ("photomultiplier", "photomultiplier tube"),
    ("pmt", "photomultiplier tube"),
    ("co2", "CO2 sensor"),
    ("o2 mole", "O2 sensor"),
    ("oxygen", "O2 sensor"),
    ("pressure", "pressure sensor"),
    ("soot", "soot diagnostic"),
    ("smps", "SMPS"),
    ("p-trak", "P-Trak"),
    ("dusttrak", "DustTrak"),
    ("oh plif", "OH PLIF"),
    ("co plif", "CO PLIF"),
]


def ensure_output_dir():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    return OUTPUT_DIR


def strip_wrapping_quotes(s):
    if s is None:
        return s
    t = str(s).strip()
    if len(t) >= 2 and t[0] == '"' and t[-1] == '"':
        t = t[1:-1].strip()
    return t.replace('""', '"')


def clean_val(v):
    if v is None or (isinstance(v, float) and math.isnan(v)):
        return None
    if pd.isna(v):
        return None
    s = strip_wrapping_quotes(str(v))
    return s if s else None


def _strip_known_units(s):
    t = str(s).strip()
    t = t.replace("~", "").replace("≈", "")
    t = t.replace("%", " ")
    t = re.sub(
        r"(?i)\b(mmhg|cm/s|sccm|mg/s|mg/min|kcal|atm|bar|psi|kpa|mm|cm|sec|s|w)\b",
        " ",
        t,
    )
    return re.sub(r"\s+", " ", t).strip()


def parse_num(v):
    if v is None or (isinstance(v, float) and math.isnan(v)) or pd.isna(v):
        return None
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v)
    s = _strip_known_units(v)
    if not s:
        return None
    if re.fullmatch(r"-?\d+(\.\d+)?\s*-\s*-?\d+(\.\d+)?", s):
        parts = [float(p.strip()) for p in re.split(r"\s*-\s*", s) if p.strip()]
        if len(parts) == 2:
            return sum(parts) / 2.0
    try:
        return float(s)
    except ValueError:
        m = re.search(r"-?\d+(?:\.\d+)?", s)
        return float(m.group(0)) if m else None


def parse_num_list(v):
    if v is None or pd.isna(v):
        return []
    s = str(v).replace("or", ";").replace(",", ";")
    vals = []
    for tok in s.split(";"):
        tok = tok.strip()
        if not tok:
            continue
        if re.fullmatch(r"-?\d+(\.\d+)?\s*-\s*-?\d+(\.\d+)?", _strip_known_units(tok)):
            parts = [parse_num(p) for p in re.split(r"\s*-\s*", tok)]
            parts = [p for p in parts if p is not None]
            if len(parts) == 2:
                vals.extend(parts)
                continue
        num = parse_num(tok)
        if num is not None:
            vals.append(num)
    return vals


def jsonable(value):
    if value is None or (isinstance(value, float) and math.isnan(value)):
        return None
    if hasattr(value, "item"):
        try:
            return jsonable(value.item())
        except Exception:
            return str(value)
    if isinstance(value, (pd.Timestamp,)):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def row_to_dict(row):
    data = {}
    for key, val in row.items():
        if pd.isna(val):
            continue
        data[str(key).strip()] = jsonable(val)
    return data


def normalize_fuel_name(raw):
    text = clean_val(raw)
    if not text:
        return None
    low = text.lower()
    for needle, canon in FUEL_CANONICAL:
        if needle in low:
            return canon
    return re.sub(r"\s+", " ", text).strip()


def infer_geometry_from_material(raw, default=None):
    text = (clean_val(raw) or "").lower()
    if "sphere" in text:
        return "sphere"
    if "slab" in text:
        return "slab"
    if "rod" in text or "cylinder" in text:
        return "rod/cylinder"
    if "film" in text:
        return "film"
    if "fabric" in text or "sibal" in text or "nomex" in text:
        return "fabric sheet"
    if "sheet" in text:
        return "sheet"
    if "candle" in text or "wax" in text:
        return "candle/wax"
    if "wake" in text:
        return "wake flame"
    return default


def classify_outcome(text):
    t = (clean_val(text) or "").lower()
    if not t:
        return None
    if "failed to ignite" in t or t.startswith("hot ignition: no"):
        return "no_ignition"
    if "insignificant" in t:
        return "insignificant_burn"
    if "self-ext" in t or re.search(r"\bse\b", t) or "self ext" in t:
        return "self_extinction"
    if "disrupt" in t:
        return "disruption"
    if "extinction" in t or "extinguish" in t:
        return "extinction"
    if "suppressed" in t or "suppress" in t:
        return "suppressed"
    if "sampled" in t:
        return "sampling"
    if "ignit" in t:
        return "ignition"
    if "burned" in t or "burn" in t:
        return "sustained_burn"
    return None


def extract_sensors(*texts):
    blob = " ".join(t for t in texts if t).lower()
    found = []
    for needle, label in SENSOR_KEYWORDS:
        if needle in blob and label not in found:
            found.append(label)
    return found


def psi_id_from_folder(folder_name):
    m = re.match(r"^(\d+)\b", str(folder_name).strip())
    return f"PSI-{int(m.group(1))}" if m else None


def dump_json(path, obj):
    ensure_output_dir()
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False, default=str)


def _positive_values(vals):
    return [v for v in (vals or []) if v is not None and v > 0]


def _nonnegative_values(vals):
    return [v for v in (vals or []) if v is not None and v >= 0]


def finalize_experiment_record(rec):
    """Null invalid numbers, expose a single is_assumed flag, and tag solver scope."""
    invalid = list(rec.get("invalid_fields") or [])
    assumed = list(rec.get("assumed_fields") or [])

    flow = rec.get("flow_velocity_cm_s")
    if flow is not None and flow < 0:
        rec["flow_velocity_cm_s"] = None
        rec["flow_values"] = _nonnegative_values(rec.get("flow_values"))
        src = rec.get("flow_velocity_source") or ""
        rec["flow_velocity_source"] = (src + " [invalid negative airflow nulled]").strip()
        if "flow_velocity_cm_s" not in invalid:
            invalid.append("flow_velocity_cm_s")

    pressure = rec.get("pressure_atm")
    if pressure is not None and pressure <= 0:
        rec["pressure_atm"] = None
        rec["pressure_values"] = _positive_values(rec.get("pressure_values"))
        src = rec.get("pressure_source") or ""
        rec["pressure_source"] = (src + " [invalid non-positive pressure nulled]").strip()
        if "pressure_atm" not in invalid:
            invalid.append("pressure_atm")

    rec["pressure_values"] = _positive_values(rec.get("pressure_values"))
    rec["flow_values"] = [
        v for v in (rec.get("flow_values") or [])
        if v is not None and v >= 0
    ]

    if rec.get("o2_is_assumed") and "o2_concentration_pct" not in assumed:
        assumed.append("o2_concentration_pct")
    if rec.get("pressure_is_assumed") and "pressure_atm" not in assumed:
        assumed.append("pressure_atm")
    if rec.get("flow_is_assumed") and "flow_velocity_cm_s" not in assumed:
        assumed.append("flow_velocity_cm_s")

    psi_id = rec.get("investigation_id")
    exclude_reason = ATMOSPHERE_SOLVER_EXCLUDE.get(psi_id)
    rec["include_in_atmosphere_solver"] = exclude_reason is None
    if exclude_reason:
        rec["solver_exclude_reason"] = exclude_reason

    rec["assumed_fields"] = assumed
    rec["invalid_fields"] = invalid
    rec["is_assumed"] = bool(assumed)
    rec["has_invalid_values"] = bool(invalid)
    rec["value_status"] = (
        "invalid" if invalid else ("assumed" if assumed else "reported")
    )
    rec.setdefault("condition_level", "experiment")
    return rec
