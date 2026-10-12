// Finn – logica interfeței. Calculele de afișare sunt locale; analizele vin de la /api/insights
// (tot local, gratuit). Textele sunt în română sau engleză (vezi i18n.js).
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
const PRESETS = {
  light: () => Object.fromEntries(Object.keys(CAT).map((c) => [c, 10])),
  smart: () => ({ "Mâncare": 25, "Shopping": 40, "Divertisment": 30, "Călătorii": 20, "Transport": 10, "Utilități": 10, "Altele": 50 }),
  hard: () => Object.fromEntries(Object.keys(CAT).map((c) => [c, ["Locuință", "Sănătate"].includes(c) ? 0 : 50])),
};

const store = {
  get(k, d) { try { const v = localStorage.getItem(k); return v === null ? d : JSON.parse(v); } catch { return d; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch { /* fără stocare: ok */ } },
};

const state = {
  txs: [], insights: null, rates: { RON: 1, EUR: 5.25, USD: 4.4 }, categories: [], aiEnabled: false,
  cur: store.get("finn-cur", "RON"), month: "", tab: "home", curFilter: "", srcFilter: "", catFilter: "", dirFilter: "", search: "",
  showDup: false, sort: { key: "date", asc: false }, highlight: null, lastHeadline: "",
  sim: store.get("finn-sim", {}), goal: store.get("finn-goal", null), goalWasNear: false,
};

// ---------------------------------------------------------------- utilitare
const locale = () => (LANG === "en" ? "en-GB" : "ro-RO");
const conv = (t, to = state.cur) => (t.amount * state.rates[t.currency]) / state.rates[to];
const ronTo = (v, to = state.cur) => v / state.rates[to];
const fmt = (v, cur = state.cur) =>
  `${new Intl.NumberFormat(locale(), { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v)} ${cur}`;
const fmt0 = (v, cur = state.cur) => `${new Intl.NumberFormat(locale(), { maximumFractionDigits: 0 }).format(v)} ${cur}`;
const monthLabel = (ym) => (ym ? `${t("months")[+ym.slice(5)]} ${ym.slice(0, 4)}` : t("period.all"));
const fmtDate = (iso) => {
  const [y, m, d] = iso.split("-");
  return LANG === "en" ? `${+d} ${t("months")[+m].slice(0, 3)} ${y}` : `${d}.${m}.${y}`;
};
const weekdayOf = (iso) => t("weekdays")[(new Date(iso + "T12:00:00").getDay() + 6) % 7];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const isExpense = (x) => x.direction === "debit" && x.category !== "Venituri";
const active = () => state.txs.filter((x) => !x.duplicate_of && (!state.month || x.date.startsWith(state.month)));
const srcName = (k) => t(`src.${k}`);
const STOP = /\b(BUCURESTI|BUC|SRL|SA|SCS|ROMANIA|RO|COM|HELP|AFI|COTROCENI|BANEASA|AMSTERDAM|STOCKHOLM|MUNTENIA|DISCOUNT|PLATA|CARD)\b/g;
const prettyName = (d) => {
  const s = d.toUpperCase().replace(/\d+/g, " ").replace(/[*/]/g, " ").replace(/\.(EU|RO|COM)\b/g, "").replace(STOP, " ").replace(/\s+/g, " ").trim();
  return s.split(" ").filter((w) => w.length > 1).slice(0, 3).map((w) => w[0] + w.slice(1).toLowerCase()).join(" ") || d;
};

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
  if (!r.ok) throw new Error(data.detail || `Error ${r.status}`);
  return data;
}

const greeting = () => {
  const h = new Date().getHours();
  return t(h < 11 ? "greet.morning" : h < 18 ? "greet.day" : "greet.evening");
};

// text „scris” de Finn, cu gura mișcându-se cât timp scrie
function typeText(el, text, speed = 13) {
  clearInterval(el._t);
  el.classList.add("typing");
  el.textContent = "";
  Finn.talk(true);
  let i = 0;
  el._t = setInterval(() => {
    el.textContent = text.slice(0, ++i);
    if (i >= text.length) { clearInterval(el._t); el.classList.remove("typing"); Finn.talk(false); }
  }, speed);
}

// numerele „urcă” animat până la valoarea nouă
function countTo(el, value, format = fmt) {
  const from = el._v ?? 0;
  el._v = value;
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) { el.textContent = format(value); return; }
  const t0 = performance.now(), dur = 900;
  cancelAnimationFrame(el._raf);
  const step = (now) => {
    const p = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - p, 3);
    el.textContent = format(from + (value - from) * e);
    if (p < 1) el._raf = requestAnimationFrame(step);
  };
  el._raf = requestAnimationFrame(step);
}

// ---------------------------------------------------------------- pornire
async function init() {
  applyTheme(store.get("finn-theme", "dark"));
  [["#brandBot", {}], ["#heroBot", { wave: true }], ["#fabBot", {}], ["#chatBot", {}], ["#saveBot", { wave: true }],
    ["#navBot", {}], ["#simBot", {}]].forEach(([s, o]) => ($(s).innerHTML = Finn.svg(o)));
  $$("#displayCur button").forEach((b) => b.classList.toggle("on", b.dataset.v === state.cur));
  setLang(LANG, false);

  try {
    const st = await api("/api/status");
    Object.assign(state, { rates: st.rates, categories: st.categories });
    renderStatus(st);
    const { transactions } = await api("/api/transactions");
    await setTxs(transactions, true);
  } catch (e) {
    toast(t("noServer") + e.message);
  }
  chatSay(t("chat.hello"));
  showWelcome();
  registerPWA();
}

function setLang(lang, rerender = true) {
  LANG = lang;
  store.set("finn-lang", lang);
  applyI18n();
  $$("#langSeg button, .welcome-lang button").forEach((b) => b.classList.toggle("on", (b.dataset.v || b.dataset.lang) === lang));
  $("#suggestions").innerHTML = t("chat.suggestions").map((s) => `<button class="chip" type="button">${esc(s)}</button>`).join("");
  const catOpts = (state.categories.length ? state.categories : Object.keys(CAT))
    .map((c) => `<option value="${c}">${CAT[c]?.i || ""} ${catName(c)}</option>`).join("");
  const cf = $("#catFilter"), mc = $("#manualCat");
  const cv = cf.value, mv = mc.value;
  cf.innerHTML = `<option value="">${t("f.all")}</option>` + catOpts; cf.value = cv;
  mc.innerHTML = `<option value="">${t("tx.auto")}</option>` + catOpts; mc.value = mv;
  if (!state.goal) $("#goalName").value = t("goal.default");
  if (rerender) {
    state.lastHeadline = "";
    fillMonths();
    refresh();
    if (!$("#welcome").hidden) showWelcome();
    api("/api/status").then(renderStatus).catch(() => {});
  }
}

function showWelcome() {
  const has = state.txs.length > 0;
  $("#welcomeBot").innerHTML = Finn.svg({ wave: true });
  $("#welcomeTitle").textContent = t(has ? "welcome.back" : "welcome.new");
  $("#welcomeGo").textContent = t(has ? "welcome.see" : "welcome.go");
  $("#welcomeAlt").textContent = t(has ? "welcome.story" : "welcome.demo");
  $("#welcome").hidden = false;
  typeText($("#welcomeText"), has ? state.insights?.headline || "" : t("welcome.text", { g: greeting() }), 11);
}
const closeWelcome = () => { $("#welcome").hidden = true; Finn.talk(false); };

function renderStatus(st) {
  state.aiEnabled = st.ai_enabled;
  const el = $("#aiStatus");
  el.textContent = st.ai_enabled ? `● ${t("aiOn")} · $${st.usage.cost_usd.toFixed(4)}` : `● ${t("aiOff")}`;
  el.classList.toggle("off", !st.ai_enabled);
  el.title = st.ai_enabled ? `${st.model} · ${st.usage.calls} calls · ${st.usage.input_tokens + st.usage.output_tokens} tokens` : t("aiOffTitle");
}
const refreshStatus = () => api("/api/status").then(renderStatus).catch(() => {});

function fillMonths() {
  const months = [...new Set(state.txs.map((x) => x.date.slice(0, 7)))].sort();
  $("#monthSel").innerHTML = `<option value="">${t("period.all")}</option>` +
    months.map((m) => `<option value="${m}" ${m === state.month ? "selected" : ""}>${shortMonth(m)}</option>`).join("");
}
// pe telefon, luna scurtă („mar. 2026”) ca să încapă în bară
const shortMonth = (m) => (innerWidth < 760 ? `${t("months")[+m.slice(5)].slice(0, 3)}. ${m.slice(0, 4)}` : monthLabel(m));

async function setTxs(txs, pickMonth = false) {
  state.txs = txs;
  const months = [...new Set(txs.map((x) => x.date.slice(0, 7)))];
  if (pickMonth || (state.month && !months.includes(state.month))) {
    // luna implicită = luna cu cele mai multe tranzacții (nu zilele rătăcite de la margine)
    const cnt = {};
    txs.forEach((x) => (cnt[x.date.slice(0, 7)] = (cnt[x.date.slice(0, 7)] || 0) + 1));
    state.month = months.sort((a, b) => cnt[b] - cnt[a])[0] || "";
  }
  fillMonths();
  await refresh();
}

async function refresh() {
  try {
    state.insights = await api(`/api/insights?month=${state.month}&currency=${state.cur}&lang=${LANG}`);
  } catch (e) {
    toast(e.message);
  }
  render();
}

function render() {
  const has = state.txs.length > 0;
  $("#homeEmpty").hidden = has;
  $("#homeData").hidden = !has;
  Finn.setMood(has && state.insights ? state.insights.score_level : "good");
  renderHero();
  if (has && state.insights) {
    renderKpis(); renderDonut(); renderPersona(); renderAlerts(); renderHeatmap(); renderDaily(); renderRule(); renderTopTips();
  }
  renderAnalytics();
  renderSim();
  renderTips();
  renderTable();
}

// ---------------------------------------------------------------- ACASĂ
function renderHero() {
  const ins = state.insights, has = state.txs.length > 0;
  $("#heroHello").textContent = `${greeting()}! 👋 ${t("greet.iam")}`;
  const text = has && ins ? `${ins.headline} ${t("mood")[ins.score_level]}` : t("hero.empty");
  if (text !== state.lastHeadline) { typeText($("#heroBubble"), text); state.lastHeadline = text; }
  $("#heroScore").hidden = !has;
  $("#heroBot").classList.toggle("story-ring", has);
  if (has && ins) Charts.gauge($("#heroScore"), ins.score, `${ins.score_label} · ${t("story.score")}`);
}

function renderKpis() {
  const x = state.insights.totals;
  countTo($("#kSpend"), x.expenses);
  $("#kSpendN").textContent = `${x.count} ${t("kpi.payments")} · ${t("kpi.avg")} ${fmt(x.avg_tx)}`;
  countTo($("#kIncome"), x.income);
  $("#kIncomeN").textContent = `${active().filter((y) => y.direction === "credit").length} ${t("kpi.incomeNote")}`;
  const net = $("#kNet");
  countTo(net, x.net, (v) => (v > 0 ? "+" : "") + fmt(v));
  net.className = x.net >= 0 ? "pos" : "neg";
  const rate = $("#kRate");
  if (x.savings_rate === null) { rate.textContent = "–"; rate.className = ""; }
  else {
    countTo(rate, x.savings_rate, (v) => `${v.toFixed(1)}%`);
    rate.className = x.savings_rate >= 20 ? "pos" : x.savings_rate < 0 ? "neg" : "";
  }
  countTo($("#kSave"), state.insights.potential_saving);
  $("#kSaveY").textContent = `≈ ${fmt(state.insights.potential_saving_year)} ${t("kpi.perYear")}`;
}

function renderDonut() {
  const cats = state.insights.categories;
  const items = cats.map((c) => ({ label: catName(c.category), value: c.total, color: CAT[c.category]?.c, fmt: fmt(c.total), key: c.category }));
  const hover = (i) => $$("#donutLegend .legend-row").forEach((r, j) => r.classList.toggle("hov", j === i));
  Charts.donut($("#donut"), items, {
    center: fmt0(state.insights.totals.expenses), sub: monthLabel(state.month),
    onClick: (it) => goToTx({ catFilter: it.key }), onHover: hover,
  });
  $("#donutLegend").innerHTML = cats.map((c, i) => `
    <div class="legend-row" data-i="${i}" data-cat="${esc(c.category)}">
      <i style="background:${CAT[c.category]?.c}"></i><span>${CAT[c.category]?.i || ""} ${esc(catName(c.category))}</span>
      <b>${fmt(c.total)}</b><small>${c.share.toFixed(0)}%</small></div>`).join("");
  $$("#donutLegend .legend-row").forEach((r) => {
    const sl = () => $(`#donut .slice[data-i="${r.dataset.i}"]`);
    r.addEventListener("mouseenter", () => sl()?.classList.add("hov"));
    r.addEventListener("mouseleave", () => sl()?.classList.remove("hov"));
    r.addEventListener("click", () => goToTx({ catFilter: r.dataset.cat }));
  });
}

function renderPersona() {
  const p = state.insights.personality;
  $("#persona").innerHTML = `<span class="p-kicker">${t("card.personality")}</span>
    <div class="p-emoji">${p.emoji}</div><div><h3 class="display">${esc(p.title)}</h3><p>${esc(p.text)}</p></div>
    <span class="p-cta">▶ ${t("hero.story")}</span>`;
}

function renderAlerts() {
  const icons = { danger: "🚨", warn: "⚠️", info: "ℹ️", success: "🎉" };
  const a = state.insights.alerts;
  $("#alertCount").textContent = a.length ? `${a.length} ${t(a.length === 1 ? "alerts.msg" : "alerts.msgs")}` : "";
  $("#alerts").innerHTML = a.length
    ? a.map((x, i) => `<div class="alert ${x.level}" style="animation-delay:${i * 0.07}s"><span class="ai">${icons[x.level]}</span>
        <div><b>${esc(x.title)}</b><p>${esc(x.text)}</p></div></div>`).join("")
    : `<div class="alert success"><span class="ai">🎉</span><div><b>${t("alerts.none")}</b><p>${t("alerts.noneText")}</p></div></div>`;
}

function dayMap() {
  const by = {};
  active().filter(isExpense).forEach((x) => (by[x.date] ||= []).push(x));
  return by;
}

function renderHeatmap() {
  const by = dayMap();
  const month = state.month || Object.keys(by).sort().pop()?.slice(0, 7);
  if (!month) { $("#heatmap").innerHTML = `<div class="empty">${t("noData")}</div>`; return; }
  const [y, m] = month.split("-").map(Number);
  const first = (new Date(y, m - 1, 1).getDay() + 6) % 7, n = new Date(y, m, 0).getDate();
  const cells = Array.from({ length: first }, () => ({ inMonth: false }));
  for (let d = 1; d <= n; d++) {
    const iso = `${month}-${String(d).padStart(2, "0")}`, list = by[iso] || [];
    cells.push({ inMonth: true, day: d, date: iso, full: `${weekdayOf(iso)}, ${fmtDate(iso)}`, value: list.reduce((a, x) => a + conv(x), 0),
      n: `${list.length} ${t("kpi.payments")}`, ids: list.map((x) => x.id) });
  }
  Charts.heatmap($("#heatmap"), cells, { fmt, weekdays: t("weekdays"),
    onClick: (c) => c.ids.length && goToTx({ highlight: { ids: new Set(c.ids), label: t("tx.dayLabel", { d: fmtDate(c.date) }) } }) });
}

function renderDaily() {
  const by = dayMap();
  let days = Object.keys(by).sort();
  if (state.month && days.length) {
    const [y, m] = state.month.split("-").map(Number);
    days = Array.from({ length: new Date(y, m, 0).getDate() }, (_, i) => `${state.month}-${String(i + 1).padStart(2, "0")}`);
  }
  const data = days.map((d) => {
    const list = by[d] || [];
    const top = [...list].sort((a, b) => conv(b) - conv(a)).slice(0, 3).map((x) => esc(prettyName(x.description))).join("<br>");
    return { date: d, label: String(+d.slice(8)), full: fmtDate(d), value: list.reduce((a, x) => a + conv(x), 0),
      n: list.length, top: top || "—", ids: list.map((x) => x.id) };
  });
  Charts.daily($("#daily"), data, {
    fmt, onClick: (d) => d.ids.length && goToTx({ highlight: { ids: new Set(d.ids), label: t("tx.dayLabel", { d: d.full }) } }),
  });
}

function renderRule() {
  const r = state.insights.rule_50_30_20;
  if (!r.income) { $("#rule").innerHTML = `<div class="empty">${t("rule.noIncome")}</div>`; return; }
  const over = Math.max(r.needs_pct + r.wants_pct + r.savings_pct, 100);
  const w = (p) => `${(p / over) * 100}%`;
  const verdict = (val, ideal, lower) => {
    const ok = lower ? val <= ideal : val >= ideal;
    return `<span class="verdict ${ok ? "pos" : "neg"}">${ok ? t("rule.ok") : lower ? `▲ +${val - ideal} pp ${t("rule.over")}` : `▼ ${ideal - val} pp ${t("rule.under")}`}</span>`;
  };
  $("#rule").innerHTML = `
    <div class="rule-row"><div class="rl"><span>${t("rule.ideal")}</span><span>50 / 30 / 20</span></div>
      <div class="stack"><span style="width:50%;background:var(--g-sky)">${t("rule.needs")} 50%</span><span style="width:30%;background:var(--g-coral)">${t("rule.wants")} 30%</span><span style="width:20%;background:var(--g-mint)">20%</span></div></div>
    <div class="rule-row"><div class="rl"><span>${t("rule.you")} · ${monthLabel(state.month)}</span><span>${r.needs_pct} / ${r.wants_pct} / ${r.savings_pct}</span></div>
      <div class="stack"><span style="width:${w(r.needs_pct)};background:var(--g-sky)">${r.needs_pct}%</span><span style="width:${w(r.wants_pct)};background:var(--g-coral)">${r.wants_pct}%</span><span style="width:${w(r.savings_pct)};background:var(--g-mint)">${r.savings_pct ? r.savings_pct + "%" : ""}</span></div></div>
    <div class="rule-legend">
      <div>🏠 ${t("rule.needs")}<b>${fmt0(r.needs)}</b>${verdict(r.needs_pct, 50, true)}</div>
      <div>🎉 ${t("rule.wants")}<b>${fmt0(r.wants)}</b>${verdict(r.wants_pct, 30, true)}</div>
      <div>🐷 ${t("rule.savings")}<b>${fmt0(r.savings)}</b>${verdict(r.savings_pct, 20, false)}</div>
    </div>`;
}

function renderTopTips() {
  const recs = state.insights.recommendations.filter((r) => r.saving > 0).slice(0, 4);
  $("#topTips").innerHTML = recs.length ? recs.map((r) => `
    <div class="mini-tip" data-goto="tips"><span class="em" style="background:${REC_G[r.priority]}">${r.icon}</span>
      <div><b>${esc(r.title)}</b><small>${esc(r.tips[0])}</small></div><span class="sv">+${fmt0(r.saving)}</span></div>`).join("")
    : `<div class="empty">—</div>`;
}

// ---------------------------------------------------------------- ANALIZE
function renderAnalytics() {
  const ins = state.insights;
  if (!ins) return;
  const cats = ins.categories, hasIncome = ins.totals.income > 0;
  $("#catTable").innerHTML = cats.length ? `
    <thead><tr><th>${t("th.category")}</th><th class="num">${t("th.total")}</th><th class="num">${t("th.share")}</th><th class="num">${t("th.count")}</th>
      <th class="num">${t("th.avg")}</th><th class="num">${t("th.max")}</th>${hasIncome ? `<th>${t("th.budget")}</th><th>${t("th.status")}</th>` : ""}</tr></thead>
    <tbody>${cats.map((c, i) => {
      const col = CAT[c.category]?.c || "#94a3b8";
      const fillCol = c.status === "over" ? "var(--neg)" : c.status === "warn" ? "var(--warn)" : col;
      return `<tr class="clickable" data-cat="${esc(c.category)}">
        <td><span class="cat-cell"><span class="cat-ico" style="background:${col}2e">${CAT[c.category]?.i || ""}</span>${esc(catName(c.category))}</span></td>
        <td class="num"><b>${fmt(c.total)}</b></td><td class="num">${c.share.toFixed(1)}%</td><td class="num">${c.count}</td>
        <td class="num">${fmt(c.avg)}</td><td class="num">${fmt(c.max)}</td>
        ${hasIncome ? `<td><div class="usage" title="${c.budget_pct}% → ${fmt(c.budget)}"><span class="track"><span class="fill"
          style="width:${Math.min(c.usage, 100)}%;background:${fillCol};animation-delay:${i * 0.06}s"></span></span><small>${c.usage}%</small></div></td>
          <td><span class="status ${c.status}">${t("status." + c.status)}</span></td>` : ""}</tr>`;
    }).join("")}</tbody>
    <tfoot><tr><td>${t("th.total")}</td><td class="num">${fmt(ins.totals.expenses)}</td><td class="num">100%</td><td class="num">${ins.totals.count}</td>
      <td class="num">${fmt(ins.totals.avg_tx)}</td><td colspan="${hasIncome ? 3 : 1}"></td></tr></tfoot>`
    : `<tbody><tr><td class="empty">${t("noData")}</td></tr></tbody>`;
  $$("#catTable tr[data-cat]").forEach((r) => r.addEventListener("click", () => goToTx({ catFilter: r.dataset.cat })));

  const rows = active().filter(isExpense);
  const wd = t("weekdays").map((d) => ({ label: d.slice(0, 2), full: d, value: 0, n: 0 }));
  rows.forEach((x) => { const i = (new Date(x.date + "T12:00:00").getDay() + 6) % 7; wd[i].value += conv(x); wd[i].n++; });
  Charts.columns($("#weekday"), wd, { fmt });
  const top = [...wd].sort((a, b) => b.value - a.value)[0];
  $("#weekdayHint").textContent = top?.value ? `${t("weekdayTop")}: ${top.full}` : "";

  const src = {};
  rows.forEach((x) => (src[x.source] = (src[x.source] || 0) + conv(x)));
  const sItems = Object.entries(src).sort((a, b) => b[1] - a[1]).map(([k, v]) => ({ label: srcName(k), value: v, color: SRC[k]?.c, fmt: fmt(v), key: k }));
  const sTot = sItems.reduce((a, i) => a + i.value, 0) || 1;
  Charts.donut($("#sourceDonut"), sItems, { center: String(sItems.length), sub: t("sources"), size: 180, onClick: (it) => goToTx({ srcFilter: it.key }) });
  $("#sourceLegend").innerHTML = sItems.map((s) => `<div class="legend-row" data-src="${s.key}"><i style="background:${s.color}"></i>
    <span>${SRC[s.key]?.i || ""} ${esc(s.label)}</span><b>${s.fmt}</b><small>${((s.value / sTot) * 100).toFixed(0)}%</small></div>`).join("");
  $$("#sourceLegend .legend-row").forEach((r) => r.addEventListener("click", () => goToTx({ srcFilter: r.dataset.src })));

  const mMax = Math.max(...ins.merchants.map((m) => m.total), 1);
  $("#merchTable").innerHTML = ins.merchants.length ? `
    <thead><tr><th>#</th><th>${t("th.merchant")}</th><th class="num">${t("th.visits")}</th><th class="num">${t("th.total")}</th><th class="num">${t("th.avg")}</th><th>${t("th.last")}</th></tr></thead>
    <tbody>${ins.merchants.map((m, i) => `<tr class="clickable" data-q="${esc(m.name.split(" ")[0])}">
      <td>${["🥇", "🥈", "🥉"][i] || i + 1}</td>
      <td><b>${esc(m.name)}</b><div class="mini-bar" style="width:${(m.total / mMax) * 100}%;background:${CAT[m.category]?.c};animation-delay:${i * 0.05}s"></div>
        <small class="muted">${CAT[m.category]?.i || ""} ${esc(catName(m.category))}</small></td>
      <td class="num">${m.visits}×</td><td class="num"><b>${fmt(m.total)}</b></td><td class="num">${fmt(m.avg)}</td>
      <td class="muted">${fmtDate(m.last)}</td></tr>`).join("")}</tbody>` : `<tbody><tr><td class="empty">—</td></tr></tbody>`;
  $$("#merchTable tr[data-q]").forEach((r) => r.addEventListener("click", () => goToTx({ search: r.dataset.q })));

  const subs = ins.subscriptions, yr = subs.reduce((a, s) => a + s.yearly, 0);
  $("#subsHint").textContent = subs.length ? `≈ ${fmt(yr)} / ${t("th.yearly").toLowerCase()}` : "";
  $("#subsTable").innerHTML = subs.length ? `
    <thead><tr><th>${t("th.service")}</th><th class="num">${t("th.monthly")}</th><th class="num">${t("th.yearly")}</th><th>${t("th.tip")}</th></tr></thead>
    <tbody>${subs.map((s) => `<tr><td><span class="cat-cell"><span class="cat-ico" style="background:${CAT[s.category]?.c}2e">${CAT[s.category]?.i}</span>${esc(s.name)}</span></td>
      <td class="num">${fmt(s.monthly)}</td><td class="num"><b>${fmt(s.yearly)}</b></td><td class="sub-tip">${esc(s.tip)}</td></tr>`).join("")}</tbody>
    <tfoot><tr><td>${t("th.total")}</td><td class="num">${fmt(yr / 12)}</td><td class="num">${fmt(yr)}</td><td></td></tr></tfoot>`
    : `<tbody><tr><td class="empty">${t("noSubs")}</td></tr></tbody>`;
}

// ---------------------------------------------------------------- SIMULATOR
function renderSim() {
  const cats = (state.insights?.categories || []);
  $("#sliders").innerHTML = cats.length ? cats.map((c) => {
    const p = state.sim[c.category] || 0, col = CAT[c.category]?.c;
    return `<div class="slider" data-cat="${esc(c.category)}">
      <span class="si" style="background:${col}2e">${CAT[c.category]?.i}</span>
      <div><div class="sn"><span>${esc(catName(c.category))}</span><small>${fmt0(c.total)} · −<b class="pp">${p}</b>%</small></div>
        <input type="range" min="0" max="100" step="5" value="${p}" style="--c:${col};--p:${p}%" aria-label="${esc(catName(c.category))}"></div>
      <div class="sv"><b class="sm">+${fmt0((c.total * p) / 100)}</b><small>${t("sim.perMonth")}</small></div></div>`;
  }).join("") : `<div class="empty">${t("tips.empty")}</div>`;
  if (!$("#goalAmount").value || $("#goalAmount")._cur !== state.cur) {
    const g = state.goal;
    $("#goalAmount").value = Math.round(ronTo(g ? g.ron : 3500));
    $("#goalAmount")._cur = state.cur;
    if (g) $("#goalName").value = g.name;
  }
  updateSim();
}

function updateSim() {
  const cats = state.insights?.categories || [];
  let month = 0;
  const parts = [];
  cats.forEach((c) => {
    const v = (c.total * (state.sim[c.category] || 0)) / 100;
    month += v;
    if (v > 0) parts.push([c.category, v]);
  });
  countTo($("#simMonth"), month, fmt0);
  $("#simYear").textContent = fmt0(month * 12);
  $("#sim5").textContent = fmt0(month * 60);
  $("#simBars").innerHTML = parts.map(([c, v]) => `<span style="width:${(v / month) * 100}%;background:${CAT[c].c}"></span>`).join("");
  $$("#simPresets .chip").forEach((b) => b.classList.remove("on"));

  // obiectivul
  const amount = parseFloat(String($("#goalAmount").value).replace(",", ".")) || 0;
  const months = month > 0 && amount > 0 ? Math.ceil(amount / month) : null;
  const frac = months ? Math.min(1, 12 / months) : 0;
  const R = 62, L = 2 * Math.PI * R;
  $("#goalRing").innerHTML = `<svg viewBox="0 0 150 150">
    <defs><linearGradient id="gr" x1="0" x2="1"><stop offset="0" stop-color="#22d3ee"/><stop offset=".5" stop-color="#8b5cf6"/><stop offset="1" stop-color="#ec4899"/></linearGradient></defs>
    <circle cx="75" cy="75" r="${R}" fill="none" stroke="var(--glass-strong)" stroke-width="13"/>
    <circle cx="75" cy="75" r="${R}" fill="none" stroke="url(#gr)" stroke-width="13" stroke-linecap="round" transform="rotate(-90 75 75)"
      stroke-dasharray="${L}" stroke-dashoffset="${L * (1 - frac)}" style="transition: stroke-dashoffset .6s cubic-bezier(.2,.8,.2,1)"/>
    <text x="75" y="76" text-anchor="middle" class="goal-num">${months ?? "∞"}</text>
    <text x="75" y="96" text-anchor="middle" class="goal-sub">${months ? t("sim.months") : ""}</text></svg>`;
  const near = !!months && months <= 12;
  if (near && !state.goalWasNear && state.tab === "sim") { confetti(); toast(t("goal.done")); Finn.wave($("#simBot")); }
  state.goalWasNear = near;

  // ce-ți permiți cu economia de un an
  const year = month * 12;
  const goods = t("goods").map(([e, n, ron]) => ({ e, n, k: Math.floor(year / ronTo(ron)) })).filter((g) => g.k >= 1);
  $("#afford").innerHTML = goods.length
    ? goods.slice(-4).reverse().map((g, i) => `<div style="animation-delay:${i * 0.06}s"><span class="ae">${g.e}</span><b>×${g.k}</b><small>${esc(g.n)}</small></div>`).join("")
    : `<div class="empty" style="grid-column:1/-1">${t("sim.never")}</div>`;
}

// ---------------------------------------------------------------- SFATURI
function renderTips() {
  const ins = state.insights;
  if (!ins) return;
  const recs = ins.recommendations;
  $$(".badge-dot").forEach((b) => { b.hidden = !recs.length; b.textContent = recs.length; });
  countTo($("#saveMonth"), ins.potential_saving);
  $("#saveYear").innerHTML = recs.length ? t("tips.yearText", { y: fmt(ins.potential_saving_year), n: recs.length }) : t("tips.empty");
  const done = store.get("finn-done", {});
  $("#recs").innerHTML = recs.map((r, i) => {
    const d = r.tips.filter((_, j) => done[`${r.id}:${j}`]).length;
    return `<article class="rec card glass spot" style="--g:${REC_G[r.priority]};animation-delay:${i * 0.05}s">
      <div class="rec-top"><span class="rec-ico">${r.icon}</span><div><h3>${esc(r.title)}</h3><span class="prio ${r.priority}">${t("prio." + r.priority)}</span></div></div>
      <p>${esc(r.text)}</p>
      <div class="rec-save">${r.saving > 0
        ? `<div><small>${t("tips.estimated")}</small><br><b>+${fmt(r.saving)}</b> <small>${t("tips.perMonth")}</small></div><small>≈ ${fmt0(r.saving_year)} / ${t("th.yearly").toLowerCase()}</small>`
        : `<div><small>${t("tips.habit")}</small><br><b>${t("tips.habitText")}</b></div>`}</div>
      <div class="rec-progress"><span style="width:${(d / r.tips.length) * 100}%"></span></div>
      <ul>${r.tips.map((x, j) => `<li class="${done[`${r.id}:${j}`] ? "done" : ""}" data-k="${r.id}:${j}">${esc(x)}</li>`).join("")}</ul>
    </article>`;
  }).join("");
}

async function loadAiTips() {
  const btn = $("#aiTipsBtn"), box = $("#aiTips");
  btn.disabled = true;
  box.hidden = false;
  box.innerHTML = `<div class="dots"><span></span><span></span><span></span></div> ${t("tips.thinking")}`;
  Finn.talk(true);
  try {
    const r = await api("/api/ai-tips", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ month: state.month, currency: state.cur, lang: LANG }) });
    box.innerHTML = `<h3>🤖 ${t("tips.aiTitle")} ${r.mode === "cache" ? `<small class="muted">${t("tips.cached")}</small>` : ""}</h3>
      <p class="muted">${esc(r.salut)}</p>
      <div class="ai-grid">${r.sfaturi.map((s) => `<div class="ai-card"><span style="font-size:24px">${esc(s.emoji)}</span><b>${esc(s.titlu)}</b>
        <p>${esc(s.detaliu)}</p>${s.economie_lunara > 0 ? `<p class="pos" style="margin-top:6px;font-weight:800">+${fmt(s.economie_lunara)} ${t("tips.perMonth")}</p>` : ""}</div>`).join("")}</div>`;
  } catch (e) {
    box.innerHTML = `<h3>🔌 ${esc(e.message)}</h3><p class="muted">${t("tips.aiFallback")}</p>`;
  } finally {
    btn.disabled = false;
    Finn.talk(false);
    refreshStatus();
  }
}

// ---------------------------------------------------------------- TRANZACȚII
function filtered() {
  const s = state.search.toLowerCase();
  return state.txs.filter((x) =>
    (state.showDup || !x.duplicate_of) && (!state.month || x.date.startsWith(state.month)) &&
    (!state.curFilter || x.currency === state.curFilter) && (!state.srcFilter || x.source === state.srcFilter) &&
    (!state.catFilter || x.category === state.catFilter) && (!state.dirFilter || x.direction === state.dirFilter) &&
    (!s || x.description.toLowerCase().includes(s)));
}

function renderTable() {
  const rows = state.highlight ? state.txs.filter((x) => state.highlight.ids.has(x.id)) : filtered();
  const { key, asc } = state.sort;
  const val = (x) => (key === "conv" ? conv(x) : String(x[key] ?? "").toLowerCase());
  rows.sort((a, b) => (val(a) > val(b) ? 1 : val(a) < val(b) ? -1 : 0) * (asc ? 1 : -1));
  $$("#txTable th[data-sort]").forEach((th) => {
    th.classList.toggle("sorted", th.dataset.sort === key);
    th.classList.toggle("asc", th.dataset.sort === key && asc);
  });
  const cats = state.categories.length ? state.categories : Object.keys(CAT);
  const catOpts = (sel) => cats.map((c) => `<option value="${c}" ${c === sel ? "selected" : ""}>${CAT[c]?.i || ""} ${catName(c)}</option>`).join("");
  $("#txTable tbody").innerHTML = rows.map((x) => {
    const income = x.direction === "credit";
    const cls = [income && "income", x.duplicate_of && "dup", state.highlight && "hl"].filter(Boolean).join(" ");
    const sign = income ? "+" : "−";
    const orig = x.currency !== state.cur ? `<small>${sign}${fmt(x.amount, x.currency)} ${t("tx.original")}</small>` : "";
    const note = x.duplicate_of ? t("tx.dupNote") : esc(x.file || "");
    return `<tr class="${cls}" data-id="${x.id}">
      <td class="date">${fmtDate(x.date)}</td>
      <td class="desc"><b>${esc(x.description)}</b><small>${note}</small></td>
      <td class="catc"><div class="cat-pick"><span class="dot" style="background:${CAT[x.category]?.c}"></span>
        <select class="cat" aria-label="${t("th.category")}">${catOpts(x.category)}</select></div><span class="cat-by">${esc(x.category_by || "")}</span></td>
      <td class="srcc"><span class="src">${SRC[x.source]?.i || ""} ${esc(srcName(x.source))}</span></td>
      <td class="num amt">${sign}${fmt(conv(x))}${orig}</td>
      <td class="delc"><button class="del" title="${t("tx.delete")}">✕</button></td>
    </tr>`;
  }).join("");
  const spent = rows.filter((x) => !x.duplicate_of && isExpense(x)).reduce((a, x) => a + conv(x), 0);
  $("#txCount").textContent = `(${rows.length})`;
  $("#txSum").textContent = rows.length ? `· ${t("tx.spent")} ${fmt(spent)}` : "";
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
  toast(t(demo ? "up.demo" : "up.reading"));
  Finn.talk(true);
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
    toast(added ? `${t("up.added", { n: added })}${errs ? " · " + t("up.issues", { n: errs }) : ""}` : t("up.none"));
    if (added) {
      chatSay(`${t("chat.afterUpload", { n: added })} ${state.insights?.headline || ""}`);
      Finn.wave($("#heroBot"));
      confetti(90);
    }
  } catch (e) {
    toast(e.message);
  } finally {
    $$("[data-drop]").forEach((d) => d.classList.remove("busy"));
    $("#fileInput").value = ""; $("#fileInputHero").value = "";
    Finn.talk(false);
    refreshStatus();
  }
}

function reportHtml(r) {
  if (r.error) return `<div class="report err"><b>${esc(r.file)}</b>${esc(r.code ? t("err." + r.code) : r.error)}</div>`;
  const c = r.categorii || {};
  const how = [c.ai && `${c.ai} ${t("up.byAi")}`, c.cache && `${c.cache} ${t("up.cache")}`, c.reguli && `${c.reguli} ${t("up.rules")}`].filter(Boolean).join(" · ");
  const warn = [...(r.warnings || []), c.ai_error && (state.aiEnabled ? c.ai_error : t("warn.ai_off"))].filter(Boolean);
  return `<div class="report ${warn.length ? "warn" : ""}"><b>✓ ${esc(r.file)}</b>${r.added} ${t("up.tx")} · ${esc(srcName(r.source))}
    <small>${esc(how)}</small>${warn.map((w) => `<small>⚠ ${esc(w)}</small>`).join("")}</div>`;
}

// ---------------------------------------------------------------- chat + voce
function openChat(open = true) {
  $("#chatDrawer").setAttribute("aria-hidden", String(!open));
  $("#sheetBackdrop").classList.toggle("on", open);
  if (open && matchMedia("(hover: hover)").matches) setTimeout(() => $("#question").focus(), 200);
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
  Finn.talk(true);
  try {
    const r = await api("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, display_currency: state.cur, lang: LANG }) });
    const q = r.query || {};
    const mode = { AI: t("chat.modeAI"), cache: t("chat.modeCache"), local: t("chat.modeLocal") }[r.mode] || "";
    const big = r.count && ["suma", "pe_categorii", "lista", "numar", "pe_comercianti"].includes(q.operatie)
      ? `<span class="big">${fmt(r.total, r.currency)}</span>` : "";
    const bd = r.breakdown?.length ? `<ul class="bd">${r.breakdown.slice(0, 8).map((b) =>
      `<li><span>${CAT[b.key || b.label]?.i || "•"} ${esc(b.label)}</span><b>${fmt(b.value, r.currency)}</b></li>`).join("")}</ul>` : "";
    const answer = r.breakdown?.length ? r.answer.split(/ (Defalcare|Breakdown)/)[0] : r.answer;
    pending.innerHTML = `${big}${esc(answer)}${bd}
      <span class="meta">${q.interpretare ? `„${esc(q.interpretare)}” · ` : ""}${mode}</span>
      ${r.ids?.length ? `<span class="link">${t("chat.see", { n: r.ids.length })}</span>` : ""}`;
    const link = pending.querySelector(".link");
    if (link) link.onclick = () => { openChat(false); goToTx({ highlight: { ids: new Set(r.ids), label: t("tx.forQ", { q: question }) } }); };
  } catch (e) {
    pending.textContent = t("chat.oops") + e.message;
  } finally {
    $("#askBtn").disabled = false;
    Finn.talk(false);
    log.scrollTop = log.scrollHeight;
    refreshStatus();
  }
}

const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
let recog = null;
function toggleVoice() {
  if (!SR) return toast(t("chat.noVoice"));
  if (recog) { recog.stop(); return; }
  recog = new SR();
  recog.lang = LANG === "en" ? "en-US" : "ro-RO";
  recog.interimResults = true;
  $("#micBtn").classList.add("rec");
  $("#question").placeholder = t("chat.listening");
  recog.onresult = (e) => {
    const txt = [...e.results].map((r) => r[0].transcript).join("");
    $("#question").value = txt;
    if (e.results[e.results.length - 1].isFinal) ask(txt);
  };
  recog.onend = recog.onerror = () => { recog = null; $("#micBtn").classList.remove("rec"); $("#question").placeholder = t("chat.ph"); };
  recog.start();
}

// ---------------------------------------------------------------- povestea lunii
function openStory() {
  const ins = state.insights;
  if (!state.txs.length || !ins) return toast(t("story.noData"));
  closeWelcome();
  const exp = active().filter(isExpense);
  const big = [...exp].sort((a, b) => conv(b) - conv(a)).find((x) => x.category !== "Locuință") || exp[0];
  const days = {};
  exp.forEach((x) => (days[x.date] = (days[x.date] || 0) + conv(x)));
  const busiest = Object.entries(days).sort((a, b) => b[1] - a[1])[0];
  const fav = [...ins.merchants].sort((a, b) => b.visits - a.visits || b.total - a.total)[0];
  const top = ins.categories[0];
  const saveN = ins.recommendations.filter((r) => r.saving > 0).length;
  const data = {
    month: monthLabel(state.month), spent: ins.totals.expenses, count: ins.totals.count,
    topCat: top && { name: catName(top.category), icon: CAT[top.category]?.i, color: CAT[top.category]?.c, share: Math.round(top.share), value: fmt(top.total) },
    biggest: big && { name: prettyName(big.description), amount: conv(big), date: `${weekdayOf(big.date)}, ${fmtDate(big.date)}` },
    busiest: busiest && { weekday: weekdayOf(busiest[0]), date: fmtDate(busiest[0]), amount: busiest[1] },
    topMerchant: fav && { name: fav.name, visits: fav.visits, total: fmt(fav.total) },
    subsYear: ins.subscriptions.reduce((a, s) => a + s.yearly, 0),
    saveYear: ins.potential_saving_year, saveN,
    persona: ins.personality, score: ins.score, scoreLabel: ins.score_label,
  };
  data.summary = `Finn · ${data.month}\n${t("story.spent")}: ${fmt(data.spent)}\n` +
    (data.topCat ? `${t("story.topCat")}: ${data.topCat.icon} ${data.topCat.name} (${data.topCat.share}%)\n` : "") +
    `${t("story.save")}: ${fmt(data.saveYear)} ${t("sim.perYear")}\n${ins.personality.emoji} ${ins.personality.title} · ${t("story.score")} ${ins.score}/100`;
  $("#heroBot").classList.add("seen");
  Story.open(data);
}

// ---------------------------------------------------------------- export, temă, taburi, PWA
function exportCsv() {
  const rows = filtered();
  const head = [t("th.date"), t("th.desc"), t("th.amount"), t("tx.currency"), `${t("th.amount")} ${state.cur}`, t("tx.type"), t("th.category"), t("th.source"), "Dup"];
  const lines = rows.map((x) => [x.date, x.description, x.amount.toFixed(2), x.currency, conv(x).toFixed(2),
    t(x.direction === "credit" ? "tx.incomeOne" : "tx.expense"), catName(x.category), srcName(x.source), x.duplicate_of ? "x" : ""]
    .map((v) => `"${String(v).replace(/"/g, '""')}"`).join(";"));
  const blob = new Blob(["﻿" + [head.join(";"), ...lines].join("\n")], { type: "text/csv" });
  const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: `finn_${state.month || "all"}.csv` });
  a.click();
  URL.revokeObjectURL(a.href);
}

function applyTheme(th) {
  document.documentElement.dataset.theme = th;
  $("#themeBtn").textContent = th === "dark" ? "☀️" : "🌙";
  $('meta[name="theme-color"]').content = th === "dark" ? "#07061a" : "#f5f3ff";
  store.set("finn-theme", th);
}

function setTab(tab) {
  state.tab = tab;
  $$(".tab, .bottom-nav button[data-tab]").forEach((b) => b.classList.toggle("on", b.dataset.tab === tab));
  $$(".view").forEach((v) => v.classList.toggle("on", v.id === `view-${tab}`));
  window.scrollTo({ top: 0, behavior: "smooth" });
  if (tab === "home" && state.txs.length && state.insights) { renderDaily(); renderDonut(); renderHeatmap(); }
  if (tab === "sim") updateSim();
}

let installEvt = null;
function registerPWA() {
  if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
  addEventListener("beforeinstallprompt", (e) => {
    e.preventDefault();
    installEvt = e;
    if ($("#installBtn")) return;
    const b = Object.assign(document.createElement("button"), { id: "installBtn", className: "icon-btn", textContent: "📲", title: t("install") });
    b.onclick = async () => { installEvt?.prompt(); const r = await installEvt?.userChoice; if (r?.outcome === "accepted") { toast(t("installed")); b.remove(); } };
    $(".controls").insertBefore(b, $("#themeBtn"));
  });
}

// spotlight + înclinare 3D pe carduri (doar cu mouse)
const finePointer = matchMedia("(hover: hover) and (pointer: fine)").matches;
document.addEventListener("pointermove", (e) => {
  const card = e.target.closest?.(".spot");
  if (!card) return;
  const r = card.getBoundingClientRect();
  card.style.setProperty("--mx", `${e.clientX - r.left}px`);
  card.style.setProperty("--my", `${e.clientY - r.top}px`);
  if (finePointer && card.classList.contains("tilt")) {
    const x = (e.clientX - r.left) / r.width - 0.5, y = (e.clientY - r.top) / r.height - 0.5;
    card.style.transform = `perspective(700px) rotateX(${-y * 7}deg) rotateY(${x * 9}deg) translateY(-2px)`;
  }
}, { passive: true });
document.addEventListener("pointerout", (e) => {
  const card = e.target.closest?.(".tilt");
  if (card && !card.contains(e.relatedTarget)) card.style.transform = "";
});

// ---------------------------------------------------------------- evenimente
document.addEventListener("click", (e) => {
  const tab = e.target.closest("[data-tab]");
  if (tab) setTab(tab.dataset.tab);
  const g = e.target.closest("[data-goto]");
  if (g) setTab(g.dataset.goto);
  if (e.target.closest("[data-open-chat]")) openChat($("#chatDrawer").getAttribute("aria-hidden") === "true");
  if (e.target.closest("[data-story], #persona")) openStory();
  if (e.target.closest("#heroBot")) state.txs.length ? openStory() : Finn.wave($("#heroBot"));
  if (e.target.closest("[data-demo]")) uploadFiles(null, true);
});
$("#chatClose").addEventListener("click", () => openChat(false));
$("#sheetBackdrop").addEventListener("click", () => openChat(false));
$("#themeBtn").addEventListener("click", () => applyTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark"));
$("#langSeg").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b && b.dataset.v !== LANG) setLang(b.dataset.v); });
$(".welcome-lang").addEventListener("click", (e) => { const b = e.target.closest("button"); if (b && b.dataset.lang !== LANG) setLang(b.dataset.lang); });

$("#displayCur").addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  state.cur = b.dataset.v;
  store.set("finn-cur", state.cur);
  $$("#displayCur button").forEach((x) => x.classList.toggle("on", x === b));
  state.lastHeadline = "";
  refresh();
});
$("#monthSel").addEventListener("change", (e) => { state.month = e.target.value; state.highlight = null; state.lastHeadline = ""; refresh(); });
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
  try {
    const tx = await api(`/api/transactions/${id}`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ category: e.target.value }) });
    Object.assign(state.txs.find((x) => x.id === id), tx);
    await refresh();
    toast(t("tx.catSaved"));
  } catch (err) { toast(err.message); }
});
$("#txTable").addEventListener("click", async (e) => {
  if (!e.target.matches(".del")) return;
  await api(`/api/transactions/${e.target.closest("tr").dataset.id}`, { method: "DELETE" });
  const { transactions } = await api("/api/transactions");
  await setTxs(transactions);
});
$("#resetBtn").addEventListener("click", async () => {
  if (!confirm(t("tx.confirmReset"))) return;
  await api("/api/transactions", { method: "DELETE" });
  $("#uploadReports").innerHTML = "";
  state.highlight = null;
  await setTxs([], true);
  toast(t("tx.cleared"));
});
$("#exportBtn").addEventListener("click", exportCsv);
$("#aiTipsBtn").addEventListener("click", loadAiTips);
$("#recs").addEventListener("click", (e) => {
  const li = e.target.closest("li[data-k]");
  if (!li) return;
  const done = store.get("finn-done", {});
  done[li.dataset.k] = !done[li.dataset.k];
  store.set("finn-done", done);
  li.classList.toggle("done", done[li.dataset.k]);
  const card = li.closest(".rec"), all = card.querySelectorAll("li"), n = card.querySelectorAll("li.done").length;
  card.querySelector(".rec-progress span").style.width = `${(n / all.length) * 100}%`;
  if (done[li.dataset.k]) { toast(t("tips.bravo")); if (n === all.length) confetti(80); }
});

// simulator
$("#sliders").addEventListener("input", (e) => {
  if (e.target.type !== "range") return;
  const row = e.target.closest(".slider"), c = row.dataset.cat, p = +e.target.value;
  state.sim[c] = p;
  store.set("finn-sim", state.sim);
  e.target.style.setProperty("--p", p + "%");
  row.querySelector(".pp").textContent = p;
  const total = state.insights.categories.find((x) => x.category === c)?.total || 0;
  row.querySelector(".sm").textContent = "+" + fmt0((total * p) / 100);
  updateSim();
});
$("#simPresets").addEventListener("click", (e) => {
  const b = e.target.closest("[data-preset]");
  if (!b) return;
  state.sim = PRESETS[b.dataset.preset]();
  store.set("finn-sim", state.sim);
  renderSim();
  b.classList.add("on");
});
$("#simReset").addEventListener("click", () => { state.sim = {}; store.set("finn-sim", {}); renderSim(); });
["#goalAmount", "#goalName"].forEach((s) => $(s).addEventListener("input", () => {
  const amount = parseFloat(String($("#goalAmount").value).replace(",", ".")) || 0;
  state.goal = { name: $("#goalName").value, ron: amount * state.rates[state.cur] };
  store.set("finn-goal", state.goal);
  updateSim();
}));

// upload: input-uri, drag & drop oriunde în pagină
$("#fileInput").addEventListener("change", (e) => uploadFiles(e.target.files));
$("#fileInputHero").addEventListener("change", (e) => uploadFiles(e.target.files));
$$("[data-drop]").forEach((d) => {
  // un <label> deschide singur dialogul (are input-ul înăuntru); un <div> are nevoie de ajutor
  if (d.tagName !== "LABEL") d.addEventListener("click", () => $("#fileInput").click());
  d.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") $("#fileInput").click(); });
});
let dragDepth = 0;
addEventListener("dragenter", (e) => { if (!e.dataTransfer?.types?.includes("Files")) return; e.preventDefault(); dragDepth++; $("#dropOverlay").hidden = false; });
addEventListener("dragleave", () => { if (--dragDepth <= 0) { dragDepth = 0; $("#dropOverlay").hidden = true; } });
addEventListener("dragover", (e) => e.preventDefault());
addEventListener("drop", (e) => { e.preventDefault(); dragDepth = 0; $("#dropOverlay").hidden = true; if (e.dataTransfer.files.length) uploadFiles(e.dataTransfer.files); });

$("#welcomeGo").addEventListener("click", closeWelcome);
$("#welcomeAlt").addEventListener("click", () => { if (state.txs.length) openStory(); else { closeWelcome(); uploadFiles(null, true); } });
$("#welcome").addEventListener("click", (e) => { if (e.target.id === "welcome") closeWelcome(); });
addEventListener("keydown", (e) => {
  if (Story.isOpen()) return;
  if (e.key === "Escape") { closeWelcome(); openChat(false); }
  if (e.key === "/" && !e.target.matches("input, select, textarea")) { e.preventDefault(); openChat(true); }
});

$("#askForm").addEventListener("submit", (e) => { e.preventDefault(); ask($("#question").value); });
$("#suggestions").addEventListener("click", (e) => { if (e.target.matches(".chip")) ask(e.target.textContent); });
$("#micBtn").addEventListener("click", toggleVoice);
if (!SR) $("#micBtn").hidden = true;

$("#manualForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = Object.fromEntries(new FormData(e.target));
  try {
    await api("/api/transactions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    e.target.reset();
    const { transactions } = await api("/api/transactions");
    await setTxs(transactions);
    toast(t("tx.added"));
  } catch (err) { toast(err.message); }
});

init();
