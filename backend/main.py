"""FireOrbit backend (FastAPI).

Run from the repo root:
    pip install -r backend/requirements.txt
    uvicorn backend.main:app --reload
Docs: http://127.0.0.1:8000/docs
Optional env: GEMINI_API_KEY (LLM answers/summaries), GEMINI_MODEL, CORS_ORIGINS (comma-separated).
"""
import os
from dotenv import load_dotenv
load_dotenv()
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from . import data as d
from .routers import ai, analytics, investigations

app = FastAPI(title="FireOrbit API", version="0.2.0",
              description="NASA PSI combustion data for spacecraft fire-safety research.")
app.add_middleware(CORSMiddleware,
                   allow_origins=os.getenv("CORS_ORIGINS", "*").split(","),
                   allow_methods=["*"], allow_headers=["*"])

for r in (investigations.router, analytics.router, ai.router):
    app.include_router(r, prefix="/api")


@app.get("/health")
def health():
    k = d.kb()
    return {"status": "ok", "generated_at": k["generated_at"], "investigations": k["total_investigations"],
            "experiments": len(d.experiments()), "llm_configured": ai.llm_available(),
            "vector_search": ai.vector_ready(), "retrieval_mode": "hybrid" if ai.vector_ready() else "keyword"}