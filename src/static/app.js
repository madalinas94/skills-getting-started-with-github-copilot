const $ = (sel) => document.querySelector(sel);
const FIELD_LABELS = { title: "titlu", problem: "problema", description: "ce face", audience: "cine o folosește" };
// Răspunsul despre „problema” rezolvată se adaugă la descriere
const TARGET_FIELD = { problem: "description" };
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

let auth = null;
try { auth = JSON.parse(localStorage.getItem("cutia-auth")); } catch (_) { auth = null; }

let questions = [];
let proposals = [];
let lastMissing = [];
let lastStats = {};

// ================================================================ helpers

async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(auth ? { Authorization: `Bearer ${auth.token}` } : {}),
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && auth) logout();
  if (!res.ok) {
    const detail = Array.isArray(data.detail) ? "Verifică datele introduse." : data.detail;
    throw new Error(detail || "A apărut o eroare.");
  }
  return data;
}

function el(tag, attrs = {}, ...children) {
  const node = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === "class") node.className = v;
    else if (k === "style") node.style.cssText = v;
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) node.setAttribute(k, v === true ? "" : v);
  }
  for (const child of children.flat()) {
    if (child == null || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(child));
  }
  return node;
}

const sleep = (ms) => new Promise((r) => setTimeout(r, reducedMotion ? 0 : ms));

function timeAgo(iso) {
  if (!iso) return "";
  const s = (Date.now() - new Date(iso).getTime()) / 1000;
  if (s < 60) return "acum";
  if (s < 3600) return `acum ${Math.floor(s / 60)} min`;
  if (s < 86400) return `acum ${Math.floor(s / 3600)} h`;
  return new Date(iso).toLocaleDateString("ro-RO", { day: "numeric", month: "short" });
}

function hue(name) {
  let h = 0;
  for (const c of name || "") h = (h * 31 + c.charCodeAt(0)) % 360;
  return h;
}

function avatar(name, small = true) {
  if (!name || name === "Anonim") return el("span", { class: `avatar anon ${small ? "sm" : ""}` }, "?");
  const initials = name.trim().split(/\s+/).slice(0, 2).map((w) => w[0]).join("").toUpperCase();
  return el("span", { class: `avatar ${small ? "sm" : ""}`, style: `--h:${hue(name)}` }, initials);
}

let toastTimer;
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  t.style.animation = "none"; void t.offsetWidth; t.style.animation = "";
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.add("hidden"), 2600);
}

const isTrainer = () => auth && auth.role === "trainer";

// ================================================================ confetti

function confetti() {
  if (reducedMotion) return;
  const canvas = $("#confetti");
  const ctx = canvas.getContext("2d");
  const dpr = window.devicePixelRatio || 1;
  canvas.width = innerWidth * dpr;
  canvas.height = innerHeight * dpr;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  const colors = ["#8b5cf6", "#22d3ee", "#f472b6", "#34d399", "#fbbf24"];
  const parts = Array.from({ length: 140 }, () => ({
    x: innerWidth / 2 + (Math.random() - .5) * 120,
    y: innerHeight * .35,
    vx: (Math.random() - .5) * 14,
    vy: Math.random() * -13 - 4,
    r: Math.random() * 6 + 4,
    rot: Math.random() * 6,
    vr: (Math.random() - .5) * .3,
    c: colors[Math.floor(Math.random() * colors.length)],
  }));
  const start = performance.now();
  (function frame(t) {
    ctx.clearRect(0, 0, innerWidth, innerHeight);
    for (const p of parts) {
      p.vy += .35; p.vx *= .99; p.x += p.vx; p.y += p.vy; p.rot += p.vr;
      ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.rot);
      ctx.fillStyle = p.c; ctx.fillRect(-p.r / 2, -p.r / 4, p.r, p.r / 2);
      ctx.restore();
    }
    if (t - start < 2600) requestAnimationFrame(frame);
    else ctx.clearRect(0, 0, innerWidth, innerHeight);
  })(start);
}

// ================================================================ theme

$("#theme-btn").addEventListener("click", () => {
  const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem("cutia-theme", next); } catch (_) {}
});

// ================================================================ login terminal

const TERM_SCRIPT = [
  ["t-prompt", "$ ", "t-cmd", 'claude "vreau o aplicație pentru clasa mea"'],
  ["t-ai", "› ", "t-ai", "citesc ideea…"],
  ["t-q", "? ", "t-q", "Cine o va folosi?"],
  ["t-prompt", "$ ", "t-cmd", "studenții și trainerul"],
  ["t-ai", "› ", "t-ai", "retușez textul, totul e clar"],
  ["t-ok", "✓ ", "t-ok", "propunere trimisă · ora următoare 🚀"],
];

let terminalRunning = false;
async function runTerminal() {
  if (terminalRunning) return;
  terminalRunning = true;
  const body = $("#term-body");
  while (!$("#login-view").classList.contains("hidden")) {
    body.replaceChildren();
    for (const [pc, prefix, tc, text] of TERM_SCRIPT) {
      const span = el("span", { class: tc });
      const cursor = el("span", { class: "cursor" });
      body.append(el("div", {}, el("span", { class: pc }, prefix), span, cursor));
      const typed = tc === "t-cmd" && !reducedMotion;
      if (typed) {
        for (let i = 1; i <= text.length; i++) {
          span.textContent = text.slice(0, i);
          await sleep(28 + Math.random() * 40);
        }
      } else {
        span.textContent = text;
      }
      await sleep(typed ? 350 : 550);
      cursor.remove();
    }
    body.lastChild.append(el("span", { class: "cursor" }));
    if (reducedMotion) break;
    await sleep(3500);
  }
  terminalRunning = false;
}

// ================================================================ auth

document.querySelectorAll('input[name="role"]').forEach((r) =>
  r.addEventListener("change", () => {
    const trainer = document.querySelector('input[name="role"]:checked').value === "trainer";
    $("#code-field").classList.toggle("hidden", !trainer);
    $("#password-field").classList.toggle("hidden", trainer);
  })
);

$("#login-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  $("#login-error").textContent = "";
  const role = document.querySelector('input[name="role"]:checked').value;
  try {
    auth = await api("/api/login", {
      method: "POST",
      body: {
        name: $("#login-name").value,
        role,
        password: $("#login-password").value,
        code: $("#login-code").value,
      },
    });
    try { localStorage.setItem("cutia-auth", JSON.stringify(auth)); } catch (_) {}
    $("#login-password").value = "";
    $("#login-code").value = "";
    start();
  } catch (err) {
    $("#login-error").textContent = err.message;
  }
});

$("#logout-btn").addEventListener("click", logout);

function logout() {
  auth = null;
  try { localStorage.removeItem("cutia-auth"); } catch (_) {}
  $("#app-view").classList.add("hidden");
  $("#user-box").classList.add("hidden");
  $("#login-view").classList.remove("hidden");
  runTerminal();
}

function greeting() {
  const h = new Date().getHours();
  return h < 11 ? "Bună dimineața" : h < 18 ? "Salut" : "Bună seara";
}

async function start() {
  try {
    await api("/api/me");
  } catch (_) {
    logout();
    return;
  }
  $("#login-view").classList.add("hidden");
  $("#app-view").classList.remove("hidden");
  $("#user-box").classList.remove("hidden");
  $("#user-name").textContent = auth.name;
  const av = avatar(auth.name, false);
  av.id = "user-avatar";
  $("#user-avatar").replaceWith(av);
  $("#user-role").textContent = isTrainer() ? "trainer" : "student";
  const first = auth.name.split(/\s+/)[0];
  $("#greet-eyebrow").textContent = isTrainer() ? "// panoul trainerului" : "// clasa de vibe coding";
  $("#greet-title").textContent = `${greeting()}, ${first} 👋`;
  document.querySelectorAll(".student-only").forEach((n) => n.classList.toggle("hidden", isTrainer()));
  $("#questions-title").textContent = isTrainer() ? "Întrebările clasei" : "Întrebările mele";
  document.querySelector('.tab[data-tab="questions"]').click();
  lastStats = {};
  refresh();
}

// ================================================================ tabs & shortcuts

document.querySelectorAll(".tab").forEach((tab) =>
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t === tab));
    document.querySelectorAll(".tab-panel").forEach((p) =>
      p.classList.toggle("hidden", p.id !== `tab-${tab.dataset.tab}`)
    );
  })
);

document.addEventListener("keydown", (e) => {
  const typing = /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName);
  if (e.key === "/" && !typing && auth) {
    e.preventDefault();
    const panel = document.querySelector(".tab-panel:not(.hidden)");
    if (panel) panel.querySelector('input[type="search"]').focus();
  }
  // Ctrl/Cmd + Enter trimite formularul în care scrii
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && typing) {
    const form = document.activeElement.closest("form");
    if (form) { e.preventDefault(); form.requestSubmit(); }
  }
});

// ================================================================ stats

function renderStats() {
  const answered = questions.filter((q) => q.answer).length;
  const stats = isTrainer()
    ? [
        ["open", questions.length - answered, "fără răspuns", true],
        ["answered", answered, "răspunse"],
        ["proposals", proposals.length, "propuneri"],
        ["chosen", proposals.filter((p) => p.chosen).length, "alese"],
      ]
    : [
        ["mine", questions.length, "întrebările mele"],
        ["answered", answered, "cu răspuns", answered > 0],
        ["proposals", proposals.length, "propuneri în clasă"],
        ["votes", proposals.filter((p) => p.voted).length, "voturile tale"],
      ];

  $("#stats").replaceChildren(...stats.map(([key, value, label, hl]) => {
    const b = el("b", {}, String(lastStats[key] ?? 0));
    countUp(b, lastStats[key] ?? 0, value);
    lastStats[key] = value;
    return el("div", { class: `stat ${hl ? "hl" : ""}` }, b, el("span", {}, label));
  }));
}

function countUp(node, from, to) {
  if (from === to || reducedMotion) { node.textContent = to; return; }
  const t0 = performance.now();
  (function step(t) {
    const k = Math.min(1, (t - t0) / 600);
    node.textContent = Math.round(from + (to - from) * (1 - Math.pow(1 - k, 3)));
    if (k < 1) requestAnimationFrame(step);
  })(t0);
}

// ================================================================ questions

async function loadCategories() {
  const cats = await api("/api/categories");
  $("#question-category").replaceChildren(...cats.map((c) => el("option", { value: c }, c)));
}

$("#question-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/api/questions", {
      method: "POST",
      body: {
        text: $("#question-text").value,
        category: $("#question-category").value,
        anonymous: $("#question-anon").checked,
      },
    });
    $("#question-text").value = "";
    toast("📨 Întrebarea a ajuns la trainer.");
    loadQuestions();
  } catch (err) {
    toast(err.message);
  }
});

$("#question-search").addEventListener("input", renderQuestions);
$("#question-filter").addEventListener("change", renderQuestions);

async function loadQuestions() {
  questions = await api("/api/questions");
  renderQuestions();
  renderStats();
}

function renderQuestions() {
  const term = $("#question-search").value.trim().toLowerCase();
  const filter = $("#question-filter").value;
  const shown = questions.filter((q) => {
    if (filter === "open" && q.answer) return false;
    if (filter === "answered" && !q.answer) return false;
    return !term || `${q.text} ${q.answer || ""} ${q.author}`.toLowerCase().includes(term);
  });

  const open = questions.filter((q) => !q.answer).length;
  const badge = $("#q-badge");
  badge.textContent = open;
  badge.classList.toggle("hidden", !isTrainer() || open === 0);

  const list = $("#questions-list");
  if (!shown.length) {
    list.replaceChildren(el("div", { class: "empty" },
      questions.length ? "// nimic nu se potrivește căutării" :
      isTrainer() ? "// liniște în clasă. Nicio întrebare încă." :
      "// nicio întrebare încă. Nu există întrebări proaste 🙂"));
    return;
  }
  list.replaceChildren(...shown.map((q, i) => {
    const card = questionCard(q);
    card.style.animationDelay = `${Math.min(i, 8) * 40}ms`;
    return card;
  }));
}

function questionCard(q) {
  const head = el("div", { class: "item-head" },
    isTrainer() ? avatar(q.author) : null,
    isTrainer() ? el("strong", {}, q.author) : null,
    el("span", { class: "tag" }, `#${q.category.toLowerCase()}`),
    !isTrainer() && q.anonymous ? el("span", { class: "tag" }, "anonim") : null,
    el("span", {}, timeAgo(q.created_at)),
    el("span", { class: `right status ${q.answer ? "ok" : "open"}` }, q.answer ? "✓ răspuns" : "în așteptare"),
  );
  const card = el("article", { class: "item" }, head, el("p", { class: "item-text" }, q.text));

  if (q.answer) {
    card.append(el("div", { class: "answer" },
      el("div", { class: "label" }, "🧑‍🏫 trainer", el("span", { class: "muted" }, `· ${timeAgo(q.answered_at)}`)),
      el("div", { class: "item-text" }, q.answer)));
  } else if (!isTrainer()) {
    card.append(el("div", { class: "waiting" }, "trainerul încă n-a răspuns"));
  }

  if (isTrainer()) {
    const area = el("textarea", { rows: 3, placeholder: "Scrie răspunsul…  (Ctrl ↵ trimite)" });
    area.value = q.answer || "";
    const form = el("form", { class: "answer-form hidden" }, area,
      el("div", { class: "row end" }, el("button", { type: "submit", class: "primary small" }, "Trimite răspunsul")));
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        await api(`/api/questions/${q.id}/answer`, { method: "POST", body: { text: area.value } });
        toast("✅ Răspuns trimis.");
        loadQuestions();
      } catch (err) { toast(err.message); }
    });
    const toggle = el("button", { class: "small", onclick: () => { form.classList.toggle("hidden"); area.focus(); } },
      q.answer ? "✎ Editează răspunsul" : "↩ Răspunde");
    card.append(el("div", { class: "actions" }, toggle), form);
  }
  return card;
}

// ================================================================ proposals: wizard

function setStep(n) {
  document.querySelectorAll("#pipeline li").forEach((li) => {
    const s = Number(li.dataset.step);
    li.classList.toggle("active", s === n);
    li.classList.toggle("dark", s === n && (s === 2 || s === 5));
    li.classList.toggle("done", s < n);
  });
}

function showStage(id) {
  ["#proposal-form", "#ai-thinking", "#refine-result"].forEach((s) => $(s).classList.toggle("hidden", s !== id));
}

function draft() {
  return {
    title: $("#p-title").value,
    description: $("#p-description").value,
    audience: $("#p-audience").value,
  };
}

const AI_LOG = [
  "citesc ciorna…",
  "verific titlul",
  "verific ce problemă rezolvă și pentru cine",
  "verific ce poate face un utilizator",
  "retușez textul (fără să inventez funcții)",
];

async function runRefine(body) {
  $("#proposal-error").textContent = "";
  showStage("#ai-thinking");
  setStep(2);
  const log = $("#ai-log");
  log.replaceChildren(el("div", {}, el("span", { class: "t-prompt" }, "$ "), "claude refine propunere.json"));

  let done = false;
  const request = api("/api/proposals/refine", { method: "POST", body }).finally(() => { done = true; });
  request.catch(() => {}); // eroarea e tratată mai jos, după animație
  for (const line of AI_LOG) {
    log.append(el("div", { class: "t-ai" }, "› " + line));
    await sleep(380);
  }
  const cursor = el("span", { class: "cursor" });
  if (!done) log.append(el("div", { class: "t-dim" }, "› aștept răspunsul de la Claude ", cursor));

  try {
    const r = await request;
    cursor.remove();
    const n = (r.missing || []).length;
    log.append(el("div", { class: "t-ok" }, `✓ gata · ${n ? n + (n === 1 ? " întrebare" : " întrebări") : "totul e clar"}`));
    await sleep(500);
    showRefined(r);
  } catch (err) {
    showStage("#proposal-form");
    setStep(1);
    $("#proposal-error").textContent = err.message;
  }
}

async function typewrite(node, text) {
  node.textContent = "";
  if (reducedMotion) { node.textContent = text; return; }
  for (let i = 0; i < text.length; i += 2) {
    node.textContent = text.slice(0, i + 2);
    await new Promise((r) => setTimeout(r, 12));
  }
}

function showRefined(r) {
  showStage("#refine-result");
  typewrite($("#understood-text"), r.understood || "Încă prea puțin ca să înțeleg ideea. Răspunde la întrebările de mai jos.");
  $("#refine-notes").textContent = (r.engine === "claude" ? "Claude · " : "mod local · ") + (r.notes || "");
  $("#f-title").value = r.title || "";
  $("#f-description").value = r.description || "";
  $("#f-audience").value = r.audience || "";
  $("#approve").checked = false;
  $("#submit-proposal").disabled = true;

  lastMissing = r.missing || [];
  $("#missing-box").classList.toggle("hidden", lastMissing.length === 0);
  $("#missing-list").replaceChildren(...lastMissing.map((m, i) => {
    const ta = el("textarea", { rows: 2, "data-missing": i, placeholder: "Răspunsul tău…", "aria-label": m.question });
    ta.addEventListener("input", () => setStep(4), { once: true });
    return el("div", { class: "q-bubble" },
      el("div", { class: "q" }, el("small", {}, `🤖 ${FIELD_LABELS[m.field] || m.field}`), m.question),
      ta);
  }));
  setStep(lastMissing.length ? 3 : 4);
}

$("#proposal-form").addEventListener("submit", (e) => {
  e.preventDefault();
  runRefine(draft());
});

$("#apply-answers").addEventListener("click", (e) => {
  e.preventDefault();
  // Pornim de la varianta retușată și adăugăm răspunsurile la câmpurile cerute
  const body = {
    title: $("#f-title").value,
    description: $("#f-description").value,
    audience: $("#f-audience").value,
  };
  document.querySelectorAll("[data-missing]").forEach((ta) => {
    const answer = ta.value.trim();
    if (!answer) return;
    const asked = lastMissing[Number(ta.dataset.missing)].field;
    const field = TARGET_FIELD[asked] || asked;
    body[field] = body[field] ? `${body[field]} ${answer}` : answer;
  });
  // Ținem ciorna sincronizată, ca „Înapoi” să nu piardă detaliile
  $("#p-title").value = body.title;
  $("#p-description").value = body.description;
  $("#p-audience").value = body.audience;
  runRefine(body);
});

$("#approve").addEventListener("change", () => {
  $("#submit-proposal").disabled = !$("#approve").checked;
  setStep($("#approve").checked ? 5 : 4);
});

["#f-title", "#f-description", "#f-audience"].forEach((id) =>
  $(id).addEventListener("input", () => {
    // Orice modificare cere o nouă aprobare
    $("#approve").checked = false;
    $("#submit-proposal").disabled = true;
    setStep(4);
  })
);

$("#back-edit").addEventListener("click", (e) => {
  e.preventDefault();
  showStage("#proposal-form");
  setStep(1);
});

$("#submit-proposal").addEventListener("click", async (e) => {
  e.preventDefault();
  $("#proposal-error").textContent = "";
  try {
    await api("/api/proposals", {
      method: "POST",
      body: {
        title: $("#f-title").value,
        description: $("#f-description").value,
        audience: $("#f-audience").value,
        approved: $("#approve").checked,
      },
    });
    ["#p-title", "#p-description", "#p-audience"].forEach((id) => ($(id).value = ""));
    showStage("#proposal-form");
    setStep(1);
    confetti();
    toast("🚀 Propunerea ta e în cutie!");
    loadProposals();
  } catch (err) {
    $("#proposal-error").textContent = err.message;
  }
});

// ================================================================ proposals: list

$("#proposal-search").addEventListener("input", renderProposals);
$("#proposal-sort").addEventListener("change", renderProposals);

async function loadProposals() {
  proposals = await api("/api/proposals");
  renderProposals();
  renderStats();
}

function renderProposals() {
  const term = $("#proposal-search").value.trim().toLowerCase();
  const sort = $("#proposal-sort").value;
  const shown = proposals
    .filter((p) => !term || `${p.title} ${p.description} ${p.audience} ${p.author}`.toLowerCase().includes(term))
    .sort((a, b) => {
      if (sort === "votes") return b.votes - a.votes || b.id - a.id;
      if (sort === "chosen") return b.chosen - a.chosen || b.votes - a.votes || b.id - a.id;
      return b.id - a.id;
    });

  const pBadge = $("#p-badge");
  pBadge.textContent = proposals.length;
  pBadge.classList.toggle("hidden", proposals.length === 0);

  const list = $("#proposals-list");
  if (!shown.length) {
    list.replaceChildren(el("div", { class: "empty" },
      proposals.length ? "// nimic nu se potrivește căutării" : "// cutia e goală. Fii primul care propune ceva ✨"));
    return;
  }
  list.replaceChildren(...shown.map((p, i) => {
    const card = proposalCard(p, sort === "votes" && !term ? i + 1 : null);
    card.style.animationDelay = `${Math.min(i, 8) * 40}ms`;
    return card;
  }));
}

function proposalCard(p, rank) {
  const actions = el("div", { class: "actions" });
  if (isTrainer()) {
    actions.append(el("button", {
      class: `small choose ${p.chosen ? "on" : ""}`,
      onclick: async () => { const was = p.chosen; if (await act(`/api/proposals/${p.id}/choose`) && !was) confetti(); },
    }, p.chosen ? "✓ Aleasă · anulează" : "★ Marchează „Aleasă”"));
    actions.append(el("span", { class: "muted small mono" }, `▲ ${p.votes} ${p.votes === 1 ? "vot" : "voturi"}`));
  } else {
    actions.append(el("button", {
      class: `small vote ${p.voted ? "on" : ""}`,
      title: p.voted ? "Retrage votul" : "Votează",
      onclick: () => act(`/api/proposals/${p.id}/vote`),
    }, `▲ ${p.votes}`));
  }

  return el("article", { class: `item ${p.chosen ? "chosen" : ""}` },
    el("div", { class: "item-head" },
      rank && p.votes > 0 ? el("span", { class: `rank ${rank <= 3 ? "top" : ""}` }, `#${rank}`) : null,
      avatar(p.author),
      el("strong", {}, p.mine ? `${p.author} (tu)` : p.author),
      el("span", {}, timeAgo(p.created_at)),
      p.chosen ? el("span", { class: "right chosen-badge" }, "★ ALEASĂ") : null),
    el("h3", {}, p.title),
    el("p", { class: "meta-line" }, el("b", {}, "ce face"), p.description),
    el("p", { class: "meta-line" }, el("b", {}, "pentru"), p.audience),
    actions);
}

async function act(path) {
  try {
    await api(path, { method: "POST" });
    await loadProposals();
    return true;
  } catch (err) {
    toast(err.message);
    return false;
  }
}

// ================================================================ boot

async function refresh() {
  try {
    await Promise.all([loadCategories(), loadQuestions(), loadProposals()]);
  } catch (err) { toast(err.message); }
}

// Reîmprospătare periodică, ca trainerul să vadă întrebările noi
setInterval(() => {
  if (!auth || document.hidden || $("#app-view").classList.contains("hidden")) return;
  // Nu redesenăm întrebările cât timp trainerul scrie un răspuns
  if (!document.querySelector(".answer-form:not(.hidden)")) loadQuestions().catch(() => {});
  loadProposals().catch(() => {});
}, 15000);

if (auth) start();
else runTerminal();
