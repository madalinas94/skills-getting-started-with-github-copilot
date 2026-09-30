// Carduri de împărtășit (Instagram): „Ziua mea” și „Săptămâna mea”, în format post (4:5) sau story (9:16).
// Se randează offscreen dintr-un șablon HTML și se salvează ca PNG în Imagini\Desktop Buddy.
const { BrowserWindow, app } = require('electron');
const path = require('path');
const fs = require('fs');
const store = require('./store');
const sessions = require('./sessions');
const today = require('./today');

const FORMATS = { post: { width: 1080, height: 1350 }, story: { width: 1080, height: 1920 } };

function dayData() {
  const hist = sessions.history();
  const k = today.key();
  const t = today.state();
  const h = hist[k] || { totalSec: 0, pomodoros: 0, sessions: [], topApps: [] };
  const cur = sessions.current();
  let totalSec = h.totalSec;
  if (cur && today.key(new Date(cur.start)) === k) totalSec += Math.round(sessions.elapsedMs(cur) / 1000);
  return {
    kind: 'day',
    date: new Date().toLocaleDateString('ro-RO', { weekday: 'long', day: 'numeric', month: 'long' }),
    focus: sessions.fmt(totalSec),
    sessions: h.sessions.length + (cur ? 1 : 0),
    pomodoros: h.pomodoros + (cur && cur.pomo ? cur.pomo.count : 0),
    intention: t.day.intention,
    top3: t.day.top3.filter(x => x.text.trim()),
    habits: t.habits.map(x => ({ name: x.name, done: x.week[(new Date().getDay() + 6) % 7], streak: x.streak })),
    water: t.day.water,
    mood: t.day.mood,
    gratitude: t.day.gratitude,
    quote: t.quote,
    topApp: h.topApps[0]?.name || ''
  };
}

function fromKey(k) {
  const [y, m, d] = k.split('-').map(Number);
  return new Date(y, m - 1, d);
}

function weekData() {
  const hist = sessions.history();
  const keys = today.weekDays();
  const names = ['L', 'M', 'M', 'J', 'V', 'S', 'D'];
  const days = keys.map((k, i) => ({ label: names[i], sec: hist[k]?.totalSec || 0, today: k === today.key() }));
  const total = days.reduce((a, d) => a + d.sec, 0);
  const goal = Number(store.get().settings.weeklyGoalHours) || 0;
  const t = today.state();
  const tops = keys.flatMap(k => (store.get().days?.[k]?.top3 || [])).filter(x => x.text && x.text.trim());
  const apps = {};
  keys.forEach(k => (hist[k]?.topApps || []).forEach(a => { apps[a.name] = (apps[a.name] || 0) + a.sec; }));
  return {
    kind: 'week',
    range: `${fromKey(keys[0]).toLocaleDateString('ro-RO', { day: 'numeric', month: 'short' })} – ${fromKey(keys[6]).toLocaleDateString('ro-RO', { day: 'numeric', month: 'short' })}`,
    focus: sessions.fmt(total),
    goal,
    pct: goal ? Math.round((total / (goal * 3600)) * 100) : 0,
    days,
    pomodoros: keys.reduce((a, k) => a + (hist[k]?.pomodoros || 0), 0),
    prioritiesDone: tops.filter(x => x.done).length,
    prioritiesTotal: tops.length,
    habits: t.habits.map(x => ({ name: x.name, week: x.week, streak: x.streak })),
    topApps: Object.entries(apps).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([n]) => n),
    quote: t.quote
  };
}

const MOOD_LABELS = { radiant: 'radiantă', bine: 'bine', ok: 'ok', obosit: 'obosită', stresat: 'stresată' };

function monthData(ref = new Date()) {
  const hist = sessions.history();
  const y = ref.getFullYear(), m = ref.getMonth();
  const lastDay = new Date(y, m + 1, 0).getDate();
  const upTo = (y === new Date().getFullYear() && m === new Date().getMonth()) ? new Date().getDate() : lastDay;
  const keys = [...Array(lastDay)].map((_, i) => today.key(new Date(y, m, i + 1)));
  const elapsed = keys.slice(0, upTo);
  const d = store.get();
  const days = keys.map((k, i) => ({ day: i + 1, sec: hist[k]?.totalSec || 0, future: i >= upTo, today: k === today.key() }));
  const worked = days.filter(x => x.sec > 0);
  const total = worked.reduce((a, x) => a + x.sec, 0);
  const best = worked.reduce((a, x) => (x.sec > (a?.sec || 0) ? x : a), null);
  const apps = {};
  elapsed.forEach(k => (hist[k]?.topApps || []).forEach(a => { apps[a.name] = (apps[a.name] || 0) + a.sec; }));
  const tops = elapsed.flatMap(k => d.days?.[k]?.top3 || []).filter(x => x.text && x.text.trim());
  const moods = {};
  elapsed.forEach(k => { const mo = d.days?.[k]?.mood; if (mo) moods[mo] = (moods[mo] || 0) + 1; });
  const waterDays = elapsed.map(k => d.days?.[k]?.water || 0).filter(Boolean);
  const habits = (d.habits || []).map(h => {
    const log = d.habitLog?.[h.id] || {};
    const done = elapsed.filter(k => log[k]).length;
    return { name: h.name, done, pct: Math.round((done / elapsed.length) * 100) };
  });
  const favs = Object.values(d.mantras || {}).filter(x => x.fav && keys.includes(x.date));
  const mantraPick = favs[0] || d.mantras?.[today.key()] || null;
  const monthName = new Date(y, m, 1).toLocaleDateString('ro-RO', { month: 'long', year: 'numeric' });
  return {
    kind: 'month',
    month: monthName[0].toUpperCase() + monthName.slice(1),
    firstWeekday: (new Date(y, m, 1).getDay() + 6) % 7,
    focus: sessions.fmt(total),
    totalSec: total,
    daysWorked: worked.length,
    daysElapsed: upTo,
    best: best ? { label: new Date(y, m, best.day).toLocaleDateString('ro-RO', { weekday: 'long', day: 'numeric' }), focus: sessions.fmt(best.sec) } : null,
    avg: worked.length ? sessions.fmt(Math.round(total / worked.length)) : '0m',
    sessions: elapsed.reduce((a, k) => a + (hist[k]?.sessions.length || 0), 0),
    pomodoros: elapsed.reduce((a, k) => a + (hist[k]?.pomodoros || 0), 0),
    days,
    topApps: Object.entries(apps).sort((a, b) => b[1] - a[1]).slice(0, 3).map(([n]) => n),
    prioritiesDone: tops.filter(x => x.done).length,
    prioritiesTotal: tops.length,
    moods: Object.entries(moods).sort((a, b) => b[1] - a[1]).map(([k, n]) => ({ label: MOOD_LABELS[k] || k, n })),
    water: waterDays.length ? +(waterDays.reduce((a, b) => a + b, 0) / waterDays.length).toFixed(1) : 0,
    habits,
    mantra: mantraPick ? { text: mantraPick.text, author: mantraPick.author || mantraPick.title || '', label: mantraPick.label } : null,
    quote: today.quote()
  };
}

async function mantraData() {
  const mantra = require('./mantra');
  const mm = await mantra.today();
  return { kind: 'mantra', date: new Date().toLocaleDateString(mm.locale || 'ro-RO', { weekday: 'long', day: 'numeric', month: 'long' }), mantra: mm };
}

function outDir() {
  const dir = path.join(app.getPath('pictures'), 'Desktop Buddy');
  fs.mkdirSync(dir, { recursive: true });
  return dir;
}

async function render(kind, format) {
  const size = FORMATS[format] || FORMATS.post;
  const data = kind === 'week' ? weekData() : kind === 'month' ? monthData() : kind === 'mantra' ? await mantraData() : dayData();
  const s = store.get().settings;
  data.name = s.buddyName;
  data.user = s.userName || '';
  data.format = format;
  // offscreen + mărimea setată după creare: altfel Windows o limitează la mărimea ecranului
  const win = new BrowserWindow({
    width: size.width, height: size.height, show: false, useContentSize: true,
    webPreferences: { offscreen: true }
  });
  win.setContentSize(size.width, size.height);
  try {
    await win.loadFile(path.join(__dirname, '..', 'renderer', 'card.html'));
    await win.webContents.executeJavaScript(`render(${JSON.stringify(data)}).then(() => new Promise(r => setTimeout(r, 250)))`);
    const img = await win.webContents.capturePage({ x: 0, y: 0, width: size.width, height: size.height });
    const names = { week: 'saptamana', month: 'luna', mantra: 'mantra', day: 'ziua' };
    const file = path.join(outDir(), `mady-${names[kind] || 'ziua'}-${today.key()}-${format}.png`);
    fs.writeFileSync(file, img.toPNG());
    return { file, dataUrl: img.resize({ width: 360 }).toDataURL(), image: img };
  } finally {
    win.destroy();
  }
}

module.exports = { render, outDir, dayData, weekData, monthData };
