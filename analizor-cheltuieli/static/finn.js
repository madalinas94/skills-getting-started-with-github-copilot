// Finn – robotul-asistent. SVG animat: plutește, clipește, urmărește cursorul cu privirea
// și își schimbă expresia după scorul financiar (great / good / watch / critical).
const Finn = (() => {
  let uid = 0;
  let mood = "good";

  function svg({ wave = false, size = "" } = {}) {
    const id = "f" + uid++;
    return `<svg class="finn mood-${mood} ${wave ? "wave" : ""} ${size}" viewBox="0 0 120 150" role="img" aria-label="Finn">
      <defs>
        <radialGradient id="${id}o" cx="35%" cy="28%" r="85%">
          <stop offset="0" stop-color="#fffdf7"/><stop offset=".55" stop-color="#ece3cf"/><stop offset="1" stop-color="#c9b48a"/>
        </radialGradient>
        <linearGradient id="${id}g" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#f3dfa6"/><stop offset=".5" stop-color="#b8925a"/><stop offset="1" stop-color="#e9cf8f"/></linearGradient>
        <linearGradient id="${id}v" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1a2742"/><stop offset="1" stop-color="#0a1222"/></linearGradient>
        <linearGradient id="${id}t" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#1d2b4a"/><stop offset="1" stop-color="#101a30"/></linearGradient>
        <radialGradient id="${id}j"><stop offset="0" stop-color="#f3dfa6" stop-opacity=".9"/><stop offset="1" stop-color="#b8925a" stop-opacity="0"/></radialGradient>
        <filter id="${id}f" x="-50%" y="-50%" width="200%" height="200%"><feGaussianBlur stdDeviation="1.4" result="b"/><feMerge><feMergeNode in="b"/><feMergeNode in="SourceGraphic"/></feMerge></filter>
      </defs>
      <ellipse class="f-shadow" cx="60" cy="144" rx="24" ry="3.5" fill="#000" opacity=".35"/>
      <g class="f-body">
        <ellipse class="f-jet" cx="60" cy="134" rx="16" ry="5" fill="url(#${id}j)"/>
        <line x1="60" y1="17" x2="60" y2="8" stroke="url(#${id}g)" stroke-width="2" stroke-linecap="round"/>
        <circle class="f-antenna" cx="60" cy="7" r="4" fill="url(#${id}g)"/>
        <circle cx="16" cy="58" r="6" fill="url(#${id}g)"/><circle cx="104" cy="58" r="6" fill="url(#${id}g)"/>
        <rect x="38" y="96" width="44" height="32" rx="13" fill="url(#${id}t)" stroke="url(#${id}g)" stroke-width="1"/>
        <path d="M52 96 L60 110 L68 96 Z" fill="#f6f1e6"/>
        <circle cx="60" cy="115" r="1.6" fill="url(#${id}g)"/><circle cx="60" cy="121" r="1.6" fill="url(#${id}g)"/>
        <path d="M43 103 l6 0 l-3 4 z" fill="url(#${id}g)"/>
        <g class="f-hand-l"><rect x="27" y="100" width="11" height="17" rx="5.5" fill="#f6f1e6" stroke="url(#${id}g)" stroke-width="1"/></g>
        <g class="f-hand-r"><rect x="82" y="100" width="11" height="17" rx="5.5" fill="#f6f1e6" stroke="url(#${id}g)" stroke-width="1"/></g>
        <circle cx="60" cy="56" r="42" fill="url(#${id}o)" stroke="url(#${id}g)" stroke-width="2"/>
        <ellipse cx="45" cy="30" rx="13" ry="6" fill="#fff" opacity=".7" transform="rotate(-25 45 30)"/>
        <rect x="25" y="40" width="70" height="32" rx="16" fill="url(#${id}v)" stroke="url(#${id}g)" stroke-width="1.2"/>
        <g class="f-brows"><path d="M38 47 Q44 43 51 43" stroke="#f1cf7c" stroke-width="2.2" fill="none" stroke-linecap="round"/><path d="M82 47 Q76 43 69 43" stroke="#f1cf7c" stroke-width="2.2" fill="none" stroke-linecap="round"/></g>
        <g class="f-eyes" filter="url(#${id}f)">
          <ellipse class="f-eye" cx="46" cy="56" rx="5" ry="6.5" fill="#f1cf7c"/>
          <ellipse class="f-eye" cx="74" cy="56" rx="5" ry="6.5" fill="#f1cf7c"/>
          <path class="f-happy" d="M40 58 Q46 50 52 58 M68 58 Q74 50 80 58" stroke="#f1cf7c" stroke-width="3" fill="none" stroke-linecap="round"/>
        </g>
        <circle cx="74" cy="56" r="10.5" fill="#ffffff10" stroke="url(#${id}g)" stroke-width="2"/>
        <path d="M84 60 C 92 70, 86 84, 93 98" stroke="url(#${id}g)" stroke-width="1" fill="none"/>
        <path class="f-mouth" d="M53 65 Q60 69 67 65" stroke="#f1cf7c" stroke-width="2.2" fill="none" stroke-linecap="round"/>
        <circle class="f-blush" cx="31" cy="72" r="4" fill="#d68c8c" opacity=".5"/><circle class="f-blush" cx="89" cy="72" r="4" fill="#d68c8c" opacity=".5"/>
        <path d="M60 99 L48 93 L48 105 Z M60 99 L72 93 L72 105 Z" fill="#7a1f2b" stroke="#5a141e" stroke-width=".6"/>
        <rect x="57" y="96" width="6" height="6" rx="1.5" fill="#8f2633"/>
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

// Praf de aur pe canvas, pentru momentele de „bravo”.
function confetti(n = 110) {
  if (matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  const c = document.createElement("canvas");
  c.className = "confetti";
  c.width = innerWidth * devicePixelRatio; c.height = innerHeight * devicePixelRatio;
  document.body.appendChild(c);
  const ctx = c.getContext("2d");
  ctx.scale(devicePixelRatio, devicePixelRatio);
  // praf de aur, nu confetti colorat: mai potrivit pentru stilul sobru
  const colors = ["#f3dfa6", "#d4b46a", "#b8925a", "#fff7e3", "#e9cf8f"];
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
      ctx.save(); ctx.translate(p.x, p.y); ctx.rotate(p.r); ctx.fillStyle = p.c; ctx.globalAlpha = Math.max(0, 1 - frame / 170);
      if (p.s > 8) { ctx.beginPath(); ctx.arc(0, 0, p.s / 4, 0, 6.3); ctx.fill(); } else ctx.fillRect(-p.s / 2, -p.s / 6, p.s, p.s / 3);
      ctx.restore();
    });
    if (++frame < 160) requestAnimationFrame(loop); else c.remove();
  })();
}
