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
