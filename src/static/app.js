const $ = (sel) => document.querySelector(sel);
// Răspunsul despre „problema” rezolvată se adaugă la descriere
const TARGET_FIELD = { problem: "description" };
const reducedMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

let auth = null;
try { auth = JSON.parse(localStorage.getItem("cutia-auth")); } catch (_) { auth = null; }

let lang = document.documentElement.lang === "en" ? "en" : "ro";
let cfg = { ai: false, topics: Object.keys(TOPICS) };
let questions = [];
let proposals = [];
let lastMissing = [];
let lastStats = {};
let selectedTopic = "prompting";
const aiPending = new Set();

// ================================================================ i18n

function t(key, ...args) {
  let s = STRINGS[lang][key] ?? STRINGS.ro[key] ?? key;
  for (const a of args) s = typeof s === "string" ? s.replace("{}", a) : s;
  return s;
}

function topic(key) {
  const info = TOPICS[key];
  if (!info) return { key, icon: "✨", hue: 50, title: key, summary: "", tips: [], prompt: "", pitfall: "" };
  return { key, icon: info.icon, hue: info.hue, ...info[lang] };
}

function applyI18n() {
  document.documentElement.lang = lang;
  document.querySelectorAll("[data-i18n]").forEach((n) => (n.textContent = t(n.dataset.i18n)));
  document.querySelectorAll("[data-i18n-placeholder]").forEach((n) => (n.placeholder = t(n.dataset.i18nPlaceholder)));
  document.querySelectorAll("[data-i18n-title]").forEach((n) => {
    n.title = t(n.dataset.i18nTitle);
    n.setAttribute("aria-label", n.title);
  });
  document.querySelectorAll(".lang-switch button").forEach((b) => b.classList.toggle("on", b.dataset.lang === lang));
}

function setLang(next) {
  if (next === lang) return;
  lang = next;
  try { localStorage.setItem("cutia-lang", lang); } catch (_) {}
  applyI18n();
  renderMarquee();
  if (auth && !$("#app-view").classList.contains("hidden")) {
    renderHeader();
    renderChips();
    renderTopicFilter();
    renderQuestions();
    renderProposals();
    renderGuide();
    renderStats(true);
    if (!$("#drawer").classList.contains("hidden")) openTopic($("#drawer").dataset.topic);
  }
}

document.querySelectorAll(".lang-switch button").forEach((b) => b.addEventListener("click", () => setLang(b.dataset.lang)));

// ================================================================ helpers

async function api(path, options = {}) {
  const res = await fetch(path, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      "X-Lang": lang,
      ...(auth ? { Authorization: `Bearer ${auth.token}` } : {}),
    },
    body: options.body ? JSON.stringify(options.body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (res.status === 401 && auth) logout();
  if (!res.ok) {
    const detail = Array.isArray(data.detail) ? t("err.check") : data.detail;
    throw new Error(detail || t("err.generic"));
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
  if (s < 60) return t("time.now");
  if (s < 3600) return t("time.min", Math.floor(s / 60));
  if (s < 86400) return t("time.h", Math.floor(s / 3600));
  return new Date(iso).toLocaleDateString(lang === "en" ? "en-GB" : "ro-RO", { day: "numeric", month: "short" });
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
  const box = $("#toast");
  box.textContent = msg;
  box.classList.remove("hidden");
  box.style.animation = "none"; void box.offsetWidth; box.style.animation = "";
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => box.classList.add("hidden"), 2600);
}

async function copy(text) {
  try { await navigator.clipboard.writeText(text); toast(t("g.copied")); } catch (_) {}
}

const isTrainer = () => auth && auth.role === "trainer";

// Markdown minimal și sigur (doar noduri text, fără innerHTML): paragrafe,
// liste, blocuri de cod, `cod` și **bold**.
function inlineMd(text) {
  const out = [];
  const re = /(`[^`]+`|\*\*[^*]+\*\*)/g;
  let last = 0, m;
  while ((m = re.exec(text))) {
    if (m.index > last) out.push(text.slice(last, m.index));
    const tok = m[0];
    out.push(tok.startsWith("`") ? el("code", {}, tok.slice(1, -1)) : el("strong", {}, tok.slice(2, -2)));
    last = m.index + tok.length;
  }
  if (last < text.length) out.push(text.slice(last));
  return out;
}

function renderMd(src) {
  const root = el("div", { class: "md" });
  const parts = src.split(/```[^\n]*\n?/);
  parts.forEach((part, i) => {
    if (i % 2 === 1) {
      const code = part.replace(/\n$/, "");
      root.append(el("pre", {}, el("code", {}, code),
        el("button", { class: "copy-btn small", type: "button", onclick: () => copy(code) }, t("g.copy"))));
      return;
    }
    let list = null;
    for (const block of part.split(/\n{2,}/)) {
      for (const line of block.split("\n")) {
        const item = line.match(/^\s*(?:[-*]|\d+\.)\s+(.*)/);
        if (item) {
          if (!list) { list = el(/^\s*\d/.test(line) ? "ol" : "ul"); root.append(list); }
          list.append(el("li", {}, inlineMd(item[1])));
        } else if (line.trim()) {
          list = null;
          root.append(el("p", {}, inlineMd(line.replace(/^#+\s*/, ""))));
        }
      }
      list = null;
    }
  });
  return root;
}

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
  (function frame(now) {
    ctx.clearRect(0, 0, innerWidth, innerHeight);
    for (const p of parts) {
      p.vy += .35; p.vx *= .99; p.x += p.vx; p.y += p.vy; p.rot += p.vr;
      ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.rot);
      ctx.fillStyle = p.c; ctx.fillRect(-p.r / 2, -p.r / 4, p.r, p.r / 2);
      ctx.restore();
    }
    if (now - start < 2600) requestAnimationFrame(frame);
    else ctx.clearRect(0, 0, innerWidth, innerHeight);
  })(start);
}

// ================================================================ theme

$("#theme-btn").addEventListener("click", () => {
  const next = document.documentElement.dataset.theme === "light" ? "dark" : "light";
  document.documentElement.dataset.theme = next;
  try { localStorage.setItem("cutia-theme", next); } catch (_) {}
});

// ================================================================ login: terminal & topics marquee

let terminalRunning = false;
async function runTerminal() {
  if (terminalRunning) return;
  terminalRunning = true;
  const body = $("#term-body");
  while (!$("#login-view").classList.contains("hidden")) {
    body.replaceChildren();
    for (const [prefix, text, typed] of t("term")) {
      const cls = prefix === "$ " ? "t-prompt" : prefix === "? " ? "t-q" : prefix === "✓ " ? "t-ok" : "t-ai";
      const span = el("span", { class: typed ? "" : cls });
      const cursor = el("span", { class: "cursor" });
      body.append(el("div", {}, el("span", { class: cls }, prefix), span, cursor));
      if (typed && !reducedMotion) {
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

function renderMarquee() {
  const chips = cfg.topics.map((k) => {
    const tp = topic(k);
    return el("span", { class: "chip", style: `--h:${tp.hue}` }, tp.icon, " ", tp.title);
  });
  // Lista apare de două ori, ca animația să se repete fără salt
  $("#topic-marquee .marquee-track").replaceChildren(...chips, ...chips.map((c) => c.cloneNode(true)));
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
  closeTopic();
  $("#app-view").classList.add("hidden");
  $("#user-box").classList.add("hidden");
  $("#login-view").classList.remove("hidden");
  runTerminal();
}

function renderHeader() {
  const h = new Date().getHours();
  const hello = h < 11 ? t("greet.morning") : h < 18 ? t("greet.day") : t("greet.evening");
  $("#user-role").textContent = t(isTrainer() ? "role.trainer" : "role.student");
  $("#greet-eyebrow").textContent = t(isTrainer() ? "greet.trainer" : "greet.student");
  $("#greet-title").textContent = `${hello}, ${auth.name.split(/\s+/)[0]} 👋`;
  $("#questions-title").textContent = t(isTrainer() ? "q.class" : "q.mine");
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
  renderHeader();
  document.querySelectorAll(".student-only").forEach((n) => n.classList.toggle("hidden", isTrainer()));
  document.querySelector('.tab[data-tab="questions"]').click();
  lastStats = {};
  renderChips();
  renderTopicFilter();
  refresh();
}

// ================================================================ tabs & shortcuts

function showTab(name) {
  document.querySelectorAll(".tab").forEach((tb) => tb.classList.toggle("active", tb.dataset.tab === name));
  document.querySelectorAll(".tab-panel").forEach((p) => p.classList.toggle("hidden", p.id !== `tab-${name}`));
}

document.querySelectorAll(".tab").forEach((tab) => tab.addEventListener("click", () => showTab(tab.dataset.tab)));

document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") closeTopic();
  const typing = /INPUT|TEXTAREA|SELECT/.test(document.activeElement.tagName);
  if (e.key === "/" && !typing && auth) {
    const search = document.querySelector('.tab-panel:not(.hidden) input[type="search"]');
    if (search) { e.preventDefault(); search.focus(); }
  }
  // Ctrl/Cmd + Enter trimite formularul în care scrii
  if (e.key === "Enter" && (e.ctrlKey || e.metaKey) && typing) {
    const form = document.activeElement.closest("form");
    if (form) { e.preventDefault(); form.requestSubmit(); }
  }
});

// ================================================================ stats

function renderStats(instant = false) {
  const answered = questions.filter((q) => q.answer).length;
  const stats = isTrainer()
    ? [
        ["open", questions.length - answered, "stat.open", true],
        ["answered", answered, "stat.answeredT"],
        ["proposals", proposals.length, "stat.proposalsT"],
        ["chosen", proposals.filter((p) => p.chosen).length, "stat.chosen"],
      ]
    : [
        ["mine", questions.length, "stat.mine"],
        ["answered", answered, "stat.answered", answered > 0],
        ["proposals", proposals.length, "stat.proposals"],
        ["votes", proposals.filter((p) => p.voted).length, "stat.votes"],
      ];

  $("#stats").replaceChildren(...stats.map(([key, value, label, hl]) => {
    const from = instant ? value : lastStats[key] ?? 0;
    const b = el("b", {}, String(from));
    countUp(b, from, value);
    lastStats[key] = value;
    return el("div", { class: `stat ${hl ? "hl" : ""}` }, b, el("span", {}, t(label)));
  }));
}

function countUp(node, from, to) {
  if (from === to || reducedMotion) { node.textContent = to; return; }
  const t0 = performance.now();
  (function step(now) {
    const k = Math.min(1, (now - t0) / 600);
    node.textContent = Math.round(from + (to - from) * (1 - Math.pow(1 - k, 3)));
    if (k < 1) requestAnimationFrame(step);
  })(t0);
}

// ================================================================ questions

function renderChips() {
  $("#topic-chips").replaceChildren(...cfg.topics.map((k) => {
    const tp = topic(k);
    return el("button", {
      type: "button", role: "radio", "aria-checked": String(k === selectedTopic),
      class: `chip ${k === selectedTopic ? "on" : ""}`, style: `--h:${tp.hue}`,
      onclick: () => { selectedTopic = k; renderChips(); },
    }, tp.icon, " ", tp.title);
  }));
  const tp = topic(selectedTopic);
  $("#topic-hint").replaceChildren(t("q.tryFirst"),
    el("code", { title: t("g.copy"), onclick: () => copy(tp.prompt) }, tp.prompt));
}

function renderTopicFilter() {
  const select = $("#question-topic");
  const current = select.value || "all";
  select.replaceChildren(el("option", { value: "all" }, t("q.allTopics")),
    ...cfg.topics.map((k) => el("option", { value: k }, `${topic(k).icon} ${topic(k).title}`)));
  select.value = current;
}

$("#question-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    const q = await api("/api/questions", {
      method: "POST",
      body: { text: $("#question-text").value, category: selectedTopic, anonymous: $("#question-anon").checked },
    });
    $("#question-text").value = "";
    toast(t("q.sent"));
    await loadQuestions();
    if (cfg.ai) requestAiAnswer(q.id);
  } catch (err) {
    toast(err.message);
  }
});

async function requestAiAnswer(id) {
  aiPending.add(id);
  renderQuestions();
  try {
    const updated = await api(`/api/questions/${id}/ai-answer`, { method: "POST" });
    questions = questions.map((q) => (q.id === id ? updated : q));
  } catch (err) {
    toast(err.message);
  } finally {
    aiPending.delete(id);
    renderQuestions();
  }
}

$("#question-search").addEventListener("input", renderQuestions);
$("#question-filter").addEventListener("change", renderQuestions);
$("#question-topic").addEventListener("change", renderQuestions);

async function loadQuestions() {
  questions = await api("/api/questions");
  renderQuestions();
  renderStats();
  renderGuide();
}

function renderQuestions() {
  const term = $("#question-search").value.trim().toLowerCase();
  const filter = $("#question-filter").value;
  const topicFilter = $("#question-topic").value || "all";
  const shown = questions.filter((q) => {
    if (filter === "open" && q.answer) return false;
    if (filter === "answered" && !q.answer) return false;
    if (topicFilter !== "all" && q.category !== topicFilter) return false;
    return !term || `${q.text} ${q.answer || ""} ${q.ai_answer || ""} ${q.author}`.toLowerCase().includes(term);
  });

  const open = questions.filter((q) => !q.answer).length;
  const badge = $("#q-badge");
  badge.textContent = open;
  badge.classList.toggle("hidden", !isTrainer() || open === 0);

  const list = $("#questions-list");
  if (!shown.length) {
    list.replaceChildren(el("div", { class: "empty" },
      t(questions.length ? "q.emptyFilter" : isTrainer() ? "q.emptyTrainer" : "q.emptyStudent")));
    return;
  }
  list.replaceChildren(...shown.map((q, i) => {
    const card = questionCard(q);
    card.style.animationDelay = `${Math.min(i, 8) * 40}ms`;
    return card;
  }));
}

function topicChip(key) {
  const tp = topic(key);
  return el("button", { type: "button", class: "topic-chip", style: `--h:${tp.hue}`, onclick: () => openTopic(key) },
    tp.icon, " ", tp.title);
}

function questionCard(q) {
  const head = el("div", { class: "item-head" },
    isTrainer() ? avatar(q.author) : null,
    isTrainer() ? el("strong", {}, q.anonymous ? t("q.anonTag") : q.author) : null,
    topicChip(q.category),
    !isTrainer() && q.anonymous ? el("span", { class: "tag" }, t("q.anonTag")) : null,
    el("span", {}, timeAgo(q.created_at)),
    el("span", { class: `right status ${q.answer ? "ok" : "open"}` }, t(q.answer ? "q.statusOk" : "q.statusOpen")),
  );
  const card = el("article", { class: "item" }, head, el("p", { class: "item-text" }, q.text));

  // Răspunsul oficial al trainerului vine primul
  if (q.answer) {
    card.append(el("div", { class: "answer" },
      el("div", { class: "label" }, t("q.trainer"), el("span", { class: "muted" }, ` · ${timeAgo(q.answered_at)}`)),
      renderMd(q.answer)));
  }

  if (q.ai_answer) {
    card.append(el("div", { class: "ai-answer" }, el("div", { class: "label" }, t("q.ai")), renderMd(q.ai_answer)));
  } else if (aiPending.has(q.id)) {
    card.append(el("div", { class: "ai-loading" }, "› ", t("q.aiThinking"), el("span", { class: "dots" })));
  }

  if (!isTrainer() && !q.answer) {
    card.append(el("div", { class: "waiting" }, t("q.waiting")));
    if (!q.ai_answer && !aiPending.has(q.id)) {
      if (cfg.ai) {
        card.append(el("div", { class: "actions" },
          el("button", { class: "small glow", onclick: () => requestAiAnswer(q.id) }, t("q.aiAsk"))));
      } else {
        const tp = topic(q.category);
        card.append(el("div", { class: "guide-peek" },
          el("strong", {}, `${t("q.fromGuide")} · ${tp.icon} ${tp.title}`),
          el("ul", {}, tp.tips.slice(0, 2).map((tip) => el("li", {}, tip))),
          el("button", { class: "link-btn", type: "button", onclick: () => openTopic(q.category) }, t("q.openGuide"))));
      }
    }
  }

  if (isTrainer()) {
    const area = el("textarea", { rows: 3, placeholder: t("q.replyPh") });
    area.value = q.answer || "";
    const formButtons = el("div", { class: "row end" });
    if (q.ai_answer) {
      formButtons.append(el("button", { type: "button", class: "ghost small", onclick: () => { area.value = q.ai_answer; area.focus(); } }, t("q.useAi")));
    }
    formButtons.append(el("button", { type: "submit", class: "primary small" }, t("q.sendReply")));
    const form = el("form", { class: "answer-form hidden" }, area, formButtons);
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        await api(`/api/questions/${q.id}/answer`, { method: "POST", body: { text: area.value } });
        toast(t("q.replied"));
        loadQuestions();
      } catch (err) { toast(err.message); }
    });
    const actions = el("div", { class: "actions" },
      el("button", { class: "small", onclick: () => { form.classList.toggle("hidden"); area.focus(); } },
        t(q.answer ? "q.edit" : "q.reply")));
    if (cfg.ai && !q.ai_answer && !aiPending.has(q.id)) {
      actions.append(el("button", { class: "small ghost", onclick: () => requestAiAnswer(q.id) }, "✨ ", t("q.aiDraft")));
    }
    card.append(actions, form);
  }
  return card;
}

// ================================================================ guide

function topicCounts() {
  const counts = {};
  for (const q of questions) counts[q.category] = (counts[q.category] || 0) + 1;
  return counts;
}

function renderGuide() {
  const counts = topicCounts();
  $("#topic-grid").replaceChildren(...cfg.topics.map((k, i) => {
    const tp = topic(k);
    const n = counts[k] || 0;
    const card = el("button", { type: "button", class: "topic-card", style: `--h:${tp.hue}; animation-delay:${i * 30}ms`, onclick: () => openTopic(k) },
      el("span", { class: "ico" }, tp.icon),
      n ? el("span", { class: "count" }, `${n} ${t(n === 1 ? "g.qcount1" : "g.qcount")}`) : null,
      el("h3", {}, tp.title),
      el("p", {}, tp.summary));
    card.addEventListener("pointermove", (e) => {
      const r = card.getBoundingClientRect();
      card.style.setProperty("--mx", `${e.clientX - r.left}px`);
      card.style.setProperty("--my", `${e.clientY - r.top}px`);
    });
    return card;
  }));

  const ranked = Object.entries(counts).sort((a, b) => b[1] - a[1]).slice(0, 6);
  const heat = $("#heat");
  heat.classList.toggle("hidden", ranked.length === 0);
  if (!ranked.length) return;
  const max = ranked[0][1];
  heat.replaceChildren(el("h3", {}, t(isTrainer() ? "g.heatT" : "g.heatS")),
    ...ranked.map(([k, n]) => {
      const tp = topic(k);
      return el("div", { class: "heat-row", style: `--h:${tp.hue}` },
        el("span", { class: "name" }, `${tp.icon} ${tp.title}`),
        el("div", { class: "heat-bar" }, el("i", { style: `width:${(n / max) * 100}%` })),
        el("b", {}, String(n)));
    }));
}

function openTopic(key) {
  const tp = topic(key);
  const drawer = $("#drawer");
  drawer.dataset.topic = key;
  drawer.style.setProperty("--h", tp.hue);
  const body = [
    el("div", { class: "ico" }, tp.icon),
    el("h2", { id: "drawer-title" }, tp.title),
    el("p", { class: "muted" }, tp.summary),
    el("h4", {}, t("g.tips")),
    el("ol", {}, tp.tips.map((tip) => el("li", {}, tip))),
    el("h4", {}, t("g.prompt")),
    el("div", { class: "md" }, el("pre", {}, el("code", {}, tp.prompt),
      el("button", { class: "copy-btn small", type: "button", onclick: () => copy(tp.prompt) }, t("g.copy")))),
    el("h4", {}, t("g.pitfall")),
    el("p", { class: "pitfall" }, "⚠️ ", tp.pitfall),
  ];
  if (!isTrainer()) {
    body.push(el("button", {
      class: "primary glow", type: "button",
      onclick: () => {
        selectedTopic = cfg.topics.includes(key) ? key : "other";
        renderChips();
        closeTopic();
        showTab("questions");
        $("#question-text").focus();
      },
    }, t("g.ask")));
  }
  $("#drawer-body").replaceChildren(...body);
  drawer.classList.remove("hidden");
  $("#drawer-backdrop").classList.remove("hidden");
  document.body.classList.add("no-scroll");
  $("#drawer-close").focus();
}

function closeTopic() {
  $("#drawer").classList.add("hidden");
  $("#drawer-backdrop").classList.add("hidden");
  document.body.classList.remove("no-scroll");
}

$("#drawer-close").addEventListener("click", closeTopic);
$("#drawer-backdrop").addEventListener("click", closeTopic);

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

async function runRefine(body) {
  $("#proposal-error").textContent = "";
  showStage("#ai-thinking");
  setStep(2);
  const log = $("#ai-log");
  log.replaceChildren(el("div", {}, el("span", { class: "t-prompt" }, "$ "), "claude refine proposal.json"));

  let done = false;
  const request = api("/api/proposals/refine", { method: "POST", body }).finally(() => { done = true; });
  request.catch(() => {}); // eroarea e tratată mai jos, după animație
  for (const line of t("p.log")) {
    log.append(el("div", { class: "t-ai" }, "› " + line));
    await sleep(380);
  }
  const cursor = el("span", { class: "cursor" });
  if (!done) log.append(el("div", { class: "t-dim" }, "› " + t("p.waitClaude"), cursor));

  try {
    const r = await request;
    cursor.remove();
    const n = (r.missing || []).length;
    log.append(el("div", { class: "t-ok" }, t("p.done") + (n ? n + t(n === 1 ? "p.oneQ" : "p.manyQ") : t("p.allClear"))));
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
  typewrite($("#understood-text"), r.understood || t("p.understoodEmpty"));
  $("#refine-notes").textContent = t(r.engine === "claude" ? "p.engineClaude" : "p.engineLocal") + (r.notes || "");
  $("#f-title").value = r.title || "";
  $("#f-description").value = r.description || "";
  $("#f-audience").value = r.audience || "";
  $("#approve").checked = false;
  $("#submit-proposal").disabled = true;

  lastMissing = r.missing || [];
  $("#missing-box").classList.toggle("hidden", lastMissing.length === 0);
  $("#missing-list").replaceChildren(...lastMissing.map((m, i) => {
    const ta = el("textarea", { rows: 2, "data-missing": i, placeholder: t("p.answerPh"), "aria-label": m.question });
    ta.addEventListener("input", () => setStep(4), { once: true });
    return el("div", { class: "q-bubble" },
      el("div", { class: "q" }, el("small", {}, `🤖 ${t("field." + m.field)}`), m.question),
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
    toast(t("p.submitted"));
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
    list.replaceChildren(el("div", { class: "empty" }, t(proposals.length ? "q.emptyFilter" : "p.empty")));
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
    }, t(p.chosen ? "p.unchoose" : "p.choose")));
    actions.append(el("span", { class: "muted small mono" }, `▲ ${p.votes} ${t(p.votes === 1 ? "p.vote1" : "p.votes")}`));
  } else {
    actions.append(el("button", {
      class: `small vote ${p.voted ? "on" : ""}`,
      title: t(p.voted ? "p.unvote" : "p.vote"),
      onclick: () => act(`/api/proposals/${p.id}/vote`),
    }, `▲ ${p.votes}`));
  }

  return el("article", { class: `item ${p.chosen ? "chosen" : ""}` },
    el("div", { class: "item-head" },
      rank && p.votes > 0 ? el("span", { class: `rank ${rank <= 3 ? "top" : ""}` }, `#${rank}`) : null,
      avatar(p.author),
      el("strong", {}, p.mine ? p.author + t("p.you") : p.author),
      el("span", {}, timeAgo(p.created_at)),
      p.chosen ? el("span", { class: "right chosen-badge" }, t("p.chosen")) : null),
    el("h3", {}, p.title),
    el("p", { class: "meta-line" }, el("b", {}, t("p.what")), p.description),
    el("p", { class: "meta-line" }, el("b", {}, t("p.for")), p.audience),
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
    await Promise.all([loadQuestions(), loadProposals()]);
  } catch (err) { toast(err.message); }
}

// Reîmprospătare periodică, ca trainerul să vadă întrebările noi
setInterval(() => {
  if (!auth || document.hidden || $("#app-view").classList.contains("hidden")) return;
  // Nu redesenăm întrebările cât timp cineva scrie un răspuns sau așteaptă AI-ul
  if (!document.querySelector(".answer-form:not(.hidden)") && aiPending.size === 0) loadQuestions().catch(() => {});
  loadProposals().catch(() => {});
}, 15000);

(async function boot() {
  applyI18n();
  try { cfg = await api("/api/config"); } catch (_) {}
  renderMarquee();
  if (auth) start();
  else runTerminal();
})();
