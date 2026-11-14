"""RAG chat, investigation summaries and the evidence-based 'what-if' engine."""
import json
import math
import os
import sys
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field

from .. import data as d

router = APIRouter(tags=["ai"])

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(REPO_ROOT / "embedding") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "embedding"))

CHROMA_PATH = REPO_ROOT / "index" / "chroma"
CHROMA_COLLECTION = "fireorbit"

# ---------- Retrieval Engine ----------
_retriever = None


def vector_ready() -> bool:
    """Check if chromadb and the vector index exist."""
    return (CHROMA_PATH / "chroma.sqlite3").exists()


def get_retriever():
    """Lazily load and cache the hybrid Retriever."""
    global _retriever
    if _retriever is not None:
        return _retriever
    try:
        from embedding.retrieval import Retriever
        _retriever = Retriever(mode="hybrid")
        return _retriever
    except Exception as exc:
        print(f"[AI] Failed to initialize hybrid Retriever: {exc}")
        return None


@lru_cache
def _keyword_index():
    import re
    docs = []
    for c in d.chunks():
        toks = re.findall(r"[a-z0-9]{3,}", c["text"].lower())
        docs.append((c, Counter(toks), len(toks) or 1))
    df = Counter(t for _, tf, _ in docs for t in tf)
    return docs, df


def is_conversational_or_irrelevant(query: str) -> bool:
    import re
    return bool(re.match(
        r"^\s*(?:hi|hello|hey|howdy|hola|greetings|good\s+(?:morning|afternoon|evening|night|day)|"
        r"how\s+are\s+you(?:(?:\s+doing|\s+today))?|"
        r"how(?:'s|\s+is)\s+it\s+going|"
        r"what(?:'s|\s+is)\s+up|"
        r"who\s+are\s+you|"
        r"what\s+(?:are\s+you|can\s+you\s+do|do\s+you\s+do)|"
        r"what\s+is\s+your\s+name|"
        r"thank\s+you|thanks|thx|"
        r"bye|goodbye|see\s+ya|see\s+you|"
        r"help)[\s\.\?!]*$",
        query.strip(),
        re.I,
    ))


def keyword_search(q: str, top_k: int, psi_id: Optional[str] = None, include_general: bool = False):
    import re
    if is_conversational_or_irrelevant(q):
        return []
    docs, df = _keyword_index()
    stop_words = {
        "how", "are", "you", "what", "the", "and", "for", "with", "all", "can", "tell",
        "about", "that", "this", "from", "which", "who", "why", "when", "where", "does",
        "will", "would", "could", "should", "your", "name", "help"
    }
    terms = set(re.findall(r"[a-z0-9]{3,}", q.lower())) - stop_words
    if not terms:
        return []
    n = len(docs)
    scored = []
    for c, tf, ln in docs:
        meta_psi = c.get("metadata", {}).get("psi_id")
        if psi_id and (meta_psi or "").lower() != psi_id.lower():
            continue
        if not include_general and not meta_psi:
            continue
        s = sum((tf[t] / ln) * math.log(1 + n / df[t]) for t in terms if t in tf)
        if s > 0.4:
            scored.append((s, c))
    scored.sort(key=lambda x: -x[0])
    return [{"chunk_id": c.get("chunk_id", ""), "text": c["text"],
             "metadata": c.get("metadata", {}), "score": round(s, 5)}
            for s, c in scored[:top_k]]


def retrieve(q: str, top_k: int = 6, psi_id: Optional[str] = None, include_general: bool = False):
    """Retrieve using hybrid Retriever, with keyword fallback if unavailable."""
    if is_conversational_or_irrelevant(q):
        return "none", [], None, None

    retriever = get_retriever()
    if retriever:
        try:
            # min_score=0.65 allows natural queries with slight wording variations through without false negatives
            hits = retriever.search(q, top_k=top_k, psi_id=psi_id, min_score=0.65)
            total = retriever.last_route.get("total_matches")
            summary = retriever.last_route.get("match_summary")
            return "hybrid", hits, total, summary
        except Exception as exc:
            print(f"[AI] Hybrid retrieval error: {exc}")
    # Fallback to local keyword search only if retriever failed to initialize
    hits = keyword_search(q, top_k, psi_id, include_general)
    return "keyword", hits, None, None


@router.get("/search")
def search(q: str = Query(..., min_length=2), top_k: int = Query(5, ge=1, le=20),
           psi_id: Optional[str] = None, include_general: bool = False):
    mode, hits, _, _ = retrieve(q, top_k, psi_id, include_general)
    return {"retrieval": mode, "hits": hits}


# ---------- LLM Layer ----------
def llm_available() -> bool:
    try:
        from llm import GeminiClient
        client = GeminiClient()
        return bool(client.api_key)
    except Exception:
        return bool(os.getenv("GEMINI_API_KEY"))


def format_source_for_frontend(chunk: Dict[str, Any]) -> Dict[str, Any]:
    """Map chunk or normalized source to the frontend Source interface."""
    meta = chunk.get("metadata", {})
    source_name = (
        chunk.get("source")
        or meta.get("filename")
        or meta.get("source_id")
        or meta.get("psi_id")
        or "NASA PSI Document"
    )
    page = chunk.get("page") if chunk.get("page") is not None else meta.get("page")
    chunk_id = chunk.get("chunk_id") or chunk.get("id") or "chunk_0"
    content = chunk.get("text") or chunk.get("content") or ""
    label = f"{source_name}{f' p.{page}' if page else ''}"

    return {
        "label": label,
        "document": source_name,
        "psi_id": chunk.get("psi_id") or meta.get("psi_id"),
        "file": meta.get("filename"),
        "page": page,
        "chunk_id": chunk_id,
        "content": content[:1200],
    }


class ChatRequest(BaseModel):
    question: str = Field(min_length=3)
    conversation_id: Optional[str] = None
    psi_id: Optional[str] = None
    top_k: int = Field(6, ge=1, le=15)
    include_general: bool = Field(False)
    psi_only: bool = Field(False)


@router.post("/chat")
def chat(req: ChatRequest):
    mode, hits, total_matches, match_summary = retrieve(
        req.question, req.top_k, req.psi_id, req.include_general and not req.psi_only
    )

    if not llm_available():
        frontend_sources = [format_source_for_frontend(h) for h in hits]
        return {
            "answer": None,
            "llm": False,
            "retrieval": mode,
            "sources": frontend_sources,
            "passages": [h["text"][:600] for h in hits],
            "note": "Set GEMINI_API_KEY to generate answers; returning retrieved passages only."
        }

    try:
        from llm import generate_answer, GeminiClient
        client = GeminiClient()
        result = generate_answer(
            question=req.question,
            retrieved_chunks=hits,
            client=client,
            total_matches=total_matches,
            match_summary=match_summary,
        )

        # Merge cited sources with passage text for display in the frontend
        # The result["sources"] contains {source, page, psi_id, chunk_id, ...}
        # We supplement with text snippet so frontend Source view has full content
        hit_map = {h.get("chunk_id", ""): h.get("text", "") for h in hits}
        frontend_sources = []
        for s in result.get("sources", []):
            cid = s.get("chunk_id", "")
            snippet = hit_map.get(cid, "")
            page_val = s.get("page")
            page_suffix = f" p.{page_val}" if page_val is not None else ""
            src_name = s.get("source", "NASA PSI Document")
            frontend_sources.append({
                "label": f"{src_name}{page_suffix}",
                "document": src_name,
                "psi_id": s.get("psi_id"),
                "file": src_name,
                "page": page_val,
                "chunk_id": cid,
                "content": snippet[:1200] if snippet else "",
            })

        return {
            "answer": result.get("answer", ""),
            "llm": True,
            "model": result.get("model", client.model),
            "retrieval": mode,
            "sources": frontend_sources,
            "warning": result.get("warning"),
        }
    except Exception as exc:
        raise HTTPException(502, f"LLM generation failed: {exc}") from exc


_summary_cache: dict = {}


@router.get("/investigations/{psi_id}/summary")
def summary(psi_id: str, refresh: bool = False):
    inv = d.get_inv(psi_id)
    if psi_id in _summary_cache and not refresh:
        return _summary_cache[psi_id]

    if llm_available():
        from llm import GeminiClient
        from llm.prompt import SYSTEM_PROMPT
        client = GeminiClient()
        facts = {k: inv.get(k) for k in ("title", "objective", "hypothesis", "approach", "research_impacts",
                                         "tested_fuels", "o2_range", "pressure_range_atm")}
        prompt = (
            "Write a ~200-word plain-English summary of this investigation for spacecraft fire safety:\n"
            f"{json.dumps(facts, ensure_ascii=False)[:12000]}"
        )
        text = client.generate(prompt, SYSTEM_PROMPT)
        out = {"psi_id": inv["psi_id"], "summary": text, "generated_by": client.model}
    else:
        out = {
            "psi_id": inv["psi_id"],
            "generated_by": None,
            "summary": (inv.get("objective") or "")[:900],
            "note": "Extractive fallback (objective text). Set GEMINI_API_KEY for an AI summary."
        }
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
            s += 0.5
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
