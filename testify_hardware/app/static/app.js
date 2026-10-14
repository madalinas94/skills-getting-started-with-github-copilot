"use strict";

/* ================= Utilitare ================= */

const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];

const MONTHS = ["Ianuarie", "Februarie", "Martie", "Aprilie", "Mai", "Iunie", "Iulie",
  "August", "Septembrie", "Octombrie", "Noiembrie", "Decembrie"];

function esc(value) {
  return String(value ?? "").replace(/[&<>"']/g, (c) => (
    { "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
}

const numberFmt = new Intl.NumberFormat("ro-RO", { maximumFractionDigits: 0 });
const numberFmt2 = new Intl.NumberFormat("ro-RO", { minimumFractionDigits: 2, maximumFractionDigits: 2 });
const lei = (v, decimals = false) => `${(decimals ? numberFmt2 : numberFmt).format(v || 0)} lei`;
const pct = (v) => `${new Intl.NumberFormat("ro-RO", { maximumFractionDigits: 1 }).format(v || 0)}%`;

function todayISO() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
}
const currentMonth = () => todayISO().slice(0, 7);
function shiftMonth(ym, delta) {
  const [y, m] = ym.split("-").map(Number);
  const idx = y * 12 + (m - 1) + delta;
  return `${Math.floor(idx / 12)}-${String((idx % 12) + 1).padStart(2, "0")}`;
}
function monthLabel(ym) {
  const [y, m] = ym.split("-").map(Number);
  return `${MONTHS[m - 1]} ${y}`;
}
function formatDate(iso) {
  if (!iso) return "—";
  const [y, m, d] = iso.split("-");
  return `${d}.${m}.${y}`;
}
const initials = (name) => name.split(/\s+/).filter(Boolean).slice(0, 2).map((p) => p[0].toUpperCase()).join("");
const GRADIENTS = [
  ["#22d3ee", "#3b82f6"], ["#fde68a", "#f59e0b"], ["#a78bfa", "#6366f1"],
  ["#34d399", "#059669"], ["#f9a8d4", "#ec4899"], ["#fdba74", "#f97316"],
];
function gradientFor(name) {
  let h = 0;
  for (const ch of name) h = (h * 31 + ch.charCodeAt(0)) >>> 0;
  const [a, b] = GRADIENTS[h % GRADIENTS.length];
  return `linear-gradient(135deg, ${a}, ${b})`;
}

/* ================= Iconițe ================= */

const ICONS = {
  dashboard: '<path d="M3 13h8V3H3zM13 21h8V11h-8zM3 21h8v-6H3zM13 3v6h8V3z"/>',
  sales: '<path d="M3 3h2l2.4 12.2a2 2 0 002 1.8h8.9a2 2 0 002-1.6L22 7H6"/><circle cx="9" cy="21" r="1"/><circle cx="18" cy="21" r="1"/>',
  expenses: '<rect x="2" y="5" width="20" height="14" rx="2"/><path d="M2 10h20M6 15h4"/>',
  team: '<path d="M17 21v-2a4 4 0 00-4-4H5a4 4 0 00-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M23 21v-2a4 4 0 00-3-3.9M16 3.1a4 4 0 010 7.8"/>',
  taxes: '<path d="M4 2v20l3-2 3 2 3-2 3 2 3-2 1 .7V2l-1 .7-3-2-3 2-3-2-3 2-3-2z"/><path d="M9 8l6 6M9.5 14h0M14.5 8h0"/>',
  reports: '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6M8 13h8M8 17h5"/>',
  settings: '<circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 00.3 1.8l.1.1a2 2 0 11-2.8 2.8l-.1-.1a1.7 1.7 0 00-1.8-.3 1.7 1.7 0 00-1 1.5V21a2 2 0 11-4 0v-.1a1.7 1.7 0 00-1.1-1.5 1.7 1.7 0 00-1.8.3l-.1.1a2 2 0 11-2.8-2.8l.1-.1a1.7 1.7 0 00.3-1.8 1.7 1.7 0 00-1.5-1H3a2 2 0 110-4h.1a1.7 1.7 0 001.5-1.1 1.7 1.7 0 00-.3-1.8l-.1-.1a2 2 0 112.8-2.8l.1.1a1.7 1.7 0 001.8.3H9a1.7 1.7 0 001-1.5V3a2 2 0 114 0v.1a1.7 1.7 0 001 1.5 1.7 1.7 0 001.8-.3l.1-.1a2 2 0 112.8 2.8l-.1.1a1.7 1.7 0 00-.3 1.8V9a1.7 1.7 0 001.5 1H21a2 2 0 110 4h-.1a1.7 1.7 0 00-1.5 1z"/>',
  plus: '<path d="M12 5v14M5 12h14"/>',
  edit: '<path d="M12 20h9M16.5 3.5a2.1 2.1 0 013 3L7 19l-4 1 1-4z"/>',
  trash: '<path d="M3 6h18M8 6V4a2 2 0 012-2h4a2 2 0 012 2v2M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/>',
  up: '<path d="M12 19V5M5 12l7-7 7 7"/>',
  down: '<path d="M12 5v14M19 12l-7 7-7-7"/>',
  trend: '<path d="M23 6l-9.5 9.5-5-5L1 18"/><path d="M17 6h6v6"/>',
  wallet: '<path d="M21 12V7H5a2 2 0 010-4h14v4"/><path d="M3 5v14a2 2 0 002 2h16v-5"/><path d="M18 12a2 2 0 000 4h4v-4z"/>',
  alert: '<path d="M10.3 3.9L1.8 18a2 2 0 001.7 3h17a2 2 0 001.7-3L13.7 3.9a2 2 0 00-3.4 0z"/><path d="M12 9v4M12 17h0"/>',
  percent: '<path d="M19 5L5 19"/><circle cx="6.5" cy="6.5" r="2.5"/><circle cx="17.5" cy="17.5" r="2.5"/>',
  star: '<path d="M12 2l3.1 6.3 6.9 1-5 4.9 1.2 6.8L12 17.8 5.8 21l1.2-6.8-5-4.9 6.9-1z"/>',
  coins: '<circle cx="8" cy="8" r="6"/><path d="M18.1 10.4A6 6 0 1110.4 18.1M7 6h1v4M16.7 13.9l.7.7-2.8 2.8"/>',
  profit: '<path d="M12 1v22M17 5H9.5a3.5 3.5 0 000 7h5a3.5 3.5 0 010 7H6"/>',
  user: '<path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/>',
  excel: '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6M8 12l5 6M13 12l-5 6"/>',
  pdf: '<path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6M9 15h6M9 18h4M9 12h2"/>',
  search: '<circle cx="11" cy="11" r="8"/><path d="M21 21l-4.3-4.3"/>',
  check: '<path d="M20 6L9 17l-5-5"/>',
  x: '<path d="M18 6L6 18M6 6l12 12"/>',
  money: '<rect x="2" y="6" width="20" height="12" rx="2"/><circle cx="12" cy="12" r="2.5"/><path d="M6 12h0M18 12h0"/>',
  calendar: '<rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>',
  box: '<path d="M21 16V8a2 2 0 00-1-1.7l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.7l7 4a2 2 0 002 0l7-4a2 2 0 001-1.7z"/><path d="M3.3 7L12 12l8.7-5M12 22V12"/>',
  raise: '<path d="M12 20V10M18 20V4M6 20v-4"/>',
};
const icon = (name) => `<svg viewBox="0 0 24 24" aria-hidden="true">${ICONS[name] || ""}</svg>`;

/* ================= Stare și API ================= */

const state = {
  month: shiftMonth(currentMonth(), -1),
  route: "dashboard",
  charts: [],
  categories: [],
};

async function api(path, options = {}) {
  const opts = { credentials: "same-origin", headers: {}, ...options };
  if (opts.body && typeof opts.body !== "string") {
    opts.body = JSON.stringify(opts.body);
    opts.headers["Content-Type"] = "application/json";
  }
  const res = await fetch(path, opts);
  if (res.status === 401 && !path.startsWith("/api/auth/")) {
    showAuth(true);
    throw new Error("Sesiunea a expirat. Autentificați-vă din nou.");
  }
  const data = res.headers.get("content-type")?.includes("json") ? await res.json() : null;
  if (!res.ok) {
    let msg = data?.detail || "A apărut o eroare.";
    if (Array.isArray(msg)) msg = msg.map((e) => e.msg.replace(/^Value error, /, "")).join(" ");
    throw new Error(msg);
  }
  return data;
}

function toast(message, type = "ok") {
  const el = document.createElement("div");
  el.className = `toast ${type}`;
  el.innerHTML = `${icon(type === "ok" ? "check" : "alert")}<span>${esc(message)}</span>`;
  $("#toasts").append(el);
  setTimeout(() => { el.classList.add("out"); setTimeout(() => el.remove(), 300); }, 3200);
}

/* ================= Autentificare ================= */

let authMode = "login";

async function boot() {
  try {
    const status = await api("/api/auth/status");
    if (status.company) $("#brand-name").textContent = status.company;
    if (status.logged_in) return showApp();
    authMode = status.setup_done ? "login" : "setup";
    showAuth();
  } catch (err) {
    toast(err.message, "err");
  }
}

function showAuth(expired = false) {
  $("#app").classList.add("hidden");
  $("#auth-screen").classList.remove("hidden");
  const setup = authMode === "setup";
  $("#auth-title").textContent = setup ? "Bun venit la Testify Hardware" : "Bun venit înapoi";
  $("#auth-subtitle").textContent = setup
    ? "Prima pornire: alegeți o parolă. Doar dumneavoastră veți avea acces la aplicație."
    : expired ? "Sesiunea a expirat. Introduceți parola din nou." : "Introduceți parola ca să vedeți cifrele firmei.";
  $("#auth-confirm-wrap").classList.toggle("hidden", !setup);
  $("#auth-demo-wrap").classList.toggle("hidden", !setup);
  $("#auth-submit").textContent = setup ? "Creează parola și intră" : "Intră în aplicație";
  $("#auth-password").autocomplete = setup ? "new-password" : "current-password";
  $("#auth-error").textContent = "";
  setTimeout(() => $("#auth-password").focus(), 50);
}

$("#auth-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const password = $("#auth-password").value;
  const err = $("#auth-error");
  err.textContent = "";
  try {
    if (authMode === "setup") {
      if (password !== $("#auth-confirm").value) {
        err.textContent = "Parolele nu coincid.";
        return;
      }
      $("#auth-submit").textContent = "Se pregătește aplicația…";
      await api("/api/auth/setup", { method: "POST", body: { password, demo: $("#auth-demo").checked } });
    } else {
      await api("/api/auth/login", { method: "POST", body: { password } });
    }
    $("#auth-password").value = "";
    $("#auth-confirm").value = "";
    showApp();
  } catch (ex) {
    err.textContent = ex.message;
    if (authMode === "setup") $("#auth-submit").textContent = "Creează parola și intră";
  }
});

$("#logout-btn").addEventListener("click", async () => {
  await api("/api/auth/logout", { method: "POST" }).catch(() => {});
  authMode = "login";
  showAuth();
});

/* ================= Navigare ================= */

const ROUTES = {
  dashboard: { label: "Dashboard", icon: "dashboard", eyebrow: "Imagine de ansamblu", title: "Cum merge firma", render: renderDashboard },
  vanzari: { label: "Vânzări", icon: "sales", eyebrow: "Bani care intră", title: "Vânzări", render: renderSales },
  cheltuieli: { label: "Cheltuieli", icon: "expenses", eyebrow: "Bani care ies", title: "Cheltuieli", render: renderExpenses },
  angajati: { label: "Angajați", icon: "team", eyebrow: "Echipa și salariile", title: "Angajați", render: renderEmployees },
  taxe: { label: "Taxe", icon: "taxes", eyebrow: "Ce plătiți statului", title: "Taxe și contribuții", render: renderTaxes },
  rapoarte: { label: "Rapoarte", icon: "reports", eyebrow: "Pentru contabilă", title: "Rapoarte și export", render: renderReports },
  setari: { label: "Setări", icon: "settings", eyebrow: "Configurare", title: "Setări", render: renderSettings, noMonth: true },
};

function buildNav() {
  $("#nav").innerHTML = Object.entries(ROUTES).map(([key, r]) =>
    `<a class="nav-item" href="#${key}" data-route="${key}">${icon(r.icon)}<span>${r.label}</span></a>`).join("");
}

function showApp() {
  $("#auth-screen").classList.add("hidden");
  $("#app").classList.remove("hidden");
  buildNav();
  route();
}

function route() {
  const key = location.hash.slice(1);
  state.route = ROUTES[key] ? key : "dashboard";
  render();
}
window.addEventListener("hashchange", route);

function destroyCharts() {
  state.charts.forEach((c) => c.destroy());
  state.charts = [];
}

async function render() {
  const r = ROUTES[state.route];
  $$(".nav-item[data-route]").forEach((a) => a.classList.toggle("active", a.dataset.route === state.route));
  $("#page-title").textContent = r.title;
  $("#page-eyebrow").textContent = r.eyebrow;
  $("#month-picker").classList.toggle("hidden", !!r.noMonth);
  const inProgress = state.month === currentMonth();
  $("#month-label").textContent = monthLabel(state.month) + (inProgress ? " · în curs" : "");
  $("#month-next").disabled = state.month >= currentMonth();
  $("#month-next").style.opacity = state.month >= currentMonth() ? 0.3 : 1;
  destroyCharts();
  // Element nou la fiecare randare, ca să nu se adune event listener-ele vechi.
  const old = $("#view");
  const view = old.cloneNode(false);
  old.replaceWith(view);
  view.innerHTML = '<div class="grid kpis"><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div><div class="skeleton"></div></div>';
  try {
    await r.render(view);
  } catch (err) {
    view.innerHTML = `<div class="card glass empty">${icon("alert")}<p>${esc(err.message)}</p></div>`;
  }
}

$("#month-prev").addEventListener("click", () => { state.month = shiftMonth(state.month, -1); render(); });
$("#month-next").addEventListener("click", () => {
  if (state.month < currentMonth()) { state.month = shiftMonth(state.month, 1); render(); }
});

function setMonthFromDate(iso) {
  const ym = iso.slice(0, 7);
  if (ym !== state.month) {
    state.month = ym;
    toast(`Am trecut la ${monthLabel(ym)}.`);
  }
}

/* ================= Modal ================= */

function openModal(title, html, onMount) {
  $("#modal-title").textContent = title;
  $("#modal-body").innerHTML = html;
  $("#modal").classList.remove("hidden");
  onMount?.($("#modal-body"));
  setTimeout(() => $("#modal-body input:not([type=hidden]), #modal-body select")?.focus(), 60);
}
function closeModal() { $("#modal").classList.add("hidden"); $("#modal-body").innerHTML = ""; }
$("#modal-close").addEventListener("click", closeModal);
$("#modal").addEventListener("click", (e) => { if (e.target.id === "modal") closeModal(); });
document.addEventListener("keydown", (e) => { if (e.key === "Escape") closeModal(); });

function confirmBox(title, text, confirmLabel = "Șterge") {
  return new Promise((resolve) => {
    openModal(title, `
      <p class="muted">${esc(text)}</p>
      <div class="form-actions">
        <button class="btn btn-ghost" type="button" data-no>Renunță</button>
        <button class="btn btn-danger" type="button" data-yes>${icon("trash")}${esc(confirmLabel)}</button>
      </div>`, (body) => {
      $("[data-no]", body).onclick = () => { closeModal(); resolve(false); };
      $("[data-yes]", body).onclick = () => { closeModal(); resolve(true); };
    });
  });
}

function formData(form) {
  const data = {};
  for (const [k, v] of new FormData(form).entries()) data[k] = typeof v === "string" ? v.trim() : v;
  return data;
}

/* ================= Grafice ================= */

const hasChart = () => typeof window.Chart !== "undefined";
if (hasChart()) {
  Chart.defaults.color = "#8a99b4";
  Chart.defaults.font.family = getComputedStyle(document.body).fontFamily;
  Chart.defaults.borderColor = "rgba(148,163,184,0.08)";
  Chart.defaults.plugins.tooltip.backgroundColor = "rgba(13,20,37,0.96)";
  Chart.defaults.plugins.tooltip.borderColor = "rgba(148,163,184,0.25)";
  Chart.defaults.plugins.tooltip.borderWidth = 1;
  Chart.defaults.plugins.tooltip.padding = 12;
  Chart.defaults.plugins.tooltip.cornerRadius = 10;
  Chart.defaults.plugins.tooltip.titleFont = { weight: "700" };
}

function gradient(ctx, area, from, to) {
  const g = ctx.createLinearGradient(0, area.top, 0, area.bottom);
  g.addColorStop(0, from);
  g.addColorStop(1, to);
  return g;
}

function makeChart(canvas, config) {
  if (!hasChart() || !canvas) return null;
  const chart = new Chart(canvas, config);
  state.charts.push(chart);
  return chart;
}

const moneyTick = (v) => (Math.abs(v) >= 1000 ? `${numberFmt.format(v / 1000)}k` : numberFmt.format(v));

function sparkline(values, color) {
  if (values.length < 2) return "";
  const w = 96, h = 36, pad = 3;
  const min = Math.min(...values), max = Math.max(...values);
  const span = max - min || 1;
  const pts = values.map((v, i) => [pad + (i * (w - pad * 2)) / (values.length - 1), h - pad - ((v - min) / span) * (h - pad * 2)]);
  const line = pts.map((p, i) => `${i ? "L" : "M"}${p[0].toFixed(1)},${p[1].toFixed(1)}`).join(" ");
  const id = `sg${Math.random().toString(36).slice(2, 8)}`;
  return `<svg class="spark" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none">
    <defs><linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="${color}" stop-opacity=".35"/><stop offset="1" stop-color="${color}" stop-opacity="0"/></linearGradient></defs>
    <path d="${line} L${w - pad},${h} L${pad},${h} Z" fill="url(#${id})" stroke="none"/>
    <path d="${line}" stroke="${color}" stroke-width="2" fill="none"/>
    <circle cx="${pts.at(-1)[0]}" cy="${pts.at(-1)[1]}" r="2.8" fill="${color}" stroke="none"/></svg>`;
}

function countUp(el, target, suffix = " lei") {
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const duration = 1100;
  const start = performance.now();
  const step = (now) => {
    const t = Math.min(1, (now - start) / duration);
    const eased = 1 - Math.pow(1 - t, 4);
    el.innerHTML = `${numberFmt.format(target * (reduce ? 1 : eased))}<small>${suffix}</small>`;
    if (t < 1 && !reduce) requestAnimationFrame(step);
  };
  requestAnimationFrame(step);
}

function changeChip(value, invert = false) {
  if (value === null || value === undefined) return '<span class="chip">—</span>';
  const good = invert ? value <= 0 : value >= 0;
  return `<span class="chip ${good ? "up" : "down"}">${icon(value >= 0 ? "up" : "down")}${pct(Math.abs(value))}</span>`;
}

function animateBars(root) {
  requestAnimationFrame(() => $$(".bar i[data-w]", root).forEach((b) => { b.style.width = b.dataset.w; }));
}

/* ================= Dashboard ================= */

function greeting() {
  const h = new Date().getHours();
  return h < 11 ? "Bună dimineața" : h < 18 ? "Bună ziua" : "Bună seara";
}

async function renderDashboard(view) {
  const d = await api(`/api/dashboard?month=${state.month}`);
  const c = d.current;
  const trend = d.trend;
  const cmp = d.in_progress ? `vs. 1–${d.compared_until_day} luna trecută` : "vs. luna trecută";

  const kpis = [
    { key: "revenue", label: "Venituri", icon: "coins", accent: "#22d3ee", value: c.revenue, spark: trend.map((t) => t.revenue), sub: `${c.sales_count} înregistrări` },
    { key: "total_costs", label: "Costuri totale", icon: "wallet", accent: "#f87171", value: c.total_costs, spark: trend.map((t) => t.costs), invert: true, sub: "marfă, salarii, taxe…" },
    { key: "profit", label: "Profit net", icon: "profit", accent: c.profit >= 0 ? "#34d399" : "#f87171", value: c.profit, spark: trend.map((t) => t.profit), sub: `marjă ${pct(c.margin)}` },
    { key: "owner_income", label: "Îți rămâne ție", icon: "star", accent: "#fbbf24", value: c.owner_income, spark: trend.map((t) => Math.max(t.profit, 0)), sub: "după impozitul pe dividende" },
  ];

  view.innerHTML = `
    <div class="hero">
      <h2>${greeting()}! Iată cum arată <span>${esc(d.company)}</span> în ${esc(c.label)}.</h2>
      ${d.in_progress
        ? `<span class="badge"><span class="dot"></span>Lună în curs — date până azi</span>`
        : `<span class="chip up">${icon("check")}Lună încheiată</span>`}
    </div>

    <section class="grid kpis">
      ${kpis.map((k) => `
        <article class="card glass kpi" style="--accent:${k.accent}">
          <div class="kpi-top">
            <span class="kpi-label"><span class="kpi-icon">${icon(k.icon)}</span>${k.label}</span>
            ${changeChip(d.changes[k.key], k.invert)}
          </div>
          <div class="kpi-value" data-count="${k.value}">0<small> lei</small></div>
          <div class="kpi-foot">
            <span class="sub">${esc(k.sub)}<br>${esc(cmp)}</span>
            ${sparkline(k.spark, k.accent)}
          </div>
        </article>`).join("")}
    </section>

    <section class="grid cols-2 mt">
      <article class="card glass fill">
        <div class="card-head">
          <div><h2>Evoluție pe 12 luni</h2><p>Venituri, costuri și profit</p></div>
          <div class="stat-strip" style="grid-template-columns:repeat(3,auto);gap:18px">
            <div><span class="muted" style="font-size:12px">Venituri ${c.month.slice(0, 4)}</span><br><strong class="num">${lei(d.year.revenue)}</strong></div>
            <div><span class="muted" style="font-size:12px">Profit ${c.month.slice(0, 4)}</span><br><strong class="num" style="color:var(--green)">${lei(d.year.profit)}</strong></div>
          </div>
        </div>
        <div class="chart-box"><canvas id="trend-chart"></canvas></div>
      </article>

      <article class="card glass">
        <div class="card-head"><div><h2>Unde se duc banii</h2><p>Toate ieșirile din ${esc(c.label)}</p></div></div>
        ${d.flow.length ? `
        <div class="donut-wrap">
          <div class="donut"><canvas id="flow-chart"></canvas>
            <div class="donut-center"><span>Total ieșiri</span><strong class="num">${lei(d.flow.reduce((s, f) => s + f.amount, 0))}</strong></div>
          </div>
          <ul class="legend">
            ${d.flow.map((f) => `<li><span class="sw" style="background:${esc(f.color)}"></span><span>${esc(f.name)}</span><span class="val"><b>${pct(f.share)}</b> · ${lei(f.amount)}</span></li>`).join("")}
          </ul>
        </div>` : emptyState("Nu există încă ieșiri de bani în această lună.")}
      </article>
    </section>

    <section class="grid cols-3 mt">
      <article class="card glass">
        <div class="card-head"><div><h2>Ce trebuie să știi</h2><p>Observații automate</p></div></div>
        ${d.insights.length ? `<ul class="insights">${d.insights.map((n, i) => `
          <li class="insight ${n.tone}" style="animation-delay:${i * 80}ms"><span class="ic">${icon(n.icon)}</span><span>${esc(n.text)}</span></li>`).join("")}</ul>`
          : emptyState("Adăugați vânzări și cheltuieli ca să apară observații.")}
      </article>

      <article class="card glass">
        <div class="card-head"><div><h2>Taxe luna aceasta</h2><p>Total: <b style="color:var(--text)">${lei(c.taxes.total)}</b></p></div>
          <a class="btn btn-sm" href="#taxe">Detalii</a></div>
        <div class="bars">${taxBars(c.taxes)}</div>
      </article>

      <article class="card glass">
        <div class="card-head"><div><h2>Top produse</h2><p>După valoarea vânzărilor</p></div></div>
        ${d.top_products.length ? `<div class="bars">${d.top_products.map((p, i) => `
          <div class="bar-row"><header><span>${i + 1}. ${esc(p.product)}</span><span>${lei(p.amount)}</span></header>
          <div class="bar"><i data-w="${(p.amount / d.top_products[0].amount) * 100}%" style="background:linear-gradient(90deg,#3b82f6,#22d3ee)"></i></div>
          <small class="muted" style="font-size:12px">${numberFmt.format(p.quantity)} buc.</small></div>`).join("")}</div>`
          : emptyState("Completați produsul la vânzări ca să vedeți topul.")}
      </article>
    </section>`;

  $$("[data-count]", view).forEach((el) => countUp(el, Number(el.dataset.count)));
  animateBars(view);

  makeChart($("#trend-chart"), {
    data: {
      labels: trend.map((t) => t.label),
      datasets: [
        { type: "line", label: "Profit", data: trend.map((t) => t.profit), borderColor: "#fbbf24", backgroundColor: "#fbbf24",
          borderWidth: 3, tension: 0.4, pointRadius: 3, pointHoverRadius: 6, order: 0 },
        { type: "bar", label: "Venituri", data: trend.map((t) => t.revenue), borderRadius: 8, maxBarThickness: 22, order: 1,
          backgroundColor: (ctx) => ctx.chart.chartArea ? gradient(ctx.chart.ctx, ctx.chart.chartArea, "#22d3ee", "rgba(59,130,246,0.25)") : "#22d3ee" },
        { type: "bar", label: "Costuri", data: trend.map((t) => t.costs), borderRadius: 8, maxBarThickness: 22, order: 2,
          backgroundColor: (ctx) => ctx.chart.chartArea ? gradient(ctx.chart.ctx, ctx.chart.chartArea, "rgba(248,113,113,0.85)", "rgba(248,113,113,0.12)") : "#f87171" },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false, interaction: { mode: "index", intersect: false },
      animation: { duration: 1200, easing: "easeOutQuart" },
      plugins: {
        legend: { position: "bottom", labels: { usePointStyle: true, pointStyle: "rectRounded", padding: 18 } },
        tooltip: { callbacks: { label: (ctx) => ` ${ctx.dataset.label}: ${lei(ctx.parsed.y)}` } },
      },
      scales: { x: { grid: { display: false } }, y: { ticks: { callback: moneyTick } } },
    },
  });

  makeChart($("#flow-chart"), {
    type: "doughnut",
    data: { labels: d.flow.map((f) => f.name), datasets: [{ data: d.flow.map((f) => f.amount), backgroundColor: d.flow.map((f) => f.color), borderColor: "#0d1425", borderWidth: 3, hoverOffset: 10 }] },
    options: {
      cutout: "72%", responsive: true, maintainAspectRatio: false, animation: { animateRotate: true, duration: 1300 },
      plugins: { legend: { display: false }, tooltip: { callbacks: { label: (ctx) => ` ${ctx.label}: ${lei(ctx.parsed)}` } } },
    },
  });
}

function taxBars(t) {
  const items = [
    ["CAS — pensii", t.cas, "#a78bfa"], ["CASS — sănătate", t.cass, "#34d399"],
    ["Impozit pe salarii", t.income_tax, "#22d3ee"], ["CAM — contribuția firmei", t.cam, "#fb923c"],
    ["Impozit microîntreprindere", t.micro_tax, "#fbbf24"],
  ];
  const max = Math.max(...items.map((i) => i[1]), 1);
  return items.map(([name, value, color]) => `
    <div class="bar-row"><header><span>${name}</span><span>${lei(value)}</span></header>
    <div class="bar"><i data-w="${(value / max) * 100}%" style="background:${color}"></i></div></div>`).join("");
}

/* Tabelele lungi afișează 25 de rânduri, cu „Arată mai multe” și căutare. */
function paginate(view, rowsSel, searchSel, pageSize = 25) {
  const tbody = $(rowsSel, view);
  if (!tbody) return;
  let limit = pageSize;
  const more = document.createElement("div");
  more.className = "more";
  tbody.closest(".table-wrap").after(more);
  const apply = () => {
    const q = ($(searchSel, view)?.value || "").toLowerCase();
    const matches = $$("tr", tbody).filter((tr) => tr.dataset.search.includes(q));
    $$("tr", tbody).forEach((tr) => { tr.style.display = "none"; });
    matches.slice(0, limit).forEach((tr) => { tr.style.display = ""; });
    const rest = matches.length - limit;
    more.innerHTML = rest > 0
      ? `<button class="btn btn-sm" type="button">Arată mai multe (${rest} rămase)</button>` : "";
    $("button", more)?.addEventListener("click", () => { limit += 50; apply(); });
  };
  $(searchSel, view)?.addEventListener("input", () => { limit = pageSize; apply(); });
  apply();
}

function emptyState(text) {
  return `<div class="empty">${icon("box")}<p>${esc(text)}</p></div>`;
}

/* ================= Vânzări ================= */

let saleMode = "order";

function saleFormHTML(sale = {}, mode = "order") {
  const isOrder = mode === "order";
  const unit = sale.quantity && sale.amount ? (sale.amount / sale.quantity).toFixed(2) : "";
  return `
    <div class="form-grid">
      <label class="field"><span>Data</span><input type="date" name="date" required value="${esc(sale.date || defaultDate())}"></label>
      ${isOrder ? `
        <label class="field" style="grid-column:span 2"><span>Produs</span><input name="product" list="products-list" required maxlength="200" placeholder="ex. Mouse wireless Logitech" value="${esc(sale.product || "")}"></label>
        <label class="field"><span>Cantitate</span><input type="number" name="quantity" min="1" step="1" required value="${esc(sale.quantity || 1)}"></label>
        <label class="field"><span>Preț / bucată</span><input type="number" name="unit" min="0.01" step="0.01" placeholder="0,00" value="${esc(unit)}"></label>
      ` : `
        <label class="field" style="grid-column:span 2"><span>Descriere</span><input name="description" required maxlength="200" placeholder="ex. Vânzări magazin — total zi" value="${esc(sale.description || "")}"></label>
      `}
      <label class="field"><span>Total (lei)</span><input type="number" name="amount" min="0.01" step="0.01" required placeholder="0,00" value="${esc(sale.amount ?? "")}"></label>
    </div>`;
}

// Data propusă e mereu azi; după salvare, aplicația trece la luna înregistrării.
function defaultDate() {
  return todayISO();
}

function wireSaleForm(form) {
  const qty = $("[name=quantity]", form), unit = $("[name=unit]", form), amount = $("[name=amount]", form);
  if (!qty) return;
  const recalc = () => {
    const q = Number(qty.value), u = Number(unit.value);
    if (q > 0 && u > 0) amount.value = (q * u).toFixed(2);
  };
  qty.addEventListener("input", recalc);
  unit.addEventListener("input", recalc);
  amount.addEventListener("input", () => {
    const q = Number(qty.value), a = Number(amount.value);
    if (q > 0 && a > 0) unit.value = (a / q).toFixed(2);
  });
}

function salePayload(form, mode) {
  const d = formData(form);
  const payload = { date: d.date, amount: Number(d.amount) };
  if (mode === "order") {
    payload.product = d.product;
    payload.quantity = Number(d.quantity) || 1;
    payload.description = `Comandă ${d.product}${payload.quantity > 1 ? ` ×${payload.quantity}` : ""}`;
  } else {
    payload.description = d.description;
    payload.product = null;
    payload.quantity = null;
  }
  return payload;
}

async function renderSales(view) {
  const sales = await api(`/api/sales?month=${state.month}`);
  const total = sales.reduce((s, x) => s + x.amount, 0);
  const orders = sales.filter((s) => s.product);
  const byDay = {};
  sales.forEach((s) => { byDay[s.date] = (byDay[s.date] || 0) + s.amount; });
  const bestDay = Object.entries(byDay).sort((a, b) => b[1] - a[1])[0];
  const products = [...new Set(sales.map((s) => s.product).filter(Boolean))];

  view.innerHTML = `
    <section class="card glass">
      <div class="card-head">
        <div><h2>Adaugă o vânzare</h2><p>Introduceți fiecare comandă sau doar totalul pe zi/lună — cum vă e mai comod.</p></div>
        <div class="segmented" id="sale-mode">
          <button type="button" data-mode="order" class="${saleMode === "order" ? "active" : ""}">Comandă</button>
          <button type="button" data-mode="total" class="${saleMode === "total" ? "active" : ""}">Total zi / lună</button>
        </div>
      </div>
      <form id="sale-form">
        <div id="sale-fields">${saleFormHTML({}, saleMode)}</div>
        <div class="form-actions"><button class="btn btn-primary" type="submit">${icon("plus")}Adaugă vânzarea</button></div>
      </form>
      <datalist id="products-list">${products.map((p) => `<option value="${esc(p)}">`).join("")}</datalist>
    </section>

    <section class="stat-strip mt">
      <div class="stat"><span>Total vânzări</span><strong>${lei(total)}</strong></div>
      <div class="stat"><span>Înregistrări</span><strong>${sales.length}</strong></div>
      <div class="stat"><span>Valoare medie comandă</span><strong>${lei(orders.length ? orders.reduce((s, o) => s + o.amount, 0) / orders.length : 0)}</strong></div>
      <div class="stat"><span>Cea mai bună zi</span><strong>${bestDay ? `${formatDate(bestDay[0]).slice(0, 5)} · ${lei(bestDay[1])}` : "—"}</strong></div>
    </section>

    <section class="card glass mt">
      <div class="card-head">
        <div><h2>Vânzări — ${esc(monthLabel(state.month))}</h2><p>${sales.length} înregistrări</p></div>
        <div class="toolbar"><label class="field search">${icon("search")}<input id="sale-search" placeholder="Caută produs sau descriere…"></label></div>
      </div>
      ${sales.length ? `<div class="table-wrap"><table>
        <thead><tr><th>Data</th><th>Descriere</th><th>Tip</th><th class="r">Cant.</th><th class="r">Sumă</th><th></th></tr></thead>
        <tbody id="sale-rows">${sales.map((s) => `
          <tr data-search="${esc(`${s.description} ${s.product || ""}`.toLowerCase())}">
            <td>${formatDate(s.date)}</td>
            <td>${esc(s.description)}</td>
            <td>${s.product ? '<span class="tag order">Comandă</span>' : '<span class="tag total">Total</span>'}</td>
            <td class="r">${s.quantity ?? "—"}</td>
            <td class="r"><b>${lei(s.amount, true)}</b></td>
            <td class="actions">
              <button class="icon-btn" data-edit="${s.id}" title="Editează">${icon("edit")}</button>
              <button class="icon-btn danger" data-del="${s.id}" title="Șterge">${icon("trash")}</button>
            </td>
          </tr>`).join("")}</tbody>
        <tfoot><tr><td colspan="4">Total lună</td><td class="r">${lei(total, true)}</td><td></td></tr></tfoot>
      </table></div>` : emptyState("Nu există vânzări în această lună. Adăugați prima vânzare mai sus.")}
    </section>`;

  const form = $("#sale-form");
  wireSaleForm(form);
  $$("#sale-mode button").forEach((b) => b.addEventListener("click", () => {
    saleMode = b.dataset.mode;
    $$("#sale-mode button").forEach((x) => x.classList.toggle("active", x === b));
    $("#sale-fields").innerHTML = saleFormHTML({ date: $("[name=date]", form).value }, saleMode);
    wireSaleForm(form);
  }));
  form.addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const payload = salePayload(form, saleMode);
      await api("/api/sales", { method: "POST", body: payload });
      toast(`Vânzare adăugată: ${lei(payload.amount, true)}`);
      setMonthFromDate(payload.date);
      render();
    } catch (err) { toast(err.message, "err"); }
  });

  paginate(view, "#sale-rows", "#sale-search");

  view.addEventListener("click", async (e) => {
    const edit = e.target.closest("[data-edit]"), del = e.target.closest("[data-del]");
    if (edit) {
      const sale = sales.find((s) => s.id === Number(edit.dataset.edit));
      const mode = sale.product ? "order" : "total";
      openModal("Editează vânzarea", `<form id="edit-sale">${saleFormHTML(sale, mode)}
        <div class="form-actions"><button class="btn btn-ghost" type="button" onclick="closeModal()">Renunță</button>
        <button class="btn btn-primary" type="submit">${icon("check")}Salvează</button></div></form>`, (body) => {
        const f = $("#edit-sale", body);
        wireSaleForm(f);
        f.addEventListener("submit", async (ev) => {
          ev.preventDefault();
          try {
            const payload = salePayload(f, mode);
            await api(`/api/sales/${sale.id}`, { method: "PUT", body: payload });
            closeModal(); toast("Vânzarea a fost actualizată."); setMonthFromDate(payload.date); render();
          } catch (err) { toast(err.message, "err"); }
        });
      });
    }
    if (del && await confirmBox("Ștergeți vânzarea?", "Vânzarea va fi ștearsă definitiv.")) {
      try { await api(`/api/sales/${del.dataset.del}`, { method: "DELETE" }); toast("Vânzarea a fost ștearsă."); render(); }
      catch (err) { toast(err.message, "err"); }
    }
  });
}

/* ================= Cheltuieli ================= */

async function loadCategories() {
  state.categories = await api("/api/categories");
  return state.categories;
}
const categoryColor = (name) => state.categories.find((c) => c.name === name)?.color || "#94a3b8";

function expenseFormHTML(exp = {}) {
  return `
    <div class="form-grid">
      <label class="field"><span>Data</span><input type="date" name="date" required value="${esc(exp.date || defaultDate())}"></label>
      <label class="field"><span>Categorie</span><select name="category" required>
        ${state.categories.map((c) => `<option ${c.name === exp.category ? "selected" : ""}>${esc(c.name)}</option>`).join("")}
      </select></label>
      <label class="field" style="grid-column:span 2"><span>Descriere</span><input name="description" maxlength="200" placeholder="ex. Factură furnizor" value="${esc(exp.description || "")}"></label>
      <label class="field"><span>Sumă (lei)</span><input type="number" name="amount" min="0.01" step="0.01" required placeholder="0,00" value="${esc(exp.amount ?? "")}"></label>
    </div>`;
}

function expensePayload(form) {
  const d = formData(form);
  return { date: d.date, category: d.category, description: d.description, amount: Number(d.amount) };
}

async function renderExpenses(view) {
  const [expenses, summary] = await Promise.all([
    api(`/api/expenses?month=${state.month}`), api(`/api/summary?month=${state.month}`), loadCategories(),
  ]);
  const total = expenses.reduce((s, x) => s + x.amount, 0);
  const cats = Object.entries(summary.expenses_by_category);
  const maxCat = Math.max(...cats.map((c) => c[1]), 1);

  view.innerHTML = `
    <section class="grid cols-2">
      <article class="card glass">
        <div class="card-head"><div><h2>Adaugă o cheltuială</h2><p>Facturi, chirie, utilități, transport…</p></div>
          <button class="btn btn-sm" id="manage-cats" type="button">${icon("settings")}Categorii</button></div>
        <form id="expense-form">${expenseFormHTML()}
          <div class="form-actions"><button class="btn btn-primary" type="submit">${icon("plus")}Adaugă cheltuiala</button></div>
        </form>
      </article>
      <article class="card glass">
        <div class="card-head"><div><h2>Pe categorii</h2><p>Total: <b style="color:var(--text)">${lei(total)}</b> · fără salarii și taxe</p></div></div>
        ${cats.length ? `<div class="bars">${cats.map(([name, value]) => `
          <div class="bar-row"><header><span>${esc(name)}</span><span>${lei(value)} · ${pct((value / total) * 100)}</span></header>
          <div class="bar"><i data-w="${(value / maxCat) * 100}%" style="background:${esc(categoryColor(name))}"></i></div></div>`).join("")}</div>`
          : emptyState("Nicio cheltuială în această lună.")}
      </article>
    </section>

    <section class="card glass mt">
      <div class="card-head">
        <div><h2>Cheltuieli — ${esc(monthLabel(state.month))}</h2><p>${expenses.length} înregistrări</p></div>
        <div class="toolbar"><label class="field search">${icon("search")}<input id="exp-search" placeholder="Caută…"></label></div>
      </div>
      ${expenses.length ? `<div class="table-wrap"><table>
        <thead><tr><th>Data</th><th>Categorie</th><th>Descriere</th><th class="r">Sumă</th><th></th></tr></thead>
        <tbody id="exp-rows">${expenses.map((x) => `
          <tr data-search="${esc(`${x.category} ${x.description}`.toLowerCase())}">
            <td>${formatDate(x.date)}</td>
            <td><span class="tag"><span class="sw" style="background:${esc(categoryColor(x.category))}"></span>${esc(x.category)}</span></td>
            <td>${esc(x.description) || '<span class="muted">—</span>'}</td>
            <td class="r"><b>${lei(x.amount, true)}</b></td>
            <td class="actions">
              <button class="icon-btn" data-edit="${x.id}" title="Editează">${icon("edit")}</button>
              <button class="icon-btn danger" data-del="${x.id}" title="Șterge">${icon("trash")}</button>
            </td>
          </tr>`).join("")}</tbody>
        <tfoot><tr><td colspan="3">Total lună</td><td class="r">${lei(total, true)}</td><td></td></tr></tfoot>
      </table></div>` : emptyState("Nu există cheltuieli în această lună.")}
    </section>`;

  animateBars(view);
  $("#manage-cats").addEventListener("click", () => openCategories(render));
  $("#expense-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      const payload = expensePayload(e.target);
      await api("/api/expenses", { method: "POST", body: payload });
      toast(`Cheltuială adăugată: ${lei(payload.amount, true)}`);
      setMonthFromDate(payload.date);
      render();
    } catch (err) { toast(err.message, "err"); }
  });
  paginate(view, "#exp-rows", "#exp-search");
  view.addEventListener("click", async (e) => {
    const edit = e.target.closest("[data-edit]"), del = e.target.closest("[data-del]");
    if (edit) {
      const exp = expenses.find((x) => x.id === Number(edit.dataset.edit));
      openModal("Editează cheltuiala", `<form id="edit-exp">${expenseFormHTML(exp)}
        <div class="form-actions"><button class="btn btn-ghost" type="button" onclick="closeModal()">Renunță</button>
        <button class="btn btn-primary" type="submit">${icon("check")}Salvează</button></div></form>`, (body) => {
        $("#edit-exp", body).addEventListener("submit", async (ev) => {
          ev.preventDefault();
          try {
            const payload = expensePayload(ev.target);
            await api(`/api/expenses/${exp.id}`, { method: "PUT", body: payload });
            closeModal(); toast("Cheltuiala a fost actualizată."); setMonthFromDate(payload.date); render();
          } catch (err) { toast(err.message, "err"); }
        });
      });
    }
    if (del && await confirmBox("Ștergeți cheltuiala?", "Cheltuiala va fi ștearsă definitiv.")) {
      try { await api(`/api/expenses/${del.dataset.del}`, { method: "DELETE" }); toast("Cheltuiala a fost ștearsă."); render(); }
      catch (err) { toast(err.message, "err"); }
    }
  });
}

function categoriesHTML() {
  return `
    <ul class="legend" style="gap:6px;margin-bottom:16px">
      ${state.categories.map((c) => `<li style="grid-template-columns:12px 1fr auto"><span class="sw" style="background:${esc(c.color)}"></span><span>${esc(c.name)}</span>
        <button class="icon-btn danger" data-delcat="${c.id}" title="Șterge">${icon("trash")}</button></li>`).join("")}
    </ul>
    <form id="cat-form" class="form-grid" style="grid-template-columns:1fr 70px auto;align-items:end">
      <label class="field"><span>Categorie nouă</span><input name="name" required maxlength="100" placeholder="ex. Asigurări"></label>
      <label class="field"><span>Culoare</span><input type="color" name="color" value="#22d3ee" style="padding:4px;height:46px"></label>
      <button class="btn btn-primary" type="submit">${icon("plus")}Adaugă</button>
    </form>`;
}

function openCategories(onChange) {
  const mount = (body) => {
    $("#cat-form", body).addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        await api("/api/categories", { method: "POST", body: formData(e.target) });
        await loadCategories(); body.innerHTML = categoriesHTML(); mount(body); toast("Categorie adăugată."); onChange?.();
      } catch (err) { toast(err.message, "err"); }
    });
    $$("[data-delcat]", body).forEach((b) => b.addEventListener("click", async () => {
      try {
        await api(`/api/categories/${b.dataset.delcat}`, { method: "DELETE" });
        await loadCategories(); body.innerHTML = categoriesHTML(); mount(body); toast("Categorie ștearsă."); onChange?.();
      } catch (err) { toast(err.message, "err"); }
    }));
  };
  loadCategories().then(() => openModal("Categorii de cheltuieli", categoriesHTML(), mount));
}

/* ================= Angajați ================= */

function previewHTML(p, current) {
  const diff = current ? p.net - current.net : null;
  return `
    <div class="row"><span>Salariu brut</span><b>${lei(p.gross, true)}</b></div>
    <div class="row"><span>− CAS (pensie)</span><b>${lei(p.cas, true)}</b></div>
    <div class="row"><span>− CASS (sănătate)</span><b>${lei(p.cass, true)}</b></div>
    <div class="row"><span>− Impozit pe venit</span><b>${lei(p.income_tax, true)}</b></div>
    <div class="row big"><span>Salariu net (primește angajatul)</span><b>${lei(p.net, true)}</b></div>
    <div class="row"><span>+ CAM plătit de firmă</span><b>${lei(p.cam, true)}</b></div>
    <div class="row big"><span>Cost total pentru firmă</span><b style="color:var(--gold)">${lei(p.employer_cost, true)}</b></div>
    ${diff !== null ? `<div class="row"><span>Diferență net față de acum</span><b style="color:${diff >= 0 ? "var(--green)" : "var(--red)"}">${diff >= 0 ? "+" : ""}${lei(diff, true)}</b></div>` : ""}`;
}

function wirePreview(body, current) {
  const input = $("[name=gross]", body), out = $(".preview", body);
  let timer;
  const update = () => {
    clearTimeout(timer);
    const gross = Number(input.value);
    if (!(gross > 0)) { out.classList.add("hidden"); return; }
    timer = setTimeout(async () => {
      try {
        const p = await api(`/api/salary-preview?gross=${gross}`);
        out.innerHTML = previewHTML(p, current);
        out.classList.remove("hidden");
      } catch { /* valoare invalidă în timpul tastării */ }
    }, 180);
  };
  input.addEventListener("input", update);
  update();
}

async function renderEmployees(view) {
  const [employees, pay] = await Promise.all([api("/api/employees"), api(`/api/payroll?month=${state.month}`)]);
  const t = pay.totals;
  const active = employees.filter((e) => e.active);

  view.innerHTML = `
    <section class="stat-strip">
      <div class="stat"><span>Angajați activi</span><strong>${active.length}</strong></div>
      <div class="stat"><span>Total brut — ${esc(monthLabel(state.month))}</span><strong>${lei(t.gross)}</strong></div>
      <div class="stat"><span>Total net plătit</span><strong>${lei(t.net)}</strong></div>
      <div class="stat"><span>Cost total firmă</span><strong style="color:var(--gold)">${lei(t.employer_cost)}</strong></div>
    </section>

    <div class="card-head mt" style="margin-bottom:14px">
      <div><h2>Echipa</h2><p>Adăugați angajați și modificați salariile pe măsură ce evoluează.</p></div>
      <button class="btn btn-primary" id="add-emp" type="button">${icon("plus")}Adaugă angajat</button>
    </div>

    ${employees.length ? `<section class="employees">${employees.map((e) => `
      <article class="card glass emp ${e.active ? "" : "inactive"}">
        <div class="emp-head">
          <div class="avatar" style="background:${gradientFor(e.name)}">${esc(initials(e.name))}</div>
          <div style="flex:1;min-width:0"><h3>${esc(e.name)}</h3><p>${esc(e.role || "—")}</p></div>
          ${e.active ? "" : '<span class="tag">Inactiv</span>'}
        </div>
        <div class="emp-pay">
          <div><span>Brut</span><strong>${lei(e.salary.gross)}</strong></div>
          <div><span>Net</span><strong style="color:var(--cyan)">${lei(e.salary.net)}</strong></div>
          <div><span>Cost firmă</span><strong style="color:var(--gold)">${lei(e.salary.employer_cost)}</strong></div>
        </div>
        <ul class="timeline">${e.history.map((h) => `<li><b>${lei(h.gross)}</b> brut din ${formatDate(h.effective_from)} · ${esc(h.note)}</li>`).join("")}
          <li>Angajat din <b>${formatDate(e.hire_date)}</b>${e.end_date ? ` · plecat ${formatDate(e.end_date)}` : ""}</li></ul>
        <div class="emp-actions">
          <button class="btn btn-sm btn-gold" data-raise="${e.id}" type="button">${icon("raise")}Modifică salariul</button>
          <button class="btn btn-sm" data-edit="${e.id}" type="button">${icon("edit")}Editează</button>
          <button class="icon-btn danger" data-del="${e.id}" title="Șterge">${icon("trash")}</button>
        </div>
      </article>`).join("")}</section>` : `<div class="card glass">${emptyState("Nu aveți încă angajați. Adăugați primul angajat.")}</div>`}

    <section class="card glass mt">
      <div class="card-head"><div><h2>Stat de plată — ${esc(monthLabel(state.month))}</h2><p>Calculat automat din salariile brute</p></div></div>
      ${pay.lines.length ? `<div class="table-wrap"><table>
        <thead><tr><th>Angajat</th><th class="r">Brut</th><th class="r">CAS</th><th class="r">CASS</th><th class="r">Impozit</th><th class="r">Net</th><th class="r">CAM</th><th class="r">Cost firmă</th></tr></thead>
        <tbody>${pay.lines.map((l) => `<tr><td>${esc(l.name)}<br><small class="muted">${esc(l.role)}</small></td>
          <td class="r">${lei(l.gross, true)}</td><td class="r">${lei(l.cas, true)}</td><td class="r">${lei(l.cass, true)}</td>
          <td class="r">${lei(l.income_tax, true)}</td><td class="r"><b style="color:var(--cyan)">${lei(l.net, true)}</b></td>
          <td class="r">${lei(l.cam, true)}</td><td class="r"><b>${lei(l.employer_cost, true)}</b></td></tr>`).join("")}</tbody>
        <tfoot><tr><td>Total</td><td class="r">${lei(t.gross, true)}</td><td class="r">${lei(t.cas, true)}</td><td class="r">${lei(t.cass, true)}</td>
          <td class="r">${lei(t.income_tax, true)}</td><td class="r">${lei(t.net, true)}</td><td class="r">${lei(t.cam, true)}</td><td class="r">${lei(t.employer_cost, true)}</td></tr></tfoot>
      </table></div>` : emptyState("Niciun angajat activ în această lună.")}
    </section>`;

  $("#add-emp").addEventListener("click", () => {
    openModal("Angajat nou", `<form id="emp-form">
      <div class="form-grid">
        <label class="field" style="grid-column:1/-1"><span>Nume complet</span><input name="name" required maxlength="120" placeholder="ex. Maria Ionescu"></label>
        <label class="field"><span>Funcție</span><input name="role" maxlength="120" placeholder="ex. Vânzări"></label>
        <label class="field"><span>Data angajării</span><input type="date" name="hire_date" required value="${todayISO()}"></label>
        <label class="field" style="grid-column:1/-1"><span>Salariu brut (lei)</span><input type="number" name="gross" min="1" step="1" required placeholder="ex. 5000"></label>
      </div>
      <div class="preview hidden"></div>
      <div class="form-actions"><button class="btn btn-ghost" type="button" onclick="closeModal()">Renunță</button>
      <button class="btn btn-primary" type="submit">${icon("check")}Adaugă angajatul</button></div></form>`, (body) => {
      wirePreview(body);
      $("#emp-form", body).addEventListener("submit", async (ev) => {
        ev.preventDefault();
        const d = formData(ev.target);
        try {
          await api("/api/employees", { method: "POST", body: { ...d, gross: Number(d.gross) } });
          closeModal(); toast(`${d.name} a fost adăugat(ă) în echipă.`); render();
        } catch (err) { toast(err.message, "err"); }
      });
    });
  });

  view.addEventListener("click", async (ev) => {
    const raise = ev.target.closest("[data-raise]"), edit = ev.target.closest("[data-edit]"), del = ev.target.closest("[data-del]");
    const find = (el, attr) => employees.find((x) => x.id === Number(el.dataset[attr]));
    if (raise) {
      const e = find(raise, "raise");
      const nextMonth = `${shiftMonth(currentMonth(), 1)}-01`;
      openModal(`Salariu nou — ${e.name}`, `<form id="raise-form">
        <p class="muted" style="margin-top:0">Salariul actual: <b style="color:var(--text)">${lei(e.salary.gross)} brut</b> (${lei(e.salary.net)} net). Istoricul se păstrează.</p>
        <div class="form-grid">
          <label class="field"><span>Salariu brut nou (lei)</span><input type="number" name="gross" min="1" step="1" required value="${e.salary.gross}"></label>
          <label class="field"><span>Valabil de la</span><input type="date" name="effective_from" required value="${nextMonth}"></label>
          <label class="field" style="grid-column:1/-1"><span>Motiv (opțional)</span><input name="note" maxlength="200" placeholder="ex. Performanță foarte bună"></label>
        </div>
        <div class="preview hidden"></div>
        <div class="form-actions"><button class="btn btn-ghost" type="button" onclick="closeModal()">Renunță</button>
        <button class="btn btn-gold" type="submit">${icon("check")}Salvează salariul</button></div></form>`, (body) => {
        wirePreview(body, e.salary);
        $("#raise-form", body).addEventListener("submit", async (sub) => {
          sub.preventDefault();
          const d = formData(sub.target);
          try {
            await api(`/api/employees/${e.id}/salary`, { method: "POST", body: { ...d, gross: Number(d.gross) } });
            closeModal(); toast(`Salariul lui ${e.name} a fost actualizat.`); render();
          } catch (err) { toast(err.message, "err"); }
        });
      });
    }
    if (edit) {
      const e = find(edit, "edit");
      openModal(`Editează — ${e.name}`, `<form id="edit-emp">
        <div class="form-grid">
          <label class="field" style="grid-column:1/-1"><span>Nume complet</span><input name="name" required maxlength="120" value="${esc(e.name)}"></label>
          <label class="field" style="grid-column:1/-1"><span>Funcție</span><input name="role" maxlength="120" value="${esc(e.role)}"></label>
          <label class="field"><span>Data angajării</span><input type="date" name="hire_date" required value="${esc(e.hire_date)}"></label>
          <label class="field"><span>Data plecării</span><input type="date" name="end_date" value="${esc(e.end_date || "")}"><small>Lăsați gol dacă lucrează în continuare.</small></label>
          <label class="field" style="grid-column:1/-1"><span>Notițe</span><textarea name="notes" rows="2" maxlength="500">${esc(e.notes)}</textarea></label>
        </div>
        <div class="form-actions"><button class="btn btn-ghost" type="button" onclick="closeModal()">Renunță</button>
        <button class="btn btn-primary" type="submit">${icon("check")}Salvează</button></div></form>`, (body) => {
        $("#edit-emp", body).addEventListener("submit", async (sub) => {
          sub.preventDefault();
          const d = formData(sub.target);
          try {
            await api(`/api/employees/${e.id}`, { method: "PUT", body: { ...d, end_date: d.end_date || null } });
            closeModal(); toast("Datele angajatului au fost salvate."); render();
          } catch (err) { toast(err.message, "err"); }
        });
      });
    }
    if (del) {
      const e = find(del, "del");
      if (await confirmBox(`Ștergeți pe ${e.name}?`, "Se șterge și tot istoricul salarial, inclusiv din lunile trecute. Dacă angajatul a plecat, mai bine completați „Data plecării” la Editează.")) {
        try { await api(`/api/employees/${e.id}`, { method: "DELETE" }); toast("Angajatul a fost șters."); render(); }
        catch (err) { toast(err.message, "err"); }
      }
    }
  });
}

/* ================= Taxe ================= */

const rateTxt = (v) => String(Number(v)).replace(".", ",");

async function renderTaxes(view) {
  const [d, sample, settings] = await Promise.all([
    api(`/api/dashboard?month=${state.month}`), api("/api/salary-preview?gross=100"), api("/api/settings"),
  ]);
  const t = d.current.taxes;
  const salaryTaxes = t.total - t.micro_tax;
  const share = d.current.revenue ? (t.total / d.current.revenue) * 100 : 0;
  const yearTaxes = d.trend.filter((m) => m.month.slice(0, 4) === state.month.slice(0, 4)).reduce((s, m) => s + m.taxes, 0);

  const explain = [
    ["CAS", "#a78bfa", "Contribuția la pensie", `${rateTxt(settings.cas_rate)}% din salariul brut, reținut din salariul angajatului.`, t.cas],
    ["CASS", "#34d399", "Contribuția la sănătate", `${rateTxt(settings.cass_rate)}% din salariul brut, reținut din salariul angajatului.`, t.cass],
    ["IV", "#22d3ee", "Impozit pe venit", `${rateTxt(settings.income_tax_rate)}% din ce rămâne după CAS și CASS.`, t.income_tax],
    ["CAM", "#fb923c", "Contribuția asiguratorie pentru muncă", `${rateTxt(settings.cam_rate)}% din brut, plătit de firmă peste salariu.`, t.cam],
    ["μ", "#fbbf24", "Impozit microîntreprindere", `${rateTxt(settings.micro_tax_rate)}% din veniturile lunii (${lei(d.current.revenue)}).`, t.micro_tax],
  ];

  view.innerHTML = `
    <section class="grid kpis">
      <article class="card glass kpi" style="--accent:#f87171"><div class="kpi-top"><span class="kpi-label"><span class="kpi-icon">${icon("taxes")}</span>Total taxe — luna</span></div>
        <div class="kpi-value" data-count="${t.total}"></div><div class="kpi-foot"><span class="sub">${esc(monthLabel(state.month))}</span></div></article>
      <article class="card glass kpi" style="--accent:#a78bfa"><div class="kpi-top"><span class="kpi-label"><span class="kpi-icon">${icon("team")}</span>Din salarii</span></div>
        <div class="kpi-value" data-count="${salaryTaxes}"></div><div class="kpi-foot"><span class="sub">CAS + CASS + impozit + CAM</span></div></article>
      <article class="card glass kpi" style="--accent:#fbbf24"><div class="kpi-top"><span class="kpi-label"><span class="kpi-icon">${icon("percent")}</span>Din fiecare 100 lei încasați</span></div>
        <div class="kpi-value" data-count="${share}" data-suffix=" lei"></div><div class="kpi-foot"><span class="sub">merg la stat ca taxe</span></div></article>
      <article class="card glass kpi" style="--accent:#22d3ee"><div class="kpi-top"><span class="kpi-label"><span class="kpi-icon">${icon("calendar")}</span>Total taxe ${state.month.slice(0, 4)}</span></div>
        <div class="kpi-value" data-count="${yearTaxes}"></div><div class="kpi-foot"><span class="sub">de la începutul anului</span></div></article>
    </section>

    <section class="grid cols-2-even mt">
      <article class="card glass">
        <div class="card-head"><div><h2>Ce taxe plătiți, pe înțeles</h2><p>${esc(monthLabel(state.month))}</p></div></div>
        <div class="tax-explain">${explain.map(([abbr, color, name, text, value]) => `
          <div class="tax-item"><span class="ic" style="background:${color}22;color:${color}">${abbr}</span>
          <div><h4>${name}</h4><p>${esc(text)}</p></div><strong>${lei(value)}</strong></div>`).join("")}
        </div>
      </article>
      <article class="card glass">
        <div class="card-head"><div><h2>Din 100 lei salariu brut</h2><p>Cât ajunge la angajat și cât la stat</p></div></div>
        <div class="split">
          <div style="flex:${sample.net};background:#22d3ee">Net ${numberFmt2.format(sample.net)}</div>
          <div style="flex:${sample.cas};background:#a78bfa">CAS ${numberFmt.format(sample.cas)}</div>
          <div style="flex:${sample.cass};background:#34d399">CASS</div>
          <div style="flex:${sample.income_tax};background:#38bdf8">Imp.</div>
        </div>
        <p class="muted" style="font-size:13px;margin:0 0 18px">Pentru fiecare 100 lei brut, angajatul primește <b style="color:var(--text)">${numberFmt2.format(sample.net)} lei</b>, iar firma mai plătește <b style="color:var(--text)">${numberFmt2.format(sample.cam)} lei</b> CAM. Costul real al unui salariu este brutul + CAM.</p>
        <div class="card-head" style="margin-bottom:8px"><div><h3>Taxe pe ultimele 12 luni</h3></div></div>
        <div class="chart-box sm"><canvas id="tax-chart"></canvas></div>
      </article>
    </section>`;

  $$("[data-count]", view).forEach((el) => countUp(el, Number(el.dataset.count), el.dataset.suffix || " lei"));
  makeChart($("#tax-chart"), {
    type: "bar",
    data: {
      labels: d.trend.map((m) => m.label),
      datasets: [
        { label: "Taxe din salarii", data: d.trend.map((m) => m.salary_taxes), backgroundColor: "#a78bfa", borderRadius: 6, stack: "t", maxBarThickness: 20 },
        { label: "Impozit micro", data: d.trend.map((m) => m.micro_tax), backgroundColor: "#fbbf24", borderRadius: 6, stack: "t", maxBarThickness: 20 },
      ],
    },
    options: {
      responsive: true, maintainAspectRatio: false,
      plugins: { legend: { position: "bottom", labels: { usePointStyle: true, pointStyle: "rectRounded" } },
        tooltip: { mode: "index", intersect: false, callbacks: { label: (ctx) => ` ${ctx.dataset.label}: ${lei(ctx.parsed.y)}` } } },
      scales: { x: { stacked: true, grid: { display: false } }, y: { stacked: true, ticks: { callback: moneyTick } } },
    },
  });
}

/* ================= Rapoarte ================= */

async function renderReports(view) {
  const d = await api(`/api/dashboard?month=${state.month}`);
  const c = d.current;
  const rows = [
    ["Venituri din vânzări", c.revenue, "var(--cyan)"], ["Cheltuieli operaționale", -c.operating_expenses],
    ["Salarii brute", -c.payroll.gross], ["CAM (plătit de firmă)", -c.taxes.cam],
    ["Impozit microîntreprindere", -c.taxes.micro_tax], ["Profit net", c.profit, c.profit >= 0 ? "var(--green)" : "var(--red)"],
    ["Impozit pe dividende (estimat)", -c.dividend_tax], ["Rămâne proprietarului", c.owner_income, "var(--gold)"],
  ];
  const year = d.trend;
  const sum = (k) => year.reduce((s, m) => s + m[k], 0);

  view.innerHTML = `
    <section class="grid cols-2-even">
      <button class="card glass export-card" id="exp-excel" type="button">
        <span class="ic" style="background:rgba(52,211,153,.15);color:var(--green)">${icon("excel")}</span>
        <div><h3>Descarcă Excel</h3><p>Raport ${esc(c.label)}: sumar, vânzări, cheltuieli, salarii — pe foi separate.</p></div>
      </button>
      <button class="card glass export-card" id="exp-pdf" type="button">
        <span class="ic" style="background:rgba(248,113,113,.15);color:var(--red)">${icon("pdf")}</span>
        <div><h3>Descarcă PDF</h3><p>Raport lunar gata de trimis contabilei sau de printat.</p></div>
      </button>
    </section>

    <section class="grid cols-2-even mt">
      <article class="card glass">
        <div class="card-head"><div><h2>Calculul lunii — ${esc(c.label)}</h2><p>De la venituri la ce vă rămâne</p></div></div>
        <div class="table-wrap"><table><tbody>
          ${rows.map(([name, value, color]) => `<tr><td${color ? ' style="font-weight:700"' : ""}>${name}</td>
            <td class="r" style="${color ? `color:${color};font-weight:800;font-size:16px` : "color:var(--muted)"}">${value < 0 ? "− " : ""}${lei(Math.abs(value), true)}</td></tr>`).join("")}
        </tbody></table></div>
      </article>
      <article class="card glass">
        <div class="card-head"><div><h2>Ultimele 12 luni</h2><p>Comparație lună de lună</p></div></div>
        <div class="table-wrap"><table>
          <thead><tr><th>Luna</th><th class="r">Venituri</th><th class="r">Costuri</th><th class="r">Profit</th><th class="r">Marjă</th></tr></thead>
          <tbody>${year.slice().reverse().map((m) => `<tr${m.month === state.month ? ' style="background:rgba(34,211,238,.07)"' : ""}>
            <td>${esc(monthLabel(m.month))}</td><td class="r">${lei(m.revenue)}</td><td class="r">${lei(m.costs)}</td>
            <td class="r" style="color:${m.profit >= 0 ? "var(--green)" : "var(--red)"};font-weight:700">${lei(m.profit)}</td>
            <td class="r">${m.revenue ? pct((m.profit / m.revenue) * 100) : "—"}</td></tr>`).join("")}</tbody>
          <tfoot><tr><td>Total</td><td class="r">${lei(sum("revenue"))}</td><td class="r">${lei(sum("costs"))}</td><td class="r">${lei(sum("profit"))}</td>
            <td class="r">${sum("revenue") ? pct((sum("profit") / sum("revenue")) * 100) : "—"}</td></tr></tfoot>
        </table></div>
      </article>
    </section>`;

  const download = (type) => {
    const a = document.createElement("a");
    a.href = `/api/export/${type}?month=${state.month}`;
    a.download = `raport-${state.month}.${type === "excel" ? "xlsx" : "pdf"}`;
    document.body.append(a); a.click(); a.remove();
    toast(`Se descarcă raportul ${type === "excel" ? "Excel" : "PDF"}…`);
  };
  $("#exp-excel").addEventListener("click", () => download("excel"));
  $("#exp-pdf").addEventListener("click", () => download("pdf"));
}

/* ================= Setări ================= */

async function renderSettings(view) {
  const [s] = await Promise.all([api("/api/settings"), loadCategories()]);
  const rateField = (name, label, hint) => `
    <label class="field"><span>${label}</span><input type="number" name="${name}" min="0" max="100" step="0.01" required value="${esc(s[name])}"><small>${hint}</small></label>`;

  view.innerHTML = `
    <section class="grid cols-2-even">
      <article class="card glass">
        <div class="card-head"><div><h2>Firma și cotele de taxe</h2><p>Dacă se schimbă legislația, actualizați cotele aici.</p></div></div>
        <form id="settings-form">
          <div class="form-grid">
            <label class="field" style="grid-column:1/-1"><span>Numele firmei</span><input name="company_name" required maxlength="120" value="${esc(s.company_name)}"></label>
            ${rateField("micro_tax_rate", "Impozit micro (%)", "din venituri")}
            ${rateField("cas_rate", "CAS (%)", "pensie, din brut")}
            ${rateField("cass_rate", "CASS (%)", "sănătate, din brut")}
            ${rateField("income_tax_rate", "Impozit pe venit (%)", "după CAS și CASS")}
            ${rateField("cam_rate", "CAM (%)", "plătit de firmă")}
            ${rateField("dividend_tax_rate", "Impozit dividende (%)", "pentru „cât îmi rămâne”")}
          </div>
          <div class="form-actions"><button class="btn btn-primary" type="submit">${icon("check")}Salvează setările</button></div>
        </form>
      </article>

      <div class="grid">
        <article class="card glass">
          <div class="card-head"><div><h2>Schimbă parola</h2><p>Doar dumneavoastră aveți acces la aplicație.</p></div></div>
          <form id="password-form" class="form-grid">
            <label class="field"><span>Parola actuală</span><input type="password" name="current" required autocomplete="current-password"></label>
            <label class="field"><span>Parola nouă</span><input type="password" name="new" required minlength="4" autocomplete="new-password"></label>
            <div class="form-actions" style="grid-column:1/-1;margin-top:0"><button class="btn" type="submit">${icon("check")}Schimbă parola</button></div>
          </form>
        </article>
        <article class="card glass">
          <div class="card-head"><div><h2>Categorii de cheltuieli</h2><p>${state.categories.length} categorii</p></div>
            <button class="btn btn-sm" id="cats-btn" type="button">${icon("edit")}Gestionează</button></div>
          <div class="toolbar">${state.categories.map((c) => `<span class="tag"><span class="sw" style="background:${esc(c.color)}"></span>${esc(c.name)}</span>`).join("")}</div>
        </article>
        <article class="card glass" style="border-color:rgba(248,113,113,.3)">
          <div class="card-head"><div><h2>Date demonstrative</h2><p>Înlocuiește TOATE datele cu un an de activitate fictivă. Util pentru prezentări.</p></div></div>
          <button class="btn btn-danger" id="demo-btn" type="button">${icon("alert")}Reîncarcă datele demo</button>
        </article>
      </div>
    </section>`;

  $("#settings-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    const d = formData(e.target);
    const body = { company_name: d.company_name };
    ["micro_tax_rate", "cas_rate", "cass_rate", "income_tax_rate", "cam_rate", "dividend_tax_rate"].forEach((k) => { body[k] = Number(d[k]); });
    try {
      await api("/api/settings", { method: "PUT", body });
      $("#brand-name").textContent = body.company_name;
      toast("Setările au fost salvate.");
    } catch (err) { toast(err.message, "err"); }
  });
  $("#password-form").addEventListener("submit", async (e) => {
    e.preventDefault();
    try {
      await api("/api/auth/change-password", { method: "POST", body: formData(e.target) });
      e.target.reset(); toast("Parola a fost schimbată.");
    } catch (err) { toast(err.message, "err"); }
  });
  $("#cats-btn").addEventListener("click", () => openCategories(render));
  $("#demo-btn").addEventListener("click", async () => {
    if (await confirmBox("Reîncărcați datele demo?", "Toate vânzările, cheltuielile și angajații actuali vor fi înlocuiți cu date fictive.", "Da, înlocuiește")) {
      try { await api("/api/demo", { method: "POST" }); toast("Datele demo au fost încărcate."); location.hash = "#dashboard"; }
      catch (err) { toast(err.message, "err"); }
    }
  });
}

window.closeModal = closeModal;
boot();
