from collections import Counter, defaultdict
from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .. import data as d

router = APIRouter(tags=["analytics"])

MOON = {"o2_min": 26.5, "o2_max": 34.0, "pressure_atm": 0.694}  # 10.2 psia anchor

TIMELINE = [  # from the project strategy doc
    {"year": 1967, "event": "Apollo 1 cabin fire"},
    {"year": 1997, "event": "Mir space station fire"},
    {"year": 2001, "event": "SAME smoke measurement experiments"},
    {"year": 2009, "event": "BASS flammability experiments"},
    {"year": 2016, "event": "Saffire large-scale fire experiments"},
    {"year": None, "event": "LUCI / FM2 (upcoming partial-gravity studies)"},
]


@router.get("/compare")
def compare(ids: str = Query(..., description="comma-separated PSI ids, 2-3 items, e.g. PSI-20,PSI-69")):
    wanted = [x.strip() for x in ids.split(",") if x.strip()]
    if not 2 <= len(wanted) <= 3:
        raise HTTPException(400, "Provide 2 or 3 investigation ids")
    out = []
    for psi in wanted:
        inv = d.get_inv(psi)
        out.append({
            **d.card(inv),
            "hardware": inv.get("hardware"),
            "flight_platform": inv.get("flight_platform"),
            "objective": inv.get("objective"),
            "hypothesis": inv.get("hypothesis"),
            "tested_fuels": inv.get("tested_fuels"),
            "descriptors": inv.get("descriptors"),
            "experiment_stats": d.exp_stats(d.exps_of(psi)),
        })
    shared_fuels = set.intersection(*[set(o["experiment_stats"]["fuels"]) for o in out])
    return {"items": out, "shared_fuels": sorted(shared_fuels)}


@router.get("/analytics/o2-coverage")
def o2_coverage(bin_width: float = Query(5.0, gt=0, le=25)):
    """Which investigation tested at which O2 level (heatmap data)."""
    cells: dict = defaultdict(Counter)
    for e in d.experiments():
        o2 = e["o2_concentration_pct"]
        if o2 is None:
            continue
        lo = int(o2 // bin_width * bin_width)
        cells[e["investigation_id"]][lo] += 1
    bins = sorted({b for c in cells.values() for b in c})
    acr = {i["psi_id"]: i["acronym"] for i in d.investigations()}
    return {
        "bin_width": bin_width,
        "moon_cabin_band": {"min": MOON["o2_min"], "max": MOON["o2_max"]},
        "bins": bins,
        "rows": [{"psi_id": p, "acronym": acr.get(p), "counts": {str(b): c.get(b, 0) for b in bins}}
                 for p, c in sorted(cells.items())],
        "without_o2_data": sorted({i["psi_id"] for i in d.investigations()} - set(cells)),
    }


@router.get("/analytics/material-matrix")
def material_matrix(min_tests: int = Query(3, ge=1)):
    """Fuel x investigation outcome counts (flammability matrix)."""
    m: dict = defaultdict(lambda: defaultdict(Counter))
    for e in d.experiments():
        if e["fuel_material_normalized"] and e["outcome_category"]:
            m[e["fuel_material_normalized"]][e["investigation_id"]][e["outcome_category"]] += 1
    rows = []
    for fuel, per_inv in m.items():
        total = sum(sum(c.values()) for c in per_inv.values())
        if total >= min_tests:
            rows.append({"fuel": fuel, "total": total,
                         "by_investigation": {k: dict(v) for k, v in per_inv.items()}})
    return sorted(rows, key=lambda r: -r["total"])


@router.get("/analytics/radar")
def radar(ids: str):
    """Parameter ranges per investigation, normalised 0-1 against the whole dataset."""
    full = d.exp_stats(d.experiments())
    axes = ["o2_pct", "pressure_atm", "flow_cm_s"]

    def norm(v, ax):
        lo, hi = full[ax]["min"], full[ax]["max"]
        return None if v is None or hi == lo else round((v - lo) / (hi - lo), 3)

    out = []
    for psi in [x.strip() for x in ids.split(",") if x.strip()]:
        s = d.exp_stats(d.exps_of(psi))
        out.append({"psi_id": psi, "axes": {ax: {"min": norm(s[ax]["min"], ax), "max": norm(s[ax]["max"], ax),
                                                  "raw": s[ax]} for ax in axes}})
    return {"dataset_ranges": {ax: full[ax] for ax in axes}, "items": out}


@router.get("/analytics/hardware-lineage")
def hardware_lineage():
    tree: dict = defaultdict(list)
    for i in d.investigations():
        tree[i.get("hardware_group") or "Unknown"].append(
            {"psi_id": i["psi_id"], "acronym": i["acronym"], "pillar": d.pillar_key(i)})
    return [{"hardware_group": h, "investigations": v} for h, v in sorted(tree.items())]


@router.get("/analytics/publication-network")
def publication_network():
    """Nodes = investigations; edges = declared relation or shared publication authors."""
    invs = d.investigations()
    authors = {i["psi_id"]: {a.strip() for p in (i.get("publications") or [])
                             for a in (p.get("authors") or "").replace(";", ",").split(",") if a.strip()}
               for i in invs}
    edges = {}
    for a in invs:
        for b in invs:
            if a["psi_id"] >= b["psi_id"]:
                continue
            shared = sorted(authors[a["psi_id"]] & authors[b["psi_id"]])
            related = b["psi_id"] in (a.get("related_investigations") or []) or \
                a["psi_id"] in (b.get("related_investigations") or [])
            if shared or related:
                edges[(a["psi_id"], b["psi_id"])] = {"source": a["psi_id"], "target": b["psi_id"],
                                                     "related": related, "shared_authors": shared[:10],
                                                     "weight": len(shared) + (2 if related else 0)}
    return {"nodes": [{**d.card(i), "publications": len(i.get("publications") or [])} for i in invs],
            "edges": list(edges.values())}


@router.get("/moon-base")
def moon_base(o2_min: float = MOON["o2_min"], o2_max: float = MOON["o2_max"],
              pressure_min: Optional[float] = None, pressure_max: Optional[float] = None):
    """'Moon Base Mode': ranking, matching experiments per investigation, and data gaps."""
    matching = [e for e in d.experiments()
                if e["o2_concentration_pct"] is not None and o2_min <= e["o2_concentration_pct"] <= o2_max
                and (pressure_min is None or (e["pressure_atm"] is not None and e["pressure_atm"] >= pressure_min))
                and (pressure_max is None or (e["pressure_atm"] is not None and e["pressure_atm"] <= pressure_max))]
    per_inv = Counter(e["investigation_id"] for e in matching)
    ranking = [{**r, "matching_experiments": per_inv.get(r["psi_id"], 0)} for r in d.kb()["moon_base_ranking"]]
    return {
        "conditions": {"o2_min": o2_min, "o2_max": o2_max, "pressure_min": pressure_min,
                       "pressure_max": pressure_max, "moon_cabin_anchor_atm": MOON["pressure_atm"]},
        "matching_experiments": len(matching),
        "ranking": ranking,
        "gaps": d.kb()["knowledge_gaps"],
        "caveat": "All PSI data is microgravity/1-g; no partial-gravity (1/6 g) measurements exist.",
    }


@router.get("/gaps")
def gaps():
    return d.kb()["knowledge_gaps"]


@router.get("/earth-applications")
def earth_applications():
    return [{**d.card(i), "research_impacts": i.get("research_impacts"), "earth_application": i.get("earth_application")}
            for i in d.investigations() if i.get("earth_application")]


@router.get("/timeline")
def timeline():
    return TIMELINE
