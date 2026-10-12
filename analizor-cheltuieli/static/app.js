// Analizor de cheltuieli – UI. Toate calculele de afișare sunt locale (gratuite).
const $ = (s) => document.querySelector(s);
const COLORS = {
  "Mâncare": "#3d5afe", "Transport": "#00a19a", "Utilități": "#f59e0b", "Locuință": "#8b5cf6",
  "Sănătate": "#ef4444", "Divertisment": "#ec4899", "Shopping": "#0ea5e9", "Călătorii": "#14b8a6",
  "Venituri": "#13854e", "Altele": "#94a3b8",
};
const MONTHS = ["", "ianuarie", "februarie", "martie", "aprilie", "mai", "iunie", "iulie", "august",
  "septembrie", "octombrie", "noiembrie", "decembrie"];
const SUGGESTIONS = [
  "Cât am cheltuit pe mâncare în martie?",
  "Pe ce categorii am cheltuit în martie?",
  "Care a fost cea mai mare cheltuială?",
  "Cât am încasat în martie?",
  "Cât am plătit cash?",
  "Câte tranzacții am făcut în euro?",
];

const state = {
  txs: [], rates: { RON: 1, EUR: 5.25, USD: 4.4 }, categories: [], sources: {},
  cur: "RON", month: "", curFilter: "", srcFilter: "", catFilter: "", search: "",
  showDup: false, sort: { key: "date", asc: true }, highlight: null,
};

// ---------------------------------------------------------------- utilitare
const conv = (t, to = state.cur) => (t.amount * state.rates[t.currency]) / state.rates[to];
const fmt = (v, cur = state.cur) =>
  new Intl.NumberFormat("ro-RO", { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(v) + " " + cur;
const monthLabel = (ym) => (ym ? `${MONTHS[+ym.slice(5)]} ${ym.slice(0, 4)}` : "toate lunile");
const fmtDate = (iso) => iso.split("-").reverse().join(".");
const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const isExpense = (t) => t.direction === "debit" && t.category !== "Venituri";

function toast(msg) {
  const el = $("#toast");
  el.textContent = msg;
  el.classList.add("show");
  clearTimeout(toast.t);
  toast.t = setTimeout(() => el.classList.remove("show"), 2600);
}

async function api(path, opts = {}) {
  const r = await fetch(path, opts);
  const data = await r.json().catch(() => ({}));
  if (!r.ok) throw new Error(data.detail || `Eroare ${r.status}`);
  return data;
}

// ---------------------------------------------------------------- încărcare
async function init() {
  const st = await api("/api/status");
  Object.assign(state, { rates: st.rates, categories: st.categories, sources: st.sources });
  renderStatus(st);
  const opts = st.categories.map((c) => `<option>${c}</option>`).join("");
  $("#catFilter").insertAdjacentHTML("beforeend", opts);
  $("#manualCat").insertAdjacentHTML("beforeend", opts);
  $("#suggestions").innerHTML = SUGGESTIONS.map((s) => `<button class="chip" type="button">${s}</button>`).join("");
  const { transactions } = await api("/api/transactions");
  setTxs(transactions, true);
}

function renderStatus(st) {
  const el = $("#aiStatus");
  el.textContent = st.ai_enabled ? `AI activ · ${st.model}` : "AI inactiv · mod local";
  el.classList.toggle("off", !st.ai_enabled);
  el.title = st.ai_enabled ? "" : "Setează ANTHROPIC_API_KEY (în .env) pentru categorii AI, bonuri foto și întrebări libere.";
  const u = st.usage;
  $("#aiCost").textContent = `${u.calls} apeluri AI · ~$${u.cost_usd.toFixed(4)}`;
}
const refreshStatus = () => api("/api/status").then(renderStatus).catch(() => {});

function setTxs(txs, pickMonth = false) {
  state.txs = txs;
  const months = [...new Set(txs.map((t) => t.date.slice(0, 7)))].sort();
  if (pickMonth || (state.month && !months.includes(state.month))) {
    // luna implicită = luna cu cele mai multe tranzacții (nu 1–2 tranzacții de la margine)
    const counts = {};
    txs.forEach((t) => (counts[t.date.slice(0, 7)] = (counts[t.date.slice(0, 7)] || 0) + 1));
    state.month = months.sort((a, b) => counts[b] - counts[a])[0] || "";
    months.sort();
  }
  $("#monthSel").innerHTML = `<option value="">Toate lunile</option>` +
    months.map((m) => `<option value="${m}" ${m === state.month ? "selected" : ""}>${monthLabel(m)}</option>`).join("");
  render();
}

// ---------------------------------------------------------------- randare
function filtered({ ignoreCat = false } = {}) {
  const s = state.search.toLowerCase();
  return state.txs.filter((t) =>
    (state.showDup || !t.duplicate_of) &&
    (!state.month || t.date.startsWith(state.month)) &&
    (!state.curFilter || t.currency === state.curFilter) &&
    (!state.srcFilter || t.source === state.srcFilter) &&
    (ignoreCat || !state.catFilter || t.category === state.catFilter) &&
    (!s || t.description.toLowerCase().includes(s)));
}

function render() {
  renderKpis();
  renderChart();
  renderTable();
}

function renderKpis() {
  const rows = filtered().filter((t) => !t.duplicate_of);
  const spend = rows.filter(isExpense), inc = rows.filter((t) => t.direction === "credit");
  const sSum = spend.reduce((a, t) => a + conv(t), 0), iSum = inc.reduce((a, t) => a + conv(t), 0);
  $("#kSpend").textContent = fmt(sSum);
  $("#kSpendN").textContent = `${spend.length} tranzacții · ${monthLabel(state.month)}`;
  $("#kIncome").textContent = fmt(iSum);
  $("#kIncomeN").textContent = `${inc.length} încasări (nu intră la cheltuieli)`;
  const net = $("#kNet");
  net.textContent = fmt(iSum - sSum);
  net.className = iSum - sSum >= 0 ? "pos" : "neg";
  $("#kDup").textContent = state.txs.filter((t) => t.duplicate_of).length;
}

function renderChart() {
  const rows = filtered({ ignoreCat: true }).filter((t) => !t.duplicate_of && isExpense(t));
  const by = {};
  rows.forEach((t) => (by[t.category] = (by[t.category] || 0) + conv(t)));
  const items = Object.entries(by).sort((a, b) => b[1] - a[1]);
  const total = items.reduce((a, [, v]) => a + v, 0);
  const max = items.length ? items[0][1] : 1;
  $("#chartTitle").textContent = `Cheltuieli pe categorii · ${monthLabel(state.month)}`;
  $("#chart").innerHTML = items.length
    ? items.map(([c, v]) => `
      <div class="bar ${state.catFilter === c ? "sel" : ""}" data-cat="${esc(c)}" title="Filtrează: ${esc(c)}">
        <span class="name"><i class="dot" style="background:${COLORS[c]}"></i>${esc(c)}</span>
        <span class="track"><span class="fill" style="width:${(v / max) * 100}%;background:${COLORS[c]}"></span></span>
        <span class="val">${fmt(v)}<small>${((v / total) * 100).toFixed(0)}%</small></span>
      </div>`).join("")
    : `<div class="empty">Nu există cheltuieli pentru selecția curentă.</div>`;
}

function renderTable() {
  let rows = filtered();
  if (state.highlight) rows = rows.filter((t) => state.highlight.ids.has(t.id));
  const { key, asc } = state.sort;
  const val = (t) => (key === "conv" ? conv(t) : String(t[key] ?? "").toLowerCase());
  rows.sort((a, b) => (val(a) > val(b) ? 1 : val(a) < val(b) ? -1 : 0) * (asc ? 1 : -1));
  document.querySelectorAll("th[data-sort]").forEach((th) => {
    th.classList.toggle("sorted", th.dataset.sort === key);
    th.classList.toggle("asc", th.dataset.sort === key && asc);
  });

  const catOpts = (sel) => state.categories.map((c) => `<option ${c === sel ? "selected" : ""}>${c}</option>`).join("");
  $("#txTable tbody").innerHTML = rows.map((t) => {
    const income = t.direction === "credit";
    const cls = [income && "income", t.duplicate_of && "dup", state.highlight && "hl"].filter(Boolean).join(" ");
    const sign = income ? "+" : "−";
    const orig = t.currency !== state.cur ? `${sign}${fmt(t.amount, t.currency)}` : "";
    const dupNote = t.duplicate_of ? `<span class="by">duplicat al plății din CSV – exclus din totaluri</span>` : "";
    return `<tr class="${cls}" data-id="${t.id}">
      <td class="date">${fmtDate(t.date)}</td>
      <td>${esc(t.description)}${dupNote}</td>
      <td class="num amt">${sign}${fmt(conv(t))}</td>
      <td class="num" style="color:var(--muted)">${orig || t.currency}</td>
      <td><select class="cat" aria-label="Categorie">${catOpts(t.category)}</select>
          <span class="by">${esc(t.category_by || "")}</span></td>
      <td><span class="badge">${esc(state.sources[t.source] || t.source)}</span></td>
      <td><button class="del" title="Șterge">×</button></td>
    </tr>`;
  }).join("");
  $("#txCount").textContent = `(${rows.length})`;
  $("#empty").hidden = state.txs.length > 0;
  $("#highlightBar").hidden = !state.highlight;
  if (state.highlight) $("#highlightText").textContent = state.highlight.label;
}

// ---------------------------------------------------------------- upload
async function uploadFiles(fileList) {
  if (!fileList.length) return;
  const fd = new FormData();
  [...fileList].forEach((f) => fd.append("files", f));
  const drop = $("#drop");
  drop.classList.add("busy");
  drop.querySelector("strong").textContent = "Se procesează…";
  try {
    const { reports, transactions } = await api("/api/upload", { method: "POST", body: fd });
    $("#uploadReports").insertAdjacentHTML("afterbegin", reports.map(reportHtml).join(""));
    setTxs(transactions, true);
    const added = reports.reduce((a, r) => a + r.added, 0);
    toast(added ? `Am adăugat ${added} tranzacții` : "Nicio tranzacție nouă");
  } catch (e) {
    toast(e.message);
  } finally {
    drop.classList.remove("busy");
    drop.querySelector("strong").textContent = "Trage fișierele aici";
    $("#fileInput").value = "";
    refreshStatus();
  }
}

function reportHtml(r) {
  if (r.error) return `<div class="report err"><b>${esc(r.file)}</b>${esc(r.error)}</div>`;
  const c = r.categorii || {};
  const how = [c.ai && `${c.ai} categorisite de AI`, c.cache && `${c.cache} din cache (gratuit)`,
    c.reguli && `${c.reguli} prin reguli locale`].filter(Boolean).join(" · ");
  const warn = [...(r.warnings || []), c.ai_error].filter(Boolean);
  return `<div class="report ${warn.length ? "warn" : ""}"><b>${esc(r.file)}</b>
    ${r.added} tranzacții · ${esc(state.sources[r.source] || "")}<small>${esc(how)}</small>
    ${warn.map((w) => `<small>⚠ ${esc(w)}</small>`).join("")}</div>`;
}

// ---------------------------------------------------------------- întrebări
async function ask(question) {
  question = question.trim();
  if (!question) return;
  const log = $("#chatLog");
  log.insertAdjacentHTML("beforeend", `<div class="msg q">${esc(question)}</div>`);
  const pending = document.createElement("div");
  pending.className = "msg a";
  pending.textContent = "Mă gândesc…";
  log.appendChild(pending);
  log.scrollTop = log.scrollHeight;
  $("#question").value = "";
  $("#askBtn").disabled = true;
  try {
    const r = await api("/api/ask", {
      method: "POST", headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, display_currency: state.cur }),
    });
    const modeLbl = { AI: "interpretat de AI, calculat local", cache: "din cache (fără cost AI)", local: "interpretare locală, fără AI" }[r.mode] || "";
    const q = r.query || {};
    const big = r.total !== undefined && r.count && ["suma", "pe_categorii", "lista", "numar"].includes(q.operatie)
      ? `<span class="big">${fmt(r.total, r.currency)}</span>` : "";
    pending.innerHTML = `${big}${esc(r.answer)}
      <span class="meta">${q.interpretare ? "„" + esc(q.interpretare) + "” · " : ""}${modeLbl}${r.warning ? " · " + esc(r.warning) : ""}</span>
      ${r.ids && r.ids.length ? `<span class="link">Vezi cele ${r.ids.length} tranzacții</span>` : ""}`;
    const link = pending.querySelector(".link");
    if (link) link.onclick = () => showHighlight(r.ids, question);
  } catch (e) {
    pending.textContent = "Eroare: " + e.message;
  } finally {
    $("#askBtn").disabled = false;
    log.scrollTop = log.scrollHeight;
    refreshStatus();
  }
}

function showHighlight(ids, question) {
  // Afișăm exact rândurile folosite la calcul, indiferent de filtrele curente.
  Object.assign(state, { month: "", curFilter: "", srcFilter: "", catFilter: "", search: "" });
  $("#monthSel").value = ""; $("#curFilter").value = ""; $("#srcFilter").value = ""; $("#catFilter").value = ""; $("#search").value = "";
  state.highlight = { ids: new Set(ids), label: `Tranzacțiile folosite pentru: „${question}”` };
  render();
  $("#txTable").scrollIntoView({ behavior: "smooth", block: "start" });
}

// ---------------------------------------------------------------- export
function exportCsv() {
  const rows = filtered();
  const head = ["Data", "Descriere", "Suma", "Moneda", `Suma ${state.cur}`, "Tip", "Categorie", "Sursa", "Duplicat"];
  const lines = rows.map((t) => [t.date, t.description, t.amount.toFixed(2), t.currency, conv(t).toFixed(2),
    t.direction === "credit" ? "incasare" : "cheltuiala", t.category, state.sources[t.source], t.duplicate_of ? "da" : ""]
    .map((v) => `"${String(v).replace(/"/g, '""')}"`).join(";"));
  const blob = new Blob(["﻿" + [head.join(";"), ...lines].join("\n")], { type: "text/csv" });
  const a = Object.assign(document.createElement("a"), { href: URL.createObjectURL(blob), download: `cheltuieli_${state.month || "toate"}.csv` });
  a.click();
  URL.revokeObjectURL(a.href);
}

// ---------------------------------------------------------------- evenimente
const drop = $("#drop");
$("#fileInput").addEventListener("change", (e) => uploadFiles(e.target.files));
["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.remove("over"); }));
drop.addEventListener("drop", (e) => uploadFiles(e.dataTransfer.files));
drop.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") $("#fileInput").click(); });

$("#displayCur").addEventListener("click", (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  state.cur = b.dataset.v;
  document.querySelectorAll("#displayCur button").forEach((x) => x.classList.toggle("on", x === b));
  render();
});
const bind = (sel, key, ev = "change") => $(sel).addEventListener(ev, (e) => { state[key] = e.target.value; state.highlight = null; render(); });
bind("#monthSel", "month"); bind("#curFilter", "curFilter"); bind("#srcFilter", "srcFilter");
bind("#catFilter", "catFilter"); bind("#search", "search", "input");
$("#showDup").addEventListener("change", (e) => { state.showDup = e.target.checked; render(); });
$("#clearHighlight").addEventListener("click", () => { state.highlight = null; render(); });

$("#chart").addEventListener("click", (e) => {
  const bar = e.target.closest(".bar");
  if (!bar) return;
  state.catFilter = state.catFilter === bar.dataset.cat ? "" : bar.dataset.cat;
  $("#catFilter").value = state.catFilter;
  render();
});

document.querySelectorAll("th[data-sort]").forEach((th) => th.addEventListener("click", () => {
  const k = th.dataset.sort;
  state.sort = { key: k, asc: state.sort.key === k ? !state.sort.asc : k !== "conv" };
  renderTable();
}));

$("#txTable").addEventListener("change", async (e) => {
  if (!e.target.matches("select.cat")) return;
  const id = e.target.closest("tr").dataset.id;
  try {
    const tx = await api(`/api/transactions/${id}`, {
      method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ category: e.target.value }),
    });
    Object.assign(state.txs.find((t) => t.id === id), tx);
    render();
    toast("Categorie salvată – va fi reținută și pentru viitor");
  } catch (err) { toast(err.message); }
});
$("#txTable").addEventListener("click", async (e) => {
  if (!e.target.matches(".del")) return;
  const id = e.target.closest("tr").dataset.id;
  await api(`/api/transactions/${id}`, { method: "DELETE" });
  const { transactions } = await api("/api/transactions");
  setTxs(transactions);
});

$("#resetBtn").addEventListener("click", async () => {
  if (!confirm("Ștergi toate tranzacțiile încărcate?")) return;
  await api("/api/transactions", { method: "DELETE" });
  $("#uploadReports").innerHTML = "";
  $("#chatLog").innerHTML = "";
  state.highlight = null;
  setTxs([], true);
});
$("#exportBtn").addEventListener("click", exportCsv);

$("#askForm").addEventListener("submit", (e) => { e.preventDefault(); ask($("#question").value); });
$("#suggestions").addEventListener("click", (e) => { if (e.target.matches(".chip")) ask(e.target.textContent); });

$("#manualForm").addEventListener("submit", async (e) => {
  e.preventDefault();
  const body = Object.fromEntries(new FormData(e.target));
  try {
    await api("/api/transactions", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
    e.target.reset();
    const { transactions } = await api("/api/transactions");
    setTxs(transactions);
    toast("Tranzacție adăugată");
    refreshStatus();
  } catch (err) { toast(err.message); }
});

init().catch((e) => toast("Nu mă pot conecta la server: " + e.message));
