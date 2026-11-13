"""RAG chat, investigation summaries and the evidence-based 'what-if' engine."""
import json
import math
import os
import re
import time
import urllib.error
import urllib.request
from collections import Counter
from functools import lru_cache
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .. import data as d

router = APIRouter(tags=["ai"])

GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
CHROMA_PATH = d.ROOT / "embedding" / "chroma_db"
CHROMA_COLLECTION = "fireorbit_chunks"
EMBED_MODEL = "BAAI/bge-base-en-v1.5"
QUERY_PREFIX = "Represent this sentence for searching relevant passages: "


# ---------- retrieval ----------
_engine = None


def vector_ready() -> bool:
    """Cheap check (no model loading): deps installed and an index has been built."""
    from importlib.util import find_spec
    return (find_spec("chromadb") is not None and find_spec("sentence_transformers") is not None
            and (CHROMA_PATH / "chroma.sqlite3").exists())


def _vector_engine():
    """Returns (collection, model) or None. Failures are not cached, so an index built
    while the server is running is picked up on a later request."""
    global _engine
    if _engine is not None:
        return _engine
    if not vector_ready():
        return None
    try:
        import chromadb
        from sentence_transformers import SentenceTransformer
        collection = chromadb.PersistentClient(path=str(CHROMA_PATH)).get_collection(CHROMA_COLLECTION)
        if collection.count() == 0:
            return None
        _engine = (collection, SentenceTransformer(EMBED_MODEL))
    except Exception:
        return None
    return _engine


@lru_cache
def _keyword_index():
    docs = []
    for c in d.chunks():
        toks = re.findall(r"[a-z0-9]{3,}", c["text"].lower())
        docs.append((c, Counter(toks), len(toks) or 1))
    df = Counter(t for _, tf, _ in docs for t in tf)
    return docs, df


def keyword_search(q: str, top_k: int, psi_id: Optional[str], include_general: bool = False):
    docs, df = _keyword_index()
    terms = set(re.findall(r"[a-z0-9]{3,}", q.lower()))
    n = len(docs)
    scored = []
    for c, tf, ln in docs:
        meta_psi = c["metadata"].get("psi_id")
        if psi_id and (meta_psi or "").lower() != psi_id.lower():
            continue
        if not include_general and not meta_psi:  # skip the general NASA mini-book
            continue
        s = sum((tf[t] / ln) * math.log(1 + n / df[t]) for t in terms if t in tf)
        if s > 0:
            scored.append((s, c))
    scored.sort(key=lambda x: -x[0])
    return [{"id": c["chunk_id"], "text": c["text"], "metadata": c["metadata"], "score": round(s, 5)}
            for s, c in scored[:top_k]]


def retrieve(q: str, top_k: int, psi_id: Optional[str], include_general: bool = False):
    """By default only the PSI investigations are searched (the general NASA mini-book is
    excluded); pass include_general=True to search it too."""
    if psi_id:
        psi_id = d.get_inv(psi_id)["psi_id"]  # canonical id (404 if unknown)
    engine = _vector_engine()
    if engine:
        try:
            collection, model = engine
            if psi_id:
                where = {"psi_id": psi_id}
            elif include_general:
                where = None
            else:
                where = {"psi_id": {"$in": [i["psi_id"] for i in d.investigations()]}}
            emb = model.encode([QUERY_PREFIX + q], normalize_embeddings=True).tolist()
            res = collection.query(query_embeddings=emb, n_results=top_k, where=where)
            return "vector", [{"id": i, "text": t, "metadata": m, "score": round(1 - dist, 4)}
                              for i, t, m, dist in zip(res["ids"][0], res["documents"][0],
                                                       res["metadatas"][0], res["distances"][0])]
        except Exception:
            pass  # fall back to keyword search
    return "keyword", keyword_search(q, top_k, psi_id, include_general)


@router.get("/search")
def search(q: str = Query(..., min_length=2), top_k: int = Query(5, ge=1, le=20),
           psi_id: Optional[str] = None, include_general: bool = False):
    mode, hits = retrieve(q, top_k, psi_id, include_general)
    return {"retrieval": mode, "hits": hits}


# ---------- LLM ----------
def llm_available() -> bool:
    return bool(os.getenv("GEMINI_API_KEY"))


def gemini(prompt: str, system: str) -> str:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise HTTPException(503, "GEMINI_API_KEY is not set")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
    body = json.dumps({
        "systemInstruction": {"parts": [{"text": system}]},
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2},
    }).encode()
    req = urllib.request.Request(url, body, {"Content-Type": "application/json", "x-goog-api-key": key})
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.load(r)["candidates"][0]["content"]["parts"][0]["text"]
    except (urllib.error.URLError, KeyError, IndexError) as exc:
        raise HTTPException(502, f"LLM call failed: {exc}") from exc


SYSTEM = ("You are FireOrbit, an assistant for NASA spacecraft fire-safety research (PSI database). "
          "Answer ONLY from the provided context. Cite sources using the exact bracketed label shown "
          "before each passage, e.g. [PSI-69] or [NASA ISS mini-book p.35]. If the context does not "
          "contain the answer, say so. Flag assumed or invalid data and note that no partial-gravity "
          "(Moon/Mars) combustion data exists in PSI.")


def source_label(meta: dict) -> str:
    """PSI id when available, otherwise 'file name p.N' so citations are never None."""
    if meta.get("psi_id"):
        return meta["psi_id"]
    name = (meta.get("filename") or "source").replace(".pdf", "")
    name = "NASA ISS mini-book" if "mini-book" in name else name
    return f"{name} p.{meta.get('page')}" if meta.get("page") else name


class ChatRequest(BaseModel):
    question: str = Field(min_length=3)
    psi_id: Optional[str] = None
    top_k: int = Field(6, ge=1, le=15)
    include_general: bool = Field(False, description="also search the general NASA ISS mini-book")
    psi_only: bool = Field(False, description="True = answer only from the 16 PSI investigations")


@router.post("/chat")
def chat(req: ChatRequest):
    mode, hits = retrieve(req.question, req.top_k, req.psi_id, req.include_general and not req.psi_only)
    sources = [{"label": source_label(h["metadata"]), "psi_id": h["metadata"].get("psi_id"),
                "file": h["metadata"].get("filename"), "page": h["metadata"].get("page"),
                "chunk_id": h["id"], "content": h["text"][:1200]} for h in hits]
    if not llm_available():
        return {"answer": None, "llm": False, "retrieval": mode, "sources": sources,
                "passages": [h["text"][:600] for h in hits],
                "note": "Set GEMINI_API_KEY to generate answers; returning retrieved passages only."}
    context = "\n\n".join(f"[{source_label(h['metadata'])}] {h['text']}" for h in hits)
    answer = gemini(f"Context:\n{context}\n\nQuestion: {req.question}", SYSTEM)
    return {"answer": answer, "llm": True, "retrieval": mode, "sources": sources}


_summary_cache: dict = {}


@router.get("/investigations/{psi_id}/summary")
def summary(psi_id: str, refresh: bool = False):
    inv = d.get_inv(psi_id)
    if psi_id in _summary_cache and not refresh:
        return _summary_cache[psi_id]
    if llm_available():
        facts = {k: inv.get(k) for k in ("title", "objective", "hypothesis", "approach", "research_impacts",
                                         "tested_fuels", "o2_range", "pressure_range_atm")}
        text = gemini("Write a ~200-word plain-English summary of this investigation for spacecraft "
                      f"fire safety:\n{json.dumps(facts, ensure_ascii=False)[:12000]}", SYSTEM)
        out = {"psi_id": inv["psi_id"], "summary": text, "generated_by": GEMINI_MODEL}
    else:
        out = {"psi_id": inv["psi_id"], "generated_by": None,
               "summary": (inv.get("objective") or "")[:900],
               "note": "Extractive fallback (objective text). Set GEMINI_API_KEY for an AI summary."}
    _summary_cache[psi_id] = out
    return out


# ---------- what-if (nearest-neighbour evidence, not a trained model) ----------
class WhatIf(BaseModel):
    o2_pct: float = Field(ge=0, le=100)
    pressure_atm: Optional[float] = Field(None, gt=0, le=3)
    flow_cm_s: Optional[float] = Field(None, ge=0)
    material: Optional[str] = Field(None, description="substring, e.g. 'PMMA'")
    gravity: str = Field("microgravity", description="microgravity | moon | mars | earth")
    k: int = Field(15, ge=3, le=50)


def _solver_pool():
    """Experiments usable for what-if: known O2, burn/no-burn outcome, valid, solver-included."""
    return [e for e in d.experiments()
            if e["o2_concentration_pct"] is not None and e["outcome_category"] in (d.BURNING | d.NOT_BURNING)
            and e.get("include_in_atmosphere_solver") and not e.get("has_invalid_values")]


@router.get("/what-if/materials")
def what_if_materials():
    """Materials the what-if engine has evidence for (populate the UI dropdown)."""
    return [{"material": m, "experiments": n}
            for m, n in Counter(e["fuel_material_normalized"] for e in _solver_pool()).most_common()]


@router.post("/what-if")
def what_if(q: WhatIf):
    base = _solver_pool()
    pool = [e for e in base if not q.material
            or q.material.lower() in (e["fuel_material_normalized"] or "").lower()]
    if not pool:
        raise HTTPException(404, {"message": f"No usable experiments for material '{q.material}'.",
                                  "available_materials": sorted({e["fuel_material_normalized"] for e in base})})

    def dist(e):
        s = ((e["o2_concentration_pct"] - q.o2_pct) / 10) ** 2
        if q.pressure_atm is not None and e["pressure_atm"] is not None:
            s += ((e["pressure_atm"] - q.pressure_atm) / 0.3) ** 2
        elif q.pressure_atm is not None:
            s += 0.5  # unknown pressure: penalise rather than ignore
        if q.flow_cm_s is not None and e["flow_velocity_cm_s"] is not None:
            s += ((e["flow_velocity_cm_s"] - q.flow_cm_s) / 20) ** 2
        return math.sqrt(s)

    near = sorted(((dist(e), e) for e in pool), key=lambda x: x[0])[:q.k]
    burning = sum(1 for _, e in near if e["outcome_category"] in d.BURNING)
    share = burning / len(near)
    mean_dist = sum(x for x, _ in near) / len(near)
    o2s = [e["o2_concentration_pct"] for e in pool]
    extrapolating = not (min(o2s) <= q.o2_pct <= max(o2s))
    confidence = "high" if mean_dist < 0.3 and len(near) >= 10 else "medium" if mean_dist < 0.8 else "low"
    if extrapolating:
        confidence = "low"
    warnings = ["Based on nearest observed experiments, not a physical model."]
    if q.gravity.lower() in ("moon", "mars"):
        warnings.append("No partial-gravity data in PSI: results are microgravity/1-g analogues only "
                        "(upcoming: LUCI, FM2).")
    if extrapolating:
        warnings.append("O2 level is outside the range covered by matching experiments (extrapolation).")
    if len({e["investigation_id"] for _, e in near}) == 1:
        warnings.append("All neighbours come from a single investigation; its outcome labels may not mean "
                        "'will it burn' (e.g. droplet extinction studies only record how flames went out).")
    if q.pressure_atm is not None and sum(1 for _, e in near if e["pressure_atm"] is None) > len(near) / 2:
        warnings.append("Most neighbours have no recorded pressure; pressure effect is unverified.")
    return {
        "burn_likelihood": round(share, 3),
        "risk_level": "high" if share >= 0.66 else "moderate" if share >= 0.33 else "low",
        "confidence": confidence,
        "neighbours_used": len(near),
        "mean_distance": round(mean_dist, 3),
        "outcome_breakdown": dict(Counter(e["outcome_category"] for _, e in near)),
        "investigations": sorted({e["investigation_id"] for _, e in near}),
        "nearest_experiments": [{"experiment_id": e["experiment_id"], "distance": round(x, 3),
                                 "fuel": e["fuel_material_normalized"], "o2_pct": e["o2_concentration_pct"],
                                 "pressure_atm": e["pressure_atm"], "flow_cm_s": e["flow_velocity_cm_s"],
                                 "outcome": e["outcome_category"]} for x, e in near[:8]],
        "warnings": warnings,
    }