const $ = (sel) => document.querySelector(sel);
const FIELD_LABELS = { title: "Titlu", problem: "Problema", description: "Ce face aplicația", audience: "Cine o folosește" };
// Răspunsul despre „problema” rezolvată se adaugă la descriere
const TARGET_FIELD = { problem: "description" };

let auth = null;
try { auth = JSON.parse(localStorage.getItem("cutia-auth")); } catch (_) { auth = null; }

let questions = [];
let proposals = [];
let lastMissing = [];

// ---------------------------------------------------------------- helpers

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
  if (res.status === 401 && auth) { logout(); }
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
    else if (k.startsWith("on")) node.addEventListener(k.slice(2), v);
    else if (v !== false && v != null) node.setAttribute(k, v === true ? "" : v);
  }
  for (const child of children.flat()) {
    if (child == null || child === false) continue;
    node.append(child instanceof Node ? child : document.createTextNode(child));
  }
  return node;
}

function fmtDate(iso) {
  if (!iso) return "";
  return new Date(iso).toLocaleString("ro-RO", { day: "numeric", month: "short", hour: "2-digit", minute: "2-digit" });
}

let toastTimer;
function toast(msg) {
  const t = $("#toast");
  t.textContent = msg;
  t.classList.remove("hidden");
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.add("hidden"), 2500);
}

const isTrainer = () => auth && auth.role === "trainer";

// ---------------------------------------------------------------- auth

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
  $("#user-role").textContent = isTrainer() ? "Trainer" : "Student";
  document.querySelectorAll(".student-only").forEach((n) => n.classList.toggle("hidden", isTrainer()));
  $("#questions-title").textContent = isTrainer() ? "Întrebările clasei" : "Întrebările mele";
  document.querySelector('.tab[data-tab="questions"]').click();
  refresh();
}

// ---------------------------------------------------------------- tabs

document.querySelectorAll(".tab").forEach((tab) =>
  tab.addEventListener("click", () => {
    document.querySelectorAll(".tab").forEach((t) => t.classList.toggle("active", t === tab));
    document.querySelectorAll(".tab-panel").forEach((p) =>
      p.classList.toggle("hidden", p.id !== `tab-${tab.dataset.tab}`)
    );
  })
);

// ---------------------------------------------------------------- questions

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
    toast("Întrebarea a fost trimisă.");
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
      questions.length ? "Nimic nu se potrivește căutării." :
      isTrainer() ? "Încă nu a pus nimeni o întrebare." : "Nu ai pus încă nicio întrebare."));
    return;
  }
  list.replaceChildren(...shown.map(questionCard));
}

function questionCard(q) {
  const head = el("div", { class: "item-head" },
    isTrainer() ? el("strong", {}, q.author) : null,
    el("span", { class: "tag" }, q.category),
    !isTrainer() && q.anonymous ? el("span", { class: "tag" }, "anonim") : null,
    el("span", {}, fmtDate(q.created_at)),
    el("span", { class: `right ${q.answer ? "status-ok" : "status-open"}` }, q.answer ? "Răspuns ✓" : "Așteaptă răspuns"),
  );
  const card = el("article", { class: "item" }, head, el("p", { class: "item-text" }, q.text));

  if (q.answer) {
    card.append(el("div", { class: "answer" },
      el("div", { class: "label" }, `Răspunsul trainerului · ${fmtDate(q.answered_at)}`),
      el("div", { class: "item-text" }, q.answer)));
  } else if (!isTrainer()) {
    card.append(el("div", { class: "waiting" }, "Trainerul n-a răspuns încă."));
  }

  if (isTrainer()) {
    const area = el("textarea", { rows: 2, placeholder: "Scrie răspunsul…" });
    area.value = q.answer || "";
    const form = el("form", { class: "answer-form hidden" }, area,
      el("div", { class: "row end" }, el("button", { type: "submit", class: "primary small" }, "Trimite răspunsul")));
    form.addEventListener("submit", async (e) => {
      e.preventDefault();
      try {
        await api(`/api/questions/${q.id}/answer`, { method: "POST", body: { text: area.value } });
        toast("Răspuns trimis.");
        loadQuestions();
      } catch (err) { toast(err.message); }
    });
    const toggle = el("button", { class: "small", onclick: () => { form.classList.toggle("hidden"); area.focus(); } },
      q.answer ? "Editează răspunsul" : "Răspunde");
    card.append(el("div", { class: "actions" }, toggle), form);
  }
  return card;
}

// ---------------------------------------------------------------- proposals: wizard

function setStep(n) {
  document.querySelectorAll(".steps li").forEach((li) => {
    const s = Number(li.dataset.step);
    li.classList.toggle("active", s === n);
    li.classList.toggle("done", s < n);
  });
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
  const btn = $("#proposal-form button[type=submit]");
  btn.disabled = true;
  btn.textContent = "AI-ul lucrează…";
  try {
    const r = await api("/api/proposals/refine", { method: "POST", body });
    showRefined(r);
  } catch (err) {
    $("#proposal-error").textContent = err.message;
  } finally {
    btn.disabled = false;
    btn.textContent = "✨ Retușează cu AI";
  }
}

function showRefined(r) {
  $("#refine-result").classList.remove("hidden");
  $("#proposal-form").classList.add("hidden");
  $("#understood-text").textContent = r.understood || "Încă prea puțin ca să înțeleg ideea — răspunde la întrebările de mai jos.";
  $("#refine-notes").textContent = (r.engine === "claude" ? "Claude: " : "") + (r.notes || "");
  $("#f-title").value = r.title || "";
  $("#f-description").value = r.description || "";
  $("#f-audience").value = r.audience || "";
  $("#approve").checked = false;
  $("#submit-proposal").disabled = true;

  lastMissing = r.missing || [];
  $("#missing-box").classList.toggle("hidden", lastMissing.length === 0);
  $("#missing-list").replaceChildren(...lastMissing.map((m, i) =>
    el("label", {}, `${FIELD_LABELS[m.field] || m.field}: ${m.question}`,
      el("textarea", { rows: 2, "data-missing": i }))));
  setStep(lastMissing.length ? 2 : 3);
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
  // Ținem ciorna sincronizată, ca „Înapoi" să nu piardă detaliile
  $("#p-title").value = body.title;
  $("#p-description").value = body.description;
  $("#p-audience").value = body.audience;
  runRefine(body);
});

$("#approve").addEventListener("change", () => {
  $("#submit-proposal").disabled = !$("#approve").checked;
  setStep($("#approve").checked ? 3 : lastMissing.length ? 2 : 3);
});

["#f-title", "#f-description", "#f-audience"].forEach((id) =>
  $(id).addEventListener("input", () => {
    // Orice modificare cere o nouă aprobare
    $("#approve").checked = false;
    $("#submit-proposal").disabled = true;
  })
);

$("#back-edit").addEventListener("click", (e) => {
  e.preventDefault();
  $("#refine-result").classList.add("hidden");
  $("#proposal-form").classList.remove("hidden");
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
    $("#refine-result").classList.add("hidden");
    $("#proposal-form").classList.remove("hidden");
    setStep(1);
    toast("Propunerea a fost trimisă!");
    loadProposals();
  } catch (err) {
    $("#proposal-error").textContent = err.message;
  }
});

// ---------------------------------------------------------------- proposals: list

$("#proposal-search").addEventListener("input", renderProposals);
$("#proposal-sort").addEventListener("change", renderProposals);

async function loadProposals() {
  proposals = await api("/api/proposals");
  renderProposals();
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

  const list = $("#proposals-list");
  if (!shown.length) {
    list.replaceChildren(el("div", { class: "empty" },
      proposals.length ? "Nimic nu se potrivește căutării." : "Încă nu există propuneri."));
    return;
  }
  list.replaceChildren(...shown.map(proposalCard));
}

function proposalCard(p) {
  const actions = el("div", { class: "actions" });
  if (isTrainer()) {
    actions.append(el("button", {
      class: `small choose ${p.chosen ? "on" : ""}`,
      onclick: () => act(`/api/proposals/${p.id}/choose`),
    }, p.chosen ? "✓ Aleasă — anulează" : "Marchează „Aleasă”"));
    actions.append(el("span", { class: "muted small" }, `${p.votes} ${p.votes === 1 ? "vot" : "voturi"}`));
  } else {
    actions.append(el("button", {
      class: `small vote ${p.voted ? "on" : ""}`,
      onclick: () => act(`/api/proposals/${p.id}/vote`),
    }, `▲ ${p.votes}`));
  }

  return el("article", { class: `item ${p.chosen ? "chosen" : ""}` },
    el("div", { class: "item-head" },
      el("strong", {}, p.mine ? `${p.author} (tu)` : p.author),
      el("span", {}, fmtDate(p.created_at)),
      p.chosen ? el("span", { class: "right chosen-badge" }, "Aleasă") : null),
    el("h3", {}, p.title),
    el("p", { class: "meta-line" }, el("b", {}, "Ce face: "), p.description),
    el("p", { class: "meta-line" }, el("b", {}, "Cine o folosește: "), p.audience),
    actions);
}

async function act(path) {
  try {
    await api(path, { method: "POST" });
    loadProposals();
  } catch (err) { toast(err.message); }
}

// ---------------------------------------------------------------- boot

async function refresh() {
  try {
    await Promise.all([loadCategories(), loadQuestions(), loadProposals()]);
  } catch (err) { toast(err.message); }
}

// Reîmprospătare periodică, ca trainerul să vadă întrebările noi
setInterval(() => {
  if (!auth || document.hidden) return;
  // Nu redesenăm întrebările cât timp trainerul scrie un răspuns
  if (!document.querySelector(".answer-form:not(.hidden)")) loadQuestions().catch(() => {});
  loadProposals().catch(() => {});
}, 15000);

if (auth) start();
