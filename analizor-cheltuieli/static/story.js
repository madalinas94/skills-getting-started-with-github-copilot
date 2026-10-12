// „Povestea lunii” – slide-uri pe tot ecranul, ca un recap de tip Wrapped.
// Atingi dreapta/stânga (sau swipe, săgeți) ca să navighezi; ții apăsat ca să pui pauză.
const Story = (() => {
  const DURATION = 5600;
  let slides = [], idx = 0, timer = 0, start = 0, paused = false, elapsed = 0, root = null, summary = "", celebrated = false;

  function countUp(el) {
    const to = +el.dataset.count, fmt = el._fmt || ((v) => Math.round(v));
    const t0 = performance.now(), dur = 1200;
    (function step(now) {
      const p = Math.min(1, (now - t0) / dur), e = 1 - Math.pow(1 - p, 3);
      el.textContent = fmt(to * e);
      if (p < 1) requestAnimationFrame(step);
    })(t0);
  }

  function build(d) {
    const s = [];
    s.push({ bg: "g1", html: `<div class="st-finn">${Finn.svg({ wave: true })}</div>
      <p class="st-kicker">${t("story.title")}</p><h2 class="st-huge">${d.month}</h2><p class="st-sub">${t("story.s1")}</p>` });
    s.push({ bg: "g2", html: `<p class="st-kicker">${t("story.spent")}</p>
      <h2 class="st-huge" data-count="${d.spent}" data-fmt="money">0</h2><p class="st-sub">${t("story.payments", { n: d.count })}</p>
      ` });
    if (d.topCat) s.push({ bg: "g3", html: `<p class="st-kicker">${t("story.topCat")}</p>
      <div class="st-big-emoji">${d.topCat.icon}</div><h2 class="st-title">${d.topCat.name}</h2>
      <div class="st-ring" style="--p:${d.topCat.share};--c:${d.topCat.color}"><span data-count="${d.topCat.share}" data-fmt="pct">0</span></div>
      <p class="st-sub">${t("story.ofAll")} · ${d.topCat.value}</p>` });
    if (d.biggest) s.push({ bg: "g4", html: `<p class="st-kicker">${t("story.biggest")}</p>
      <div class="st-big-emoji">${icon("crown")}</div><h2 class="st-title">${d.biggest.name}</h2>
      <h3 class="st-num" data-count="${d.biggest.amount}" data-fmt="money">0</h3><p class="st-sub">${d.biggest.date}</p>` });
    if (d.busiest) s.push({ bg: "g5", html: `<p class="st-kicker">${t("story.busiest")}</p>
      <div class="st-big-emoji">${icon("calendar")}</div><h2 class="st-title">${d.busiest.weekday}</h2>
      <p class="st-sub">${d.busiest.date}</p><h3 class="st-num" data-count="${d.busiest.amount}" data-fmt="money">0</h3>` });
    if (d.topMerchant) s.push({ bg: "g6", html: `<p class="st-kicker">${t("story.topMerchant")}</p>
      <div class="st-big-emoji">${icon("seal")}</div><h2 class="st-title">${d.topMerchant.name}</h2>
      <p class="st-sub">${t("story.visits", { n: d.topMerchant.visits, a: d.topMerchant.total })}</p>` });
    if (d.subsYear > 0) s.push({ bg: "g7", html: `<p class="st-kicker">${t("story.subs")}</p>
      <div class="st-big-emoji">${icon("fun")}</div><h3 class="st-num" data-count="${d.subsYear}" data-fmt="money">0</h3>
      <p class="st-sub">${t("story.subsYear")}</p>` });
    if (d.saveYear > 0) s.push({ bg: "g8", html: `<p class="st-kicker">${t("story.save")}</p>
      <div class="st-big-emoji">${icon("piggy")}</div><h2 class="st-huge" data-count="${d.saveYear}" data-fmt="money">0</h2>
      <p class="st-sub">${t("story.saveYear", { n: d.saveN })}</p>` });
    s.push({ bg: "g9", final: true, html: `<p class="st-kicker">${t("story.you")}</p>
      <div class="st-persona">${d.persona.emoji}</div><h2 class="st-title">${d.persona.title}</h2>
      <p class="st-sub">${d.persona.text}</p>
      <div class="st-score"><span>${t("story.score")}</span><b data-count="${d.score}">0</b><em>${d.scoreLabel}</em></div>
      <div class="st-actions"><button class="btn gold" data-share>${t("story.share")}</button><button class="btn ghost" data-close>${t("story.close")}</button></div>` });
    return s;
  }

  function open(data) {
    close();
    slides = build(data);
    summary = data.summary;
    idx = 0;
    celebrated = false;
    root = document.createElement("div");
    root.className = "story";
    root.innerHTML = `<div class="st-bars">${slides.map(() => `<i><b></b></i>`).join("")}</div>
      <button class="st-x" data-close aria-label="${t("story.close")}">${icon("close")}</button>
      <div class="st-stage"></div>
      <div class="st-hint">${t("story.tap")}</div>`;
    document.body.appendChild(root);
    document.body.classList.add("no-scroll");
    bind();
    show(0);
  }

  function show(i) {
    idx = Math.max(0, Math.min(slides.length - 1, i));
    const sl = slides[idx];
    root.dataset.bg = sl.bg;
    const stage = root.querySelector(".st-stage");
    stage.innerHTML = `<div class="st-slide">${sl.html}</div>`;
    stage.querySelectorAll("[data-count]").forEach((el) => {
      el._fmt = el.dataset.fmt === "money" ? (v) => fmt(v) : el.dataset.fmt === "pct" ? (v) => Math.round(v) + "%" : (v) => Math.round(v);
      countUp(el);
    });
    root.querySelectorAll(".st-bars i").forEach((b, j) => {
      b.classList.toggle("done", j < idx);
      b.classList.toggle("on", j === idx);
      b.querySelector("b").style.width = j < idx ? "100%" : "0%";
    });
    if (sl.final && !celebrated) { celebrated = true; setTimeout(() => confetti(160), 350); }
    elapsed = 0; start = performance.now(); paused = false;
    cancelAnimationFrame(timer);
    tick();
  }

  function tick() {
    timer = requestAnimationFrame((now) => {
      if (!root) return;
      const total = paused ? elapsed : elapsed + (now - start);
      const p = Math.min(1, total / DURATION);
      const bar = root.querySelectorAll(".st-bars i b")[idx];
      if (bar) bar.style.width = p * 100 + "%";
      if (p >= 1 && !slides[idx].final) return show(idx + 1);
      tick();
    });
  }

  function pause(on) {
    if (on && !paused) { elapsed += performance.now() - start; paused = true; }
    else if (!on && paused) { start = performance.now(); paused = false; }
  }

  function bind() {
    let x0 = 0, y0 = 0, t0 = 0;
    root.addEventListener("pointerdown", (e) => { x0 = e.clientX; y0 = e.clientY; t0 = Date.now(); pause(true); });
    root.addEventListener("pointerup", (e) => {
      pause(false);
      if (e.target.closest("[data-close]")) return close();
      if (e.target.closest("[data-share]")) return share();
      if (e.target.closest("button")) return;
      const dx = e.clientX - x0, dy = e.clientY - y0;
      if (Math.abs(dy) > 90 && dy > 0) return close();  // swipe în jos = închide
      if (Math.abs(dx) > 50) return show(idx + (dx < 0 ? 1 : -1));
      if (Date.now() - t0 > 350) return;  // a fost o apăsare lungă (pauză), nu un tap
      show(idx + (e.clientX > innerWidth * 0.33 ? 1 : -1));
    });
    root.addEventListener("pointercancel", () => pause(false));
  }

  async function share() {
    try {
      if (navigator.share) await navigator.share({ title: "Finn", text: summary });
      else { await navigator.clipboard.writeText(summary); toast(t("story.copied")); }
    } catch { /* utilizatorul a anulat */ }
  }

  function close() {
    cancelAnimationFrame(timer);
    root?.remove();
    root = null;
    document.body.classList.remove("no-scroll");
  }

  addEventListener("keydown", (e) => {
    if (!root) return;
    if (e.key === "ArrowRight" || e.key === " ") { e.preventDefault(); show(idx + 1); }
    if (e.key === "ArrowLeft") show(idx - 1);
    if (e.key === "Escape") close();
  });

  return { open, close, isOpen: () => !!root };
})();
