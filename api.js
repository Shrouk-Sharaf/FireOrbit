/* FireOrbit dashboard — data loader.
 * Loads every dataset from the FastAPI backend and converts it to the compact shape app.js expects.
 * If the backend is unreachable it silently falls back to the offline snapshot in data.js.
 *   window.FIREORBIT_SOURCE : 'api' | 'embedded'
 *   window.FIREORBIT_READY  : Promise that resolves once window.FIREORBIT_DATA is set
 */
(function () {
  'use strict';
  const DEFAULT_API = 'http://localhost:8000';
  const EXP_PAGE = 500; // backend max page size
  const lsGet = k => { try { return localStorage.getItem(k); } catch (e) { return null; } };
  const saved = lsGet('fireorbit.api');
  const BASE = (saved === null ? DEFAULT_API : saved).trim().replace(/\/+$/, '').replace(/\/(api\/chat|ask)$/, '');
  window.FIREORBIT_API_BASE = BASE;
  const embedded = window.FIREORBIT_DATA || null; // offline snapshot (data.js)

  async function get(path, ms = 15000) {
    const ctl = new AbortController(); const t = setTimeout(() => ctl.abort(), ms);
    try {
      const r = await fetch(BASE + path, { signal: ctl.signal });
      if (!r.ok) throw new Error(path + ' → HTTP ' + r.status);
      return await r.json();
    } finally { clearTimeout(t); }
  }

  /* ---- backend → compact shape ---- */
  const range = r => (r && typeof r === 'object') ? { min: r.min ?? null, max: r.max ?? null } : { min: null, max: null };

  function toInv(d) {
    return {
      id: d.psi_id, acr: d.acronym, title: d.title, pillar: d.pillar, area: d.subresearch_area,
      hw: d.hardware, hwg: d.hardware_group, related: d.related_investigations || [],
      rel: d.relevance_score, moon: d.moon_base_score, moonNotes: d.moon_base_score_notes || [],
      flags: {
        elevO2: !!d.covers_elevated_o2, moonO2: !!d.covers_moon_cabin_o2, lowP: !!d.covers_reduced_pressure,
        crew: !!d.crew_materials, partialG: !!d.partial_g_proxy, earth: !!d.earth_application
      },
      platform: d.flight_platform, center: d.managing_center, start: d.start_date, end: d.end_date, doi: d.doi,
      objective: d.objective, hypothesis: d.hypothesis, approach: d.approach, impacts: d.research_impacts,
      desc: d.descriptors || [],
      pubs: (d.publications || []).map(p => ({ t: p.title, doi: p.doi, a: p.authors, l: p.link })),
      sensors: d.sensors || [], fuels: d.tested_fuels || [], phases: d.fuel_phases || [],
      o2: range(d.o2_range), o2hab: range(d.o2_range_habitat), o2ox: range(d.o2_range_oxidizer_stream), p: range(d.pressure_range_atm),
      nExp: d.experiment_count, nAssumed: d.assumed_experiment_count,
      reports: (d.reports || []).map(r => r.filename)
    };
  }

  const toExpRow = e => [
    e.investigation_id, e.fuel_material_normalized, e.fuel_phase, e.o2_concentration_pct, e.pressure_atm,
    e.flow_velocity_cm_s, e.flow_direction, e.burn_time_s, e.outcome_category, e.gravity_level, e.diluent,
    e.is_assumed ? 1 : 0, e.fuel_geometry
  ];

  async function loadFromApi() {
    const health = await get('/health', 4000);
    if (!health || health.status !== 'ok') throw new Error('unexpected /health response');
    const [list, moon, gaps, first] = await Promise.all([
      get('/api/investigations?sort=acronym'), get('/api/moon-base'), get('/api/gaps'),
      get('/api/experiments?limit=' + EXP_PAGE + '&offset=0')
    ]);
    const offsets = []; for (let o = EXP_PAGE; o < first.total; o += EXP_PAGE) offsets.push(o);
    const [details, pages] = await Promise.all([
      Promise.all(list.map(c => get('/api/investigations/' + encodeURIComponent(c.psi_id)))),
      Promise.all(offsets.map(o => get('/api/experiments?limit=' + EXP_PAGE + '&offset=' + o)))
    ]);
    const items = first.items.concat(...pages.map(p => p.items));
    if (items.length !== first.total) throw new Error('experiments incomplete (' + items.length + '/' + first.total + ')');
    return {
      generated: health.generated_at,
      invs: details.map(toInv),
      ranking: moon.ranking,
      gaps: gaps,
      exp: items.map(toExpRow),
      expCols: ['inv', 'fuel', 'phase', 'o2', 'p', 'flow', 'dir', 'burn', 'outcome', 'g', 'diluent', 'assumed', 'geom'],
      // report passages are only needed for the offline keyword fallback; live answers come from /api/chat
      chunks: embedded ? embedded.chunks : []
    };
  }

  function badge(text, ok, title) {
    const put = () => {
      const h = document.querySelector('header.top'); if (!h) return;
      const b = document.createElement('div'); b.id = 'datasrc'; b.title = title || '';
      b.style.cssText = 'font-size:12px;padding:4px 10px;border-radius:999px;border:1px solid #2a3350;color:#c9d3ee;white-space:nowrap';
      b.innerHTML = '<span style="color:' + (ok ? '#3fb950' : '#f0a63a') + '">●</span> ' + text;
      h.appendChild(b);
    };
    if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', put); else put();
  }

  window.FIREORBIT_READY = (async () => {
    if (!BASE) {
      window.FIREORBIT_SOURCE = 'embedded';
      badge('Offline snapshot', false, 'Backend URL is empty — using data.js');
      return;
    }
    try {
      window.FIREORBIT_DATA = await loadFromApi();
      window.FIREORBIT_SOURCE = 'api';
      badge('Live API', true, 'All data loaded from ' + BASE);
    } catch (e) {
      if (!embedded) {
        document.addEventListener('DOMContentLoaded', () => {
          const m = document.querySelector('main'); if (m) m.innerHTML = '<div class="card"><h3>Backend not reachable</h3><p>Start it with <code>uvicorn backend.main:app --reload</code> and reload this page.<br>(' + String(e.message).replace(/</g, '&lt;') + ')</p></div>';
        });
        throw e;
      }
      window.FIREORBIT_DATA = embedded;
      window.FIREORBIT_SOURCE = 'embedded';
      window.FIREORBIT_ERROR = e.message;
      badge('Offline snapshot', false, 'Backend unavailable (' + e.message + ') — showing data.js');
    }
  })();
})();
