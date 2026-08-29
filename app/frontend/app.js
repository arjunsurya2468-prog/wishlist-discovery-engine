/* Wishlist Discovery Engine — dashboard renderer.
   Reads the published static artifact. Every number shown is read from
   analysis.json; nothing is recomputed here, so the UI cannot disagree with the
   pipeline that produced it. */
'use strict';

const $ = (s) => document.querySelector(s);
const el = (t, c, txt) => { const n = document.createElement(t); if (c) n.className = c;
  if (txt !== undefined) n.textContent = txt; return n; };
const esc = (s) => String(s ?? '');
const num = (n) => (n ?? 0).toLocaleString();
const pct = (n) => (n === null || n === undefined) ? '—' : `${n}%`;

let DATA = null;

// Quotes arrive either as plain strings or as {quote_text, validation_status}.
const quoteText = (q) => (typeof q === 'string' ? q : (q && (q.quote_text || q.text)) || '');

async function boot() {
  try {
    const r = await fetch('static/analysis.json', { cache: 'no-store' });
    if (!r.ok) throw new Error(`HTTP ${r.status}`);
    DATA = await r.json();
  } catch (e) {
    document.body.innerHTML =
      `<div style="padding:60px;text-align:center;color:#a8b6c6;font-family:sans-serif">
         <h2>Could not load analysis.json</h2><p>${esc(e.message)}</p>
         <p style="color:#6f8095">Run <code>python -m pipeline.run publish</code> first.</p></div>`;
    return;
  }
  renderHeader(); renderBanner(); renderOpportunity(); renderAxes();
  renderThemes(); renderBrief(); renderClusters(); renderValidation();
  renderLiveRunControls(); renderFooter(); wireTabs();
}

function wireTabs() {
  document.querySelectorAll('#tabs button').forEach((b) => {
    b.onclick = () => {
      document.querySelectorAll('#tabs button').forEach((x) => x.classList.remove('active'));
      document.querySelectorAll('.panel').forEach((p) => p.classList.remove('active'));
      b.classList.add('active');
      $(`#panel-${b.dataset.panel}`).classList.add('active');
    };
  });
}

function renderHeader() {
  const h = DATA.header || {}, w = DATA.corpus_weighting || {};
  $('#run-id').textContent = DATA.run_id || '—';
  const apps = Object.entries(h.per_app_counts || {})
    .map(([a, n]) => `${a} ${num(n)}`).join(' · ');
  $('#header-subtitle').textContent =
    `${num(h.usable)} usable records from ${num(h.raw_scraped)} scraped · ${apps}`;

  const stats = [
    ['Usable records', num(h.usable)],
    ['Themes', num((DATA.themes || []).length)],
    ['Clusters', num((DATA.all_clusters || []).length)],
    ['Noise', pct((DATA.noise || {}).pct)],
    ['Quotes validated', num((DATA.validation || {}).quotes_validated)],
    ['Community share', pct(w.primary_pct)],
  ];
  const row = $('#stats-row'); row.innerHTML = '';
  stats.forEach(([l, v]) => {
    const s = el('div', 'stat'); s.append(el('div', 'v', v), el('div', 'l', l)); row.append(s);
  });
}

/* The corpus caveat. It is rendered above the tabs because it qualifies every
   figure in every panel — burying it in a footnote would misrepresent the run. */
function renderBanner() {
  const w = DATA.corpus_weighting || {};
  if (!w.total) return;
  const b = $('#corpus-banner');
  const src = Object.entries(w.per_source || {}).map(([k, v]) => `${k} ${num(v)}`).join(', ');
  b.innerHTML =
    `<span class="btag">READ FIRST</span>` +
    `This corpus is <strong>${pct(w.secondary_pct)} app-store reviews</strong> and only ` +
    `<strong>${pct(w.primary_pct)} community discussion</strong> (${num(w.primary_n)} records: ${esc(src)}). ` +
    `Community text is the intended base for wishlist-abandonment reasoning — store reviews are ` +
    `transactional and largely cannot carry it. Treat every rate below as directional, not decisive.`;
}

function renderOpportunity() {
  const r = DATA.recommendation || {}, p = $('#panel-opportunity');
  p.innerHTML = '';
  if (!r.axis) {
    p.append(el('div', 'empty', r.what_this_means || 'No single opportunity area dominates.'));
    return;
  }
  const hero = el('div', 'hero');
  hero.append(el('div', 'eyebrow', 'Highest-potential opportunity area'));
  hero.append(el('div', 'axis', r.axis));
  const gate = el('div', 'gate');
  gate.innerHTML = `Fix lands at the <strong>${esc(r.funnel_gate || '—')}</strong> gate ` +
    `<span class="badge ${esc(r.confidence)}">${esc(r.confidence)} confidence</span>` +
    (r.runner_up ? ` <span class="muted">· runner-up: ${esc(r.runner_up)}</span>` : '');
  hero.append(gate);

  const m = el('div', 'hero-metrics');
  [['Stalled', num(r.stalled_count)], ['Resolved', num(r.resolved_count)],
   ['Resolution rate', `${Math.round((r.resolution_rate || 0) * 100)}%`],
   ['External refs', num(r.external_refs)]]
    .forEach(([l, v]) => { const d = el('div', 'hm');
      d.append(el('div', 'v', v), el('div', 'l', l)); m.append(d); });
  hero.append(m);
  if (r.what_this_means) hero.append(el('div', 'what', r.what_this_means));
  p.append(hero);

  const conv = r.convergent_themes || [];
  if (conv.length) {
    p.append(el('h2', null, 'Independently clustered themes corroborating this axis'));
    const w = el('div', 'table-wrap');
    w.innerHTML = `<table><thead><tr><th>Theme</th><th>Gate</th><th>Records</th></tr></thead>
      <tbody>${conv.map((c) => `<tr><td class="txt">${esc(c.theme_name)}</td>
      <td><span class="badge gate">${esc(c.funnel_gate)}</span></td>
      <td>${num(c.review_count)}</td></tr>`).join('')}</tbody></table>`;
    p.append(w);
  }
  const qs = (r.quotes || []).filter(Boolean);
  if (qs.length) {
    p.append(el('h2', null, 'Representative stalled-decision quotes'));
    const box = el('div', 'quotes');
    qs.forEach((q) => box.append(el('div', 'quote', `“${quoteText(q)}”`)));
    p.append(box);
  }
}

function renderAxes() {
  const t = DATA.resolution_template || {}, by = t.by_axis || {}, p = $('#panel-axes');
  p.innerHTML = '';
  p.append(el('h2', null, 'Where decisions stall, and where they close'));
  const intro = el('p', 'muted', t.summary || '');
  p.append(intro);
  const rows = Object.entries(by).sort((a, b) => b[1].stalled_count - a[1].stalled_count);
  if (!rows.length) { p.append(el('div', 'empty', 'No axis data in this run.')); return; }

  const lg = el('div', 'legend');
  lg.innerHTML = `<span><i style="background:#e0a33e"></i>stalled — decision left open</span>
                  <span><i style="background:#4bb974"></i>resolved — decision closed</span>`;
  p.append(lg);

  const max = Math.max(...rows.map(([, v]) => v.stalled_count + v.resolved_count)) || 1;
  rows.forEach(([axis, v]) => {
    const row = el('div', 'axis-row');
    const name = el('div', 'axis-name'); name.textContent = axis;
    if (v.unresolved_gap) name.append(' ', Object.assign(el('span', 'badge warn', 'gap'), {}));
    const total = v.stalled_count + v.resolved_count;
    const bar = el('div', 'bar');
    const width = (total / max) * 100;
    bar.style.width = `${Math.max(width, 3)}%`;
    const s = el('div', 'stalled'); s.style.flex = String(v.stalled_count);
    const rr = el('div', 'resolved'); rr.style.flex = String(v.resolved_count);
    bar.append(s, rr);
    const holder = el('div'); holder.append(bar);
    const nums = el('div', 'axis-nums',
      `${v.stalled_count} stalled / ${v.resolved_count} resolved · ${Math.round((v.resolution_rate || 0) * 100)}% closed`);
    row.append(name, holder, nums);
    p.append(row);
  });
  if (t.what_this_means) {
    const w = el('p', 'muted', t.what_this_means); w.style.marginTop = '16px'; p.append(w);
  }
}

function renderThemes() {
  const themes = DATA.themes || [];
  const gates = [...new Set(themes.map((t) => t.funnel_gate).filter(Boolean))].sort();
  const sel = $('#gate-filter');
  gates.forEach((g) => sel.append(new Option(g, g)));
  const draw = () => {
    const q = $('#theme-search').value.toLowerCase().trim();
    const g = sel.value;
    const list = themes.filter((t) => {
      if (g && t.funnel_gate !== g) return false;
      if (!q) return true;
      const hay = `${t.theme_name} ${t.summary} ${t.mapping_rationale} ${(t.quotes || []).map(quoteText).join(' ')}`;
      return hay.toLowerCase().includes(q);
    });
    $('#theme-count').textContent = `${list.length} of ${themes.length}`;
    const wrap = $('#themes-list'); wrap.innerHTML = '';
    if (!list.length) { wrap.append(el('div', 'empty', 'No themes match.')); return; }
    list.sort((a, b) => (b.review_count || 0) - (a.review_count || 0)).forEach((t) => {
      const d = el('div', 'theme');
      const head = el('div', 'theme-head');
      const left = el('div');
      left.append(el('div', 'theme-name', t.theme_name || '(unnamed)'));
      const badges = el('div'); badges.style.marginTop = '5px';
      if (t.funnel_gate) badges.append(Object.assign(el('span', 'badge gate', t.funnel_gate)));
      if (t.track) { const b = el('span', 'badge', `track ${t.track}`); b.style.marginLeft = '6px'; badges.append(b); }
      left.append(badges);
      head.append(left, el('div', 'theme-meta',
        `n=${num(t.review_count)} · ${t.pct_of_corpus ?? 0}% · #${t.cluster_id}`));
      d.append(head);
      if (t.summary) d.append(el('p', 'theme-sum', t.summary));
      if (t.mapping_rationale) {
        const r = el('div', 'rationale');
        r.append(el('span', 'lbl', 'Why this gate'), document.createTextNode(t.mapping_rationale));
        d.append(r);
      }
      const qs = (t.quotes || []).map(quoteText).filter(Boolean);
      if (qs.length) {
        const box = el('div', 'quotes');
        qs.slice(0, 3).forEach((q) => box.append(el('div', 'quote', `“${q}”`)));
        d.append(box);
      }
      wrap.append(d);
    });
  };
  $('#theme-search').oninput = draw; sel.onchange = draw; draw();
}

function renderBrief() {
  const b = DATA.brief_questions || {}, qs = b.questions || [];
  const sum = b.summary || {};
  const row = $('#brief-summary'); row.innerHTML = '';
  const counts = {};
  qs.forEach((q) => { counts[q.status] = (counts[q.status] || 0) + 1; });
  [['Questions', num(sum.total ?? qs.length)],
   ['Answerable', num(sum.answerable)],
   ['Not answerable', num(sum.not_answerable)]]
    .forEach(([l, v]) => { const c = el('div', 'card');
      c.append(el('div', 'k', l), el('div', 'v', v)); row.append(c); });

  const sd = b.source_disclosure || {};
  if (sd.corpus) {
    const c = el('div', 'card'); c.style.gridColumn = '1/-1';
    c.append(el('div', 'k', 'Source disclosure'));
    const p = el('p', 'muted');
    p.style.marginTop = '6px';
    p.textContent = [sd.corpus, sd.weighting, sd.sources_dropped, sd.primary_research]
      .filter(Boolean).join(' ');
    c.append(p); row.append(c);
  }

  const list = $('#brief-questions-list'); list.innerHTML = '';
  const cls = (s) => /Not answerable/i.test(s) ? 'bad'
    : /under-powered|Partial/i.test(s) ? 'warn' : 'good';
  qs.forEach((q) => {
    const d = el('div', 'q');
    const head = el('div', 'q-head');
    const t = el('div', 'q-text'); t.textContent = q.question;
    head.append(el('span', 'q-id', q.id), t,
      Object.assign(el('span', `badge ${cls(q.status)}`, q.status)));
    d.append(head);
    d.append(el('p', 'q-ans', q.answer || ''));
    const ev = q.evidence || [];
    if (ev.length) {
      const chips = el('div', 'chips');
      ev.forEach((e) => chips.append(el('span', 'chip',
        `${e.theme_name || e.theme_id} · n=${num(e.review_count)}`)));
      d.append(chips);
    }
    if (q.caveat) {
      const c = el('div', 'q-caveat');
      c.append(el('span', 'lbl', 'Caveat'), document.createTextNode(q.caveat));
      d.append(c);
    }
    list.append(d);
  });
}

function renderClusters() {
  const cs = DATA.all_clusters || [], n = DATA.noise || {};
  $('#clusters-brief').textContent =
    `${cs.length} clusters · ${num(n.count)} records in noise (${pct(n.pct)}). ` +
    `Ranked by size × relevance share, rating-agnostic.`;
  const apps = Object.keys((cs[0] || {}).per_app || {});
  $('#clusters-table-wrap').innerHTML =
    `<table><thead><tr><th>#</th><th>Size</th><th>Rel. share</th><th>Avg ★</th>
     ${apps.map((a) => `<th>${esc(a)}</th>`).join('')}</tr></thead><tbody>` +
    cs.slice().sort((a, b) => b.size - a.size).map((c) =>
      `<tr><td>${c.id}</td><td>${num(c.size)}</td><td>${(c.relevance_share ?? 0).toFixed(2)}</td>
       <td>${c.avg_rating ?? '—'}</td>
       ${apps.map((a) => `<td>${num((c.per_app || {})[a])}</td>`).join('')}</tr>`).join('') +
    `</tbody></table>`;
}

function renderValidation() {
  const v = DATA.validation || {}, g = $('#validation-grid');
  g.innerHTML = '';
  const nt = v.negative_test || {};
  const cards = [
    ['Quotes validated', num(v.quotes_validated), 'good'],
    ['Quotes rejected', num(v.quotes_rejected), null],
    ['Spot-check agreement', pct(v.spotcheck_agreement_pct), null],
    ['Spot-check pending', num(v.pending), v.pending ? 'warn' : null],
    ['Fabricated-quote test', nt.rejected ? 'REJECTED ✓' : 'NOT REJECTED ✗', nt.rejected ? 'good' : 'bad'],
  ];
  cards.forEach(([k, val, tone]) => {
    const c = el('div', 'card');
    c.append(el('div', 'k', k));
    const d = el('div', 'v', val);
    if (tone === 'good') d.style.color = '#7fd6a0';
    if (tone === 'warn') d.style.color = '#e8bd72';
    if (tone === 'bad') d.style.color = '#eb8f97';
    c.append(d); g.append(c);
  });
  if (nt.fabricated_quote) {
    const c = el('div', 'card'); c.style.gridColumn = '1/-1';
    c.append(el('div', 'k', 'Negative test — a quote that does NOT exist in the corpus'));
    const q = el('div', 'quote', `“${nt.fabricated_quote}”`);
    q.style.marginTop = '8px'; c.append(q);
    c.append(el('p', 'muted',
      nt.rejected
        ? 'Correctly rejected by the same substring validator every displayed quote passes — the kill-switch fires.'
        : 'WARNING: not rejected. Quote validation is not working.'));
    g.append(c);
  }
  // cross-source corroboration
  const co = DATA.corroboration || {}, box = $('#corroboration-block');
  box.innerHTML = '';
  if (co.verdict) {
    const h = el('h2', null, 'Cross-source corroboration');
    h.style.marginTop = '24px';
    box.append(h, el('p', 'muted', co.verdict));
    const cst = co.cross_source_themes || [];
    if (cst.length) {
      const w = el('div', 'table-wrap');
      w.innerHTML = `<table><thead><tr><th>Theme</th><th>Gate</th>
        <th>Community</th><th>Store</th></tr></thead><tbody>` +
        cst.map((t) => `<tr><td class="txt">${esc(t.theme_name)}</td>
          <td><span class="badge gate">${esc(t.funnel_gate)}</span></td>
          <td>${num(t.primary_n)}</td><td>${num(t.secondary_n)}</td></tr>`).join('') +
        `</tbody></table>`;
      box.append(w);
    }
  }
}

function renderLiveRunControls() {
  const sel = $('#live-run-app');
  Object.keys((DATA.header || {}).per_app_counts || {}).forEach((a) => sel.append(new Option(a, a)));
  $('#live-run-btn').onclick = async () => {
    const btn = $('#live-run-btn'), status = $('#live-run-status'), out = $('#live-run-result');
    btn.disabled = true; status.textContent = 'running — scraping, embedding, assigning…';
    out.innerHTML = '';
    try {
      const r = await fetch('api/live-run', {
        method: 'POST', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ app: sel.value }),
      });
      const d = await r.json();
      if (!r.ok) throw new Error(d.error || `HTTP ${r.status}`);
      status.textContent = '';
      renderLiveRunResult(d);
    } catch (e) {
      status.textContent = '';
      out.innerHTML = `<div class="empty">Live run failed: ${esc(e.message)}</div>`;
    } finally { btn.disabled = false; }
  };
}

function renderLiveRunResult(d) {
  const out = $('#live-run-result'); out.innerHTML = '';
  const g = el('div', 'cards');
  [['App', d.app], ['Fetched', num(d.fetched)], ['Usable', num(d.usable)],
   ['New in noise', num(d.new_noise_count)],
   ['Source', d.source === 'live' ? 'live scrape' : 'cached sample']]
    .forEach(([k, v]) => { const c = el('div', 'card');
      c.append(el('div', 'k', k), el('div', 'v', v)); g.append(c); });
  out.append(g);
  if (d.source === 'cached') {
    const n = el('p', 'muted',
      'Served from a shipped cached sample — the live scrape was blocked from this host. Labelled, never presented as fresh.');
    n.style.marginTop = '10px'; out.append(n);
  }
  const rows = d.top_clusters || d.per_cluster_delta || [];
  if (rows.length) {
    const h = el('h2', null, 'Assignments into the locked taxonomy');
    h.style.marginTop = '20px'; out.append(h);
    const w = el('div', 'table-wrap');
    w.innerHTML = `<table><thead><tr><th>Cluster</th><th>New records</th></tr></thead><tbody>` +
      rows.map((c) => `<tr><td>#${c.cluster_id}</td><td>${num(c.new_reviews)}</td></tr>`).join('') +
      `</tbody></table>`;
    out.append(w);
  } else if (d.message) {
    out.append(el('div', 'empty', d.message));
  }
}

function renderFooter() {
  const m = DATA.models || {};
  $('#footer-models').textContent =
    `embed ${m.embedding_model || '—'} · llm ${m.llm_model || '—'}` +
    (m.llm_fallback ? ` (fallback ${m.llm_fallback})` : '');
  $('#footer-run').textContent =
    `run ${DATA.run_id || '—'} · generated ${(DATA.generated_at || '').slice(0, 19).replace('T', ' ')} UTC`;
}

boot();
