const api = window.buddy;
const $ = sel => document.querySelector(sel);
let data = null;
let editing = null; // id-ul obiectivului editat, sau null pentru unul nou
let form = { type: 'money', area: '' };

const fmtNum = n => new Intl.NumberFormat('ro-RO', { maximumFractionDigits: 0 }).format(Math.round(Number(n) || 0));
const fmt = (n, unit) => `${fmtNum(n)}${unit ? ' ' + unit : ''}`;
const monthLabel = ym => {
  if (!ym) return '';
  const [y, m] = ym.split('-').map(Number);
  return new Date(y, m - 1, 1).toLocaleDateString('ro-RO', { month: 'long', year: 'numeric' });
};
const plusYears = (n, month = new Date().getMonth()) => `${new Date().getFullYear() + n}-${String(month + 1).padStart(2, '0')}`;

const TEMPLATES = [
  { title: 'Fondul de libertate financiară', area: 'bani', type: 'money', target: 750000, unit: '€', deadline: () => plusYears(15) },
  { title: 'Fond de siguranță (6 luni)', area: 'bani', type: 'money', target: 15000, unit: '€', deadline: () => plusYears(1) },
  { title: 'Avans pentru casa mea', area: 'casa', type: 'money', target: 40000, unit: '€', deadline: () => plusYears(3) },
  { title: 'Mașina visurilor', area: 'masina', type: 'money', target: 45000, unit: '€', deadline: () => plusYears(2) },
  { title: 'Fondul de călătorii', area: 'calatorii', type: 'money', target: 6000, unit: '€', deadline: () => plusYears(1) },
  { title: '24 de cărți anul acesta', area: 'carti', type: 'count', target: 24, unit: 'cărți', deadline: () => plusYears(0, 11) },
  { title: '150 de antrenamente', area: 'fit', type: 'count', target: 150, unit: 'antrenamente', deadline: () => plusYears(0, 11) },
  { title: 'Vacanță cu toată familia', area: 'familie', type: 'milestone', deadline: () => plusYears(1) }
];

function svgUse(id, cls) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  if (cls) svg.setAttribute('class', cls);
  svg.setAttribute('viewBox', id.startsWith('a-') ? '0 0 64 64' : '0 0 24 24');
  const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
  use.setAttribute('href', '#' + id);
  svg.append(use);
  return svg;
}
const art = area => svgUse('a-' + (area || 'none'));
const icon = name => svgUse('i-' + name, 'ic');
function el(tag, props = {}, children = []) {
  const n = Object.assign(document.createElement(tag), props);
  for (const c of [].concat(children)) if (c !== null && c !== undefined && c !== false) n.append(c);
  return n;
}
let toastTimer;
function toast(t, ms = 2600) {
  $('#toast').textContent = t;
  $('#toast').classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $('#toast').classList.remove('show'), ms);
}

function ring(g) {
  const r = 34, c = 2 * Math.PI * r;
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', 'r');
  svg.setAttribute('viewBox', '0 0 78 78');
  svg.innerHTML = `<circle class="bg" cx="39" cy="39" r="${r}"/><circle class="fg" cx="39" cy="39" r="${r}" stroke-dasharray="${c}" stroke-dashoffset="${c}"/>`;
  // animăm de la 0 la procentul real
  requestAnimationFrame(() => requestAnimationFrame(() => {
    svg.querySelector('.fg').style.strokeDashoffset = c * (1 - g.stats.pct / 100);
  }));
  return el('div', { className: 'ring' }, [svg, el('div', { className: 'inner' }, [art(g.area)]), el('div', { className: 'pct', textContent: g.stats.pct + '%' })]);
}

function paceLine(g) {
  const s = g.stats;
  const box = el('div', { className: 'g-pace' });
  if (s.pct >= 100) {
    box.append(el('span', { className: 'ok', textContent: 'Atins. Felicitări, e al tău.' }));
    return box;
  }
  const parts = [];
  if (g.deadline) {
    if (s.overdue) parts.push(el('span', { className: 'warn', textContent: `Termenul (${monthLabel(g.deadline)}) a trecut. ` }));
    else parts.push(`Termen: ${monthLabel(g.deadline)}, încă ${s.monthsLeft} ${s.monthsLeft === 1 ? 'lună' : 'luni'}. `);
  }
  if (s.perMonth && !s.overdue) parts.push('Ritm necesar: ', el('b', { textContent: `${fmt(s.perMonth, g.unit)}/lună` }), '. ');
  if (g.type === 'money') {
    if (s.eta) {
      parts.push(`În ritmul ultimelor 3 luni (${fmt(s.monthlyPace, g.unit)}/lună) ajungi în ${monthLabel(s.eta)}`);
      if (s.onTrack === true) parts.push(el('span', { className: 'ok', textContent: ' ✓ la timp' }));
      else if (s.onTrack === false) parts.push(el('span', { className: 'warn', textContent: ' – mărește puțin contribuția' }));
      parts.push('.');
    } else if (s.remaining > 0) parts.push('Adaugă prima contribuție și îți calculez data la care ajungi.');
  }
  if (g.type === 'milestone' && g.steps.length) parts.push(`${g.steps.filter(x => x.done).length} din ${g.steps.length} pași făcuți.`);
  if (!parts.length) parts.push('Împarte-l în pași mici; bifează-i pe rând.');
  box.append(...parts);
  return box;
}

function contribution(g) {
  if (g.type === 'milestone') {
    return el('div', { className: 'contrib' }, [
      el('button', { className: 'btn' + (g.done ? '' : ' primary'), textContent: g.done ? 'Redeschide' : 'Marchează ca atins', onclick: async () => handle(await api.goals.update(g.id, { done: !g.done }), g.id) })
    ]);
  }
  const quick = g.type === 'money' ? [50, 100, 250, 500] : [1, 5];
  const input = el('input', { type: 'number', step: 'any', placeholder: g.type === 'money' ? `Contribuție (${g.unit || '€'})` : `Progres (+ ${g.unit || 'unități'})` });
  const add = async v => {
    const n = Number(v);
    if (!n) return;
    input.value = '';
    handle(await api.goals.contribute(g.id, n), g.id, n);
  };
  input.addEventListener('keydown', e => { if (e.key === 'Enter') add(input.value); });
  return el('div', { className: 'contrib-wrap' }, [
    el('div', { className: 'contrib' }, [input, el('button', { className: 'btn primary', textContent: 'Adaugă', onclick: () => add(input.value) })]),
    el('div', { className: 'chips', style: 'margin-top:6px' }, quick.map(q => el('button', { textContent: '+' + fmtNum(q), onclick: () => add(q) })))
  ]);
}

function steps(g) {
  const addInput = el('input', { placeholder: '+ următorul pas (ex: deschide un cont de investiții)', maxLength: 100 });
  addInput.addEventListener('keydown', async e => {
    if (e.key !== 'Enter' || !addInput.value.trim()) return;
    const t = addInput.value;
    addInput.value = '';
    set((await api.goals.addStep(g.id, t)).view);
    document.querySelector(`[data-id="${g.id}"] .step-add input`)?.focus();
  });
  return el('div', { className: 'steps' }, [
    el('div', { className: 'sk', textContent: 'Pașii următori' }),
    ...g.steps.map(s => {
      const cb = el('input', { type: 'checkbox', checked: s.done, onchange: async () => handle(await api.goals.toggleStep(g.id, s.id), g.id) });
      return el('label', { className: 'step' + (s.done ? ' done' : '') }, [
        cb, el('span', { textContent: s.text }),
        el('button', { title: 'Șterge pasul', textContent: '×', onclick: async e => { e.preventDefault(); set((await api.goals.removeStep(g.id, s.id)).view); } })
      ]);
    }),
    el('div', { className: 'step-add' }, [addInput])
  ]);
}

function card(g) {
  const del = el('button', { title: 'Șterge obiectivul' }, [icon('trash')]);
  del.addEventListener('click', async () => {
    if (!del.classList.contains('confirm')) {
      del.classList.add('confirm');
      del.replaceChildren('Sigur?');
      setTimeout(() => { del.classList.remove('confirm'); del.replaceChildren(icon('trash')); }, 3000);
      return;
    }
    set((await api.goals.remove(g.id)).view);
  });
  const amount = g.type === 'milestone'
    ? null
    : el('div', { className: 'g-amount' }, [fmt(g.current, g.unit), el('small', { textContent: ` din ${fmt(g.target, g.unit)}` })]);
  return el('article', { className: 'goal' + (g.stats.pct >= 100 ? ' done' : '') }, [
    el('div', { className: 'g-head' }, [
      ring(g),
      el('div', { className: 'g-title' }, [el('b', { textContent: g.title }), el('span', { textContent: [g.areaLabel, g.type === 'money' ? 'fond' : ''].filter(Boolean).join(' · ') })]),
      el('div', { className: 'g-ops' }, [el('button', { title: 'Editează', onclick: () => openForm(g) }, [icon('edit')]), del])
    ]),
    amount,
    paceLine(g),
    g.stats.pct < 100 || g.type === 'milestone' ? contribution(g) : null,
    steps(g)
  ]);
}

function render() {
  const s = data.summary;
  const moneyPct = s.savedTarget ? Math.min(100, Math.round((s.saved / s.savedTarget) * 100)) : 0;
  const stat = (k, v, extra) => el('div', { className: 'stat' }, [el('div', { className: 'k', textContent: k }), v, extra]);
  $('#summary').replaceChildren(
    stat('Fonduri economisite', el('div', { className: 'v' }, [fmt(s.saved, s.currency), el('small', { textContent: s.savedTarget ? ` / ${fmt(s.savedTarget, s.currency)}` : '' })]),
      el('div', { className: 'bar-line' }, [el('i', { style: `width:${moneyPct}%` })])),
    stat('Obiective active', el('div', { className: 'v', textContent: s.active })),
    stat('Pași bifați săptămâna asta', el('div', { className: 'v', textContent: s.stepsThisWeek })),
    stat('Obiective atinse', el('div', { className: 'v', textContent: s.done }))
  );
  $('#summary').classList.toggle('hidden', !data.goals.length);
  $('#empty').classList.toggle('hidden', data.goals.length > 0);
  const sorted = [...data.goals].sort((a, b) => (a.stats.pct >= 100) - (b.stats.pct >= 100) || b.createdAt - a.createdAt);
  $('#goals').replaceChildren(...sorted.map(g => {
    const c = card(g);
    c.dataset.id = g.id;
    return c;
  }));
}

function set(v) { data = v; render(); }

function confetti() {
  const colors = ['#b8955a', '#d8c08a', '#1f3a2e', '#e9dcc3', '#8a6d3b'];
  const box = $('#confetti');
  for (let i = 0; i < 60; i++) {
    const p = el('i');
    p.style.left = Math.random() * 100 + 'vw';
    p.style.background = colors[i % colors.length];
    p.style.animationDelay = Math.random() * 0.6 + 's';
    p.style.animationDuration = 2 + Math.random() * 1.4 + 's';
    box.append(p);
  }
  setTimeout(() => box.replaceChildren(), 4200);
}

// Rezultatul unei acțiuni: redesenăm și sărbătorim pragurile (25/50/75/100%).
function handle(r, id, amount) {
  set(r.view);
  const c = document.querySelector(`[data-id="${id}"]`);
  if (r.milestone) {
    confetti();
    c?.classList.add('pulse');
    toast(r.milestone >= 100 ? `„${r.goal.title}” e atins. Brava!` : `${r.milestone}% din „${r.goal.title}”. Continuă așa.`, 4000);
  } else if (r.stepDone) {
    toast('Pas bifat. Încă unul mai aproape.');
  } else if (amount) {
    toast(amount > 0 ? `+${fmt(amount, r.goal?.unit)} adăugat` : 'Corecție salvată');
  }
}

// ---------- formular ----------
function templateButtons(box, onPick) {
  box.replaceChildren(...TEMPLATES.map(t => el('button', { type: 'button', onclick: () => onPick(t) }, [art(t.area), t.title])));
}

function fillForm(g) {
  $('#fTitle').value = g.title || '';
  $('#fTarget').value = g.target || '';
  $('#fCurrent').value = g.current || '';
  $('#fUnit').value = g.unit || '';
  $('#fDeadline').value = typeof g.deadline === 'function' ? g.deadline() : g.deadline || '';
  form = { type: g.type || 'money', area: g.area || '' };
  syncForm();
}

function syncForm() {
  for (const b of $('#fType').children) b.classList.toggle('on', b.dataset.v === form.type);
  for (const b of $('#fAreas').children) b.classList.toggle('on', b.dataset.v === form.area);
  $('#fNumbers').classList.toggle('hidden', form.type === 'milestone');
  $('#fCalc').classList.toggle('hidden', !(form.type === 'money' && form.area === 'bani'));
  if (form.type === 'money' && !$('#fUnit').value) $('#fUnit').value = '€';
}

function openForm(g) {
  editing = g?.id || null;
  $('#formTitle').textContent = editing ? 'Editează obiectivul' : 'Obiectiv nou';
  $('#templates').classList.toggle('hidden', !!editing);
  fillForm(g || { type: 'money', area: '' });
  $('#modal').classList.remove('hidden');
  $('#fTitle').focus();
}

$('#fAreas').addEventListener('click', e => {
  const b = e.target.closest('button');
  if (!b) return;
  form.area = form.area === b.dataset.v ? '' : b.dataset.v;
  syncForm();
});
$('#fType').addEventListener('click', e => {
  const b = e.target.closest('button');
  if (!b) return;
  if (form.type === 'money' && b.dataset.v !== 'money' && $('#fUnit').value === '€') $('#fUnit').value = '';
  form.type = b.dataset.v;
  syncForm();
});
$('#fExpenses').addEventListener('input', () => {
  const v = Number($('#fExpenses').value) || 0;
  $('#fCalcOut').textContent = v ? fmt(v * 12 * 25, $('#fUnit').value || '€') : '–';
});
$('#fCalcUse').addEventListener('click', () => {
  const v = Number($('#fExpenses').value) || 0;
  if (v) $('#fTarget').value = v * 12 * 25;
});
$('#fCancel').addEventListener('click', () => $('#modal').classList.add('hidden'));
$('#form').addEventListener('submit', async e => {
  e.preventDefault();
  const patch = {
    title: $('#fTitle').value, area: form.area, type: form.type,
    target: $('#fTarget').value, current: $('#fCurrent').value, unit: $('#fUnit').value, deadline: $('#fDeadline').value
  };
  $('#modal').classList.add('hidden');
  if (editing) handle(await api.goals.update(editing, patch), editing);
  else {
    const r = await api.goals.add(patch);
    set(r.view);
    toast('Obiectiv adăugat. Scrie-i primul pas.');
    document.querySelector(`[data-id="${r.id}"] .step-add input`)?.focus();
  }
});

$('#newGoal').addEventListener('click', () => openForm(null));
$('#close').addEventListener('click', () => api.goals.close());
document.addEventListener('keydown', e => {
  if (e.key !== 'Escape') return;
  if (!$('#modal').classList.contains('hidden')) $('#modal').classList.add('hidden');
  else if (!['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) api.goals.close();
});

templateButtons($('#templates'), t => fillForm(t));
templateButtons($('#emptyTemplates'), t => { openForm(null); fillForm(t); });

function applyTheme(s) { document.documentElement.dataset.theme = s.themeResolved || s.theme; }
api.settings.get().then(applyTheme);
api.settings.onUpdate(applyTheme);
api.goals.onUpdate(v => { if (!document.querySelector('.goal input:focus, .step-add input:focus')) set(v); });
api.goals.get().then(v => {
  set(v);
  $('#fAreas').replaceChildren(...v.areas.map(a => el('button', { type: 'button', title: a.label }, [art(a.id), a.label.split(' ')[0]])));
  [...$('#fAreas').children].forEach((b, i) => { b.dataset.v = v.areas[i].id; });
  if (new URLSearchParams(location.search).has('new')) openForm(null);
});
