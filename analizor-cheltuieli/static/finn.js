// Finn – robotul-asistent. SVG animat: plutește, clipește, urmărește cursorul cu privirea
// și își schimbă expresia după scorul financiar (great / good / watch / critical).
const Finn = (() => {
  let uid = 0;
  let mood = "good";

  function svg({ wave = false, size = "" } = {}) {
    const id = "f" + uid++;
    return `<svg class="finn mood-${mood} ${wave ? "wave" : ""} ${size}" viewBox="0 0 120 150" role="img" aria-label="Finn">
      <defs>
        <radialGradient id="${id}o" cx="35%" cy="28%" r="80%">
          <stop offset="0" stop-color="#a5f3fc"/><stop offset=".35" stop-color="#60a5fa"/>
          <stop offset=".7" stop-color="#8b5cf6"/><stop offset="1" stop-color="#db2777"/>
        </radialGradient>
        <linearGradient id="${id}v" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#0f1535"/><stop offset="1" stop-color="#070a1f"/></linearGradient>
        <radialGradient id="${id}j"><stop offset="0" stop-color="#fde68a"/><stop offset=".5" stop-color="#fb923c" stop-opacity=".8"/><stop offset="1" stop-color="#f43f5e" stop-opacity="0"/></radialGradient>
        <filter id="${id}g" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="1.6" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      </defs>
      <ellipse class="f-shadow" cx="60" cy="143" rx="26" ry="4" fill="#000" opacity=".35"/>
      <g class="f-body">
        <ellipse class="f-jet" cx="60" cy="116" rx="11" ry="15" fill="url(#${id}j)"/>
        <line x1="60" y1="20" x2="60" y2="9" stroke="#c4b5fd" stroke-width="3" stroke-linecap="round"/>
        <circle class="f-antenna" cx="60" cy="8" r="5" fill="#fde047"/>
        <g class="f-hand-l"><rect x="5" y="70" width="12" height="20" rx="6" fill="#7c3aed"/></g>
        <g class="f-hand-r"><rect x="103" y="70" width="12" height="20" rx="6" fill="#7c3aed"/></g>
        <circle cx="13" cy="60" r="7" fill="#6d28d9"/><circle cx="107" cy="60" r="7" fill="#6d28d9"/>
        <circle cx="60" cy="62" r="45" fill="url(#${id}o)"/>
        <ellipse cx="44" cy="35" rx="15" ry="8" fill="#fff" opacity=".35" transform="rotate(-25 44 35)"/>
        <rect x="24" y="45" width="72" height="36" rx="18" fill="url(#${id}v)" stroke="#ffffff22" stroke-width="1.5"/>
        <g class="f-brows"><path d="M38 51 Q44 47 51 47" stroke="#5eead4" stroke-width="2.5" fill="none" stroke-linecap="round"/><path d="M82 51 Q76 47 69 47" stroke="#5eead4" stroke-width="2.5" fill="none" stroke-linecap="round"/></g>
        <g class="f-eyes" filter="url(#${id}g)">
          <ellipse class="f-eye" cx="46" cy="61" rx="6" ry="7.5" fill="#5eead4"/>
          <ellipse class="f-eye" cx="74" cy="61" rx="6" ry="7.5" fill="#5eead4"/>
          <path class="f-happy" d="M40 63 Q46 55 52 63 M68 63 Q74 55 80 63" stroke="#5eead4" stroke-width="3.2" fill="none" stroke-linecap="round"/>
        </g>
        <path class="f-mouth" d="M53 73 Q60 78 67 73" stroke="#5eead4" stroke-width="2.6" fill="none" stroke-linecap="round"/>
        <circle class="f-blush" cx="33" cy="72" r="4" fill="#f472b6" opacity=".6"/><circle class="f-blush" cx="87" cy="72" r="4" fill="#f472b6" opacity=".6"/>
        <circle cx="60" cy="99" r="6" fill="#fde047" opacity=".9"/><text x="60" y="101.6" text-anchor="middle" font-size="7" font-weight="900" fill="#78350f" font-family="sans-serif">F</text>
      </g>
    </svg>`;
  }

  // ochii urmăresc cursorul / degetul
  let px = innerWidth / 2, py = innerHeight / 3, raf = 0;
  function track() {
    raf = 0;
    document.querySelectorAll(".finn .f-eyes").forEach((g) => {
      const r = g.ownerSVGElement.getBoundingClientRect();
      if (!r.width) return;
      const cx = r.left + r.width / 2, cy = r.top + r.height * 0.42;
      const dx = px - cx, dy = py - cy, dist = Math.hypot(dx, dy) || 1;
      const k = Math.min(1, dist / 300);
      g.style.transform = `translate(${(dx / dist) * 4.5 * k}px, ${(dy / dist) * 3 * k}px)`;
    });
  }
  addEventListener("pointermove", (e) => { px = e.clientX; py = e.clientY; if (!raf) raf = requestAnimationFrame(track); }, { passive: true });

  function setMood(level) {
    mood = level || "good";
    document.querySelectorAll(".finn").forEach((s) => {
      s.classList.remove("mood-great", "mood-good", "mood-watch", "mood-critical");
      s.classList.add(`mood-${mood}`);
    });
  }

  function talk(on) { document.querySelectorAll(".finn").forEach((s) => s.classList.toggle("talk", on)); }

  // robotul face cu mâna din nou (la salut, după upload etc.)
  function wave(el) {
    const s = el?.querySelector(".finn");
    if (!s) return;
    s.classList.remove("wave");
    void s.getBoundingClientRect();
    s.classList.add("wave");
  }

  return { svg, setMood, talk, wave, track };
})();

// Confetti simplu pe canvas, pentru momentele de „bravo”.
function confetti(n = 140) {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const c = document.createElement("canvas");
  c.className = "confetti";
  c.width = innerWidth * devicePixelRatio; c.height = innerHeight * devicePixelRatio;
  document.body.appendChild(c);
  const ctx = c.getContext("2d");
  ctx.scale(devicePixelRatio, devicePixelRatio);
  const colors = ["#8b5cf6", "#ec4899", "#f97316", "#fde047", "#34d399", "#38bdf8"];
  const parts = Array.from({ length: n }, () => ({
    x: innerWidth / 2 + (Math.random() - 0.5) * 120, y: innerHeight * 0.35, vx: (Math.random() - 0.5) * 14,
    vy: -Math.random() * 13 - 4, s: 5 + Math.random() * 6, r: Math.random() * 6, vr: (Math.random() - 0.5) * 0.3,
    c: colors[(Math.random() * colors.length) | 0],
  }));
  let frame = 0;
  (function loop() {
    ctx.clearRect(0, 0, innerWidth, innerHeight);
    parts.forEach((p) => {
      p.vy += 0.35; p.x += p.vx; p.y += p.vy; p.vx *= 0.99; p.r += p.vr;
      ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.r); ctx.fillStyle = p.c; ctx.fillRect(-p.s / 2, -p.s / 4, p.s, p.s / 2); ctx.restore();
    });
    if (++frame < 160) requestAnimationFrame(loop); else c.remove();
  })();
}
