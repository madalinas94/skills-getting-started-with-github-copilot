// Planner-ul zilei: intenție, Top 3 priorități, obiceiuri (habit tracker), apă, stare și recunoștință.
const crypto = require('crypto');
const store = require('./store');
const i18n = require('./quotes-i18n');

const QUOTES = [
  ['Disciplina este podul dintre obiective și realizări.', 'Jim Rohn'],
  ['Nu pentru că e greu nu îndrăznim, ci pentru că nu îndrăznim e greu.', 'Seneca'],
  ['Simplitatea este sofisticarea supremă.', 'Leonardo da Vinci'],
  ['Calitatea nu este un act, ci un obicei.', 'Aristotel'],
  ['Fă ce poți, cu ce ai, acolo unde ești.', 'Theodore Roosevelt'],
  ['Arta nu reproduce vizibilul, ci face vizibilul.', 'Paul Klee'],
  ['Investiția în cunoaștere aduce cea mai bună dobândă.', 'Benjamin Franklin'],
  ['Focusul înseamnă să spui nu la o sută de idei bune.', 'Steve Jobs'],
  ['Cine are un „de ce” poate suporta aproape orice „cum”.', 'Friedrich Nietzsche'],
  ['Eleganța este singura frumusețe care nu se ofilește.', 'Audrey Hepburn'],
  ['Nu număra zilele, fă ca zilele să conteze.', 'Muhammad Ali'],
  ['Ce faci în fiecare zi contează mai mult decât ce faci din când în când.', 'Gretchen Rubin'],
  ['Stilul este un mod de a spune cine ești fără să vorbești.', 'Rachel Zoe'],
  ['Pacientul câștigă pe piață; nerăbdătorul plătește școlarizarea.', 'Warren Buffett (parafrazat)']
];

const DEFAULT_HABITS = ['Apă 2L', 'Mișcare 30 min', 'Citit 20 min', 'Fără social media până la 12'];

function key(d = new Date()) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function data() {
  const d = store.get();
  if (!d.days) d.days = {};
  if (!d.habits) d.habits = DEFAULT_HABITS.map(name => ({ id: crypto.randomUUID(), name }));
  if (!d.habitLog) d.habitLog = {};
  return d;
}

function emptyDay() {
  return { intention: '', top3: [{ text: '', done: false }, { text: '', done: false }, { text: '', done: false }], water: 0, mood: '', gratitude: '' };
}

function getDay(k = key()) {
  const d = data();
  return { ...emptyDay(), ...(d.days[k] || {}) };
}

function updateDay(patch, k = key()) {
  const d = data();
  const day = { ...getDay(k), ...patch };
  if (Array.isArray(patch.top3)) day.top3 = patch.top3.slice(0, 3).map(t => ({ text: String(t.text || ''), done: !!t.done }));
  day.water = Math.max(0, Math.min(12, Number(day.water) || 0));
  d.days[k] = day;
  // păstrăm ~120 de zile
  const keys = Object.keys(d.days).sort();
  while (keys.length > 120) delete d.days[keys.shift()];
  store.save();
  return day;
}

function weekDays(ref = new Date()) {
  const monday = new Date(ref.getFullYear(), ref.getMonth(), ref.getDate() - ((ref.getDay() + 6) % 7));
  return [...Array(7)].map((_, i) => key(new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + i)));
}

function streak(habitId) {
  const log = data().habitLog[habitId] || {};
  let n = 0;
  const d = new Date();
  if (!log[key(d)]) d.setDate(d.getDate() - 1); // ziua de azi nu rupe seria până nu se termină
  while (log[key(d)]) {
    n++;
    d.setDate(d.getDate() - 1);
  }
  return n;
}

function habitsView() {
  const d = data();
  const week = weekDays();
  return d.habits.map(h => ({
    id: h.id,
    name: h.name,
    week: week.map(k => !!(d.habitLog[h.id] || {})[k]),
    streak: streak(h.id)
  }));
}

function toggleHabit(id, k = key()) {
  const d = data();
  const log = d.habitLog[id] || (d.habitLog[id] = {});
  if (log[k]) delete log[k];
  else log[k] = true;
  store.save();
  return habitsView();
}

function addHabit(name) {
  const n = String(name || '').trim().slice(0, 40);
  if (n) data().habits.push({ id: crypto.randomUUID(), name: n });
  store.save();
  return habitsView();
}

function removeHabit(id) {
  const d = data();
  d.habits = d.habits.filter(h => h.id !== id);
  delete d.habitLog[id];
  store.save();
  return habitsView();
}

function quote(k = key()) {
  const n = [...k].reduce((a, c) => a + c.charCodeAt(0), 0);
  const lang = i18n.langFor(k);
  const list = i18n.QUOTES[lang] || QUOTES;
  const [text, author] = list[n % list.length];
  return { text, author, lang, q: i18n.META[lang].q };
}

function state() {
  return { date: key(), day: getDay(), habits: habitsView(), weekKeys: weekDays(), quote: quote() };
}

module.exports = { key, getDay, updateDay, habitsView, toggleHabit, addHabit, removeHabit, quote, state, weekDays, streak };
