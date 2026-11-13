from typing import Optional

from fastapi import APIRouter, HTTPException, Query

from .. import data as d

router = APIRouter(tags=["investigations & experiments"])


@router.get("/overview")
def overview():
    """Dashboard home: cards grouped by pillar + headline stats."""
    cards = [d.card(i) for i in d.investigations()]
    exps = d.experiments()
    by_pillar: dict = {}
    for c in cards:
        by_pillar.setdefault(c["pillar"], []).append(c)
    return {
        "stats": {
            "investigations": len(cards),
            "experiments": len(exps),
            "reports": sum(i.get("reports_count") or 0 for i in d.investigations()),
            "publications": sum(c["publication_count"] for c in cards),
            "generated_at": d.kb()["generated_at"],
        },
        "cards": sorted(cards, key=lambda c: -(c["relevance_score"] or 0)),
        "by_pillar": by_pillar,
    }


@router.get("/investigations")
def list_investigations(pillar: Optional[str] = None, hardware: Optional[str] = None,
                        fuel_phase: Optional[str] = None, moon_applicable: Optional[bool] = None,
                        sort: str = Query("relevance_score",
                                          pattern="^(relevance_score|moon_base_score|experiment_count|acronym)$")):
    cards = [d.card(i) for i in d.investigations()]
    if pillar:
        cards = [c for c in cards if c["pillar"] == pillar.lower()]
    if hardware:
        cards = [c for c in cards if hardware.lower() in (c["hardware_group"] or "").lower()]
    if fuel_phase:
        cards = [c for c in cards if fuel_phase in (c["fuel_phases"] or [])]
    if moon_applicable is not None:
        cards = [c for c in cards if c["moon_base_applicable"] == moon_applicable]
    rev = sort != "acronym"
    return sorted(cards, key=lambda c: (c[sort] is None, c[sort] or 0) if rev else c[sort], reverse=rev)


@router.get("/investigations/{psi_id}")
def investigation_detail(psi_id: str):
    """Deep-dive page: full metadata + experiment stats + related investigations."""
    inv = d.get_inv(psi_id)
    rows = d.exps_of(psi_id)
    detail = {k: v for k, v in inv.items() if k not in ("reports", "sample_experiments")}
    detail["pillar_key"] = d.pillar_key(inv)
    detail["experiment_stats"] = d.exp_stats(rows)
    detail["reports"] = [{k: r.get(k) for k in ("filename", "total_pages", "sections")}
                         | {"section_names": list((r.get("sections") or {}).keys())}
                         for r in inv.get("reports", [])]
    for r in detail["reports"]:  # keep payload small: names only, text via /search or /chat
        r.pop("sections", None)
    detail["related"] = [d.card(d.get_inv(x)) for x in inv.get("related_investigations") or []
                         if any(i["psi_id"] == x for i in d.investigations())]
    return detail


@router.get("/experiments/facets")
def facets():
    """Values for the filter UI of 'Explore by Condition'."""
    rows = d.experiments()
    return {
        "fuel_phases": sorted({e["fuel_phase"] for e in rows if e["fuel_phase"]}),
        "outcomes": sorted({e["outcome_category"] for e in rows if e["outcome_category"]}),
        "gravity_levels": sorted({e["gravity_level"] for e in rows if e["gravity_level"]}),
        "flow_directions": sorted({e["flow_direction"] for e in rows if e["flow_direction"]}),
        "fuels": [f for f, _ in __import__("collections").Counter(
            e["fuel_material_normalized"] for e in rows if e["fuel_material_normalized"]).most_common(60)],
        "ranges": {"o2_pct": d.exp_stats(rows)["o2_pct"],
                   "pressure_atm": d.exp_stats(rows)["pressure_atm"],
                   "flow_cm_s": d.exp_stats(rows)["flow_cm_s"]},
    }


@router.get("/experiments")
def list_experiments(
    psi_id: Optional[str] = None, fuel: Optional[str] = None, fuel_phase: Optional[str] = None,
    outcome: Optional[str] = None, gravity: Optional[str] = None,
    o2_min: Optional[float] = None, o2_max: Optional[float] = None,
    pressure_min: Optional[float] = None, pressure_max: Optional[float] = None,
    flow_min: Optional[float] = None, flow_max: Optional[float] = None,
    valid_only: bool = False, exclude_assumed: bool = False,
    limit: int = Query(50, ge=1, le=500), offset: int = Query(0, ge=0),
):
    def inside(v, lo, hi):
        if lo is None and hi is None:
            return True
        return v is not None and (lo is None or v >= lo) and (hi is None or v <= hi)

    def keep(e):
        return (
            (not psi_id or e["investigation_id"].lower() == psi_id.lower())
            and (not fuel or fuel.lower() in (e.get("fuel_material_normalized") or "").lower())
            and (not fuel_phase or e.get("fuel_phase") == fuel_phase)
            and (not outcome or e.get("outcome_category") == outcome)
            and (not gravity or gravity.lower() in (e.get("gravity_level") or "").lower())
            and inside(e.get("o2_concentration_pct"), o2_min, o2_max)
            and inside(e.get("pressure_atm"), pressure_min, pressure_max)
            and inside(e.get("flow_velocity_cm_s"), flow_min, flow_max)
            and not (valid_only and e.get("has_invalid_values"))
            and not (exclude_assumed and e.get("is_assumed"))
        )

    out = [e for e in d.experiments() if keep(e)]
    investigations_hit = sorted({e["investigation_id"] for e in out})
    return {"total": len(out), "limit": limit, "offset": offset,
            "investigations": investigations_hit, "items": out[offset:offset + limit]}


@router.get("/experiments/{experiment_id}")
def experiment_detail(experiment_id: str):
    for e in d.experiments():
        if e["experiment_id"] == experiment_id:
            return e
    raise HTTPException(404, f"Experiment {experiment_id} not found")
