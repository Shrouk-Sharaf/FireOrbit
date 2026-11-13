# FireOrbit dashboard (frontend)

Static, dependency-free site. Open `index.html` in a browser (keep the 4 files together), or serve with `python3 -m http.server`.

- `index.html`, `styles.css`, `app.js` — UI
- `data.js` — compact bundle built from `data_processed/` (16 investigations, 1,589 test records, 465 report passages)

Tabs: Overview · Rank (use-case weighted) · Explore data (filters, charts, CSV export) · Compare · Ask FireOrbit · Gaps & Earth.

"Ask FireOrbit" does in-browser keyword retrieval with citations. To use an LLM, run a backend and paste its URL in the page; it receives POST `{question, passages}` and must return `{answer}`.
