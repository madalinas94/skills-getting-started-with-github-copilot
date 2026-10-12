// Penny – UI. Calculele de afișare sunt locale; sfaturile vin de la /api/insights (tot local, gratuit).
const $ = (s) => document.querySelector(s);
const $$ = (s) => [...document.querySelectorAll(s)];

const CAT = {
  "Mâncare": { c: "#f97316", i: "🍽️" }, "Transport": { c: "#38bdf8", i: "🚗" }, "Utilități": { c: "#fbbf24", i: "💡" },
  "Locuință": { c: "#8b5cf6", i: "🏠" }, "Sănătate": { c: "#fb7185", i: "💊" }, "Divertisment": { c: "#ec4899", i: "🎬" },
  "Shopping": { c: "#a3e635", i: "🛍️" }, "Călătorii": { c: "#14b8a6", i: "✈️" }, "Venituri": { c: "#34d399", i: "💰" },
  "Altele": { c: "#94a3b8", i: "📦" },
};
const SRC = { card_csv: { c: "#8b5cf6", i: "💳" }, extras_pdf: { c: "#38bdf8", i: "🏦" }, bon: { c: "#fbbf24", i: "🧾" } };
const REC_G = { high: "var(--g-coral)", medium: "var(--g-sun)", low: "var(--g-sky)" };
const PRIO = { high: "prioritate mare", medium: "prioritate medie", low: "bonus" };
const MONTHS = ["", "ianuarie", "februarie", "martie", "aprilie", "mai", "iunie", "iulie", "august", "septembrie", "octombrie", "noiembrie", "decembrie"];
const WEEKDAYS = ["Luni", "Marți", "Miercuri", "Joi", "Vineri", "Sâmbătă", "Duminică"];
const SUGGESTIONS = [
  "Cât am cheltuit pe mâncare în martie?", "Pe ce categorii am cheltuit în martie?", "Care a fost cea mai mare cheltuială?",
  "Cât am încasat în martie?", "Cât am plătit cash?", "Câte tranzacții am făcut în euro?", "La ce magazine am cheltuit cel mai mult?",
];

const state = {
  txs: [], insights: null, rates: { RON: 1, EUR: 5.25, USD: 4.4 }, categories: [], sources: {},
  cur: "RON", month: "", tab: "home", curFilter: "", srcFilter: "", catFilter: "", dirFilter: "", search: "",
  showDup: false, sort: { key: "date", asc: false }, highlight: null, lastHeadline: "",
};

// ---------------------------------------------------------------- utilitare
const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* fără stocare: ok */ } },
};
const conv = (t, to = state.cur) => (t.amount * state.rates[t.currency]) / state.rates[to];
const nf = new Intl.NumberFormat("ro-RO", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const fmt = (v, cur = state.cur) => `${nf.format(v)} ${cur}`;
const monthLabel = (ym) => (ym ? `${MONTHS[+ym.slice(5)]} ${ym.slice(0, 4)}` : "toată perioada");
const fmtDate = (iso) => iso.split("-").reverse().join(".");
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const isExpense = (t) => t.direction === "debit" && t.category !== "Venituri";
const active = () => state.txs.filter((t) => !t.duplicate_of && (!state.month || t.date.startsWith(state.month)));

function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(toast.t);
  toast.t = setTimeout(() => el.classList.remove("show"), 2800);
}

async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `Eroare ${r.status}`);
  return data;
}

function greeting() {
  const h = new Date().getHours();
  return h < 11 ? "Bună dimineața" : h < 18 ? "Bună ziua" : "Bună seara";
}

// efect de „scris de mână” pentru mesajele lui Penny
function typeText(el, text, speed = 14) {
  clearInterval(el._t);
  el.classList.add("typing");
  el.textContent = "";
  let i = 0;
  el._t = setInterval(() => {
    el.textContent = text.slice(0, ++i);
    if (i >= text.length) { clearInterval(el._t); el.classList.remove("typing"); }
  }, speed);
}

// ---------------------------------------------------------------- pornire
async function init() {
  applyTheme(store.get("penny-theme", "dark"));
  $("#brandBot").innerHTML = Charts.penny();
  $("#heroBot").innerHTML = Charts.penny({ wave: true });
  $("#fabBot").innerHTML = Charts.penny();
  $("#chatBot").innerHTML = Charts.penny();
  $("#saveBot").innerHTML = Charts.penny({ wave: true });
  $("#suggestions").innerHTML = SUGGESTIONS.map((s) => `<button class="chip" type="button">${s}</button>`).join("");

  const st = await api("/api/status");
  Object.assign(state, { rates: st.rates, categories: st.categories, sources: st.sources });
  renderStatus(st);
  const opts = st.categories.map((c) => `<option>${c}</option>`).join("");
  $("#catFilter").insertAdjacentHTML("beforeend", opts);
  $("#manualCat").insertAdjacentHTML("beforeend", opts);

  const { transactions } = await api("/api/transactions");
  await setTxs(transactions, true);
  chatSay(`Hi! 👋 Sunt Penny. Întreabă-mă orice despre cheltuielile tale, de exemplu „Cât am cheltuit pe mâncare în martie?”. Calculele le fac exact, pe tranzacțiile tale.`);
  showWelcome();
}

function showWelcome() {
  const has = state.txs.length > 0;
  $("#welcomeBot").innerHTML = Charts.penny({ wave: true });
  $("#welcomeTitle").textContent = has ? `Hi! Bine ai revenit 👋` : `Hi! I'm Penny 👋`;
  $("#welcomeDemo").hidden = has;
  $("#welcomeGo").textContent = has ? "Vezi analiza 📊" : "Hai să începem 🚀";
  const text = has
    ? (state.insights?.headline || "")
    : `${greeting()}! Sunt asistentul tău pentru bani. Încarcă extrasul de card, extrasul de cont sau pozele bonurilor și îți arăt unde se duc banii, ce atenționări ai și cum poți economisi.`;
  $("#welcome").hidden = false;
  typeText($("#welcomeText"), text, 12);
}
const closeWelcome = () => { $("#welcome").hidden = true; };

function renderStatus(st) {
  const el = $("#aiStatus");
  el.textContent = st.ai_enabled ? `● AI activ · $${st.usage.cost_usd.toFixed(4)}` : "● Mod local";
  el.classList.toggle("off", !st.ai_enabled);
  el.title = st.ai_enabled
    ? `Model: ${st.model} · ${st.usage.calls} apeluri · ${st.usage.input_tokens + st.usage.output_tokens} tokeni`
    : "Fără cheie API: categorii prin reguli, întrebări interpretate local. Pune ANTHROPIC_API_KEY în .env pentru AI.";
}
const refreshStatus = () => api("/api/status").then(renderStatus).catch(() => {});

async function setTxs(txs, pickMonth = false) {
  state.txs = txs;
  const months = [...new Set(txs.map((t) => t.date.slice(0, 7)))].sort();
  if (pickMonth || (state.month && !months.includes(state.month))) {
    // luna implicită = luna cu cele mai multe tranzacții (nu zilele rătăcite de la margine)
    const cnt = {};
    txs.forEach((t) => (cnt[t.date.slice(0, 7)] = (cnt[t.date.slice(0, 7)] || 0) + 1));
    state.month = [...months].sort((a, b) => cnt[b] - cnt[a])[0] || "";
  }
  $("#monthSel").innerHTML = `<option value="">Toată perioada</option>` +
    months.map((m) => `<option value="${m}" ${m === state.month ? "selected" : ""}>${monthLabel(m)}</option>`).join("");
  await refresh();
}

async function refresh() {
  try {
    state.insights = await api(`/api/insights?month=${state.month}&currency=${state.cur}`);
  } catch (e) {
    toast(e.message);
  }
  render();
}

function render() {
  const has = state.txs.length > 0;
  $("#homeEmpty").hidden = has;
  $("#homeData").hidden = !has;
  renderHero();
  if (has) { renderKpis(); renderDonut(); renderAlerts(); renderDaily(); renderRule(); renderTopTips(); }
  renderAnalytics();
  renderTips();
  renderTable();
}

// ---------------------------------------------------------------- ACASĂ
function renderHero() {
  const ins = state.insights;
  const has = state.txs.length > 0;
  $("#heroHello").textContent = `${greeting()}! 👋 Sunt Penny`;
  const text = has && ins ? ins.headline
    : "Încarcă extrasele și pozele bonurilor, iar eu îți arăt unde se duc banii și cum poți economisi.";
  if (text !== state.lastHeadline) { typeText($("#heroBubble"), text); state.lastHeadline = text; }
  $("#heroScore").hidden = !has;
  if (has && ins) Charts.gauge($("#heroScore"), ins.score, ins.score_label);
}

function renderKpis() {
  const t = state.insights.totals;
  const rows = active();
  $("#kSpend").textContent = fmt(t.expenses);
  $("#kSpendN").textContent = `${t.count} plăți · medie ${fmt(t.avg_tx)}`;
  $("#kIncome").textContent = fmt(t.income);
  $("#kIncomeN").textContent = `${rows.filter((x) => x.direction === "credit").length} încasări (nu sunt cheltuieli)`;
  const net = $("#kNet");
  net.textContent = (t.net > 0 ? "+" : "") + fmt(t.net);
  net.className = t.net >= 0 ? "pos" : "neg";
  const rate = $("#kRate");
  rate.textContent = t.savings_rate === null ? "–" : `${t.savings_rate.toFixed(1)}%`;
  rate.className = t.savings_rate === null ? "" : t.savings_rate >= 20 ? "pos" : t.savings_rate < 0 ? "neg" : "";
  $("#kSave").textContent = fmt(state.insights.potential_saving);
  $("#kSaveY").textContent = `≈ ${fmt(state.insights.potential_saving_year)} pe an`;
}

function renderDonut() {
  const cats = state.insights.categories;
  const items = cats.map((c) => ({ label: c.category, value: c.total, color: CAT[c.category]?.c || "#94a3b8", fmt: fmt(c.total) }));
  const hover = (i) => $$("#donutLegend .legend-row").forEach((r, j) => r.classList.toggle("hov", j === i));
  Charts.donut($("#donut"), items, {
    center: fmt(state.insights.totals.expenses).replace(/,\d\d /, " "), sub: `cheltuieli · ${monthLabel(state.month)}`,
    onClick: (it) => goToTx({ catFilter: it.label }), onHover: hover,
  });
  $("#donutLegend").innerHTML = cats.map((c, i) => `
    <div class="legend-row" data-i="${i}" data-cat="${esc(c.category)}">
      <i style="background:${CAT[c.category]?.c}"></i><span>${CAT[c.category]?.i || ""} ${esc(c.category)}</span>
      <b>${fmt(c.total)}</b><small>${c.share.toFixed(0)}%</small>
    </div>`).join("");
  $$("#donutLegend .legend-row").forEach((r) => {
    const sl = () => $(`#donut .slice[data-i="${r.dataset.i}"]`);
    r.addEventListener("mouseenter", () => sl()?.classList.add("hov"));
    r.addEventListener("mouseleave", () => sl()?.classList.remove("hov"));
    r.addEventListener("click", () => goToTx({ catFilter: r.dataset.cat }));
  });
}

function renderAlerts() {
  const icons = { danger: "🚨", warn: "⚠️", info: "ℹ️", success: "🎉" };
  const a = state.insights.alerts;
  $("#alertCount").textContent = a.length ? `${a.length} ${a.length === 1 ? "mesaj" : "mesaje"}` : "";
  $("#alerts").innerHTML = a.length
    ? a.map((x, i) => `<div class="alert ${x.level}" style="animation-delay:${i * 0.06}s"><span class="ai">${icons[x.level]}</span>
        <div><b>${esc(x.title)}</b><p>${esc(x.text)}</p></div></div>`).join("")
    : `<div class="alert success"><span class="ai">🎉</span><div><b>Totul arată bine</b><p>Nicio problemă de semnalat pentru perioada aleasă.</p></div></div>`;
}

function renderDaily() {
  const rows = active().filter(isExpense);
  const by = {};
  rows.forEach((t) => (by[t.date] ||= []).push(t));
  const dates = Object.keys(by).sort();
  let days = dates;
  if (state.month && dates.length) {
    // toate zilele lunii, inclusiv cele fără cheltuieli, ca graficul să fie corect pe axă
    const [y, m] = state.month.split("-").map(Number);
    const n = new Date(y, m, 0).getDate();
    days = Array.from({ length: n }, (_, i) => `${state.month}-${String(i + 1).padStart(2, "0")}`);
  }
  const data = days.map((d) => {
    const list = by[d] || [];
    const top = [...list].sort((a, b) => conv(b) - conv(a)).slice(0, 3).map((t) => esc(t.description.slice(0, 28))).join("<br>");
    return { date: d, label: d.slice(8).replace(/^0/, ""), full: fmtDate(d), value: list.reduce((a, t) => a + conv(t), 0),
      n: list.length, top: top || "fără cheltuieli", ids: list.map((t) => t.id) };
  });
  Charts.daily($("#daily"), data, {
    fmt, onClick: (d) => d.ids.length && goToTx({ highlight: { ids: new Set(d.ids), label: `Cheltuielile din ${d.full}` } }),
  });
}

function renderRule() {
  const r = state.insights.rule_50_30_20;
  if (!r.income) {
    $("#rule").innerHTML = `<div class="empty">Regula se calculează din venit. Încarcă și extrasul de cont ca să apară încasările.</div>`;
    return;
  }
  const over = Math.max(r.needs_pct + r.wants_pct + r.savings_pct, 100);
  const w = (p) => `${(p / over) * 100}%`;
  const verdict = (val, ideal, lowerIsBetter) => {
    const ok = lowerIsBetter ? val <= ideal : val >= ideal;
    return `<span class="verdict ${ok ? "pos" : "neg"}">${ok ? "✓ în regulă" : lowerIsBetter ? `▲ +${val - ideal} pp peste` : `▼ ${ideal - val} pp sub țintă`}</span>`;
  };
  $("#rule").innerHTML = `
    <div class="rule-row"><div class="rl"><span>Ideal</span><span>50 / 30 / 20</span></div>
      <div class="stack"><span style="width:50%;background:var(--g-sky)">Nevoi 50%</span><span style="width:30%;background:var(--g-coral)">Dorințe 30%</span><span style="width:20%;background:var(--g-mint)">Economii 20%</span></div></div>
    <div class="rule-row"><div class="rl"><span>Tu, în ${monthLabel(state.month)}</span><span>${r.needs_pct} / ${r.wants_pct} / ${r.savings_pct}</span></div>
      <div class="stack"><span style="width:${w(r.needs_pct)};background:var(--g-sky)">${r.needs_pct}%</span><span style="width:${w(r.wants_pct)};background:var(--g-coral)">${r.wants_pct}%</span><span style="width:${w(r.savings_pct)};background:var(--g-mint)">${r.savings_pct ? r.savings_pct + "%" : ""}</span></div></div>
    <div class="rule-legend">
      <div>🏠 Nevoi<b>${fmt(r.needs)}</b>${verdict(r.needs_pct, 50, true)}</div>
      <div>🎉 Dorințe<b>${fmt(r.wants)}</b>${verdict(r.wants_pct, 30, true)}</div>
      <div>🐷 Economii<b>${fmt(r.savings)}</b>${verdict(r.savings_pct, 20, false)}</div>
    </div>`;
}

function renderTopTips() {
  const recs = state.insights.recommendations.filter((r) => r.saving > 0).slice(0, 4);
  $("#topTips").innerHTML = recs.length ? recs.map((r) => `
    <div class="mini-tip" data-goto="tips"><span class="em" style="background:${REC_G[r.priority]}">${r.icon}</span>
      <div><b>${esc(r.title)}</b><small>${esc(r.tips[0])}</small></div><span class="sv">+${fmt(r.saving)}</span></div>`).join("")
    : `<div class="empty">Nicio recomandare încă.</div>`;
}

// ---------------------------------------------------------------- ANALIZE
function renderAnalytics() {
  const ins = state.insights;
  if (!ins) return;
  const cats = ins.categories;
  const hasIncome = ins.totals.income > 0;
  const statusTxt = { ok: "✓ În buget", warn: "● Atenție", over: "▲ Peste buget", na: "– fără venit" };
  $("#catTable").innerHTML = cats.length ? `
    <thead><tr><th>Categorie</th><th class="num">Total</th><th class="num">% din total</th><th class="num">Plăți</th>
      <th class="num">Medie</th><th class="num">Cea mai mare</th>${hasIncome ? "<th>Folosire buget</th><th>Status</th>" : ""}</tr></thead>
    <tbody>${cats.map((c) => {
      const col = CAT[c.category]?.c || "#94a3b8";
      const fillCol = c.status === "over" ? "var(--neg)" : c.status === "warn" ? "var(--warn)" : col;
      return `<tr>
        <td><span class="cat-cell"><span class="cat-ico" style="background:${col}26">${CAT[c.category]?.i || ""}</span>${esc(c.category)}</span></td>
        <td class="num"><b>${fmt(c.total)}</b></td><td class="num">${c.share.toFixed(1)}%</td><td class="num">${c.count}</td>
        <td class="num">${fmt(c.avg)}</td><td class="num">${fmt(c.max)}</td>
        ${hasIncome ? `<td><div class="usage" title="Buget recomandat: ${c.budget_pct}% din venit = ${fmt(c.budget)}">
            <span class="track"><span class="fill" style="width:${Math.min(c.usage, 100)}%;background:${fillCol}"></span></span><small>${c.usage}%</small></div></td>
          <td><span class="status ${c.status}">${statusTxt[c.status]}</span></td>` : ""}
      </tr>`;
    }).join("")}</tbody>
    <tfoot><tr><td>Total</td><td class="num">${fmt(ins.totals.expenses)}</td><td class="num">100%</td><td class="num">${ins.totals.count}</td>
      <td class="num">${fmt(ins.totals.avg_tx)}</td><td colspan="${hasIncome ? 3 : 1}"></td></tr></tfoot>`
    : `<tbody><tr><td class="empty">Nu există cheltuieli în perioada aleasă.</td></tr></tbody>`;

  // pe zile ale săptămânii
  const rows = active().filter(isExpense);
  const wd = WEEKDAYS.map((d) => ({ label: d.slice(0, 2), full: d, value: 0, n: 0 }));
  rows.forEach((t) => { const i = (new Date(t.date).getDay() + 6) % 7; wd[i].value += conv(t); wd[i].n++; });
  Charts.columns($("#weekday"), wd, { fmt });
  const top = [...wd].sort((a, b) => b.value - a.value)[0];
  $("#weekdayHint").textContent = top?.value ? `cele mai mari cheltuieli: ${top.full.toLowerCase()}` : "";

  // pe surse
  const src = {};
  rows.forEach((t) => (src[t.source] = (src[t.source] || 0) + conv(t)));
  const sItems = Object.entries(src).sort((a, b) => b[1] - a[1])
    .map(([k, v]) => ({ label: state.sources[k] || k, value: v, color: SRC[k]?.c || "#94a3b8", fmt: fmt(v), key: k }));
  const sTot = sItems.reduce((a, i) => a + i.value, 0);
  Charts.donut($("#sourceDonut"), sItems, { center: String(sItems.length), sub: "surse", size: 180,
    onClick: (it) => goToTx({ srcFilter: it.key }) });
  $("#sourceLegend").innerHTML = sItems.map((s) => `<div class="legend-row" data-src="${s.key}"><i style="background:${s.color}"></i>
    <span>${SRC[s.key]?.i || ""} ${esc(s.label)}</span><b>${s.fmt}</b><small>${((s.value / sTot) * 100).toFixed(0)}%</small></div>`).join("");
  $$("#sourceLegend .legend-row").forEach((r) => r.addEventListener("click", () => goToTx({ srcFilter: r.dataset.src })));

  // comercianți
  const mMax = Math.max(...ins.merchants.map((m) => m.total), 1);
  $("#merchTable").innerHTML = ins.merchants.length ? `
    <thead><tr><th>#</th><th>Comerciant</th><th class="num">Vizite</th><th class="num">Total</th><th class="num">Medie</th><th>Ultima</th></tr></thead>
    <tbody>${ins.merchants.map((m, i) => `<tr class="clickable" data-q="${esc(m.name)}">
      <td>${["🥇", "🥈", "🥉"][i] || i + 1}</td>
      <td><b>${esc(m.name)}</b><div class="mini-bar" style="width:${(m.total / mMax) * 100}%;background:${CAT[m.category]?.c}"></div>
        <small class="muted">${CAT[m.category]?.i || ""} ${esc(m.category)}</small></td>
      <td class="num">${m.visits}×</td><td class="num"><b>${fmt(m.total)}</b></td><td class="num">${fmt(m.avg)}</td>
      <td class="muted">${fmtDate(m.last)}</td></tr>`).join("")}</tbody>`
    : `<tbody><tr><td class="empty">—</td></tr></tbody>`;
  $$("#merchTable tr[data-q]").forEach((r) => r.addEventListener("click", () => goToTx({ search: r.dataset.q.split(" ")[0] })));

  // abonamente
  const subs = ins.subscriptions;
  const yr = subs.reduce((a, s) => a + s.yearly, 0);
  $("#subsHint").textContent = subs.length ? `≈ ${fmt(yr)} pe an` : "";
  $("#subsTable").innerHTML = subs.length ? `
    <thead><tr><th>Serviciu</th><th class="num">Lunar</th><th class="num">Pe an</th><th>Sugestie</th></tr></thead>
    <tbody>${subs.map((s) => `<tr><td><span class="cat-cell"><span class="cat-ico" style="background:${CAT[s.category]?.c}26">${CAT[s.category]?.i}</span>${esc(s.name)}</span></td>
      <td class="num">${fmt(s.monthly)}</td><td class="num"><b>${fmt(s.yearly)}</b></td><td class="sub-tip">${esc(s.tip)}</td></tr>`).join("")}</tbody>
    <tfoot><tr><td>Total</td><td class="num">${fmt(yr / 12)}</td><td class="num">${fmt(yr)}</td><td></td></tr></tfoot>`
    : `<tbody><tr><td class="empty">Nu am găsit abonamente în perioada aleasă.</td></tr></tbody>`;
}

// ---------------------------------------------------------------- SFATURI
function renderTips() {
  const ins = state.insights;
  if (!ins) return;
  const recs = ins.recommendations;
  $("#tipsBadge").hidden = !recs.length;
  $("#tipsBadge").textContent = recs.length;
  $("#saveMonth").textContent = fmt(ins.potential_saving);
  $("#saveYear").innerHTML = recs.length
    ? `adică <b>${fmt(ins.potential_saving_year)}</b> pe an dacă aplici cele ${recs.length} recomandări de mai jos. Bifează sfaturile pe care le-ai pus deja în practică ✓`
    : "Încarcă tranzacții ca să primești recomandări.";
  const done = store.get("penny-done", {});
  $("#recs").innerHTML = recs.map((r, i) => `
    <article class="rec glass" style="--g:${REC_G[r.priority]};animation-delay:${i * 0.05}s">
      <div class="rec-top"><span class="rec-ico">${r.icon}</span>
        <div><h3>${esc(r.title)}</h3><span class="prio ${r.priority}">${PRIO[r.priority]}</span></div></div>
      <p>${esc(r.text)}</p>
      <div class="rec-save">${r.saving > 0
        ? `<div><small>economie estimată</small><br><b>+${fmt(r.saving)}</b> <small>/ lună</small></div><small>≈ ${fmt(r.saving_year)} / an</small>`
        : `<div><small>obicei sănătos</small><br><b>10% din salariu → economii</b></div>`}</div>
      <ul>${r.tips.map((t, j) => `<li class="${done[`${r.id}:${j}`] ? "done" : ""}" data-k="${r.id}:${j}">${esc(t)}</li>`).join("")}</ul>
    </article>`).join("");
}

async function loadAiTips() {
  const btn = $("#aiTipsBtn"), box = $("#aiTips");
  btn.disabled = true;
  btn.textContent = "🤖 Penny se gândește…";
  box.hidden = false;
  box.innerHTML = `<div class="dots"><span></span><span></span><span></span></div>`;
  try {
    const r = await api("/api/ai-tips", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ month: state.month, currency: state.cur }) });
    box.innerHTML = `<h3>🤖 Penny, special pentru tine ${r.mode === "cache" ? '<small class="muted">(din cache, fără cost)</small>' : ""}</h3>
      <p class="muted">${esc(r.salut)}</p>
      <div class="ai-grid">${r.sfaturi.map((s) => `<div class="ai-card"><span style="font-size:22px">${esc(s.emoji)}</span><b>${esc(s.titlu)}</b>
        <p>${esc(s.detaliu)}</p>${s.economie_lunara > 0 ? `<p class="pos" style="margin-top:6px;font-weight:700">+${fmt(s.economie_lunara)} / lună</p>` : ""}</div>`).join("")}</div>`;
  } catch (e) {
    box.innerHTML = `<h3>🔌 ${esc(e.message)}</h3><p class="muted">Recomandările de mai jos funcționează și fără AI: sunt calculate local din tranzacțiile tale.</p>`;
  } finally {
    btn.disabled = false;
    btn.textContent = "🤖 Sfaturi personalizate cu AI";
    refreshStatus();
  }
}

// ---------------------------------------------------------------- TRANZACȚII
function filtered() {
  const s = state.search.toLowerCase();
  return state.txs.filter((t) =>
    (state.showDup || !t.duplicate_of) &&
    (!state.month || t.date.startsWith(state.month)) &&
    (!state.curFilter || t.currency === state.curFilter) &&
    (!state.srcFilter || t.source === state.srcFilter) &&
    (!state.catFilter || t.category === state.catFilter) &&
    (!state.dirFilter || t.direction === state.dirFilter) &&
    (!s || t.description.toLowerCase().includes(s)));
}

function renderTable() {
  let rows = state.highlight ? state.txs.filter((t) => state.highlight.ids.has(t.id)) : filtered();
  const { key, asc } = state.sort;
  const val = (t) => (key === "conv" ? conv(t) : String(t[key] ?? "").toLowerCase());
  rows.sort((a, b) => (val(a) > val(b) ? 1 : val(a) < val(b) ? -1 : 0) * (asc ? 1 : -1));
  $$("#txTable th[data-sort]").forEach((th) => {
    th.classList.toggle("sorted", th.dataset.sort === key);
    th.classList.toggle("asc", th.dataset.sort === key && asc);
  });
  const catOpts = (sel) => state.categories.map((c) => `<option ${c === sel ? "selected" : ""}>${CAT[c]?.i || ""} ${c}</option>`).join("");
  $("#txTable tbody").innerHTML = rows.map((t) => {
    const income = t.direction === "credit";
    const cls = [income && "income", t.duplicate_of && "dup", state.highlight && "hl"].filter(Boolean).join(" ");
    const sign = income ? "+" : "−";
    const orig = t.currency !== state.cur ? `<small>${sign}${fmt(t.amount, t.currency)} original</small>` : "";
    const note = t.duplicate_of ? "duplicat al plății din CSV · exclus din totaluri" : esc(t.file || "");
    return `<tr class="${cls}" data-id="${t.id}">
      <td class="date">${fmtDate(t.date)}</td>
      <td class="desc"><b>${esc(t.description)}</b><small>${note}</small></td>
      <td><div class="cat-pick"><span class="dot" style="background:${CAT[t.category]?.c}"></span>
        <select class="cat" aria-label="Categorie">${catOpts(t.category)}</select></div><span class="cat-by">${esc(t.category_by || "")}</span></td>
      <td><span class="src">${SRC[t.source]?.i || ""} ${esc(state.sources[t.source] || t.source)}</span></td>
      <td class="num amt">${sign}${fmt(conv(t))}${orig}</td>
      <td><button class="del" title="Șterge">✕</button></td>
    </tr>`;
  }).join("");
  const counted = rows.filter((t) => !t.duplicate_of);
  const spent = counted.filter(isExpense).reduce((a, t) => a + conv(t), 0);
  $("#txCount").textContent = `(${rows.length})`;
  $("#txSum").textContent = rows.length ? `· cheltuieli ${fmt(spent)}` : "";
  $("#txEmpty").hidden = rows.length > 0;
  $("#highlightBar").hidden = !state.highlight;
  if (state.highlight) $("#highlightText").textContent = "🔎 " + state.highlight.label;
}

function goToTx(opts = {}) {
  Object.assign(state, { curFilter: "", srcFilter: "", catFilter: "", dirFilter: "", search: "", highlight: null }, opts);
  $("#curFilter").value = state.curFilter; $("#srcFilter").value = state.srcFilter; $("#catFilter").value = state.catFilter;
  $("#dirFilter").value = state.dirFilter; $("#search").value = state.search;
  setTab("tx");
  renderTable();
}

// ---------------------------------------------------------------- upload
async function uploadFiles(fileList, demo = false) {
  if (!demo && !fileList?.length) return;
  $$("[data-drop]").forEach((d) => d.classList.add("busy"));
  toast(demo ? "✨ Încarc datele demo…" : "⏳ Penny citește fișierele…");
  try {
    let res;
    if (demo) res = await api("/api/demo", { method: "POST" });
    else {
      const fd = new FormData();
      [...fileList].forEach((f) => fd.append("files", f));
      res = await api("/api/upload", { method: "POST", body: fd });
    }
    $("#uploadReports").insertAdjacentHTML("afterbegin", res.reports.map(reportHtml).join(""));
    const added = res.reports.reduce((a, r) => a + r.added, 0);
    const errs = res.reports.filter((r) => r.error).length;
    await setTxs(res.transactions, true);
    toast(added ? `🎉 Am adăugat ${added} tranzacții${errs ? ` · ${errs} fișiere cu probleme (vezi Tranzacții)` : ""}` : "Nicio tranzacție nouă");
    if (added) chatSay(`Gata! Am citit ${added} tranzacții noi. ${state.insights?.headline || ""}`);
  } catch (e) {
    toast(e.message);
  } finally {
    $$("[data-drop]").forEach((d) => d.classList.remove("busy"));
    $("#fileInput").value = ""; $("#fileInputHero").value = "";
    refreshStatus();
  }
}

function reportHtml(r) {
  if (r.error) return `<div class="report err"><b>${esc(r.file)}</b>${esc(r.error)}</div>`;
  const c = r.categorii || {};
  const how = [c.ai && `${c.ai} categorisite de AI`, c.cache && `${c.cache} din cache`, c.reguli && `${c.reguli} prin reguli locale`].filter(Boolean).join(" · ");
  const warn = [...(r.warnings || []), c.ai_error].filter(Boolean);
  return `<div class="report ${warn.length ? "warn" : ""}"><b>✓ ${esc(r.file)}</b>${r.added} tranzacții · ${esc(state.sources[r.source] || "")}
    <small>${esc(how)}</small>${warn.map((w) => `<small>⚠ ${esc(w)}</small>`).join("")}</div>`;
}

// ---------------------------------------------------------------- chat
function openChat(open = true) {
  $("#chatDrawer").setAttribute("aria-hidden", String(!open));
  if (open) setTimeout(() => $("#question").focus(), 150);
}
function chatSay(html, raw = false) {
  const el = document.createElement("div");
  el.className = "msg a";
  if (raw) el.innerHTML = html; else el.textContent = html;
  $("#chatLog").appendChild(el);
  $("#chatLog").scrollTop = $("#chatLog").scrollHeight;
  return el;
}

async function ask(question) {
  question = question.trim();
  if (!question) return;
  openChat(true);
  const log = $("#chatLog");
  log.insertAdjacentHTML("beforeend", `<div class="msg q">${esc(question)}</div>`);
  const pending = chatSay(`<div class="dots"><span></span><span></span><span></span></div>`, true);
  $("#question").value = "";
  $("#askBtn").disabled = true;
  try {
    const r = await api("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, display_currency: state.cur }) });
    const q = r.query || {};
    const mode = { AI: "🤖 interpretat de AI · 🧮 calculat exact", cache: "⚡ din cache (fără cost)", local: "🧮 interpretare locală" }[r.mode] || "";
    const big = r.count && ["suma", "pe_categorii", "lista", "numar", "pe_comercianti"].includes(q.operatie)
      ? `<span class="big">${fmt(r.total, r.currency)}</span>` : "";
    const bd = r.breakdown?.length ? `<ul class="bd">${r.breakdown.slice(0, 8).map((b) => `<li><span>${CAT[b.label]?.i || "•"} ${esc(b.label)}</span><b>${fmt(b.value, r.currency)}</b></li>`).join("")}</ul>` : "";
    const answer = r.breakdown?.length ? r.answer.split(" Defalcare")[0] : r.answer;
    pending.innerHTML = `${big}${esc(answer)}${bd}
      <span class="meta">${q.interpretare ? `„${esc(q.interpretare)}” · ` : ""}${mode}</span>
      ${r.ids?.length ? `<span class="link">🔎 Vezi cele ${r.ids.length} tranzacții</span>` : ""}`;
    const link = pending.querySelector(".link");
    if (link) link.onclick = () => goToTx({ highlight: { ids: new Set(r.ids), label: `Tranzacțiile pentru: „${question}”` } });
  } catch (e) {
    pending.textContent = "Ups: " + e.message;
  } finally {
    $("#askBtn").disabled = false;
    log.scrollTop = log.scrollHeight;
    refreshStatus();
  }
}

// ---------------------------------------------------------------- export & temă
function exportCsv() {
  const rows = filtered();
  const head = ["Data", "Descriere", "Suma", "Moneda", `Suma ${state.cur}`, "Tip", "Categorie", "Sursa", "Duplicat"];
  const lines = rows.map((t) => [t.date, t.description, t.amount.toFixed(2), t.currency, conv(t).toFixed(2),
    t.direction === "credit" ? "incasare" : "cheltuiala", t.category, state.sources[t.source], t.duplicate_of ? "da" : ""]
    .map((v) => `"${String(v).replace(/"/g, '""')}"`).join(";"));
  const blob = new Blob(["﻿" + [head.join(";"), ...lines].join("\n")], { type: "text/csv" });
  const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: `penny_${state.month || "toate"}.csv` });
  a.click();
  URL.revokeObjectURL(a.href);
}

function applyTheme(t) {
  document.documentElement.dataset.theme = t;
  $("#themeBtn").textContent = t === "dark" ? "☀️" : "🌙";
  store.set("penny-theme", t);
}

function setTab(tab) {
  state.tab = tab;
  $$(".tab").forEach((b) => b.classList.toggle("on", b.dataset.tab === tab));
  $$(".view").forEach((v) => v.classList.toggle("on", v.id === `view-${tab}`));
  window.scrollTo({ top: 0, behavior: "smooth" });
  if (tab === "home" && state.txs.length) { renderDaily(); renderDonut(); renderHero(); } // reanimează graficele
}

// ---------------------------------------------------------------- evenimente
$$(".tab").forEach((b) => b.addEventListener("click", () => setTab(b.dataset.tab)));
document.addEventListener("click", (e) => {
  const g = e.target.closest("[data-goto]");
  if (g) setTab(g.dataset.goto);
  if (e.target.closest("[data-open-chat]")) openChat($("#chatDrawer").getAttribute("aria-hidden") === "true");
});
$("#chatClose").addEventListener("click", () => openChat(false));
$("#themeBtn").addEventListener("click", () => applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark"));

$("#displayCur").addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  state.cur = b.dataset.v;
  $$("#displayCur button").forEach((x) => x.classList.toggle("on", x === b));
  state.lastHeadline = "";
  refresh();
});
$("#monthSel").addEventListener("change", (e) => { state.month = e.target.value; state.highlight = null; refresh(); });
const bind = (sel, key, ev = "change") => $(sel).addEventListener(ev, (e) => { state[key] = e.target.value; state.highlight = null; renderTable(); });
bind("#curFilter", "curFilter"); bind("#srcFilter", "srcFilter"); bind("#catFilter", "catFilter");
bind("#dirFilter", "dirFilter"); bind("#search", "search", "input");
$("#showDup").addEventListener("change", (e) => { state.showDup = e.target.checked; renderTable(); });
$("#clearHighlight").addEventListener("click", () => { state.highlight = null; renderTable(); });

$$("#txTable th[data-sort]").forEach((th) => th.addEventListener("click", () => {
  const k = th.dataset.sort;
  state.sort = { key: k, asc: state.sort.key === k ? !state.sort.asc : k !== "conv" && k !== "date" };
  renderTable();
}));
$("#txTable").addEventListener("change", async (e) => {
  if (!e.target.matches("select.cat")) return;
  const id = e.target.closest("tr").dataset.id;
  const category = e.target.value.replace(/^\S+\s/, "");
  try {
    const tx = await api(`/api/transactions/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ category }) });
    Object.assign(state.txs.find((t) => t.id === id), tx);
    await refresh();
    toast("✓ Categorie salvată. Penny o va ține minte");
  } catch (err) { toast(err.message); }
});
$("#txTable").addEventListener("click", async (e) => {
  if (!e.target.matches(".del")) return;
  await api(`/api/transactions/${e.target.closest("tr").dataset.id}`, { method: "DELETE" });
  const { transactions } = await api("/api/transactions");
  await setTxs(transactions);
});
$("#resetBtn").addEventListener("click", async () => {
  if (!confirm("Ștergi toate tranzacțiile încărcate?")) return;
  await api("/api/transactions", { method: "DELETE" });
  $("#uploadReports").innerHTML = "";
  state.highlight = null;
  await setTxs([], true);
  toast("Am șters tot");
});
$("#exportBtn").addEventListener("click", exportCsv);
$("#aiTipsBtn").addEventListener("click", loadAiTips);
$("#recs").addEventListener("click", (e) => {
  const li = e.target.closest("li[data-k]");
  if (!li) return;
  const done = store.get("penny-done", {});
  done[li.dataset.k] = !done[li.dataset.k];
  store.set("penny-done", done);
  li.classList.toggle("done", done[li.dataset.k]);
  if (done[li.dataset.k]) toast("👏 Bravo! Încă un pas spre economii");
});

// upload: input-uri, drag & drop pe zone și oriunde în pagină
$("#fileInput").addEventListener("change", (e) => uploadFiles(e.target.files));
$("#fileInputHero").addEventListener("change", (e) => uploadFiles(e.target.files));
$$("[data-drop]").forEach((d) => {
  // un <label> deschide singur dialogul (are input-ul înăuntru); un <div> are nevoie de ajutor
  if (d.tagName !== "LABEL") d.addEventListener("click", () => $("#fileInput").click());
  d.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") $("#fileInput").click(); });
});
let dragDepth = 0;
addEventListener("dragenter", (e) => { e.preventDefault(); dragDepth++; $("#dropOverlay").hidden = false; });
addEventListener("dragleave", () => { if (--dragDepth <= 0) { dragDepth = 0; $("#dropOverlay").hidden = true; } });
addEventListener("dragover", (e) => e.preventDefault());
addEventListener("drop", (e) => { e.preventDefault(); dragDepth = 0; $("#dropOverlay").hidden = true; uploadFiles(e.dataTransfer.files); });

$("#demoBtn").addEventListener("click", () => uploadFiles(null, true));
$("#welcomeGo").addEventListener("click", closeWelcome);
$("#welcomeDemo").addEventListener("click", () => { closeWelcome(); uploadFiles(null, true); });
$("#welcome").addEventListener("click", (e) => { if (e.target.id === "welcome") closeWelcome(); });
addEventListener("keydown", (e) => {
  if (e.key === "Escape") { closeWelcome(); openChat(false); }
  if (e.key === "/" && !e.target.matches("input, select, textarea")) { e.preventDefault(); openChat(true); }
});

$("#askForm").addEventListener("submit", (e) => { e.preventDefault(); ask($("#question").value); });
$("#suggestions").addEventListener("click", (e) => { if (e.target.matches(".chip")) ask(e.target.textContent); });

$("#manualForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = Object.fromEntries(new FormData(e.target));
  try {
    await api("/api/transactions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    e.target.reset();
    const { transactions } = await api("/api/transactions");
    await setTxs(transactions);
    toast("✓ Tranzacție adăugată");
  } catch (err) { toast(err.message); }
});

init().catch((e) => toast("Nu mă pot conecta la server: " + e.message));
