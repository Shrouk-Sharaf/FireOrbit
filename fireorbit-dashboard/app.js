/* FireOrbit dashboard — vanilla JS, no dependencies. Data comes from the FastAPI backend via api.js (data.js is the offline fallback) */
(function () {
  'use strict';
  const D = window.FIREORBIT_DATA;
  const INV = D.invs;
  const BYID = Object.fromEntries(INV.map(i => [i.id, i]));
  const EXP = D.exp.map(r => ({ inv: r[0], fuel: r[1], phase: r[2], o2: r[3], p: r[4], flow: r[5], dir: r[6], burn: r[7], out: r[8], g: r[9], dil: r[10], assumed: !!r[11], geom: r[12] }));
  const $ = (s, r = document) => r.querySelector(s);
  const esc = s => String(s ?? '').replace(/[&<>"]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
  const MOON = { o2lo: 26.5, o2hi: 34, p: 0.694 };
  const PCOL = { Prevention: '#ff7a3d', Detection: '#4da3ff', Suppression: '#3ecf8e', Fundamental: '#a78bfa' };
  const pillarKey = i => i.pillar.split(' ')[0];
  const pillClass = i => ({ Prevention: 'prev', Detection: 'det', Suppression: 'sup', Fundamental: 'fun' }[pillarKey(i)]);
  const OUTCOME_COL = { extinction: '#3ecf8e', self_extinction: '#2fb5a0', no_ignition: '#4da3ff', ignition: '#ff7a3d', sustained_burn: '#ff5d5d', insignificant_burn: '#ffb347', disruption: '#a78bfa', sampling: '#93a0bd', none: '#5a6785' };
  const BURN = new Set(['ignition', 'sustained_burn', 'insignificant_burn']);
  const OUT = new Set(['extinction', 'self_extinction', 'no_ignition']);
  const fmt = (v, d = 1) => v == null ? '—' : (Math.round(v * 10 ** d) / 10 ** d).toString();
  const rng = r => (r && r.min != null) ? `${fmt(r.min)}–${fmt(r.max)}` : 'not reported';

  // derived per-investigation stats from normalized experiments
  const STAT = {};
  INV.forEach(i => {
    const e = EXP.filter(x => x.inv === i.id);
    const o = e.map(x => x.o2).filter(v => v != null), p = e.map(x => x.p).filter(v => v != null);
    STAT[i.id] = {
      n: e.length, o2min: o.length ? Math.min(...o) : null, o2max: o.length ? Math.max(...o) : null,
      pmin: p.length ? Math.min(...p) : null, pmax: p.length ? Math.max(...p) : null,
      assumed: e.filter(x => x.assumed).length
    };
  });

  /* ---------- tooltip ---------- */
  const tt = document.createElement('div'); tt.className = 'tt'; document.body.appendChild(tt);
  document.addEventListener('mousemove', ev => { tt.style.left = ev.clientX + 12 + 'px'; tt.style.top = ev.clientY + 12 + 'px'; });
  function tip(node, html) { node.addEventListener('mouseenter', () => { tt.innerHTML = html; tt.style.display = 'block'; }); node.addEventListener('mouseleave', () => tt.style.display = 'none'); }

  /* ---------- tabs ---------- */
  const built = {};
  const builders = { overview: buildOverview, rank: buildRank, explore: buildExplore, compare: buildCompare, ask: buildAsk, gaps: buildGaps };
  function showTab(t) {
    document.querySelectorAll('nav button').forEach(b => b.classList.toggle('active', b.dataset.tab === t));
    document.querySelectorAll('.tab').forEach(s => s.classList.toggle('active', s.id === 'tab-' + t));
    if (!built[t]) { builders[t]($('#tab-' + t)); built[t] = true; }
    history.replaceState(null, '', '#' + t);
  }
  $('#nav').addEventListener('click', e => { if (e.target.dataset.tab) showTab(e.target.dataset.tab); });
  window.addEventListener('keydown', e => { if (e.key === 'Escape') closeDrawer(); });
  $('#scrim').onclick = closeDrawer;

  /* ---------- detail drawer ---------- */
  function openInv(id) {
    const i = BYID[id], s = STAT[id]; if (!i) return;
    const f = i.flags;
    const pill = (ok, t) => `<span class="pill ${ok ? 'ok' : 'no'}">${ok ? '✓' : '✕'} ${t}</span>`;
    $('#drawer').innerHTML = `<button class="btn ghost close" onclick="FO.close()">Close ✕</button>
      <span class="pill ${pillClass(i)}">${esc(i.pillar)}</span><span class="pill">${esc(i.id)}</span>
      <h2>${esc(i.acr)}</h2><p class="sub">${esc(i.title)}</p>
      <div>${pill(f.elevO2, 'Elevated O₂')}${pill(f.moonO2, 'Moon-cabin O₂ (26.5–34%)')}${pill(f.lowP, 'Reduced pressure')}${pill(f.crew, 'Crew materials')}${pill(f.earth, 'Earth application')}</div>
      <div class="grid g3" style="margin:12px 0">
        <div class="card"><div class="kpi">${fmt(i.rel, 0)}<small>Fire-safety relevance</small></div></div>
        <div class="card"><div class="kpi">${i.moon == null ? '—' : fmt(i.moon, 0)}<small>Moon-base score</small></div></div>
        <div class="card"><div class="kpi">${i.nExp}<small>Test records</small></div></div>
      </div>
      <h3>Objective</h3><p>${esc(i.objective)}</p>
      <h3>Hypothesis</h3><p>${esc(i.hypothesis)}</p>
      <h3>Approach</h3><p>${esc(i.approach)}</p>
      <h3>Impact (space &amp; Earth)</h3><p>${esc(i.impacts)}</p>
      <h3>Test conditions</h3>
      <table><tr><td>Hardware</td><td>${esc(i.hw)} <span class="pill">${esc(i.hwg)}</span></td></tr>
      <tr><td>Fuels</td><td>${i.fuels.map(x => `<span class="pill">${esc(x)}</span>`).join('') || '—'}</td></tr>
      <tr><td>Fuel phase</td><td>${esc(i.phases.join(', ') || '—')}</td></tr>
      <tr><td>O₂ (%)</td><td>${s.o2min != null ? fmt(s.o2min) + '–' + fmt(s.o2max) : rng(i.o2)}</td></tr>
      <tr><td>Pressure (atm)</td><td>${s.pmin != null ? fmt(s.pmin, 2) + '–' + fmt(s.pmax, 2) : rng(i.p)}</td></tr>
      <tr><td>Sensors</td><td>${i.sensors.map(x => `<span class="pill">${esc(x)}</span>`).join('') || '—'}</td></tr>
      <tr><td>Dates</td><td>${esc(i.start || '?')} → ${esc(i.end || 'n/a')}</td></tr>
      <tr><td>Dataset DOI</td><td>${i.doi ? `<a target="_blank" rel="noopener" href="https://doi.org/${esc(i.doi)}">${esc(i.doi)}</a>` : '—'}</td></tr></table>
      <h3>Tags</h3><div>${i.desc.map(x => `<span class="pill">${esc(x)}</span>`).join('')}</div>
      <h3>Related</h3><div>${i.related.map(r => `<span class="pill" style="cursor:pointer" onclick="FO.open('${r}')">${esc(BYID[r] ? BYID[r].acr : r)}</span>`).join('') || '—'}</div>
      <h3>Publications (${i.pubs.length})</h3><ul>${i.pubs.slice(0, 12).map(p => `<li>${p.l || p.doi ? `<a target="_blank" rel="noopener" href="${esc(p.l || 'https://doi.org/' + p.doi)}">${esc(p.t)}</a>` : esc(p.t)}</li>`).join('')}</ul>
      <h3>Reports</h3><ul>${i.reports.map(r => `<li>${esc(r)}</li>`).join('') || '<li>none</li>'}</ul>`;
    $('#drawer').classList.add('open'); $('#scrim').classList.add('open');
  }
  function closeDrawer() { $('#drawer').classList.remove('open'); $('#scrim').classList.remove('open'); }
  window.FO = { open: openInv, close: closeDrawer, ask: q => { showTab('ask'); $('#askq').value = q; runAsk(); } };

  /* ---------- SVG helpers ---------- */
  const NS = 'http://www.w3.org/2000/svg';
  function svg(w, h) { const s = document.createElementNS(NS, 'svg'); s.setAttribute('viewBox', `0 0 ${w} ${h}`); return s; }
  function se(p, tag, attrs, text) { const n = document.createElementNS(NS, tag); for (const k in attrs) n.setAttribute(k, attrs[k]); if (text != null) n.textContent = text; p.appendChild(n); return n; }

  /* ================= OVERVIEW ================= */
  function buildOverview(root) {
    const pill = {}; INV.forEach(i => (pill[pillarKey(i)] = pill[pillarKey(i)] || []).push(i));
    const solid = EXP.filter(e => e.phase && e.phase.startsWith('solid')).length;
    const hi = EXP.filter(e => e.o2 != null && e.o2 >= 30).length;
    const pubs = INV.reduce((a, i) => a + i.pubs.length, 0);
    root.innerHTML = `<h2>Fire safety for crewed exploration</h2>
    <p class="sub">${INV.length} NASA PSI combustion investigations · ${EXP.length.toLocaleString()} normalized test records · ${pubs} publications. Compare how each study informs <b>prevention</b>, <b>detection</b> and <b>suppression</b>.</p>
    <div class="grid g4">
      <div class="card"><div class="kpi">${INV.length}<small>Investigations</small></div></div>
      <div class="card"><div class="kpi">${EXP.length.toLocaleString()}<small>Test records</small></div></div>
      <div class="card"><div class="kpi">${hi}<small>Tests at ≥30% O₂ (Moon-cabin level)</small></div></div>
      <div class="card"><div class="kpi">0<small>Partial-gravity datasets in PSI</small></div></div>
    </div>
    <div class="grid g2" style="margin-top:16px">
      <div class="card"><h3>Oxygen coverage vs. planned Moon cabin</h3><p class="sub">Range of O₂ concentration tested per investigation. Shaded band = expected Moon-base cabin (26.5–34%); dashed line = Earth air (20.9%).</p><div class="chart" id="o2chart"></div></div>
      <div class="card"><h3>Three fire-safety pillars</h3><div id="pillars"></div></div>
    </div>
    <div class="card"><h3>Hardware lineage</h3><p class="sub">Which investigations share flight hardware — useful for comparing like-for-like results.</p><div id="hw"></div></div>
    <div class="card"><h3>Quick insights</h3><ul id="insights"></ul></div>`;

    // O2 coverage chart
    const rows = INV.filter(i => STAT[i.id].o2min != null).sort((a, b) => STAT[a.id].o2min - STAT[b.id].o2min);
    const W = 640, rh = 26, H = rows.length * rh + 40, x0 = 120, x1 = W - 20;
    const sx = v => x0 + (v - 10) / (90 - 10) * (x1 - x0);
    const s = svg(W, H);
    se(s, 'rect', { x: sx(MOON.o2lo), y: 10, width: sx(MOON.o2hi) - sx(MOON.o2lo), height: H - 40, fill: '#ff7a3d', opacity: .15 });
    se(s, 'line', { x1: sx(20.9), x2: sx(20.9), y1: 10, y2: H - 30, stroke: '#93a0bd', 'stroke-dasharray': '4 3' });
    [10, 21, 30, 40, 60, 85].forEach(t => se(s, 'text', { x: sx(t), y: H - 12, 'text-anchor': 'middle' }, t + '%'));
    rows.forEach((i, k) => {
      const st = STAT[i.id], y = 16 + k * rh;
      se(s, 'text', { x: x0 - 8, y: y + 10, 'text-anchor': 'end', class: 'lab' }, i.acr);
      const r = se(s, 'rect', { x: sx(st.o2min), y, width: Math.max(4, sx(st.o2max) - sx(st.o2min)), height: 14, rx: 3, fill: PCOL[pillarKey(i)], style: 'cursor:pointer' });
      r.onclick = () => openInv(i.id);
      tip(r, `<b>${esc(i.acr)}</b><br>O₂ ${fmt(st.o2min)}–${fmt(st.o2max)}%<br>${st.n} tests`);
    });
    $('#o2chart').appendChild(s);
    const missing = INV.filter(i => STAT[i.id].o2min == null).map(i => i.acr);
    $('#o2chart').insertAdjacentHTML('beforeend', `<div class="legend">${Object.entries(PCOL).map(([k, c]) => `<span><i style="background:${c}"></i>${k}</span>`).join('')}</div><p class="sub">No O₂ values in the experimental tables for: ${missing.join(', ') || 'none'}.</p>`);

    // pillars
    $('#pillars').innerHTML = Object.entries(pill).map(([k, a]) => `<div style="margin-bottom:12px"><span class="pill ${pillClass(a[0])}">${k}</span> <b>${a.length}</b> investigations<br>${a.sort((x, y) => y.rel - x.rel).map(i => `<span class="chip" onclick="FO.open('${i.id}')">${esc(i.acr)}</span>`).join('')}</div>`).join('');
    // hardware
    const hw = {}; INV.forEach(i => (hw[i.hwg] = hw[i.hwg] || []).push(i));
    $('#hw').innerHTML = `<div class="grid g3">${Object.entries(hw).map(([k, a]) => `<div class="card" style="background:var(--panel2)"><b>${esc(k)}</b><div class="chips">${a.map(i => `<span class="chip" onclick="FO.open('${i.id}')">${esc(i.acr)}</span>`).join('')}</div></div>`).join('')}</div>`;
    // insights
    const top = [...D.ranking][0];
    const both = INV.filter(i => i.flags.moonO2 && i.flags.lowP).map(i => i.acr);
    $('#insights').innerHTML = [
      `Best match to planned Moon-cabin conditions: <b>${esc(top.acronym)}</b> (score ${top.moon_base_score}).`,
      `Only ${both.length} investigations cover <b>both</b> Moon-cabin O₂ and reduced pressure: ${both.join(', ') || 'none'}.`,
      `${solid} test records involve solid fuels; most data (${EXP.filter(e => e.phase === 'gas').length}) is gaseous-fuel fundamental combustion.`,
      `<a href="#" onclick="FO.ask('Which investigations studied flammability at oxygen levels of 30% or more?');return false">Ask FireOrbit which studies reached ≥30% O₂ →</a>`
    ].map(t => `<li>${t}</li>`).join('');
  }

  /* ================= RANK ================= */
  const FACTORS = [
    ['direct', 'Direct fire-safety focus', i => i.area === 'Spacecraft Fire Safety' ? 1 : 0],
    ['crew', 'Crew-cabin materials', i => i.flags.crew ? 1 : 0],
    ['elev', 'Elevated O₂ coverage', i => i.flags.elevO2 || (STAT[i.id].o2max || 0) >= 26.5 ? 1 : 0],
    ['moon', 'Moon-cabin O₂ + pressure', i => (i.flags.moonO2 ? .6 : 0) + (i.flags.lowP ? .4 : 0)],
    ['solid', 'Solid-fuel testing', i => i.phases.some(p => p.startsWith('solid')) ? 1 : 0],
    ['supp', 'Suppression data', i => pillarKey(i) === 'Suppression' ? 1 : 0],
    ['det', 'Detection data', i => pillarKey(i) === 'Detection' ? 1 : 0],
    ['data', 'Data volume (model-ready)', i => Math.min(1, Math.log10(1 + i.nExp) / Math.log10(400))],
    ['pubs', 'Publications', i => Math.min(1, i.pubs.length / 30)],
    ['earth', 'Earth applications', i => i.flags.earth ? 1 : 0],
    ['pg', 'Partial-g proxy', i => i.flags.partialG ? 1 : 0]
  ];
  const PRESETS = {
    'Moon base / pressurized rover': { direct: 20, crew: 20, elev: 15, moon: 25, solid: 15, supp: 5, det: 5, data: 5, pubs: 5, earth: 0, pg: 5 },
    'Spacecraft & ISS (prevention)': { direct: 25, crew: 20, elev: 5, moon: 0, solid: 25, supp: 5, det: 5, data: 5, pubs: 5, earth: 5, pg: 0 },
    'Fire detection': { direct: 15, crew: 10, elev: 0, moon: 0, solid: 10, supp: 0, det: 50, data: 5, pubs: 5, earth: 5, pg: 0 },
    'Fire suppression': { direct: 10, crew: 5, elev: 10, moon: 10, solid: 0, supp: 50, det: 0, data: 5, pubs: 5, earth: 5, pg: 0 },
    'Predictive modeling data': { direct: 5, crew: 5, elev: 10, moon: 10, solid: 5, supp: 5, det: 0, data: 45, pubs: 10, earth: 0, pg: 5 }
  };
  function buildRank(root) {
    root.innerHTML = `<h2>Rank investigations by what you need</h2><p class="sub">Pick a use case, then tune the weights. Scores are 0–100 and recomputed live from investigation metadata and test coverage.</p>
    <div class="card"><div class="toolbar"><label>Use case<select id="preset">${Object.keys(PRESETS).map(k => `<option>${k}</option>`).join('')}</select></label>
    <label>Filter pillar<select id="pfilter"><option value="">All</option>${[...new Set(INV.map(pillarKey))].map(k => `<option>${k}</option>`).join('')}</select></label></div>
    <div class="weights" id="weights"></div></div>
    <div class="card" id="ranklist"></div>
    <div class="card"><h3>Pipeline “Moon-base” score (fixed)</h3><p class="sub">Precomputed by the preprocessing pipeline from O₂/pressure coverage of the planned habitat (≥30% O₂, ≤10.2 psi). “Assumed” values are flagged.</p><div id="moonrank"></div></div>`;
    const w = {}; const wbox = $('#weights');
    FACTORS.forEach(([k, label]) => { wbox.insertAdjacentHTML('beforeend', `<label>${label} <span id="wv-${k}"></span><input type="range" min="0" max="40" id="w-${k}" style="width:100%"></label>`); });
    function setPreset(n) { Object.assign(w, PRESETS[n]); FACTORS.forEach(([k]) => { $('#w-' + k).value = w[k]; }); draw(); }
    function draw() {
      FACTORS.forEach(([k]) => { w[k] = +$('#w-' + k).value; $('#wv-' + k).textContent = w[k]; });
      const tot = Object.values(w).reduce((a, b) => a + b, 0) || 1, pf = $('#pfilter').value;
      const sc = INV.filter(i => !pf || pillarKey(i) === pf).map(i => {
        const parts = FACTORS.map(([k, l, fn]) => [l, fn(i) * w[k] / tot * 100]);
        return { i, score: parts.reduce((a, b) => a + b[1], 0), parts: parts.sort((a, b) => b[1] - a[1]) };
      }).sort((a, b) => b.score - a.score);
      $('#ranklist').innerHTML = sc.map((r, k) => `<div class="rankrow" onclick="FO.open('${r.i.id}')"><div class="rankno">${k + 1}</div>
        <div><b>${esc(r.i.acr)}</b> <span class="pill ${pillClass(r.i)}">${esc(r.i.pillar)}</span><br><span class="sub" style="margin:0">${esc(r.i.title)}</span><br>
        <small style="color:var(--muted)">Driven by: ${r.parts.filter(p => p[1] > 0.5).slice(0, 3).map(p => esc(p[0]) + ' (+' + fmt(p[1], 0) + ')').join(' · ') || 'no weighted factors'}</small></div>
        <div><b>${fmt(r.score, 0)}</b> / 100<div class="bar"><i style="width:${r.score}%"></i></div></div></div>`).join('');
    }
    wbox.addEventListener('input', draw); $('#pfilter').onchange = draw; $('#preset').onchange = e => setPreset(e.target.value);
    setPreset(Object.keys(PRESETS)[0]);
    $('#moonrank').innerHTML = `<table><tr><th>#</th><th>Investigation</th><th>Score</th><th>Why</th></tr>${D.ranking.map(r => `<tr class="click" onclick="FO.open('${r.psi_id}')"><td>${r.rank}</td><td><b>${esc(r.acronym)}</b></td><td>${r.moon_base_score}</td><td>${r.notes.map(n => `<div>• ${esc(n)}</div>`).join('')}</td></tr>`).join('')}</table>`;
  }

  /* ================= EXPLORE ================= */
  function buildExplore(root) {
    const opt = (arr) => arr.map(v => `<option value="${esc(v)}">${esc(v)}</option>`).join('');
    const invs = [...new Set(EXP.map(e => e.inv))].map(id => BYID[id]).sort((a, b) => a.acr.localeCompare(b.acr));
    root.innerHTML = `<h2>Explore test conditions</h2><p class="sub">Filter the ${EXP.length.toLocaleString()} normalized tests, see where data exists, and export a CSV for predictive modeling.</p>
    <div class="card"><div class="toolbar">
      <label>Investigation<select id="f-inv"><option value="">All</option>${invs.map(i => `<option value="${i.id}">${esc(i.acr)}</option>`).join('')}</select></label>
      <label>Fuel phase<select id="f-phase"><option value="">All</option>${opt([...new Set(EXP.map(e => e.phase).filter(Boolean))])}</select></label>
      <label>Outcome<select id="f-out"><option value="">All</option><option value="__burn">Burned / ignited</option><option value="__ext">Extinguished / no ignition</option>${opt([...new Set(EXP.map(e => e.out).filter(Boolean))])}</select></label>
      <label>O₂ min %<input type="number" id="f-o2lo" style="width:90px" placeholder="0"></label>
      <label>O₂ max %<input type="number" id="f-o2hi" style="width:90px" placeholder="100"></label>
      <label>Fuel contains<input type="search" id="f-fuel" placeholder="PMMA, methanol…"></label>
      <label><span>Moon-cabin only</span><input type="checkbox" id="f-moon"></label>
      <label><span>Hide assumed values</span><input type="checkbox" id="f-assumed"></label>
      <button class="btn ghost" id="f-csv">⬇ Export CSV</button></div>
      <div id="count" class="sub"></div></div>
    <div class="grid g2">
      <div class="card"><h3>O₂ vs. pressure</h3><p class="sub">Each dot is a test. Dashed box = planned Moon cabin (O₂ ≥ 26.5%, ≤ 0.694 atm).</p><div class="chart" id="scatter"></div><div class="legend" id="scatterleg"></div></div>
      <div class="card"><h3>Outcomes by O₂ level</h3><p class="sub">Share of tests that ended in each outcome (tests with a recorded outcome only).</p><div class="chart" id="stack"></div></div>
    </div>
    <div class="card"><h3>Flammability matrix — % of tests that burned</h3><p class="sub">By fuel and O₂ band; only cells with ≥3 outcome-labelled tests. Darker = more likely to burn.</p><div id="matrix"></div></div>
    <div class="card"><h3>Tests <small id="shown" class="sub"></small></h3><div class="tablewrap"><table id="tbl"></table></div></div>`;
    let sortK = 'o2', sortD = -1, cur = [];
    function filt() {
      const g = id => $('#' + id).value, o = g('f-out'), lo = parseFloat(g('f-o2lo')), hi = parseFloat(g('f-o2hi')), fu = g('f-fuel').toLowerCase();
      return EXP.filter(e => (!g('f-inv') || e.inv === g('f-inv')) && (!g('f-phase') || e.phase === g('f-phase')) &&
        (!o || (o === '__burn' ? BURN.has(e.out) : o === '__ext' ? OUT.has(e.out) : e.out === o)) &&
        (isNaN(lo) || (e.o2 != null && e.o2 >= lo)) && (isNaN(hi) || (e.o2 != null && e.o2 <= hi)) &&
        (!fu || (e.fuel || '').toLowerCase().includes(fu)) && (!$('#f-moon').checked || (e.o2 != null && e.o2 >= MOON.o2lo && (e.p == null || e.p <= MOON.p + .02))) &&
        (!$('#f-assumed').checked || !e.assumed));
    }
    function draw() {
      cur = filt(); $('#count').innerHTML = `<b>${cur.length.toLocaleString()}</b> tests match · ${cur.filter(e => e.assumed).length} use assumed O₂/pressure/flow values (marked ⚠)`;
      drawScatter(); drawStack(); drawMatrix(); drawTable();
    }
    function drawScatter() {
      const pts = cur.filter(e => e.o2 != null && e.p != null), W = 560, H = 340, m = { l: 48, r: 14, t: 14, b: 40 };
      const sx = v => m.l + (v - 0) / 90 * (W - m.l - m.r), sy = v => H - m.b - (v / 5.5) * (H - m.t - m.b);
      const s = svg(W, H);
      [0, 21, 40, 60, 85].forEach(t => { se(s, 'text', { x: sx(t), y: H - 22, 'text-anchor': 'middle' }, t); });
      [0, 1, 2, 3, 4, 5].forEach(t => { se(s, 'line', { x1: m.l, x2: W - m.r, y1: sy(t), y2: sy(t), stroke: '#26324d', 'stroke-width': .5 }); se(s, 'text', { x: m.l - 6, y: sy(t) + 4, 'text-anchor': 'end' }, t); });
      se(s, 'text', { x: W / 2, y: H - 4, 'text-anchor': 'middle' }, 'O₂ concentration (%)'); se(s, 'text', { x: 12, y: H / 2, transform: `rotate(-90 12 ${H / 2})`, 'text-anchor': 'middle' }, 'Pressure (atm)');
      se(s, 'rect', { x: sx(MOON.o2lo), y: sy(MOON.p), width: sx(90) - sx(MOON.o2lo), height: sy(0) - sy(MOON.p), fill: '#ff7a3d', opacity: .1, stroke: '#ff7a3d', 'stroke-dasharray': '4 3' });
      const step = Math.ceil(pts.length / 1200);
      pts.forEach((e, k) => { if (k % step) return; const c = se(s, 'circle', { cx: sx(e.o2), cy: sy(e.p), r: 3.2, fill: PCOL[pillarKey(BYID[e.inv])], opacity: .55 }); tip(c, `<b>${esc(BYID[e.inv].acr)}</b> ${esc(e.fuel)}<br>O₂ ${e.o2}% · ${e.p} atm<br>${esc(e.out || 'outcome n/a')}${e.assumed ? ' ⚠ assumed' : ''}`); });
      $('#scatter').innerHTML = ''; $('#scatter').appendChild(s);
      $('#scatterleg').innerHTML = Object.entries(PCOL).map(([k, c]) => `<span><i style="background:${c}"></i>${k}</span>`).join('') + `<span>${pts.length} of ${cur.length} tests have both O₂ and pressure</span>`;
    }
    function drawStack() {
      const bands = [[0, 15], [15, 21], [21, 26.5], [26.5, 34], [34, 50], [50, 100]], oc = Object.keys(OUTCOME_COL).filter(k => k !== 'none');
      const W = 560, H = 340, m = { l: 70, r: 10, t: 10, b: 50 }, bw = (W - m.l - m.r) / bands.length;
      const s = svg(W, H);
      bands.forEach((b, k) => {
        const rows = cur.filter(e => e.o2 != null && e.o2 >= b[0] && e.o2 < b[1] && e.out), tot = rows.length || 1; let y = H - m.b;
        oc.forEach(o => { const n = rows.filter(e => e.out === o).length; if (!n) return; const h = n / tot * (H - m.t - m.b); y -= h; const r = se(s, 'rect', { x: m.l + k * bw + 6, y, width: bw - 12, height: h, fill: OUTCOME_COL[o] }); tip(r, `${b[0]}–${b[1]}% O₂<br>${o.replace('_', ' ')}: ${n} (${Math.round(n / tot * 100)}%)`); });
        se(s, 'text', { x: m.l + k * bw + bw / 2, y: H - 32, 'text-anchor': 'middle' }, `${b[0]}–${b[1]}%`); se(s, 'text', { x: m.l + k * bw + bw / 2, y: H - 18, 'text-anchor': 'middle' }, `n=${rows.length}`);
      });
      [0, 50, 100].forEach(t => se(s, 'text', { x: m.l - 6, y: H - m.b - t / 100 * (H - m.t - m.b) + 4, 'text-anchor': 'end' }, t + '%'));
      $('#stack').innerHTML = ''; $('#stack').appendChild(s);
      $('#stack').insertAdjacentHTML('beforeend', `<div class="legend">${oc.map(o => `<span><i style="background:${OUTCOME_COL[o]}"></i>${o.replace('_', ' ')}</span>`).join('')}</div>`);
    }
    function drawMatrix() {
      const bands = [[0, 21, '<21%'], [21, 26.5, '21–26.5%'], [26.5, 34, '26.5–34%'], [34, 100, '>34%']];
      const rows = cur.filter(e => e.o2 != null && e.fuel && (BURN.has(e.out) || OUT.has(e.out)));
      const fuels = {}; rows.forEach(e => (fuels[e.fuel] = fuels[e.fuel] || []).push(e));
      const list = Object.entries(fuels).filter(([, a]) => a.length >= 3).sort((a, b) => b[1].length - a[1].length).slice(0, 20);
      if (!list.length) { $('#matrix').innerHTML = '<p class="sub">Not enough outcome-labelled tests for the current filters.</p>'; return; }
      $('#matrix').innerHTML = `<div class="tablewrap"><table><tr><th>Fuel</th>${bands.map(b => `<th>${b[2]}</th>`).join('')}</tr>${list.map(([f, a]) => `<tr><td><b>${esc(f)}</b> <span class="sub">(${a.length})</span></td>${bands.map(b => {
        const x = a.filter(e => e.o2 >= b[0] && e.o2 < b[1]); if (x.length < 3) return '<td style="color:var(--muted)">—</td>';
        const pct = x.filter(e => BURN.has(e.out)).length / x.length;
        return `<td style="background:rgba(255,93,93,${(pct * .75).toFixed(2)})">${Math.round(pct * 100)}% <small>n=${x.length}</small></td>`;
      }).join('')}</tr>`).join('')}</table></div>`;
    }
    function drawTable() {
      const cols = [['inv', 'Study'], ['fuel', 'Fuel'], ['phase', 'Phase'], ['o2', 'O₂ %'], ['p', 'P (atm)'], ['flow', 'Flow cm/s'], ['dir', 'Flow dir'], ['burn', 'Burn s'], ['out', 'Outcome'], ['g', 'Gravity']];
      const rows = [...cur].sort((a, b) => { const x = a[sortK], y = b[sortK]; if (x == null) return 1; if (y == null) return -1; return (x > y ? 1 : x < y ? -1 : 0) * sortD; });
      $('#shown').textContent = `(showing ${Math.min(rows.length, 400)} of ${rows.length})`;
      $('#tbl').innerHTML = `<tr>${cols.map(c => `<th data-k="${c[0]}">${c[1]}${sortK === c[0] ? (sortD > 0 ? ' ▲' : ' ▼') : ''}</th>`).join('')}</tr>` +
        rows.slice(0, 400).map(e => `<tr class="click" onclick="FO.open('${e.inv}')"><td>${esc(BYID[e.inv].acr)}</td><td>${esc(e.fuel)}</td><td>${esc(e.phase)}</td><td>${fmt(e.o2)}${e.assumed ? ' <span class="tag-assumed">⚠</span>' : ''}</td><td>${fmt(e.p, 2)}</td><td>${fmt(e.flow)}</td><td>${esc(e.dir || '—')}</td><td>${fmt(e.burn)}</td><td>${esc((e.out || '—').replace('_', ' '))}</td><td>${esc(e.g || '')}</td></tr>`).join('');
      $('#tbl').querySelectorAll('th').forEach(th => th.onclick = () => { const k = th.dataset.k; sortD = sortK === k ? -sortD : 1; sortK = k; drawTable(); });
    }
    root.querySelectorAll('.toolbar select,.toolbar input').forEach(n => n.addEventListener('input', draw));
    $('#f-csv').onclick = () => {
      const h = ['investigation', 'fuel', 'phase', 'o2_pct', 'pressure_atm', 'flow_cm_s', 'flow_direction', 'burn_time_s', 'outcome', 'gravity', 'diluent', 'assumed_values', 'geometry'];
      const csv = [h.join(',')].concat(cur.map(e => [BYID[e.inv].acr, e.fuel, e.phase, e.o2, e.p, e.flow, e.dir, e.burn, e.out, e.g, e.dil, e.assumed, e.geom].map(v => `"${String(v ?? '').replace(/"/g, '""')}"`).join(','))).join('\n');
      const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([csv], { type: 'text/csv' })); a.download = 'fireorbit_filtered_tests.csv'; a.click();
    };
    draw();
  }

  /* ================= COMPARE ================= */
  function buildCompare(root) {
    const defaults = ['PSI-26', 'PSI-25', 'PSI-98'];
    root.innerHTML = `<h2>Compare investigations</h2><p class="sub">Choose 2–4 studies to see what is the same and what differs.</p>
    <div class="card"><div class="toolbar">${[0, 1, 2, 3].map(k => `<label>Study ${k + 1}<select class="cmp"><option value="">—</option>${INV.map(i => `<option value="${i.id}" ${defaults[k] === i.id ? 'selected' : ''}>${esc(i.acr)}</option>`).join('')}</select></label>`).join('')}</div></div><div id="cmpout"></div>`;
    function draw() {
      const sel = [...root.querySelectorAll('.cmp')].map(s => s.value).filter(Boolean).map(id => BYID[id]);
      if (sel.length < 2) { $('#cmpout').innerHTML = '<p class="sub">Select at least two.</p>'; return; }
      const list = f => sel.map(f);
      const shared = (arrs) => arrs[0].filter(x => arrs.every(a => a.includes(x)));
      const fuelsL = sel.map(i => i.fuels.map(f => f.split(':')[0].trim().toLowerCase()));
      const rows = [
        ['Pillar', i => esc(i.pillar)], ['Hardware', i => esc(i.hwg)], ['Fuel phase', i => esc(i.phases.join(', ') || '—')],
        ['Fuels tested', i => i.fuels.slice(0, 10).map(f => `<span class="pill">${esc(f.split(':')[0])}</span>`).join('') || '—'],
        ['O₂ range (%)', i => STAT[i.id].o2min != null ? `${fmt(STAT[i.id].o2min)}–${fmt(STAT[i.id].o2max)}` : 'not reported'],
        ['Pressure (atm)', i => STAT[i.id].pmin != null ? `${fmt(STAT[i.id].pmin, 2)}–${fmt(STAT[i.id].pmax, 2)}` : 'not reported'],
        ['Sensors', i => i.sensors.map(s => `<span class="pill">${esc(s)}</span>`).join('') || '—'],
        ['Test records', i => STAT[i.id].n], ['Moon-cabin O₂', i => i.flags.moonO2 ? '✓ yes' : '✕ no'], ['Reduced pressure', i => i.flags.lowP ? '✓ yes' : '✕ no'],
        ['Fire-safety relevance', i => fmt(i.rel, 0)], ['Objective', i => `<small>${esc(i.objective.slice(0, 380))}${i.objective.length > 380 ? '…' : ''}</small>`]
      ];
      const sf = shared(fuelsL), ss = shared(sel.map(i => i.sensors));
      $('#cmpout').innerHTML = `<div class="card"><h3>Similarities</h3><p>Shared fuels: ${sf.length ? sf.map(f => `<span class="pill ok">${esc(f)}</span>`).join('') : '<i>none</i>'}</p><p>Shared sensors: ${ss.length ? ss.map(f => `<span class="pill ok">${esc(f)}</span>`).join('') : '<i>none</i>'}</p><p>Same hardware: ${new Set(sel.map(i => i.hwg)).size === 1 ? '<span class="pill ok">yes</span>' : '<span class="pill warn">no</span>'}</p></div>
      <div class="cmpgrid" style="grid-template-columns:140px repeat(${sel.length},1fr)"><div class="h">Attribute</div>${sel.map(i => `<div class="h" style="cursor:pointer" onclick="FO.open('${i.id}')">${esc(i.acr)}</div>`).join('')}
      ${rows.map(r => `<div class="h">${r[0]}</div>${list(r[1]).map(v => `<div>${v}</div>`).join('')}`).join('')}</div>`;
    }
    root.querySelectorAll('.cmp').forEach(s => s.onchange = draw); draw();
  }

  /* ================= ASK ================= */
  const STOP = new Set('the a an of in on and or to for with is are was were be what which how do does did that this it as by from at about between into than'.split(' '));
  const tok = t => (t.toLowerCase().match(/[a-z0-9₂]+/g) || []).filter(w => !STOP.has(w));
  // knowledge docs = chunks + investigation text fields
  const DOCS = D.chunks.map(c => ({ id: c.id, text: c.t, src: c.src || 'metadata', pg: c.pg }));
  INV.forEach(i => { ['objective', 'hypothesis', 'approach', 'impacts'].forEach(f => { if (i[f]) DOCS.push({ id: i.id, text: `${i.acr} ${f}: ${i[f]}`.replace(/\s+/g, ' ').slice(0, 1100), src: i.acr + ' ' + f }); }); });
  DOCS.forEach(d => { d.tk = tok(d.text + ' ' + (BYID[d.id] ? BYID[d.id].acr : '')); d.tf = {}; d.tk.forEach(w => d.tf[w] = (d.tf[w] || 0) + 1); });
  const DF = {}; DOCS.forEach(d => Object.keys(d.tf).forEach(w => DF[w] = (DF[w] || 0) + 1));
  const AVG = DOCS.reduce((a, d) => a + d.tk.length, 0) / DOCS.length;
  function search(q, k = 4) {
    const qt = tok(q), N = DOCS.length;
    const mention = INV.filter(i => q.toLowerCase().includes(i.acr.toLowerCase()) || q.includes(i.id)).map(i => i.id);
    return DOCS.map(d => {
      let s = 0; qt.forEach(w => { const f = d.tf[w] || 0; if (!f) return; const idf = Math.log(1 + (N - DF[w] + .5) / (DF[w] + .5)); s += idf * f * 2.2 / (f + 1.2 * (.25 + .75 * d.tk.length / AVG)); });
      if (mention.includes(d.id)) s *= 1.6; return { d, s };
    }).filter(x => x.s > 0).sort((a, b) => b.s - a.s).slice(0, k);
  }
  const SUG = ['Which investigations studied flammability at oxygen levels of 30% or more?', 'What are the key findings for fire suppression in microgravity?', 'Which studies are most relevant to a Moon base cabin?', 'How do smoke detectors work in microgravity (SAME)?', 'What Earth applications came from this research?', 'What data is missing for Moon and Mars fire safety?'];
  function buildAsk(root) {
    root.innerHTML = `<h2>Ask FireOrbit</h2><p class="sub">Ask in plain language. Answers are built from the investigation records, ${D.chunks.length} report passages and the structured test data, with citations. Retrieval runs fully in your browser.</p>
    <div class="card"><textarea id="askq" rows="2" placeholder="e.g. Which materials were tested at ≥30% O₂ and what happened?"></textarea>
    <div class="toolbar" style="margin-top:8px;justify-content:space-between"><div class="chips">${SUG.map(s => `<span class="chip">${esc(s)}</span>`).join('')}</div><button class="btn" id="askgo">Ask</button></div>
    <div class="sub" id="apistat" style="margin-top:10px">Checking backend…</div><details><summary class="sub" style="cursor:pointer">Backend settings</summary><p class="sub">FireOrbit API URL (default <code>http://localhost:8000</code>). Clear it to use local search only.</p><input type="text" id="llmurl" style="width:100%"></details></div><div id="askout"></div>`;
    root.querySelector('.chips').onclick = e => { if (e.target.classList.contains('chip')) { $('#askq').value = e.target.textContent; runAsk(); } };
    initApi();
    $('#askgo').onclick = runAsk; $('#askq').addEventListener('keydown', e => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); runAsk(); } });
  }

  /* ---- FireOrbit API (FastAPI backend) ---- */
  const DEFAULT_API = 'http://localhost:8000';
  function lsGet(k) { try { return localStorage.getItem(k); } catch (e) { return null; } }
  function lsSet(k, v) { try { localStorage.setItem(k, v); } catch (e) { /* ignore */ } }
  function apiBase() {
    const el = $('#llmurl'); const raw = el ? el.value : (lsGet('fireorbit.api') ?? DEFAULT_API);
    return raw.trim().replace(/\/+$/, '').replace(/\/(api\/chat|ask)$/, '');
  }
  function initApi() {
    const el = $('#llmurl'); const saved = lsGet('fireorbit.api');
    el.value = saved === null ? DEFAULT_API : saved;
    el.addEventListener('change', () => { lsSet('fireorbit.api', el.value.trim()); location.reload(); });
    checkApi();
  }
  async function checkApi() {
    const st = $('#apistat'); if (!st) return; const base = apiBase();
    if (!base) { st.innerHTML = '○ Backend off — using local keyword search only.'; return; }
    st.textContent = 'Checking backend…';
    const ctl = new AbortController(); const t = setTimeout(() => ctl.abort(), 4000);
    try {
      const r = await fetch(base + '/health', { signal: ctl.signal }); const j = await r.json();
      if (!r.ok || j.status !== 'ok') throw new Error('unexpected response');
      st.innerHTML = `<span style="color:#3fb950">●</span> Backend connected · AI answers ${j.llm_configured ? 'on' : 'off (no GEMINI_API_KEY)'} · retrieval: ${j.vector_search ? 'semantic' : 'keyword'}`;
    } catch (e) {
      st.innerHTML = `<span style="color:#f85149">●</span> Backend not reachable at ${esc(base)} — using local keyword search. Start it with <code>uvicorn backend.main:app --reload</code>.`;
    } finally { clearTimeout(t); }
  }
  function fmtAnswer(a) { return esc(a).replace(/\*\*(.+?)\*\*/g, '<b>$1</b>').replace(/\n/g, '<br>'); }
  function srcChip(s) {
    const t = esc(s.label || s.psi_id || s.file || 'source') + (s.page ? ' p.' + esc(String(s.page)) : '');
    return s.psi_id && BYID[s.psi_id] ? `<a href="#" onclick="FO.open('${s.psi_id}');return false">${t}</a>` : `<span>${t}</span>`;
  }
  async function askBackend(q) {
    const base = apiBase(); if (!base) return { html: '', hits: null };
    try {
      const r = await fetch(base + '/api/chat', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: q }) });
      const j = await r.json().catch(() => ({}));
      if (!r.ok) throw new Error(typeof j.detail === 'string' ? j.detail : 'HTTP ' + r.status);
      const hits = (j.sources || []).filter(s => s.content).map(s => ({ d: { id: s.psi_id || s.label || '', text: s.content, src: s.file || s.label || 'source', pg: s.page } }));
      if (j.answer) return { html: `<div class="answer">${fmtAnswer(j.answer)}<div class="cite"><b>Sources:</b> ${(j.sources || []).map(srcChip).join(' · ')}</div></div>`, hits };
      return { html: `<div class="answer">Backend connected, but AI answers are off (no GEMINI_API_KEY). Showing retrieved passages instead.</div>`, hits };
    } catch (e) {
      return { html: `<div class="answer">Backend unavailable (${esc(e.message)}). Showing local results.</div>`, hits: null };
    }
  }
  async function runAsk() {
    const q = $('#askq').value.trim(); if (!q) return; const out = $('#askout'); out.innerHTML = '<div class="card">Searching…</div>';
    const ql = q.toLowerCase(); let html = '';
    // structured intent: O2 threshold
    const m = ql.match(/(\d{2,3})\s*%/); const hiIntent = /(≥|>=|at least|or more|above|over|greater|higher|more than)/.test(ql) || /elevated|moon|lunar/.test(ql);
    if (m && /oxygen|o2|o₂/.test(ql)) {
      const th = +m[1], hit = EXP.filter(e => e.o2 != null && e.o2 >= th), by = {};
      hit.forEach(e => { const b = by[e.inv] = by[e.inv] || { n: 0, mx: 0, fuels: new Set(), burn: 0, ext: 0, as: 0 }; b.n++; b.mx = Math.max(b.mx, e.o2); if (e.fuel) b.fuels.add(e.fuel); if (BURN.has(e.out)) b.burn++; if (OUT.has(e.out)) b.ext++; if (e.assumed) b.as++; });
      const ids = Object.keys(by).sort((a, b) => by[b].n - by[a].n);
      html += `<div class="answer"><b>${hit.length} tests across ${ids.length} investigations</b> reached ≥${th}% O₂ (Earth air is 20.9%).<table style="margin-top:8px"><tr><th>Study</th><th>Tests</th><th>Max O₂</th><th>Fuels</th><th>Burned</th><th>Extinguished</th></tr>${ids.map(id => { const b = by[id]; return `<tr class="click" onclick="FO.open('${id}')"><td><b>${esc(BYID[id].acr)}</b></td><td>${b.n}</td><td>${fmt(b.mx)}%</td><td>${esc([...b.fuels].slice(0, 5).join(', '))}</td><td>${b.burn}</td><td>${b.ext}</td></tr>`; }).join('')}</table><div class="cite"><b>Source:</b> normalized experiment records (${ids.map(i => BYID[i].acr).join(', ')}). ${hit.filter(e => e.assumed).length ? hit.filter(e => e.assumed).length + ' of these use assumed values.' : ''}</div></div>`;
    }
    if (/moon|lunar|habitat|rover|cabin/.test(ql) && /(rank|best|relevant|most|which|priorit)/.test(ql)) {
      html += `<div class="answer"><b>Closest to planned Moon-cabin conditions</b> (≥30% O₂, ≤10.2 psi):<ol>${D.ranking.slice(0, 5).map(r => `<li><b>${esc(r.acronym)}</b> — score ${r.moon_base_score}. ${esc(r.notes.slice(0, 2).join('; '))}</li>`).join('')}</ol><div class="cite"><b>Source:</b> FireOrbit Moon-base scoring (knowledge_base.json). No investigation provides partial-gravity data.</div></div>`;
    }
    let hits = search(q, 4);
    const bk = await askBackend(q); html = bk.html + html;
    if (bk.hits && bk.hits.length) hits = bk.hits;
    if (hits.length) {
      html += `<div class="card"><h3>Most relevant passages</h3>${hits.map(h => { const i = BYID[h.d.id]; return `<div class="answer"><div>${esc(h.d.text.slice(0, 650))}${h.d.text.length > 650 ? '…' : ''}</div><div class="cite"><b>${i ? `<a href="#" onclick="FO.open('${i.id}');return false">${esc(i.acr)}</a>` : esc(h.d.id)}</b> · ${esc(h.d.src)}${h.d.pg ? ' · p.' + h.d.pg : ''}</div></div>`; }).join('')}</div>`;
    } else if (!html) html = '<div class="card">No matching passages. Try other keywords (materials, “smoke”, “extinguish”, a study name).</div>';
    out.innerHTML = html;
  }

  /* ================= GAPS & EARTH ================= */
  function buildGaps(root) {
    const earth = INV.filter(i => i.flags.earth);
    root.innerHTML = `<h2>Gaps &amp; Earth applications</h2><p class="sub">What the PSI data cannot yet tell us, and how this research helps on Earth.</p>
    <div class="grid g2"><div class="card"><h3>Knowledge gaps</h3>${D.gaps.map(g => `<div class="gap"><b>${esc(g.title)}</b><p>${esc(g.detail)}</p>${g.upcoming ? `<p>Upcoming: ${g.upcoming.map(u => `<span class="pill warn">${esc(u)}</span>`).join('')}</p>` : ''}${g.current_proxy ? `<p><i>Current proxy:</i> ${esc(g.current_proxy)}</p>` : ''}</div>`).join('')}
      <div class="gap"><b>Rocket/propellant fire is out of scope</b><p>Combustion in rocket engines is effectively independent of gravity, so PSI does not address it.</p></div></div>
    <div class="card"><h3>Planned cabin atmospheres vs. data</h3><table><tr><th>Environment</th><th>O₂</th><th>Pressure</th></tr><tr><td>Earth sea level</td><td>20.9%</td><td>14.7 psi / 1.0 atm</td></tr><tr><td>Moon base / rover (planned)</td><td>≥30%</td><td>≤10.2 psi / ≤0.694 atm</td></tr><tr><td>Spacesuit</td><td>100%</td><td>4.3 psi / 0.29 atm</td></tr></table>
      <p class="sub" style="margin-top:10px">Studies covering both Moon-cabin O₂ and reduced pressure:</p><div>${INV.filter(i => i.flags.moonO2 && i.flags.lowP).map(i => `<span class="chip" onclick="FO.open('${i.id}')">${esc(i.acr)}</span>`).join('') || 'none'}</div>
      <p class="sub" style="margin-top:10px">Only gas-burner (ACME) tests reach the very high O₂ levels (up to 85%) relevant to suit/oxygen-system hazards.</p></div></div>
    <div class="card"><h3>Earth applications</h3><p class="sub">${earth.length} of ${INV.length} investigations list terrestrial impacts (e.g. fine-water-mist extinguishers, smoke detectors, firefighter gear).</p><div class="grid g2">${earth.map(i => `<div class="card" style="background:var(--panel2);cursor:pointer" onclick="FO.open('${i.id}')"><b>${esc(i.acr)}</b> <span class="pill ${pillClass(i)}">${esc(pillarKey(i))}</span><p><small>${esc(i.impacts.replace(/\s+/g, ' ').slice(0, 320))}${i.impacts.length > 320 ? '…' : ''}</small></p></div>`).join('')}</div></div>`;
  }

  // boot
  const start = (location.hash || '#overview').slice(1);
  showTab(builders[start] ? start : 'overview');
})();
