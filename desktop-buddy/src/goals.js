// Obiective cu progres, legate de ariile vieții din vision board.
// Tipuri: bani (fonduri: avans casă, mașină, călătorii), număr (cărți, km) sau etapă (da/nu).
const crypto = require('crypto');
const store = require('./store');
const { AREAS, byId } = require('./lifeareas');

const TYPES = ['money', 'count', 'milestone'];
const MILESTONES = [25, 50, 75, 100];

function list() {
  const d = store.get();
  if (!d.goals) d.goals = [];
  return d.goals;
}

function find(id) {
  return list().find(g => g.id === id);
}

function monthsBetween(a, b) {
  return (b.getFullYear() - a.getFullYear()) * 12 + (b.getMonth() - a.getMonth()) + (b.getDate() - a.getDate()) / 30;
}

// Procent, ritm necesar până la termen și, pentru bani, data estimată în ritmul actual.
function stats(g) {
  const target = Number(g.target) || 0;
  const current = Number(g.current) || 0;
  const pct = g.type === 'milestone'
    ? (g.done ? 100 : Math.round((g.steps.filter(s => s.done).length / Math.max(1, g.steps.length)) * 100 * 0.9))
    : target > 0 ? Math.min(100, Math.round((current / target) * 100)) : 0;
  const out = { pct, remaining: Math.max(0, target - current) };
  const now = new Date();
  if (g.deadline) {
    const [y, m] = g.deadline.split('-').map(Number);
    const end = new Date(y, m, 0);
    const months = monthsBetween(now, end);
    out.monthsLeft = Math.max(0, +months.toFixed(1));
    if (g.type !== 'milestone' && out.remaining > 0) out.perMonth = months > 0.3 ? Math.ceil(out.remaining / months) : out.remaining;
    out.overdue = months < 0 && pct < 100;
  }
  if (g.type === 'money') {
    const since = Date.now() - 90 * 86400000;
    const recent = (g.history || []).filter(h => h.at >= since && h.amount > 0);
    const monthly = recent.reduce((a, h) => a + h.amount, 0) / 3;
    out.monthlyPace = Math.round(monthly);
    if (monthly > 0 && out.remaining > 0) {
      const eta = new Date();
      eta.setMonth(eta.getMonth() + Math.ceil(out.remaining / monthly));
      out.eta = eta.toISOString().slice(0, 7);
      if (g.deadline) out.onTrack = out.eta <= g.deadline;
    }
  }
  return out;
}

function view() {
  const goals = list().map(g => ({ ...g, areaLabel: byId(g.area)?.label || '', stats: stats(g) }));
  const money = goals.filter(g => g.type === 'money');
  const weekStart = new Date();
  weekStart.setHours(0, 0, 0, 0);
  weekStart.setDate(weekStart.getDate() - ((weekStart.getDay() + 6) % 7));
  return {
    goals,
    areas: AREAS.map(a => ({ id: a.id, label: a.label })),
    summary: {
      active: goals.filter(g => g.stats.pct < 100).length,
      done: goals.filter(g => g.stats.pct >= 100).length,
      saved: money.reduce((a, g) => a + (Number(g.current) || 0), 0),
      savedTarget: money.reduce((a, g) => a + (Number(g.target) || 0), 0),
      currency: money[0]?.unit || '€',
      stepsThisWeek: goals.reduce((a, g) => a + g.steps.filter(s => s.done && s.doneAt >= weekStart.getTime()).length, 0),
      openSteps: goals.reduce((a, g) => a + g.steps.filter(s => !s.done).length, 0)
    }
  };
}

function clean(patch) {
  const out = {};
  if ('title' in patch) out.title = String(patch.title || '').trim().slice(0, 80) || require('./i18n').t('Obiectiv');
  if ('area' in patch) out.area = byId(patch.area) ? patch.area : '';
  if ('type' in patch) out.type = TYPES.includes(patch.type) ? patch.type : 'count';
  if ('target' in patch) out.target = Math.max(0, Number(patch.target) || 0);
  if ('current' in patch) out.current = Math.max(0, Number(patch.current) || 0);
  if ('unit' in patch) out.unit = String(patch.unit || '').trim().slice(0, 12);
  if ('deadline' in patch) out.deadline = /^\d{4}-\d{2}$/.test(patch.deadline || '') ? patch.deadline : '';
  if ('done' in patch) out.done = !!patch.done;
  return out;
}

// Prag atins (25/50/75/100%) după o schimbare, pentru ca Mady să sărbătorească.
function crossed(before, after) {
  return MILESTONES.filter(m => before < m && after >= m).pop() || null;
}

function add(patch) {
  const g = {
    id: crypto.randomUUID(), title: 'Obiectiv', area: '', type: 'count', target: 0, current: 0, unit: '', deadline: '',
    done: false, steps: [], history: [], createdAt: Date.now(), ...clean(patch)
  };
  if (g.type === 'money' && !g.unit) g.unit = '€';
  list().push(g);
  store.save();
  return { view: view(), id: g.id };
}

function update(id, patch) {
  const g = find(id);
  if (!g) return { view: view() };
  const before = stats(g).pct;
  Object.assign(g, clean(patch));
  store.save();
  return { view: view(), milestone: crossed(before, stats(g).pct), goal: g };
}

// Contribuție (bani) sau progres (număr): se adaugă la valoarea curentă și intră în istoric.
function contribute(id, amount) {
  const g = find(id);
  const a = Number(amount) || 0;
  if (!g || !a) return { view: view() };
  const before = stats(g).pct;
  g.current = Math.max(0, (Number(g.current) || 0) + a);
  g.history = [...(g.history || []), { at: Date.now(), amount: a }].slice(-200);
  store.save();
  return { view: view(), milestone: crossed(before, stats(g).pct), goal: g };
}

function addStep(id, text) {
  const g = find(id);
  const t = String(text || '').trim().slice(0, 100);
  if (g && t) {
    g.steps.push({ id: crypto.randomUUID(), text: t, done: false, doneAt: 0 });
    store.save();
  }
  return { view: view() };
}

function toggleStep(id, stepId) {
  const g = find(id);
  const s = g?.steps.find(x => x.id === stepId);
  if (!s) return { view: view() };
  const before = stats(g).pct;
  s.done = !s.done;
  s.doneAt = s.done ? Date.now() : 0;
  store.save();
  return { view: view(), milestone: crossed(before, stats(g).pct), goal: g, stepDone: s.done };
}

function removeStep(id, stepId) {
  const g = find(id);
  if (g) {
    g.steps = g.steps.filter(s => s.id !== stepId);
    store.save();
  }
  return { view: view() };
}

function remove(id) {
  const d = store.get();
  d.goals = list().filter(g => g.id !== id);
  store.save();
  return { view: view() };
}

// Progres pe arii (pentru insignele de pe vision board).
function byArea() {
  const out = {};
  for (const g of view().goals) {
    if (!g.area) continue;
    const cur = out[g.area];
    if (!cur || g.stats.pct < cur.pct) out[g.area] = { pct: g.stats.pct, id: g.id, title: g.title };
  }
  return out;
}

module.exports = { view, add, update, contribute, addStep, toggleStep, removeStep, remove, byArea, stats, find };
