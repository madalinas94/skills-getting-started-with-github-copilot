"use strict";

const $ = (s, el = document) => el.querySelector(s);
const $$ = (s, el = document) => [...el.querySelectorAll(s)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const fmt = (s) => { s = Math.max(0, s || 0); const m = Math.floor(s / 60); const r = s - m * 60; return m ? `${m}:${r.toFixed(0).padStart(2, "0")}` : `${r.toFixed(1)}s`; };

const TRANSITIONS = ["cut", "fade", "dissolve", "wipeleft", "wiperight", "slideup", "slidedown", "circleopen", "zoomin", "smoothleft", "fadeblack", "fadewhite"];
const TRANS_RO = { cut: "Tăietură", fade: "Fade", dissolve: "Dizolvare", wipeleft: "Ștergere ←", wiperight: "Ștergere →", slideup: "Glisare ↑", slidedown: "Glisare ↓", circleopen: "Cerc", zoomin: "Zoom", smoothleft: "Swipe", fadeblack: "Prin negru", fadewhite: "Prin alb" };
const LOOKS = { none: "Natural", cinematic: "Cinematic", warm: "Cald", cool: "Rece", vintage: "Vintage", bw: "Alb-negru", vivid: "Viu", film: "Film", matte: "Mat" };
const MOTIONS = { none: "Fără", zoom_in: "Zoom in lent", zoom_out: "Zoom out lent", pan_left: "Panoramare ←", pan_right: "Panoramare →", punch_in: "Punch-in rapid" };
const FITS = { fill: "Umple cadrul (crop)", track: "Urmărește fața", blur_bg: "Întreg + fundal blurat", fit: "Întreg + benzi negre" };
const ANIMS = { fade: "Fade", pop: "Pop", slide_up: "Glisează în sus", typewriter: "Mașină de scris", zoom_out: "Zoom", none: "Fără" };
const ISSUE_RO = { shaky: "tremurat", blurry: "neclar", dark: "întunecat", bright: "ars" };
const MOOD_RO = { calm: "calm", medium: "mediu", energetic: "energic" };
const STYLES = { title: "Titlu", caption: "Subtitrare", lower_third: "Bandă jos", label: "Etichetă", big_word: "Cuvânt mare" };
const POSITIONS = { top: "Sus", center: "Centru", bottom: "Jos", lower_third: "Treimea de jos" };
const ROLES = { material: "Material", example: "Exemplu", music: "Muzică" };
const QUICK = ["Mai dinamic, tăieturi pe beat", "Hook mai puternic la început", "Mai scurt, maxim 15 secunde", "Culori mai calde", "Text mai puțin", "Scoate pozele", "Adaugă subtitrări"];

const state = { status: null, project: null, job: null, sel: -1, quality: "1080p", pollTimer: null };

// ------------------------------------------------------------------ helpers

function toast(msg, err = false) {
  const t = $("#toast");
  t.textContent = msg;
  t.className = "toast show" + (err ? " err" : "");
  clearTimeout(toast.t);
  toast.t = setTimeout(() => (t.className = "toast"), err ? 6000 : 3000);
}

async function api(path, opts = {}) {
  const init = { method: opts.method || "GET", headers: {} };
  if (opts.body !== undefined) {
    init.headers["Content-Type"] = "application/json";
    init.body = JSON.stringify(opts.body);
  }
  const res = await fetch(path, init);
  let data = null;
  try { data = await res.json(); } catch { /* empty body */ }
  if (!res.ok) {
    const msg = (data && (typeof data.detail === "string" ? data.detail : JSON.stringify(data.detail))) || res.statusText;
    throw new Error(msg);
  }
  return data;
}

const file = (p) => `/files/${state.project.id}/${p}`;
const mediaById = (id) => state.project.media.find((m) => m.id === id);
const pid = () => state.project && state.project.id;

// ------------------------------------------------------------------ status & settings

async function loadStatus() {
  state.status = await api("/api/status");
  const s = state.status;
  const f = $("#pillFfmpeg");
  f.textContent = s.ffmpeg ? "ffmpeg ✓" : "ffmpeg lipsește";
  f.className = "pill " + (s.ffmpeg ? "ok" : "bad");
  const a = $("#pillAi");
  const short = (s.models[s.model] || s.model).split(" (")[0].replace("Claude ", "");
  a.textContent = s.has_key ? `AI: ${short} ✓` : "AI: fără cheie";
  a.className = "pill " + (s.has_key ? "ok" : "bad");
  a.title = s.has_key ? "Cheia API e setată" : "Adaugă cheia API în Setări";
  $("#model").innerHTML = Object.entries(s.models).map(([k, v]) => `<option value="${k}">${esc(v)}</option>`).join("");
  $("#model").value = s.model;
  $("#effort").value = s.effort;
  $("#elevenVoice").value = s.eleven_voice || "";
  $("#whisperModel").value = s.whisper_model;
  const feat = (ok, yes, no) => `<li>${ok ? "✅" : "⚪"} ${ok ? yes : no}</li>`;
  $("#features").innerHTML = [
    feat(s.whisper, "Whisper instalat — subtitrări din vorbire", "Whisper lipsește — <code>pip install faster-whisper</code>"),
    feat(s.faces, "OpenCV instalat — urmărirea feței", "OpenCV lipsește — <code>pip install opencv-python-headless</code>"),
    feat(s.quality, "Verificare cadre tremurate / neclare / întunecate", "numpy lipsește — <code>pip install numpy</code>"),
    feat(s.has_eleven, "ElevenLabs conectat — voce off și dublaj", "Fără cheie ElevenLabs — vocea off și dublajul cu voce sunt oprite"),
    feat(s.people, "MediaPipe — decupare fundal și thumbnail cu tine decupat", "MediaPipe lipsește — <code>pip install mediapipe</code>"),
    feat(s.demucs, "Demucs — vocea originală separată curat la dublaj", "Demucs lipsește (opțional) — <code>pip install demucs</code>"),
  ].join("");
  $("#cloneState").textContent = s.my_voice ? `— activă: „${s.my_voice}”` : "— încă nu e creată";
  renderLangs();
  $("#keyHint").innerHTML = s.key_from_env
    ? "Folosesc cheia din variabila <code>ANTHROPIC_API_KEY</code>. Poți pune alta aici."
    : "Cheia se salvează doar local, în <code>montaj/workspace/settings.json</code>. Fără cheie merge doar montajul automat.";
  renderPresets();
}

$("#openSettings").onclick = () => { $("#apiKey").value = ""; $("#elevenKey").value = ""; $("#settings").showModal(); };
$("#pillAi").onclick = () => $("#openSettings").click();
$("#settings").addEventListener("close", async () => {
  if ($("#settings").returnValue !== "save") return;
  const body = { model: $("#model").value, effort: $("#effort").value,
    eleven_voice: $("#elevenVoice").value, whisper_model: $("#whisperModel").value };
  if ($("#apiKey").value.trim()) body.api_key = $("#apiKey").value.trim();
  if ($("#elevenKey").value.trim()) body.eleven_key = $("#elevenKey").value.trim();
  try { await api("/api/settings", { method: "POST", body }); await loadStatus(); toast("Setări salvate"); }
  catch (e) { toast(e.message, true); }
});

// ------------------------------------------------------------------ projects

async function loadProjects(selectId) {
  const list = await api("/api/projects");
  let id = selectId || location.hash.slice(1) || (list[0] && list[0].id);
  if (!list.length) {
    const p = await api("/api/projects", { method: "POST", body: { name: "Primul meu montaj" } });
    return loadProjects(p.id);
  }
  if (!list.find((p) => p.id === id)) id = list[0].id;
  $("#projectSelect").innerHTML = list.map((p) => `<option value="${p.id}">${esc(p.name)} · ${p.media} fișiere</option>`).join("");
  $("#projectSelect").value = id;
  await openProject(id);
}

$("#projectSelect").onchange = (e) => openProject(e.target.value);
$("#newProject").onclick = async () => {
  const name = prompt("Numele proiectului:", "Montaj nou");
  if (name === null) return;
  const p = await api("/api/projects", { method: "POST", body: { name } });
  await loadProjects(p.id);
};

async function openProject(id) {
  location.hash = id;
  state.sel = -1;
  closeInspector();
  await refresh();
  const running = state.project.running;
  if (running) watchJob(running);
  else $("#jobPanel").hidden = true;
}

async function refresh() {
  state.project = await api(`/api/projects/${pid() || location.hash.slice(1)}`);
  renderAll();
}

function renderAll() {
  renderMedia();
  renderBrief();
  renderStage();
  renderVariants();
  renderTimeline();
  renderExports();
  renderShorts();
  renderDubs();
}

// ------------------------------------------------------------------ media bin

function renderMedia() {
  const p = state.project;
  $("#binCount").textContent = p.media.length ? `${p.media.length} fișiere` : "";
  const opt = $(`#projectSelect option[value="${p.id}"]`);
  if (opt) opt.textContent = `${p.name} · ${p.media.length} fișiere`;
  $("#mediaList").innerHTML = p.media.map((m) => {
    const icon = m.kind === "audio" ? "♪" : m.kind === "image" ? "🖼" : "🎬";
    const bg = m.thumb ? `style="background-image:url('${file(m.thumb)}')"` : "";
    const dur = m.kind === "image" ? "" : `<span class="dur">${fmt(m.duration)}</span>`;
    const info = m.kind === "audio" ? `audio · ${fmt(m.duration)}` : `${m.width}×${m.height}${m.kind === "video" ? ` · ${Math.round(m.fps)}fps${m.has_audio ? " · sunet" : ""}` : " · foto"}`;
    const roles = Object.entries(ROLES).filter(([r]) => r !== "music" || m.kind === "audio" || m.has_audio)
      .filter(([r]) => !(m.kind === "audio" && r !== "music"))
      .map(([r, l]) => `<option value="${r}" ${m.role === r ? "selected" : ""}>${l}</option>`).join("");
    return `<li class="media ${m.role}" data-id="${m.id}">
      <div class="thumb" ${bg}>${m.thumb ? "" : icon}${dur}</div>
      <div class="meta"><div class="name" title="${esc(m.name)}">${esc(m.name)}</div>
        <div class="info">${info}</div>${badges(m)}
        <select data-role aria-label="Rol">${roles}</select></div>
      <button class="ghost" data-del title="Șterge" aria-label="Șterge">✕</button></li>`;
  }).join("");
}

function badges(m) {
  const a = state.project.analysis[m.id];
  if (!a) return `<div class="badges"><i>se analizează…</i></div>`;
  const out = [];
  const q = a.quality;
  if (q && q.score != null) {
    const kinds = [...new Set(q.issues.map((i) => i.kind))];
    if (!kinds.length) out.push(`<i class="good">✓ cadre bune</i>`);
    kinds.forEach((k) => {
      const where = q.issues.filter((i) => i.kind === k).map((i) => `${fmt(i.start)}–${fmt(i.end)}`).join(", ");
      out.push(`<i class="warn" title="${esc(where)}">⚠ ${ISSUE_RO[k] || k}</i>`);
    });
  }
  if (a.face_ratio > 0.2) out.push(`<i>🙂 fețe</i>`);
  if (a.speech && a.speech.words.length) out.push(`<i title="${esc(a.speech.text.slice(0, 300))}">🗣 ${a.speech.words.length} cuvinte</i>`);
  if (a.speech_error) out.push(`<i class="warn" title="${esc(a.speech_error)}">🗣 fără transcriere</i>`);
  if (a.beats && a.beats.bpm) out.push(`<i>♪ ${Math.round(a.beats.bpm)} BPM${a.mood ? " · " + (MOOD_RO[a.mood.mood] || a.mood.mood) : ""}</i>`);
  return `<div class="badges">${out.join("")}</div>`;
}

$("#mediaList").addEventListener("change", async (e) => {
  if (!e.target.matches("[data-role]")) return;
  const id = e.target.closest(".media").dataset.id;
  try { state.project = await api(`/api/projects/${pid()}/media/${id}`, { method: "PATCH", body: { role: e.target.value } }); renderMedia(); }
  catch (err) { toast(err.message, true); }
});
$("#mediaList").addEventListener("click", async (e) => {
  if (!e.target.closest("[data-del]")) return;
  const li = e.target.closest(".media");
  const m = mediaById(li.dataset.id);
  if (!confirm(`Șterg „${m.name}” din proiect?`)) return;
  state.project = await api(`/api/projects/${pid()}/media/${m.id}`, { method: "DELETE" });
  renderMedia();
});

function upload(files) {
  if (!files.length) return;
  const form = new FormData();
  [...files].forEach((f) => form.append("files", f));
  form.append("role", "material");
  const bar = $("#uploadProgress");
  bar.hidden = false;
  const xhr = new XMLHttpRequest();
  xhr.open("POST", `/api/projects/${pid()}/media`);
  xhr.upload.onprogress = (e) => { if (e.lengthComputable) $("span", bar).style.width = `${(e.loaded / e.total) * 100}%`; };
  xhr.onload = () => {
    bar.hidden = true;
    $("span", bar).style.width = "0";
    let data = {};
    try { data = JSON.parse(xhr.responseText); } catch { /* ignore */ }
    if (xhr.status >= 400) return toast(data.detail || "Încărcarea a eșuat", true);
    state.project = data.project;
    renderMedia();
    if (data.job) watchJob(data.job, true);
    if (data.errors && data.errors.length) toast(data.errors.join(" · "), true);
    else toast(`Am adăugat ${files.length} fișier${files.length > 1 ? "e" : ""}`);
  };
  xhr.onerror = () => { bar.hidden = true; toast("Încărcarea a eșuat", true); };
  xhr.send(form);
}

$("#fileInput").onchange = (e) => { upload(e.target.files); e.target.value = ""; };
const drop = $("#drop");
["dragenter", "dragover"].forEach((ev) => drop.addEventListener(ev, (e) => { e.preventDefault(); drop.classList.add("over"); }));
["dragleave", "drop"].forEach((ev) => drop.addEventListener(ev, () => drop.classList.remove("over")));
drop.addEventListener("drop", (e) => { e.preventDefault(); upload(e.dataTransfer.files); });

// ------------------------------------------------------------------ brief

function renderPresets() {
  if (!state.status) return;
  const s = state.project ? state.project.settings : { preset: "reels" };
  const cur = s.style_id ? "" : s.preset;
  $("#presets").innerHTML = Object.entries(state.status.presets).map(([k, p]) =>
    `<button class="preset ${k === cur ? "on" : ""}" data-k="${k}" role="radio" aria-checked="${k === cur}" title="${esc(p.brief)}">
      <b>${esc(p.label)}</b><span>${p.aspect} · ~${p.duration}s</span></button>`).join("");
  const mine = state.status.styles || [];
  $("#myStyles").innerHTML = mine.length ? `<span class="small muted" style="align-self:center">Stilurile mele:</span>` + mine.map((st) =>
    `<span class="style-chip ${st.id === s.style_id ? "on" : ""}" data-sid="${st.id}" title="${esc(st.brief)}">★ ${esc(st.name)}
      <button data-del-style="${st.id}" aria-label="Șterge stilul">✕</button></span>`).join("") : "";
}

$("#myStyles").onclick = async (e) => {
  const del = e.target.closest("[data-del-style]");
  if (del) {
    e.stopPropagation();
    if (!confirm("Șterg stilul salvat?")) return;
    state.status = { ...state.status, ...(await api(`/api/styles/${del.dataset.delStyle}`, { method: "DELETE" })) };
    if (state.project.settings.style_id === del.dataset.delStyle) state.project.settings.style_id = "";
    renderPresets(); saveBrief();
    return;
  }
  const chip = e.target.closest(".style-chip");
  if (!chip) return;
  const st = state.status.styles.find((x) => x.id === chip.dataset.sid);
  state.project.settings.style_id = chip.dataset.sid;
  if (st) { $("#duration").value = Math.min(180, Math.max(10, st.duration)); $("#durationLabel").textContent = `${$("#duration").value}s`; }
  renderPresets();
  saveBrief();
};

function renderBrief() {
  const s = state.project.settings;
  renderPresets();
  $("#rules").value = s.rules || "";
  $("#title").value = s.title || "";
  $("#outro").value = s.outro || "";
  $("#duration").value = s.duration || 30;
  $("#durationLabel").textContent = `${s.duration || 30}s`;
  $("#captionStyle").value = s.caption_style || "";
  $("#beatFx").value = s.beat_fx || "";
  $("#autoColor").checked = s.auto_color !== false;
  $("#musicAlign").checked = s.music_align !== false;
  $("#selfReview").checked = s.self_review !== false;
  $("#voiceover").checked = !!s.voiceover;
  $("#voiceText").value = s.voiceover_text || "";
  $("#voiceBox").hidden = !s.voiceover;
  $("#tighten").checked = !!s.tighten;
  $("#voiceEnhance").checked = !!s.voice_enhance;
  $("#emphasisZoom").checked = !!s.emphasis_zoom;
  $("#sfx").checked = !!s.sfx;
  $("#autoBroll").checked = !!s.auto_broll;
  $("#portraitBg").checked = s.background === "portrait";
  $$("#aspect button").forEach((b) => b.classList.toggle("on", b.dataset.v === (s.aspect || "")));
}

function readBrief() {
  const s = state.project.settings;
  return {
    preset: s.preset, style_id: s.style_id || "", aspect: s.aspect || "",
    duration: +$("#duration").value, rules: $("#rules").value, title: $("#title").value,
    outro: $("#outro").value, auto_color: $("#autoColor").checked,
    caption_style: $("#captionStyle").value, beat_fx: $("#beatFx").value, music_align: $("#musicAlign").checked,
    self_review: $("#selfReview").checked, voiceover: $("#voiceover").checked, voiceover_text: $("#voiceText").value,
    tighten: $("#tighten").checked, voice_enhance: $("#voiceEnhance").checked, emphasis_zoom: $("#emphasisZoom").checked,
    sfx: $("#sfx").checked, auto_broll: $("#autoBroll").checked, background: $("#portraitBg").checked ? "portrait" : "",
  };
}

let saveTimer;
function saveBrief(now = false) {
  state.project.settings = readBrief();
  clearTimeout(saveTimer);
  const go = () => api(`/api/projects/${pid()}/settings`, { method: "PUT", body: state.project.settings }).catch((e) => toast(e.message, true));
  if (now) return go();
  saveTimer = setTimeout(go, 600);
}

$("#presets").onclick = (e) => {
  const b = e.target.closest(".preset");
  if (!b) return;
  const p = state.status.presets[b.dataset.k];
  state.project.settings.preset = b.dataset.k;
  state.project.settings.style_id = "";
  $("#duration").value = p.duration;
  $("#durationLabel").textContent = `${p.duration}s`;
  renderPresets();
  saveBrief();
};
$("#aspect").onclick = (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  state.project.settings.aspect = b.dataset.v;
  $$("#aspect button").forEach((x) => x.classList.toggle("on", x === b));
  saveBrief();
};
$("#duration").oninput = () => { $("#durationLabel").textContent = `${$("#duration").value}s`; saveBrief(); };
["#rules", "#title", "#outro", "#voiceText"].forEach((s) => $(s).addEventListener("input", () => saveBrief()));
["#captionStyle", "#beatFx", "#autoColor", "#musicAlign", "#selfReview", "#tighten", "#voiceEnhance", "#emphasisZoom",
  "#sfx", "#autoBroll", "#portraitBg"].forEach((s) => $(s).addEventListener("change", () => saveBrief()));
$("#voiceover").addEventListener("change", () => {
  $("#voiceBox").hidden = !$("#voiceover").checked;
  if ($("#voiceover").checked && !state.status.has_eleven) toast("Pentru voce off pune cheia ElevenLabs în Setări ⚙", true);
  saveBrief();
});

async function generate(mode, what = "generate") {
  try {
    await saveBrief(true);
    const job = await api(`/api/projects/${pid()}/${what}`, { method: "POST", body: { mode } });
    watchJob(job);
  } catch (e) {
    toast(e.message, true);
    if (/cheia API/i.test(e.message)) $("#openSettings").click();
  }
}
$("#generateAi").onclick = () => generate("ai");
$("#generateAuto").onclick = () => generate("auto");
$("#generateVariants").onclick = () => generate(state.status.has_key ? "ai" : "auto", "variants");

// ------------------------------------------------------------------ jobs

const JOB_KIND = { generate: "Montaj nou", revise: "Revizie", preview: "Previzualizare", export: "Export final",
  analyze: "Analiza materialului", variants: "3 variante", review: "Auto-verificare", shorts: "Shorts din video lung",
  dub: "Dublaj", clone: "Clonarea vocii" };

function watchJob(job, quiet = false) {
  state.job = job;
  clearInterval(state.pollTimer);
  renderJob();
  if (!quiet) $("#jobPanel").scrollIntoView({ behavior: "smooth", block: "nearest" });
  setBusy(true);
  state.pollTimer = setInterval(async () => {
    try { state.job = await api(`/api/jobs/${state.job.id}`); }
    catch { clearInterval(state.pollTimer); setBusy(false); return; }
    renderJob();
    if (state.job.status !== "running") {
      clearInterval(state.pollTimer);
      setBusy(false);
      const kind = state.job.kind;
      const DONE = { export: "Export gata! Fișierele sunt mai jos.", analyze: "Am analizat materialul.",
        variants: "Cele 3 variante sunt gata — alege una.", review: "Verificare terminată.",
        shorts: "Shorts-urile sunt gata!", dub: "Dublajul e gata!", clone: "Vocea ta e clonată!" };
      if (state.job.status === "error") toast(state.job.error, true);
      else toast(DONE[kind] || "Gata! Uită-te la previzualizare.");
      await refresh();
      if (state.job.status !== "done" || kind === "analyze") { /* stay put */ }
      else if (kind === "export") $("#exportPanel").scrollIntoView({ behavior: "smooth" });
      else if (kind === "variants") $("#variantsPanel").scrollIntoView({ behavior: "smooth" });
      else if (kind === "shorts") $("#shortsPanel").scrollIntoView({ behavior: "smooth" });
      else if (kind === "dub") $("#dubs").scrollIntoView({ behavior: "smooth" });
      else if (kind === "clone") { await loadStatus(); }
      else $("#stage").scrollIntoView({ behavior: "smooth" });
      if (state.job.status === "done") setTimeout(() => ($("#jobPanel").hidden = true), 2500);
    }
  }, 700);
}

function renderJob() {
  const j = state.job;
  $("#jobPanel").hidden = false;
  $("#jobMessage").textContent = j.status === "error" ? "Ceva n-a mers" : j.message;
  $("#jobKind").textContent = JOB_KIND[j.kind] || j.kind;
  $("#jobPct").textContent = `${Math.round(j.progress * 100)}%`;
  $("#jobBar").style.width = `${j.progress * 100}%`;
  $("#jobSpinner").className = "spinner" + (j.status === "done" ? " done" : j.status === "error" ? " error" : "");
  $("#jobLog").innerHTML = j.log.map((l) => `<li><span class="muted">${l.t}s</span> ${esc(l.text)}</li>`).join("");
  $("#jobLog").scrollTop = 1e6;
}

function setBusy(busy) {
  ["#generateAi", "#generateAuto", "#generateVariants", "#exportBtn", "#undo", "#inspApply", "#reviewBtn", "#saveStyle",
    "#shortsBtn", "#dubBtn"]
    .forEach((s) => ($(s).disabled = busy));
  $("#chatForm button").disabled = busy;
}

// ------------------------------------------------------------------ preview & chat

function renderStage() {
  const p = state.project;
  const has = !!p.plan;
  $("#stage").hidden = !has;
  $("#tlPanel").hidden = !has;
  $("#exportPanel").hidden = !has;
  $("#emptyState").hidden = has;
  if (!has) return;
  const plan = p.plan;
  const v = $("#video");
  if (p.preview && !v.src.endsWith(p.preview.file)) {
    v.src = file(p.preview.file);
    const [w, h] = plan.aspect.split(":").map(Number);
    $("#player").style.aspectRatio = `${w} / ${h}`;
  }
  $("#previewInfo").textContent = p.preview
    ? `Previzualizare ${p.preview.width}×${p.preview.height} · ${fmt(p.preview.duration)} · ${plan.clips.length} clipuri · ${plan.aspect}` : "";
  $("#planTitle").textContent = plan.title;
  $("#planLabel").textContent = p.plan_label || "";
  $("#planSummary").textContent = plan.summary;
  $("#issues").innerHTML = [
    ...(p.issues || []).map((t) => `<li>⚙ ${esc(t)}</li>`),
    ...(plan.notes || []).map((t) => `<li class="note">💡 ${esc(t)}</li>`),
  ].join("");
  $("#chatLog").innerHTML = p.chat.map((m) => `<div class="msg ${m.role}">${esc(m.text)}</div>`).join("")
    || `<div class="muted small">Scrie ce vrei să schimbi și agentul reface montajul.</div>`;
  $("#chatLog").scrollTop = 1e6;
  $("#quick").innerHTML = QUICK.map((q) => `<button type="button">${esc(q)}</button>`).join("");
  $("#undo").disabled = !p.history.length;
  const r = p.review;
  $("#review").hidden = !r;
  if (r) {
    const ring = r.score >= 8 ? "var(--ok)" : r.score >= 6 ? "var(--warn)" : "var(--err)";
    $("#review").innerHTML = `<div class="score" style="--p:${r.score * 10};--ring:${ring}"><span>${r.score}</span></div>
      <div><b>Auto-verificare (runda ${r.round}):</b> ${esc(r.verdict)}
      ${r.problems.length ? `<ul>${r.problems.map((x) => `<li>${esc(x)}</li>`).join("")}</ul>` : ""}</div>`;
  }
}

function renderVariants() {
  const vs = state.project.variants || [];
  $("#variantsPanel").hidden = !vs.length;
  $("#variantGrid").innerHTML = vs.map((v, i) => `<div class="variant">
    <video src="${file(v.preview.file)}" controls playsinline preload="metadata"></video>
    <h4>${esc(v.label)} <span class="badge">${fmt(v.preview.duration)} · ${v.plan.clips.length} clipuri</span></h4>
    <p>${esc(v.plan.summary)}</p>
    <button class="primary" data-choose="${i}">Alege varianta asta</button></div>`).join("");
}

$("#variantGrid").onclick = async (e) => {
  const b = e.target.closest("[data-choose]");
  if (!b) return;
  try {
    state.project = await api(`/api/projects/${pid()}/variants/choose`, { method: "POST", body: { index: +b.dataset.choose } });
    renderAll();
    toast("Varianta aleasă e acum montajul tău. O poți rafina în chat sau pe timeline.");
    $("#stage").scrollIntoView({ behavior: "smooth" });
  } catch (err) { toast(err.message, true); }
};
$("#saveStyle").onclick = async () => {
  const name = prompt("Numele stilului:", state.project.plan.title);
  if (name === null) return;
  try {
    state.status = { ...state.status, ...(await api(`/api/projects/${pid()}/styles`, { method: "POST", body: { name } })) };
    renderPresets();
    toast("Stil salvat! Îl găsești la „Stilurile mele”.");
  } catch (e) { toast(e.message, true); }
};
$("#reviewBtn").onclick = async () => {
  try { watchJob(await api(`/api/projects/${pid()}/review`, { method: "POST" })); }
  catch (e) { toast(e.message, true); if (/cheia API/i.test(e.message)) $("#openSettings").click(); }
};

$("#quick").onclick = (e) => { if (e.target.matches("button")) { $("#chatInput").value = e.target.textContent; $("#chatInput").focus(); } };
$("#chatForm").onsubmit = async (e) => {
  e.preventDefault();
  const feedback = $("#chatInput").value.trim();
  if (!feedback) return;
  try {
    const job = await api(`/api/projects/${pid()}/revise`, { method: "POST", body: { feedback } });
    $("#chatInput").value = "";
    state.project.chat.push({ role: "user", text: feedback });
    renderStage();
    watchJob(job);
  } catch (err) { toast(err.message, true); }
};
$("#undo").onclick = async () => {
  try { const r = await api(`/api/projects/${pid()}/undo`, { method: "POST" }); await refresh(); watchJob(r.job); }
  catch (e) { toast(e.message, true); }
};

// ------------------------------------------------------------------ timeline

function clipFrame(clip) {
  const info = state.project.analysis[clip.media_id];
  const m = mediaById(clip.media_id);
  if (info && info.frames && info.frames.length) {
    const mid = (clip.start + clip.end) / 2;
    const f = info.frames.reduce((a, b) => (Math.abs(b.t - mid) < Math.abs(a.t - mid) ? b : a));
    return file(`frames/${f.file}`);
  }
  return m && m.thumb ? file(m.thumb) : "";
}

let pps = 40;
function renderTimeline() {
  const p = state.project;
  if (!p.plan || !p.timeline) return;
  const plan = p.plan;
  const tl = p.timeline;
  const total = tl.length ? tl[tl.length - 1].start + tl[tl.length - 1].length : 0;
  const width = Math.max(300, $("#timeline").clientWidth - 4);
  pps = Math.max(28, width / Math.max(total, 1));
  const inner = Math.ceil(total * pps) + 2;
  ["#ruler", "#track", "#textTrack", "#musicTrack"].forEach((s) => ($(s).style.width = `${inner}px`));

  const step = total > 120 ? 10 : total > 40 ? 5 : total > 15 ? 2 : 1;
  let ruler = "";
  for (let t = 0; t <= total; t += step) ruler += `<span class="tick" style="left:${t * pps}px">${fmt(t)}</span>`;
  if (plan.music) {
    const beats = ((p.analysis[plan.music.media_id] || {}).beats || {}).beats || [];
    beats.forEach((b) => { const t = b - plan.music.start; if (t >= 0 && t <= total) ruler += `<span class="beat" style="left:${t * pps}px"></span>`; });
  }
  $("#ruler").innerHTML = ruler;

  $("#track").innerHTML = plan.clips.map((c, i) => {
    const pos = tl[i];
    const tags = [];
    if (Math.abs(c.speed - 1) > 0.01) tags.push(`${c.speed}×`);
    if (c.motion !== "none") tags.push("↗");
    if (c.color.look !== "none") tags.push(LOOKS[c.color.look]);
    if (c.keep_audio) tags.push("🔊");
    const trans = i > 0 && c.transition_in !== "cut" ? `<span class="tl-trans" style="left:${pos.start * pps}px" title="${TRANS_RO[c.transition_in]}">⇄</span>` : "";
    const m = mediaById(c.media_id);
    return `${trans}<div class="tl-clip ${i === state.sel ? "sel" : ""}" draggable="true" data-i="${i}"
      style="left:${pos.start * pps + 1}px;width:${Math.max(8, pos.length * pps - 2)}px;background-image:url('${clipFrame(c)}')"
      title="${esc((m ? m.name : c.media_id) + " · " + fmt(pos.length) + (c.reason ? " — " + c.reason : ""))}">
      <div class="tags">${tags.map((t) => `<i>${esc(t)}</i>`).join("")}</div>
      <div class="lbl">${i + 1}. ${esc(m ? m.name : c.media_id)}</div></div>`;
  }).join("");

  const texts = [];
  plan.clips.forEach((c, i) => c.overlays.forEach((o) => texts.push({ s: tl[i].start + o.start, d: o.duration, t: o.text })));
  (plan.captions || []).forEach((c) => texts.push({ s: c.start, d: c.end - c.start, t: c.text }));
  $("#textTrack").innerHTML = texts.map((x) => `<span style="left:${x.s * pps}px;width:${Math.max(6, x.d * pps - 2)}px" title="${esc(x.t)}">T ${esc(x.t)}</span>`).join("");

  const mu = plan.music && mediaById(plan.music.media_id);
  $("#musicTrack").innerHTML = mu ? `<span style="left:0;width:${total * pps}px">♪ ${esc(mu.name)}${plan.snap_to_beat ? " · tăieturi pe beat" : ""}${plan.music.duck ? " · se coboară sub voce" : ""}</span>` : "";
}

window.addEventListener("resize", () => { if (state.project) renderTimeline(); });
$("#video").addEventListener("timeupdate", () => { $("#playhead").style.left = `${$("#video").currentTime * pps}px`; });
$("#ruler").addEventListener("click", (e) => {
  const x = e.clientX - $("#ruler").getBoundingClientRect().left;
  $("#video").currentTime = x / pps;
});

let dragFrom = -1;
$("#track").addEventListener("dragstart", (e) => {
  const c = e.target.closest(".tl-clip");
  if (!c) return;
  dragFrom = +c.dataset.i;
  c.classList.add("dragging");
  e.dataTransfer.effectAllowed = "move";
});
$("#track").addEventListener("dragend", () => $$(".tl-clip").forEach((c) => c.classList.remove("dragging", "drop-before")));
$("#track").addEventListener("dragover", (e) => {
  const c = e.target.closest(".tl-clip");
  if (!c) return;
  e.preventDefault();
  $$(".tl-clip").forEach((x) => x.classList.toggle("drop-before", x === c));
});
$("#track").addEventListener("drop", async (e) => {
  const c = e.target.closest(".tl-clip");
  if (!c || dragFrom < 0) return;
  e.preventDefault();
  const to = +c.dataset.i;
  if (to === dragFrom) return;
  const clips = state.project.plan.clips;
  const [moved] = clips.splice(dragFrom, 1);
  clips.splice(to > dragFrom ? to - 1 : to, 0, moved);
  dragFrom = -1;
  await savePlan("Am mutat clipul");
});
$("#track").addEventListener("click", (e) => {
  const c = e.target.closest(".tl-clip");
  if (!c) return;
  const i = +c.dataset.i;
  $("#video").currentTime = state.project.timeline[i].start + 0.05;
  openInspector(i);
});

async function savePlan(msg) {
  try {
    const r = await api(`/api/projects/${pid()}/plan`, { method: "PUT", body: { plan: state.project.plan, render: true } });
    if (msg) toast(msg);
    await refresh();
    if (r.job) watchJob(r.job);
  } catch (e) { toast(e.message, true); await refresh(); }
}

// ------------------------------------------------------------------ clip inspector

const opts = (map, cur) => Object.entries(map).map(([k, v]) => `<option value="${k}" ${k === cur ? "selected" : ""}>${esc(v)}</option>`).join("");
const slider = (name, label, min, max, stepv, val) =>
  `<label class="slider"><span>${label}</span><input type="range" name="${name}" min="${min}" max="${max}" step="${stepv}" value="${val}"><output>${(+val).toFixed(2)}</output></label>`;

function overlayHtml(o, k) {
  return `<div class="ovl" data-k="${k}">
    <label class="field"><span>Text</span><input name="text" value="${esc(o.text)}"></label>
    <div class="grid2">
      <label class="field"><span>Stil</span><select name="style">${opts(STYLES, o.style)}</select></label>
      <label class="field"><span>Poziție</span><select name="position">${opts(POSITIONS, o.position)}</select></label>
      <label class="field"><span>Animație</span><select name="animation">${opts(ANIMS, o.animation || "fade")}</select></label>
      <span></span>
      <label class="field"><span>Apare la (s)</span><input type="number" step="0.1" min="0" name="start" value="${o.start}"></label>
      <label class="field"><span>Durată (s)</span><input type="number" step="0.1" min="0.3" name="duration" value="${o.duration}"></label>
    </div>
    <button class="ghost small" data-rm-ovl>Șterge textul</button></div>`;
}

const BG = { none: "Original", portrait: "Portret (blurat)", replace: "Înlocuit cu alt fișier" };
const mediaOpts = (cur, exclude) => state.project.media.filter((m) => (m.kind === "video" || m.kind === "image") && m.id !== exclude)
  .map((m) => `<option value="${m.id}" ${m.id === cur ? "selected" : ""}>${esc(m.name)}</option>`).join("");
const brollHtml = (b) => `<div class="broll-item">
  <label class="field"><span>Fișier</span><select data-b="media_id">${mediaOpts(b.media_id, state.editing && state.editing.media_id)}</select></label>
  <label class="field"><span>La (s)</span><input type="number" step="0.1" min="0" data-b="at" value="${b.at}"></label>
  <label class="field"><span>Durată</span><input type="number" step="0.1" min="0.5" data-b="duration" value="${b.duration}"></label>
  <button class="ghost" data-rm-broll title="Șterge">✕</button></div>`;

function openInspector(i) {
  state.sel = i;
  renderTimeline();
  const c = structuredClone(state.project.plan.clips[i]);
  state.editing = c;
  const m = mediaById(c.media_id);
  $("#inspTitle").textContent = `Clip ${i + 1} · ${m ? m.name : c.media_id}`;
  const isImg = m && m.kind === "image";
  $("#inspBody").innerHTML = `
    ${c.reason ? `<div class="reason">🤖 ${esc(c.reason)}</div>` : ""}
    <h4>Tăiere</h4>
    <div class="grid2">
      ${isImg ? `<label class="field"><span>Durată pe ecran (s)</span><input type="number" step="0.1" min="0.5" name="end" value="${c.end}"></label>`
              : `<label class="field"><span>Început (s) din ${fmt(m ? m.duration : 0)}</span><input type="number" step="0.1" min="0" name="start" value="${c.start}"></label>
                 <label class="field"><span>Sfârșit (s)</span><input type="number" step="0.1" min="0" name="end" value="${c.end}"></label>`}
    </div>
    ${isImg ? "" : slider("speed", "Viteză", 0.25, 3, 0.05, c.speed)}
    <h4>Cadru și mișcare</h4>
    <div class="grid2">
      <label class="field"><span>Încadrare</span><select name="fit">${opts(FITS, c.fit)}</select></label>
      <label class="field"><span>Mișcare</span><select name="motion">${opts(MOTIONS, c.motion)}</select></label>
      <label class="field"><span>Tranziție de intrare</span><select name="transition_in">${opts(TRANS_RO, c.transition_in)}</select></label>
      <label class="field"><span>Durată tranziție (s)</span><input type="number" step="0.05" min="0.15" max="1.5" name="transition_duration" value="${c.transition_duration}"></label>
    </div>
    <h4>Fundal</h4>
    <div class="grid2">
      <label class="field"><span>Fundalul din spatele persoanei</span><select name="background">${opts(BG, c.background || "none")}</select></label>
      <label class="field"><span>Fundal nou (la „înlocuit”)</span><select name="background_media"><option value="">—</option>${mediaOpts(c.background_media, c.media_id)}</select></label>
    </div>
    <h4>B-roll peste clip <span class="muted">(sunetul clipului continuă)</span></h4>
    <div id="brolls">${(c.broll || []).map(brollHtml).join("")}</div>
    <button class="secondary" id="addBroll">＋ Adaugă B-roll</button>
    <h4>Lumină și culoare</h4>
    ${slider("color.brightness", "Luminozitate", -0.3, 0.3, 0.01, c.color.brightness)}
    ${slider("color.contrast", "Contrast", 0.6, 1.6, 0.01, c.color.contrast)}
    ${slider("color.saturation", "Saturație", 0, 2, 0.01, c.color.saturation)}
    ${slider("color.warmth", "Temperatură", -1, 1, 0.05, c.color.warmth)}
    <div class="grid2">
      <label class="field"><span>Look</span><select name="color.look">${opts(LOOKS, c.color.look)}</select></label>
      <label class="toggle" style="margin-top:22px"><input type="checkbox" name="color.vignette" ${c.color.vignette ? "checked" : ""}><span></span>Vignetă</label>
    </div>
    ${m && m.has_audio && !isImg ? `<h4>Sunet</h4>
      <label class="toggle"><input type="checkbox" name="keep_audio" ${c.keep_audio ? "checked" : ""}><span></span>Păstrează sunetul clipului</label>
      ${slider("volume", "Volum", 0, 2, 0.05, c.volume)}` : ""}
    <h4>Text pe ecran</h4>
    <div id="ovls">${c.overlays.map(overlayHtml).join("")}</div>
    <button class="secondary" id="addOvl">＋ Adaugă text</button>`;
  $("#inspector").hidden = false;
}

function closeInspector() {
  $("#inspector").hidden = true;
  if (state.sel >= 0) { state.sel = -1; if (state.project) renderTimeline(); }
}

$("#inspClose").onclick = closeInspector;
document.addEventListener("keydown", (e) => { if (e.key === "Escape" && !$("#inspector").hidden) closeInspector(); });
$("#inspBody").addEventListener("input", (e) => {
  if (e.target.type === "range") e.target.nextElementSibling.textContent = (+e.target.value).toFixed(2);
});
$("#inspBody").addEventListener("click", (e) => {
  if (e.target.id === "addOvl") {
    readInspector();
    state.editing.overlays.push({ text: "Text nou", start: 0, duration: 2, style: "caption", position: "bottom", animation: "pop" });
    $("#ovls").insertAdjacentHTML("beforeend", overlayHtml(state.editing.overlays.at(-1), state.editing.overlays.length - 1));
  }
  if (e.target.matches("[data-rm-ovl]")) e.target.closest(".ovl").remove();
  if (e.target.id === "addBroll") {
    const other = state.project.media.find((m) => (m.kind === "video" || m.kind === "image") && m.id !== state.editing.media_id);
    if (!other) return toast("Încarcă și alte clipuri sau poze pentru B-roll.", true);
    $("#brolls").insertAdjacentHTML("beforeend", brollHtml({ media_id: other.id, at: 1, duration: 2, source_start: 0 }));
  }
  if (e.target.matches("[data-rm-broll]")) e.target.closest(".broll-item").remove();
});

function readInspector() {
  const c = state.editing;
  $$("#inspBody [name]").forEach((el) => {
    if (el.closest(".ovl") || el.closest(".broll-item")) return;
    const val = el.type === "checkbox" ? el.checked : el.type === "number" || el.type === "range" ? +el.value : el.value;
    const [a, b] = el.name.split(".");
    if (b) c[a][b] = val; else c[a] = val;
  });
  c.background_media = c.background_media || null;
  c.broll = $$("#brolls .broll-item").map((box) => ({
    media_id: $("[data-b=media_id]", box).value, at: +$("[data-b=at]", box).value,
    duration: +$("[data-b=duration]", box).value, source_start: 0 }));
  c.overlays = $$("#ovls .ovl").map((box) => {
    const get = (n) => $(`[name=${n}]`, box);
    return { text: get("text").value, style: get("style").value, position: get("position").value, animation: get("animation").value,
             start: +get("start").value, duration: +get("duration").value };
  });
  return c;
}

$("#inspApply").onclick = async () => {
  state.project.plan.clips[state.sel] = readInspector();
  closeInspector();
  await savePlan("Aplic modificările…");
};
$("#inspDelete").onclick = async () => {
  if (state.project.plan.clips.length < 2) return toast("Montajul trebuie să aibă cel puțin un clip.", true);
  state.project.plan.clips.splice(state.sel, 1);
  closeInspector();
  await savePlan("Clip șters");
};

// ------------------------------------------------------------------ export

$("#quality").onclick = (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  state.quality = b.dataset.v;
  $$("#quality button").forEach((x) => x.classList.toggle("on", x === b));
};
$("#exportBtn").onclick = async () => {
  const formats = $$("#formats input:checked").map((i) => i.value);
  try { watchJob(await api(`/api/projects/${pid()}/export`, { method: "POST", body: { quality: state.quality, formats } })); }
  catch (e) { toast(e.message, true); }
};

const FILE_LABEL = [[/_coperta\.jpg$/, "🖼 Copertă JPG"], [/_coperta\.png$/, "🖼 Copertă PNG"],
  [/_(\d+)x(\d+)\.mp4$/, (f) => `🎬 Video ${f.match(/_(\d+)x(\d+)\.mp4$/).slice(1).join(":")}`], [/\.mp4$/, "🎬 Video MP4"], [/\.mp3$/, "🎵 Audio MP3"],
  [/postare\.txt$/, "✍ Texte pentru postare"], [/_thumbnail_youtube\.jpg$/, "🖼 Thumbnail YouTube"],
  [/_thumbnail_vertical\.jpg$/, "🖼 Thumbnail vertical"],
  [/\.fcpxml$/, "🎛 DaVinci / FCPXML"], [/\.edl$/, "🎛 EDL"], [/\.srt$/, "💬 Subtitrări SRT"], [/_plan\.json$/, "{ } Plan JSON"]];

function renderSocial() {
  const c = state.project.social;
  $("#social").hidden = !c;
  if (!c) return;
  const copyBtn = (txt) => `<button class="ghost" data-copy="${esc(txt)}">Copiază</button>`;
  $("#social").innerHTML = `<h4>✍ Texte pentru postare</h4>
    <div class="small"><b>Hook-uri:</b> ${c.hooks.map(esc).join(" · ")}</div>
    <div class="small"><b>Titlu YouTube:</b> ${esc(c.youtube_title)} ${copyBtn(c.youtube_title)}</div>
    ${c.posts.map((p) => {
      const tags = p.hashtags.map((t) => "#" + t.replace(/^#/, "")).join(" ");
      const full = `${p.caption}\n\n${tags}`;
      return `<div class="post"><b>${esc(p.platform)} ${copyBtn(full)}</b>${esc(p.caption)}\n<span class="tags">${esc(tags)}</span></div>`;
    }).join("")}
    <div class="small muted" style="margin-top:8px">🕖 ${esc(c.best_time)}</div>`;
}
$("#social").onclick = async (e) => {
  const b = e.target.closest("[data-copy]");
  if (!b) return;
  try { await navigator.clipboard.writeText(b.dataset.copy); toast("Copiat!"); } catch { toast("Nu pot copia automat — selectează textul.", true); }
};

function renderExports() {
  renderSocial();
  const ex = state.project.exports || [];
  $("#exports").innerHTML = ex.map((e) => {
    const d = new Date(e.time * 1000);
    const files = e.files.map((f) => {
      let label = (FILE_LABEL.find(([re]) => re.test(f)) || [null, f.split("/").pop()])[1];
      if (typeof label === "function") label = label(f);
      return `<a href="${file(f)}?download=true" download>${label}</a>`;
    }).join("");
    const mp4 = e.files.find((f) => f.endsWith(".mp4"));
    return `<div class="export-item"><div class="row wrap"><strong>${d.toLocaleString("ro-RO")}</strong>
      <span class="badge">${e.quality}</span>${mp4 ? `<a href="${file(mp4)}" target="_blank" rel="noopener">▶ Deschide</a>` : ""}</div>
      <div class="files">${files}</div></div>`;
  }).join("");
}

// ------------------------------------------------------------------ shorts

function renderShorts() {
  const vids = state.project.media.filter((m) => m.kind === "video" && m.role === "material");
  const cur = $("#shortsSource").value;
  $("#shortsSource").innerHTML = vids.length
    ? vids.map((m) => `<option value="${m.id}">${esc(m.name)} · ${fmt(m.duration)}</option>`).join("")
    : `<option value="">(încarcă un video lung)</option>`;
  if (cur && vids.find((m) => m.id === cur)) $("#shortsSource").value = cur;
  else if (vids.length) $("#shortsSource").value = vids.reduce((a, b) => (b.duration > a.duration ? b : a)).id;
  const sh = state.project.shorts;
  $("#shortsGrid").innerHTML = sh && sh.items ? sh.items.map((x) => `<div class="short">
      <video src="${file(x.file)}" controls playsinline preload="metadata" ${x.cover ? `poster="${file(x.cover)}"` : ""}></video>
      <h4><span>${esc(x.title)}</span><span class="vscore" title="Scor de viralitate">🔥 ${x.score}</span></h4>
      <p>${esc(x.why)}</p>
      <p>${fmt(x.start)}–${fmt(x.end)} din original · ${fmt(x.duration)} după tăieri</p>
      <div class="links"><a href="${file(x.file)}?download=true" download>⬇ MP4</a>
        ${x.cover ? `<a href="${file(x.cover)}?download=true" download>🖼 Copertă</a>` : ""}
        <a href="#" data-copy="${esc(x.caption + "\n\n" + x.hashtags.map((t) => "#" + t.replace(/^#/, "")).join(" "))}">✍ Copiază textul</a></div>
    </div>`).join("") : "";
}

$("#shortsGrid").onclick = async (e) => {
  const b = e.target.closest("[data-copy]");
  if (!b) return;
  e.preventDefault();
  try { await navigator.clipboard.writeText(b.dataset.copy); toast("Copiat!"); } catch { toast("Nu pot copia automat.", true); }
};
$("#shortsBtn").onclick = async () => {
  const media_id = $("#shortsSource").value;
  if (!media_id) return toast("Încarcă întâi un video lung (podcast, vlog).", true);
  try {
    watchJob(await api(`/api/projects/${pid()}/shorts`, { method: "POST",
      body: { media_id, count: +$("#shortsCount").value, mode: state.status.has_key ? "ai" : "auto" } }));
  } catch (e) { toast(e.message, true); }
};

// ------------------------------------------------------------------ dubbing

const DEFAULT_LANGS = ["en", "fr", "it", "es"];
function renderLangs() {
  if (!state.status || !state.status.languages) return;
  const picked = new Set($$("#langs input:checked").map((i) => i.value));
  const use = picked.size ? picked : new Set(DEFAULT_LANGS);
  $("#langs").innerHTML = Object.entries(state.status.languages).filter(([k]) => k !== "ro").map(([k, name]) =>
    `<label class="chip"><input type="checkbox" value="${k}" ${use.has(k) ? "checked" : ""}><span>${k.toUpperCase()} · ${esc(name)}</span></label>`).join("");
  const s = state.status;
  $("#voiceRow").innerHTML = !s.has_eleven ? "Pentru dublaj cu voce pune cheia ElevenLabs în ⚙ Setări."
    : s.my_voice ? `Vocea folosită: <b>„${esc(s.my_voice)}” (clonată)</b>` : "Vocea folosită: una standard. Clonează-ți vocea din ⚙ Setări ca să sune ca tine.";
}

let dubMode = "voice";
$("#dubMode").onclick = (e) => {
  const b = e.target.closest("button");
  if (!b) return;
  dubMode = b.dataset.v;
  $$("#dubMode button").forEach((x) => x.classList.toggle("on", x === b));
};
$("#dubBtn").onclick = async () => {
  const languages = $$("#langs input:checked").map((i) => i.value);
  if (!languages.length) return toast("Alege cel puțin o limbă.", true);
  try { watchJob(await api(`/api/projects/${pid()}/dub`, { method: "POST", body: { languages, mode: dubMode, quality: state.quality } })); }
  catch (e) { toast(e.message, true); if (/Setări/.test(e.message)) $("#openSettings").click(); }
};

function renderDubs() {
  const d = state.project.dubs;
  $("#dubs").innerHTML = d && d.items ? d.items.map((x) => `<div class="dub-item"><b>${x.lang.toUpperCase()}</b> ${esc(x.name)}
      <a href="${file(x.file)}" target="_blank" rel="noopener">▶ Vezi</a>
      <a href="${file(x.file)}?download=true" download>⬇ MP4</a>
      <a href="${file(x.srt)}?download=true" download>💬 SRT</a></div>`).join("")
      + (d.issues || []).map((t) => `<div class="small muted">⚙ ${esc(t)}</div>`).join("") : "";
}

$("#cloneBtn").onclick = async () => {
  try {
    const job = await api("/api/voice/clone", { method: "POST", body: { project_id: pid(), consent: $("#cloneConsent").checked } });
    $("#settings").close();
    watchJob(job);
  } catch (e) { toast(e.message, true); }
};
$("#forgetVoice").onclick = async () => {
  state.status = { ...state.status, ...(await api("/api/voice/clone", { method: "DELETE" })) };
  $("#cloneState").textContent = "— încă nu e creată";
  renderLangs();
  toast("Am uitat vocea clonată (din aplicație).");
};

// ------------------------------------------------------------------ boot

(async function boot() {
  try {
    await loadStatus();
    await loadProjects();
  } catch (e) {
    toast("Nu pot porni: " + e.message, true);
  }
})();
