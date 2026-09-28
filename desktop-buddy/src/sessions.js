// Sesiuni de lucru: timer cu pauză, aplicații folosite, reminder la fiecare oră,
// raport la final și istoric pe ultimele 30 de zile.
const crypto = require('crypto');
const { powerMonitor } = require('electron');
const store = require('./store');
const { ActivityTracker } = require('./activity');

const KEEP_DAYS = 30;
const IDLE_LIMIT_SEC = 5 * 60; // după 5 minute fără mouse/tastatură nu mai numărăm timp activ

let tracker = null;
let tickTimer = null;
let hooks = { onChange() {}, onHour() {}, onEnd() {} };

function elapsedMs(s, now = Date.now()) {
  const end = s.end || now;
  const pausedNow = s.pausedAt ? now - s.pausedAt : 0;
  return Math.max(0, end - s.start - s.pausedMs - pausedNow);
}

function current() {
  return store.get().currentSession;
}

function prune() {
  const d = store.get();
  const limit = Date.now() - KEEP_DAYS * 86400000;
  d.sessions = (d.sessions || []).filter(s => s.start >= limit);
}

function onSample(app, seconds) {
  const s = current();
  if (!s || s.pausedAt) return;
  if (powerMonitor.getSystemIdleTime() >= IDLE_LIMIT_SEC) {
    s.idleSec += seconds;
    return;
  }
  s.activeSec += seconds;
  s.apps[app] = (s.apps[app] || 0) + seconds;
  store.save();
}

function startTracking() {
  const s = current();
  if (!s || s.pausedAt || !store.get().settings.timerTrackApps) return;
  if (!tracker) tracker = new ActivityTracker(onSample);
  tracker.start();
}

function stopTracking() {
  if (tracker) tracker.stop();
}

function tick() {
  const s = current();
  if (!s || s.pausedAt) return;
  const hours = Math.floor(elapsedMs(s) / 3600000);
  if (hours > s.hoursNotified) {
    s.hoursNotified = hours;
    store.save();
    if (store.get().settings.timerHourlyReminder) hooks.onHour(hours, s);
  }
}

function init(h) {
  hooks = { ...hooks, ...h };
  prune();
  const s = current();
  if (s) {
    // aplicația a fost închisă în timpul unei sesiuni: continuăm de unde a rămas
    startTracking();
  }
  clearInterval(tickTimer);
  tickTimer = setInterval(tick, 1000);
}

function start(title) {
  if (current()) return current();
  const s = {
    id: crypto.randomUUID(),
    title: String(title || '').trim() || 'Sesiune de lucru',
    start: Date.now(),
    end: null,
    pausedMs: 0,
    pausedAt: null,
    activeSec: 0,
    idleSec: 0,
    apps: {},
    hoursNotified: 0,
    feedback: ''
  };
  store.get().currentSession = s;
  store.save();
  startTracking();
  hooks.onChange(s);
  return s;
}

function pause() {
  const s = current();
  if (!s || s.pausedAt) return s;
  s.pausedAt = Date.now();
  stopTracking();
  store.save();
  hooks.onChange(s);
  return s;
}

function resume() {
  const s = current();
  if (!s || !s.pausedAt) return s;
  s.pausedMs += Date.now() - s.pausedAt;
  s.pausedAt = null;
  store.save();
  startTracking();
  hooks.onChange(s);
  return s;
}

function stop() {
  const s = current();
  if (!s) return null;
  if (s.pausedAt) {
    s.pausedMs += Date.now() - s.pausedAt;
    s.pausedAt = null;
  }
  s.end = Date.now();
  s.durationSec = Math.round(elapsedMs(s) / 1000);
  stopTracking();
  const d = store.get();
  d.sessions.push(s);
  d.currentSession = null;
  prune();
  store.save();
  const rep = report(s);
  hooks.onChange(null);
  hooks.onEnd(rep);
  return rep;
}

function topApps(apps, limit = 8) {
  const total = Object.values(apps).reduce((a, b) => a + b, 0) || 1;
  return Object.entries(apps)
    .sort((a, b) => b[1] - a[1])
    .slice(0, limit)
    .map(([name, sec]) => ({ name, sec, pct: Math.round((sec / total) * 100) }));
}

function report(s) {
  return {
    id: s.id,
    title: s.title,
    start: s.start,
    end: s.end,
    durationSec: s.durationSec ?? Math.round(elapsedMs(s) / 1000),
    activeSec: s.activeSec,
    idleSec: s.idleSec,
    apps: topApps(s.apps),
    feedback: s.feedback || ''
  };
}

function dayKey(ts) {
  const d = new Date(ts);
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

// Istoric pe zile (ultimele 30), pentru calendarul Workdays și statisticile pe săptămână.
function history() {
  prune();
  const days = {};
  for (const s of store.get().sessions) {
    const k = dayKey(s.start);
    const day = days[k] || (days[k] = { date: k, totalSec: 0, activeSec: 0, sessions: [], apps: {} });
    day.totalSec += s.durationSec || 0;
    day.activeSec += s.activeSec || 0;
    day.sessions.push({ id: s.id, title: s.title, start: s.start, end: s.end, durationSec: s.durationSec || 0 });
    for (const [app, sec] of Object.entries(s.apps || {})) day.apps[app] = (day.apps[app] || 0) + sec;
  }
  for (const day of Object.values(days)) day.topApps = topApps(day.apps, 5);
  return days;
}

function getSession(id) {
  return store.get().sessions.find(s => s.id === id);
}

function setFeedback(id, text) {
  const s = getSession(id);
  if (s) {
    s.feedback = text;
    store.save();
  }
}

function fmt(sec) {
  const h = Math.floor(sec / 3600);
  const m = Math.round((sec % 3600) / 60);
  return h ? `${h}h ${m}m` : `${m}m`;
}

// Textul trimis modelului AI pentru feedback.
function feedbackPrompt(id) {
  const s = getSession(id);
  if (!s) return null;
  const r = report(s);
  const days = Object.values(history()).sort((a, b) => a.date.localeCompare(b.date)).slice(-7);
  return [
    'Dă-mi feedback scurt și concret despre sesiunea mea de lucru și despre ultimele zile:',
    'ce a mers bine, ce pot îmbunătăți, și 2-3 next actions pentru mâine.',
    '',
    `Sesiune: „${r.title}”, ${new Date(r.start).toLocaleString('ro-RO')}`,
    `Durată: ${fmt(r.durationSec)}, timp activ: ${fmt(r.activeSec)}, inactiv: ${fmt(r.idleSec)}`,
    'Aplicații: ' + (r.apps.map(a => `${a.name} ${fmt(a.sec)} (${a.pct}%)`).join(', ') || 'nedetectate'),
    '',
    'Ultimele zile:',
    ...days.map(d => `- ${d.date}: ${fmt(d.totalSec)} în ${d.sessions.length} sesiuni; top: ${d.topApps.map(a => a.name).join(', ') || '-'}`)
  ].join('\n');
}

function shutdown() {
  stopTracking();
  clearInterval(tickTimer);
}

module.exports = {
  init, start, pause, resume, stop, current, history, report, getSession,
  setFeedback, feedbackPrompt, elapsedMs, fmt, shutdown, startTracking, stopTracking
};
