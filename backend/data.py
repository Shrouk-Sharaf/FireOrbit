"""Data access layer: loads the processed JSON once and exposes helpers."""
import json
import statistics
from collections import Counter
from functools import lru_cache
from pathlib import Path

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data_processed"
CHUNKS_PATH = ROOT / "chunking" / "chunks.json"

PILLARS = {
    "Prevention": "prevention",
    "Detection": "detection",
    "Suppression": "suppression",
    "Fundamental": "fundamental",
}
BURNING = {"ignition", "sustained_burn", "insignificant_burn"}
NOT_BURNING = {"no_ignition", "extinction", "self_extinction"}


@lru_cache
def _json(path: Path):
    if not path.exists():
        raise HTTPException(500, f"Missing data file: {path.name}")
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def kb() -> dict:
    return _json(DATA / "knowledge_base.json")


def experiments() -> list:
    return _json(DATA / "experiments_normalized.json")


def chunks() -> list:
    return _json(CHUNKS_PATH)


def pillar_key(inv: dict) -> str:
    name = (inv.get("pillar") or "").split(" ")[0]
    return PILLARS.get(name, "other")


def investigations() -> list:
    return kb()["investigations"]


def get_inv(psi_id: str) -> dict:
    for i in investigations():
        if i["psi_id"].lower() == psi_id.lower():
            return i
    raise HTTPException(404, f"Investigation {psi_id} not found")


def exps_of(psi_id: str) -> list:
    return [e for e in experiments() if e["investigation_id"].lower() == psi_id.lower()]


def _rng(values):
    vals = [v for v in values if v is not None]
    return {"min": min(vals), "max": max(vals)} if vals else {"min": None, "max": None}


def exp_stats(rows: list) -> dict:
    """Summary of a list of experiments (used by compare / radar / cards)."""
    return {
        "experiment_count": len(rows),
        "o2_pct": _rng(e["o2_concentration_pct"] for e in rows),
        "pressure_atm": _rng(e["pressure_atm"] for e in rows),
        "flow_cm_s": _rng(e["flow_velocity_cm_s"] for e in rows),
        "outcomes": dict(Counter(e["outcome_category"] for e in rows if e["outcome_category"])),
        "fuels": [f for f, _ in Counter(e["fuel_material_normalized"] for e in rows
                                        if e["fuel_material_normalized"]).most_common(8)],
        "gravity": sorted({e["gravity_level"] for e in rows if e["gravity_level"]}),
        "assumed_count": sum(1 for e in rows if e.get("is_assumed")),
        "invalid_count": sum(1 for e in rows if e.get("has_invalid_values")),
    }


def card(inv: dict) -> dict:
    return {
        "psi_id": inv["psi_id"],
        "acronym": inv["acronym"],
        "title": inv["title"],
        "pillar": pillar_key(inv),
        "pillar_label": inv["pillar"],
        "hardware_group": inv.get("hardware_group"),
        "relevance_score": inv.get("relevance_score"),
        "moon_base_score": inv.get("moon_base_score"),
        "moon_base_applicable": inv.get("moon_base_applicable"),
        "experiment_count": inv.get("experiment_count"),
        "o2_range": inv.get("o2_range"),
        "pressure_range_atm": inv.get("pressure_range_atm"),
        "fuel_phases": inv.get("fuel_phases"),
        "covers_moon_cabin_o2": inv.get("covers_moon_cabin_o2"),
        "covers_reduced_pressure": inv.get("covers_reduced_pressure"),
        "publication_count": len(inv.get("publications") or []),
    }


def median(vals):
    vals = [v for v in vals if v is not None]
    return statistics.median(vals) if vals else None
