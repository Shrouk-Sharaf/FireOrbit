# FireOrbit backend

    pip install -r backend/requirements.txt
    uvicorn backend.main:app --reload        # run from the repo root
    # http://127.0.0.1:8000/docs

Optional: `export GEMINI_API_KEY=...` for AI answers/summaries; `pip install chromadb sentence-transformers`
for semantic search (keyword fallback otherwise).

| Dashboard page | Endpoints |
|---|---|
| Overview | `GET /api/overview`, `GET /api/investigations` |
| Deep dive | `GET /api/investigations/{id}`, `/api/investigations/{id}/summary` |
| Compare | `GET /api/compare?ids=PSI-20,PSI-69`, `/api/analytics/radar?ids=` |
| Explore by condition | `GET /api/experiments/facets`, `GET /api/experiments?o2_min=&fuel=...` |
| Charts | `/api/analytics/o2-coverage`, `/material-matrix`, `/hardware-lineage`, `/publication-network` |
| Moon Base mode / insights | `GET /api/moon-base`, `/api/gaps`, `/api/timeline` |
| Earth applications | `GET /api/earth-applications` |
| AI chat | `POST /api/chat`, `GET /api/search?q=` |
| What-if | `POST /api/what-if`, `GET /api/what-if/materials` |
