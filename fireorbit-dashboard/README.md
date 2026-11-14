# FireOrbit dashboard (frontend)

Static, dependency-free site (vanilla JS). **All data is loaded from the FastAPI backend** (`backend/`).
If the backend is not running, it falls back to the offline snapshot in `data.js`; a badge in the header shows which one is in use (`● Live API` / `● Offline snapshot`).

## Run

```bash
# 1) backend (from the repo root)
uvicorn backend.main:app --reload

# 2) dashboard (from this folder)
python -m http.server 5500
```

Open http://localhost:5500

Optional: put `GEMINI_API_KEY=...` in a `.env` file in the repo root to get written AI answers in the **Ask FireOrbit** tab (without it, the tab shows the retrieved passages).

## Files

- `index.html`, `styles.css` — page and styles
- `api.js` — loads investigations, experiments, Moon-base ranking and gaps from the backend and converts them to the shape `app.js` uses; falls back to `data.js` if the backend is unreachable
- `app.js` — UI (tabs: Overview · Rank · Explore data · Compare · Ask FireOrbit · Gaps & Earth)
- `data.js` — offline snapshot built from `data_processed/` (fallback only)

## Backend endpoints used

`GET /health`, `GET /api/investigations`, `GET /api/investigations/{psi_id}`, `GET /api/experiments` (paged), `GET /api/moon-base`, `GET /api/gaps`, `POST /api/chat`.

The backend URL defaults to `http://localhost:8000`. Change it in **Ask FireOrbit → Backend settings** (the page reloads); clear it to use the offline snapshot only.
