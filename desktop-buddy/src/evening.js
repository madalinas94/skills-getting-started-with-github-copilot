// Ritualul de seară: un jurnal scurt la final de zi (ce a mers bine, ce am învățat,
// recunoștință și rugăciune, planul pentru mâine), cu un gând de noapte bună de la Mady.
const { powerMonitor } = require('electron');
const store = require('./store');
const today = require('./today');
const sessions = require('./sessions');
const goals = require('./goals');
const ai = require('./ai');
const { byId } = require('./lifeareas');
const { t, locale, plural } = require('./i18n');

const settings = () => store.get().settings;

function tomorrowKey() {
  const d = new Date();
  d.setDate(d.getDate() + 1);
  return today.key(d);
}

function minutesOf(hhmm) {
  const m = /^(\d{1,2}):(\d{2})$/.exec(hhmm || '');
  return m ? Number(m[1]) * 60 + Number(m[2]) : 21 * 60;
}

// E momentul invitației: după ora aleasă, jurnalul de azi nescris, invitația încă netrimisă azi,
// iar utilizatorul e la calculator.
function due(now = new Date()) {
  const s = settings();
  if (!s.eveningRitual) return false;
  const k = today.key(now);
  if (store.get().lastEveningPrompt === k || today.getDay(k).evening) return false;
  if (now.getHours() * 60 + now.getMinutes() < minutesOf(s.eveningTime)) return false;
  return powerMonitor.getSystemIdleTime() < 300;
}

function prompted() {
  store.get().lastEveningPrompt = today.key();
  store.save();
}

function focusToday() {
  const k = today.key();
  const day = sessions.history()[k];
  let sec = day ? day.totalSec : 0;
  let count = day ? day.sessions.length : 0;
  const cur = sessions.current();
  if (cur && today.key(new Date(cur.start)) === k) {
    sec += Math.max(0, Math.round((Date.now() - cur.start - (cur.pausedMs || 0)) / 1000));
    count++;
  }
  return { sec, count, pomodoros: day ? day.pomodoros : 0 };
}

function pick(list, k) {
  const n = [...k].reduce((a, c) => a + c.charCodeAt(0), 0);
  return list[n % list.length];
}

// Tot ce afișează jurnalul: statisticile zilei, pașii spre obiective, afirmația de credință,
// prioritățile nebifate (propuse pentru mâine) și ce e deja scris.
function context() {
  const k = today.key();
  const day = today.getDay(k);
  const habits = today.habitsView();
  const idx = today.weekDays().indexOf(k);
  const start = new Date();
  start.setHours(0, 0, 0, 0);
  const g = goals.view().goals;
  const stepsToday = g.flatMap(x => x.steps.filter(s => s.done && s.doneAt >= start.getTime()).map(s => ({ goal: x.title, text: s.text })));
  const contribToday = g
    .map(x => ({ title: x.title, unit: x.unit, type: x.type, amount: (x.history || []).filter(h => h.at >= start.getTime()).reduce((a, h) => a + h.amount, 0) }))
    .filter(x => x.amount > 0);
  const tomorrow = today.getDay(tomorrowKey());
  const unfinished = day.top3.filter(t => t.text && !t.done).map(t => t.text);
  const plannedTomorrow = tomorrow.top3.filter(t => t.text).map(t => t.text);
  return {
    date: k,
    dateLabel: new Date().toLocaleDateString(locale(), { weekday: 'long', day: 'numeric', month: 'long' }),
    name: settings().userName || '',
    buddyName: settings().buddyName,
    stats: {
      focus: focusToday(),
      top3: { done: day.top3.filter(t => t.text && t.done).length, total: day.top3.filter(t => t.text).length, items: day.top3.filter(t => t.text) },
      habits: { done: idx < 0 ? 0 : habits.filter(h => h.week[idx]).length, total: habits.length },
      water: day.water,
      mood: day.mood,
      stepsToday,
      contribToday
    },
    intention: day.intention,
    gratitude: day.gratitude,
    prayer: pick(byId('credinta').affirmations, k),
    evening: day.evening || null,
    tomorrow: {
      intention: tomorrow.intention,
      top3: (plannedTomorrow.length ? plannedTomorrow : unfinished).concat(['', '', '']).slice(0, 3)
    }
  };
}

function clip(v, n) {
  return String(v || '').trim().slice(0, n);
}

function templateNote(e, c) {
  const name = c.name ? `, ${c.name}` : '';
  const parts = [];
  const win = e.wins.split('\n').map(l => l.replace(/^[\s•*-]+/, '').trim()).find(Boolean);
  if (win) parts.push(t('Ai avut o zi cu merite reale: „{w}”. Păstrează sentimentul acesta.', { w: clip(win, 90) }));
  else if (c.stats.focus.sec >= 3600) parts.push(t('{d} de focus azi. Asta e disciplină, nu noroc.', { d: sessions.fmt(c.stats.focus.sec) }));
  else parts.push(t('Nu toate zilele sunt spectaculoase; contează că ai rămas pe drum.'));
  if (e.learned) parts.push(t('Ce ai învățat azi e o investiție cu dobândă compusă.'));
  const first = e.tomorrowTop3.find(Boolean);
  if (first) parts.push(t('Mâine începem cu „{f}”. Primele două ore sunt ale lui.', { f: first }));
  parts.push(t(e.prayed ? 'Ai încheiat ziua cu rugăciune; dormi liniștită, ești în mâini bune.' : 'Lasă ziua să plece. Mâine e o pagină nouă.'));
  return `${t('Noapte bună')}${name}. ${parts.join(' ')}`;
}

function aiPrompt(e, c) {
  return [
    'Scrie-mi un gând scurt de noapte bună (maxim 60 de cuvinte), cald și elegant, în stilul tău, pe baza jurnalului meu de seară.',
    'Recunoaște un lucru concret bun din zi, apoi încurajează-mă pentru prima prioritate de mâine. Fără liste, fără emoji.',
    '',
    `Focus azi: ${sessions.fmt(c.stats.focus.sec)}; priorități bifate: ${c.stats.top3.done}/${c.stats.top3.total}.`,
    `Ce a mers bine: ${e.wins || '-'}`,
    `Ce am învățat: ${e.learned || '-'}`,
    `Recunoștință: ${e.gratitude || '-'}`,
    `Mâine: ${e.tomorrowIntention || '-'}; priorități: ${e.tomorrowTop3.filter(Boolean).join('; ') || '-'}`,
    e.prayed ? 'Mi-am spus rugăciunea de seară.' : ''
  ].join('\n');
}

async function save(input) {
  const c = context();
  const e = {
    wins: clip(input.wins, 600),
    learned: clip(input.learned, 600),
    gratitude: clip(input.gratitude, 300),
    prayed: !!input.prayed,
    rating: Math.max(0, Math.min(5, Number(input.rating) || 0)),
    tomorrowIntention: clip(input.tomorrowIntention, 90),
    tomorrowTop3: (input.tomorrowTop3 || []).slice(0, 3).map(t => clip(t, 120))
  };
  while (e.tomorrowTop3.length < 3) e.tomorrowTop3.push('');
  const s = settings();
  let note;
  if ((s.aiProvider || 'demo') === 'demo') note = templateNote(e, c);
  else {
    try {
      note = await ai.complete(aiPrompt(e, c), s, store.getApiKey());
    } catch {
      note = templateNote(e, c);
    }
  }
  e.note = note;
  e.at = Date.now();
  const patch = { evening: e };
  if (e.gratitude && !c.gratitude) patch.gratitude = e.gratitude;
  today.updateDay(patch);
  // planul de mâine apare direct în tab-ul Azi, la prima oră
  const tk = tomorrowKey();
  const tom = today.getDay(tk);
  const top3 = e.tomorrowTop3.map((text, i) => (text ? { text, done: tom.top3[i]?.text === text ? tom.top3[i].done : false } : { text: '', done: false }));
  today.updateDay({ intention: e.tomorrowIntention || tom.intention, top3 }, tk);
  store.get().lastEveningPrompt = today.key();
  store.save();
  return { note, context: context() };
}

// Ultimele seri scrise, cele mai noi primele.
function history(limit = 30) {
  const days = store.get().days || {};
  return Object.keys(days)
    .filter(k => days[k].evening)
    .sort()
    .reverse()
    .slice(0, limit)
    .map(k => ({
      date: k,
      label: new Date(k + 'T12:00:00').toLocaleDateString(locale(), { weekday: 'short', day: 'numeric', month: 'short' }),
      ...days[k].evening
    }));
}

// Pentru briefingul de dimineață: intenția și prioritățile scrise aseară.
function lastNightPlan() {
  const y = new Date();
  y.setDate(y.getDate() - 1);
  const ev = today.getDay(today.key(y)).evening;
  if (!ev) return null;
  const day = today.getDay();
  return { intention: day.intention, top3: day.top3.filter(t => t.text).map(t => t.text) };
}

module.exports = { due, prompted, context, save, history, lastNightPlan, tomorrowKey, templateNote };
