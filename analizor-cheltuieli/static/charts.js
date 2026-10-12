// Grafice SVG desenate de mână: fără biblioteci externe, merg și offline.
const Charts = (() => {
  let uid = 0;
  const NS = "http://www.w3.org/2000/svg";
  const tip = () => document.getElementById("tooltip");

  function showTip(evt, html) {
    const t = tip();
    t.innerHTML = html;
    t.classList.add("show");
    const pad = 14, w = t.offsetWidth, h = t.offsetHeight;
    let x = evt.clientX + pad, y = evt.clientY - h - pad;
    if (x + w > innerWidth - 8) x = evt.clientX - w - pad;
    if (y < 8) y = evt.clientY + pad;
    t.style.left = x + "px";
    t.style.top = y + "px";
  }
  const hideTip = () => tip().classList.remove("show");
  function bindTips(root) {
    root.querySelectorAll("[data-tip]").forEach((el) => {
      el.addEventListener("mousemove", (e) => showTip(e, el.dataset.tip));
      el.addEventListener("mouseleave", hideTip);
    });
  }

  // ---------------------------------------------------------------- donut
  function donut(el, items, { center = "", sub = "", size = 220, onClick, onHover } = {}) {
    const total = items.reduce((a, i) => a + i.value, 0);
    if (!total) { el.innerHTML = `<div class="empty">Nicio cheltuială</div>`; return; }
    const r = 78, cx = 100, cy = 100, w = 22, gap = items.length > 1 ? 0.025 : 0;
    let a0 = -Math.PI / 2;
    const arcs = items.map((it, i) => {
      const frac = it.value / total, a1 = a0 + frac * Math.PI * 2;
      const large = a1 - a0 > Math.PI ? 1 : 0;
      const p = (a, rr) => [cx + rr * Math.cos(a), cy + rr * Math.sin(a)];
      const [x0, y0] = p(a0 + gap / 2, r), [x1, y1] = p(Math.max(a0 + gap / 2 + 1e-3, Math.min(a1, a0 + Math.PI * 2 - 1e-4) - gap / 2), r);
      const d = frac >= 0.9999
        ? `M ${cx} ${cy - r} A ${r} ${r} 0 1 1 ${cx - 0.01} ${cy - r}`
        : `M ${x0} ${y0} A ${r} ${r} 0 ${large} 1 ${x1} ${y1}`;
      a0 = a1;
      return `<path class="slice" data-i="${i}" d="${d}" stroke="${it.color}" stroke-width="${w}" fill="none"
        data-tip="<b>${it.label}</b>${it.fmt} · ${(frac * 100).toFixed(1)}%"
        style="animation: fadeIn .5s ${i * 0.06}s both"/>`;
    }).join("");
    el.innerHTML = `<svg viewBox="0 0 200 200" style="max-width:${size}px;margin:auto">
      <circle cx="${cx}" cy="${cy}" r="${r}" fill="none" stroke="var(--glass-strong)" stroke-width="${w}"/>
      ${arcs}
      <text x="100" y="98" text-anchor="middle" class="donut-center-big">${center}</text>
      <text x="100" y="117" text-anchor="middle" class="donut-center-small">${sub}</text>
    </svg>`;
    bindTips(el);
    el.querySelectorAll(".slice").forEach((s) => {
      const i = +s.dataset.i;
      if (onClick) s.addEventListener("click", () => onClick(items[i]));
      if (onHover) { s.addEventListener("mouseenter", () => onHover(i)); s.addEventListener("mouseleave", () => onHover(-1)); }
    });
  }

  // ---------------------------------------------------------------- gauge scor
  function gauge(el, score, label) {
    const r = 80, cx = 100, cy = 100, len = Math.PI * r;
    const color = score >= 80 ? "#7fae8f" : score >= 60 ? "#8fb0d6" : score >= 40 ? "#d4b46a" : "#c2626e";
    const id = "g" + uid++;
    el.innerHTML = `<svg viewBox="0 0 200 128">
      <defs><linearGradient id="${id}" x1="0" x2="1"><stop offset="0" stop-color="#8f2633"/><stop offset=".55" stop-color="#d4b46a"/><stop offset="1" stop-color="#5f8f75"/></linearGradient></defs>
      <path d="M20 100 A80 80 0 0 1 180 100" fill="none" stroke="var(--glass-strong)" stroke-width="16" stroke-linecap="round"/>
      <path d="M20 100 A80 80 0 0 1 180 100" fill="none" stroke="url(#${id})" stroke-width="16" stroke-linecap="round"
        stroke-dasharray="${len}" stroke-dashoffset="${len}" style="transition: stroke-dashoffset 1.2s cubic-bezier(.2,.8,.2,1)" data-g/>
      <text x="100" y="92" class="gauge-label gauge-num">${score}</text>
      <text x="100" y="116" class="gauge-label gauge-txt" style="fill:${color}">${label}</text>
    </svg>`;
    requestAnimationFrame(() => requestAnimationFrame(() => {
      el.querySelector("[data-g]").style.strokeDashoffset = len * (1 - score / 100);
    }));
  }

  // ---------------------------------------------------------------- bare zilnice + linie cumulată
  function daily(el, days, { fmt, onClick } = {}) {
    if (!days.length) { el.innerHTML = `<div class="empty">Nicio cheltuială în perioada aleasă</div>`; return; }
    const W = 900, H = 260, P = { l: 56, r: 56, t: 16, b: 34 };
    const iw = W - P.l - P.r, ih = H - P.t - P.b;
    const max = Math.max(...days.map((d) => d.value)) * 1.1 || 1;
    let cum = 0;
    const cumPts = days.map((d) => (cum += d.value));
    const cmax = cum * 1.05 || 1;
    const bw = Math.max(4, Math.min(26, (iw / days.length) * 0.62));
    const x = (i) => P.l + (iw * (i + 0.5)) / days.length;
    const y = (v) => P.t + ih - (v / max) * ih;
    const yc = (v) => P.t + ih - (v / cmax) * ih;
    const id = "d" + uid++;
    const grid = [0, .25, .5, .75, 1].map((f) => {
      const yy = P.t + ih - f * ih;
      return `<line class="gridline" x1="${P.l}" x2="${W - P.r}" y1="${yy}" y2="${yy}" stroke-dasharray="3 4"/>
        <text x="${P.l - 8}" y="${yy + 4}" text-anchor="end">${short(max * f)}</text>
        <text x="${W - P.r + 8}" y="${yy + 4}">${short(cmax * f)}</text>`;
    }).join("");
    const step = Math.ceil(days.length / 12);
    const labels = days.map((d, i) => (i % step === 0 ? `<text x="${x(i)}" y="${H - 10}" text-anchor="middle">${d.label}</text>` : "")).join("");
    const bars = days.map((d, i) => `<rect class="bar-rect" x="${x(i) - bw / 2}" y="${y(d.value)}" width="${bw}" height="${P.t + ih - y(d.value)}"
        rx="${Math.min(6, bw / 2)}" fill="url(#${id}b)" data-i="${i}"
        data-tip="<b>${d.full}</b>${fmt(d.value)} · ${d.n} plăți<br><small>${d.top}</small>"
        style="transform-origin: ${x(i)}px ${P.t + ih}px; animation: growY .6s ${i * 0.015}s cubic-bezier(.2,.8,.2,1) both"/>`).join("");
    const line = cumPts.map((v, i) => `${i ? "L" : "M"}${x(i)},${yc(v)}`).join(" ");
    const area = `${line} L${x(days.length - 1)},${P.t + ih} L${x(0)},${P.t + ih} Z`;
    el.innerHTML = `<svg viewBox="0 0 ${W} ${H}">
      <defs>
        <linearGradient id="${id}b" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e9cf8f"/><stop offset="1" stop-color="#9c7a45"/></linearGradient>
        <linearGradient id="${id}a" x1="0" y1="0" x2="0" y2="1"><stop offset="0" class="c-area-top"/><stop offset="1" class="c-area-bottom"/></linearGradient>
      </defs>
      <g class="axis">${grid}${labels}</g>
      <path d="${area}" fill="url(#${id}a)"/>
      ${bars}
      <path d="${line}" fill="none" class="c-line" stroke-width="2" stroke-linejoin="round" stroke-linecap="round"
        style="stroke-dasharray: 3000; stroke-dashoffset: 3000; animation: draw 1.4s .2s ease forwards"/>
      ${cumPts.map((v, i) => `<circle cx="${x(i)}" cy="${yc(v)}" r="3" class="c-dot" stroke-width="1.5"
          data-tip="<b>Cumulat până pe ${days[i].full}</b>${fmt(v)}"/>`).join("")}
    </svg>`;
    bindTips(el);
    if (onClick) el.querySelectorAll(".bar-rect").forEach((b) => b.addEventListener("click", () => onClick(days[+b.dataset.i])));
  }

  // ---------------------------------------------------------------- bare verticale simple
  function columns(el, items, { fmt, highlightMax = true } = {}) {
    const W = 520, H = 220, P = { l: 10, r: 10, t: 24, b: 30 };
    const iw = W - P.l - P.r, ih = H - P.t - P.b;
    const max = Math.max(...items.map((i) => i.value), 1);
    const bw = (iw / items.length) * 0.58;
    const id = "c" + uid++;
    const imax = items.findIndex((i) => i.value === max);
    el.innerHTML = `<svg viewBox="0 0 ${W} ${H}">
      <defs>
        <linearGradient id="${id}" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#8fa7c9"/><stop offset="1" stop-color="#3d5478"/></linearGradient>
        <linearGradient id="${id}m" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="#e9cf8f"/><stop offset="1" stop-color="#9c7a45"/></linearGradient>
      </defs>
      <g class="axis">${items.map((it, i) => {
        const x = P.l + (iw * (i + 0.5)) / items.length, h = (it.value / max) * ih, yy = P.t + ih - h;
        return `<rect class="bar-rect" x="${x - bw / 2}" y="${yy}" width="${bw}" height="${Math.max(h, 2)}" rx="8"
            fill="url(#${highlightMax && i === imax ? id + "m" : id})" data-tip="<b>${it.full || it.label}</b>${fmt(it.value)} · ${it.n} plăți"
            style="transform-origin: ${x}px ${P.t + ih}px; animation: growY .6s ${i * 0.05}s cubic-bezier(.2,.8,.2,1) both"/>
          <text x="${x}" y="${yy - 7}" text-anchor="middle" style="font-weight:700;fill:var(--text)">${it.value ? short(it.value) : ""}</text>
          <text x="${x}" y="${H - 9}" text-anchor="middle">${it.label}</text>`;
      }).join("")}</g>
    </svg>`;
    bindTips(el);
  }

  // ---------------------------------------------------------------- calendar heatmap
  // weeks: luni-prima zi; cells = [{date, day, value, n, inMonth}]
  function heatmap(el, cells, { fmt, weekdays, onClick } = {}) {
    const max = Math.max(...cells.map((c) => c.value || 0), 1);
    const level = (v) => (v <= 0 ? 0 : Math.min(4, 1 + Math.floor((v / max) * 3.999)));
    el.innerHTML = `<div class="heat">
      ${weekdays.map((w) => `<span class="heat-wd">${w.slice(0, 2)}</span>`).join("")}
      ${cells.map((c, i) => c.inMonth
        ? `<button class="heat-cell l${level(c.value)}" data-i="${i}" style="animation-delay:${i * 12}ms"
             data-tip="<b>${c.full}</b>${c.value ? fmt(c.value) + " · " + c.n : "—"}"><span>${c.day}</span></button>`
        : `<span class="heat-cell blank"></span>`).join("")}
    </div>
    <div class="heat-legend"><span>0</span>${[0, 1, 2, 3, 4].map((l) => `<i class="heat-cell l${l}"></i>`).join("")}<span>${fmt(max)}</span></div>`;
    bindTips(el);
    if (onClick) el.querySelectorAll("button.heat-cell").forEach((b) => b.addEventListener("click", () => onClick(cells[+b.dataset.i])));
  }

  function short(v) {
    if (v >= 1e6) return (v / 1e6).toFixed(1) + "M";
    if (v >= 1e4) return Math.round(v / 1e3) + "k";
    if (v >= 1e3) return (v / 1e3).toFixed(1).replace(".0", "") + "k";
    return Math.round(v).toString();
  }

  // animații folosite de grafice
  const st = document.createElement("style");
  st.textContent = "@keyframes growY{from{transform:scaleY(0)}}@keyframes draw{to{stroke-dashoffset:0}}";
  document.head.appendChild(st);

  return { donut, gauge, daily, columns, heatmap, bindTips, showTip, hideTip };
})();
