// Briefingul de dimineață: la prima activitate din zi, Mady adună emailurile importante
// primite de ieri seară, orele lucrate ieri și progresul săptămânii, și propune prioritatea zilei.
const { powerMonitor } = require('electron');
const store = require('./store');
const sessions = require('./sessions');
const mail = require('./mail');
const ai = require('./ai');
const goals = require('./goals');
const evening = require('./evening');
const { t, locale, plural } = require('./i18n');

const settings = () => store.get().settings;

function todayKey() {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function due() {
  const s = settings();
  if (!s.morningBrief) return false;
  if (store.get().lastBriefDate === todayKey()) return false;
  if (new Date().getHours() < 5) return false;
  return powerMonitor.getSystemIdleTime() < 120; // doar când utilizatorul e la calculator
}

function weekStats() {
  const days = sessions.history();
  const now = new Date();
  const monday = new Date(now.getFullYear(), now.getMonth(), now.getDate() - ((now.getDay() + 6) % 7));
  let weekSec = 0;
  for (const d of Object.values(days)) {
    const [y, m, dd] = d.date.split('-').map(Number);
    if (new Date(y, m - 1, dd) >= monday) weekSec += d.totalSec;
  }
  const past = Object.values(days).filter(d => d.date < todayKey()).sort((a, b) => b.date.localeCompare(a.date));
  return { weekSec, lastDay: past[0] || null };
}

function dayLabel(key) {
  const [y, m, d] = key.split('-').map(Number);
  const date = new Date(y, m - 1, d);
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  if (date.toDateString() === yesterday.toDateString()) return t('ieri');
  return date.toLocaleDateString(locale(), { weekday: 'long', day: 'numeric', month: 'long' });
}

async function collect() {
  const s = settings();
  const { weekSec, lastDay } = weekStats();
  const goalH = Number(s.weeklyGoalHours) || 0;
  const active = goals.view().goals.filter(g => g.stats.pct < 100).sort((a, b) => b.stats.pct - a.stats.pct);
  const data = { weekSec, goalH, lastDay, emails: null, emailError: '', plan: evening.lastNightPlan(), goal: active[0] || null };
  if (s.mailAddress && store.getMailPassword()) {
    const since = new Date();
    since.setDate(since.getDate() - 1);
    since.setHours(17, 0, 0, 0);
    try {
      const msgs = await mail.fetchUnreadSince({
        host: s.mailHost, port: s.mailPort, user: s.mailAddress, pass: store.getMailPassword()
      }, since.getTime());
      data.emails = { count: msgs.length, top: mail.rankImportant(msgs).slice(0, 5) };
    } catch (err) {
      data.emailError = err.message;
    }
  }
  return data;
}

function greeting() {
  const h = new Date().getHours();
  return t(h < 12 ? 'Bună dimineața' : h < 18 ? 'Bună ziua' : 'Bună seara');
}

// Varianta fără AI (modul demo sau dacă modelul nu răspunde): tot utilă, construită din date.
function templateBrief(d, name) {
  const today = new Date().toLocaleDateString(locale(), { weekday: 'long', day: 'numeric', month: 'long' });
  const lines = [t('{g}! Sunt {name}, iată briefingul tău pentru {day}.', { g: greeting(), name, day: today }), ''];
  if (d.emails) {
    lines.push(plural(d.emails.count, '• Inbox: {n} email necitit de ieri seară încoace.', '• Inbox: {n} emailuri necitite de ieri seară încoace.'));
    d.emails.top.slice(0, 3).forEach(m => lines.push(`   – ${m.from}: ${m.subject}`));
  } else if (d.emailError) {
    lines.push(t('• Inbox: nu am putut verifica ({e}).', { e: d.emailError }));
  } else {
    lines.push(t('• Inbox: neconectat. Îl poți conecta din Setări → Inbox.'));
  }
  if (d.lastDay) {
    const label = dayLabel(d.lastDay.date);
    const vars = { day: label[0].toUpperCase() + label.slice(1), dur: sessions.fmt(d.lastDay.totalSec), n: d.lastDay.sessions.length, app: d.lastDay.topApps[0]?.name };
    const one = d.lastDay.sessions.length === 1;
    lines.push('• ' + (d.lastDay.topApps[0]
      ? t(one ? '{day} ai lucrat {dur} într-o sesiune, mai ales în {app}.' : '{day} ai lucrat {dur} în {n} sesiuni, mai ales în {app}.', vars)
      : t(one ? '{day} ai lucrat {dur} într-o sesiune.' : '{day} ai lucrat {dur} în {n} sesiuni.', vars)));
  } else {
    lines.push(t('• Încă nu am sesiuni de lucru înregistrate. Pornește una din tab-ul Timer.'));
  }
  if (d.goalH) {
    const pct = Math.round((d.weekSec / (d.goalH * 3600)) * 100);
    lines.push(t('• Săptămâna aceasta: {dur} din {goal}h ({pct}%).', { dur: sessions.fmt(d.weekSec), goal: d.goalH, pct }));
  }
  if (d.plan && (d.plan.intention || d.plan.top3.length)) {
    const parts = [];
    if (d.plan.intention) parts.push(t('o zi „{i}”', { i: d.plan.intention }));
    if (d.plan.top3.length) parts.push(t('priorități: {p}', { p: d.plan.top3.join(', ') }));
    lines.push(t('• Aseară ți-ai propus {what}.', { what: parts.join('; ') }));
  }
  if (d.goal) lines.push(t('• Obiectiv: {g}.', { g: goalLine(d.goal) }));
  const top = d.emails?.top?.[0];
  if (d.plan?.top3?.[0]) {
    lines.push('', t('Prioritatea zilei: „{p}”, din planul tău de aseară. Dă-i primele 2 ore de focus.', { p: d.plan.top3[0] }));
    return lines.join('\n');
  }
  lines.push('', top
    ? t('Prioritatea zilei: răspunde-i lui {from} („{subject}”), apoi blochează 2 ore de focus.', { from: top.from, subject: top.subject })
    : t('Prioritatea zilei: alege un singur obiectiv important și dă-i primele 2 ore de focus.'));
  return lines.join('\n');
}

function goalLine(g) {
  const n = v => new Intl.NumberFormat(locale()).format(Math.round(v));
  const unit = g.unit ? ' ' + g.unit : '';
  const amount = g.type === 'milestone' ? '' : ' ' + t('({cur} din {target})', { cur: n(g.current) + unit, target: n(g.target) + unit });
  const pace = g.stats.perMonth ? t(', ritm necesar {v}/lună', { v: n(g.stats.perMonth) + unit }) : '';
  return `„${g.title}” – ${g.stats.pct}%${amount}${pace}`;
}

function aiPrompt(d) {
  const parts = [
    `Fă-mi briefingul de dimineață (acum e ${new Date().toLocaleString('ro-RO', { weekday: 'long', hour: '2-digit', minute: '2-digit' })}).`,
    'Format: un salut scurt în stilul tău, apoi 3-5 puncte (inbox, ziua de lucru anterioară, progresul săptămânii),',
    'apoi „Prioritatea zilei:” cu o singură recomandare concretă. Maxim 130 de cuvinte.',
    ''
  ];
  if (d.emails) {
    parts.push(`Emailuri necitite de ieri seară: ${d.emails.count}. Cele mai importante:`);
    d.emails.top.forEach((m, i) => parts.push(`#${i + 1} ${m.from} – ${m.subject}: ${m.text.slice(0, 300)}`));
  } else {
    parts.push(d.emailError ? `Inbox: eroare (${d.emailError}).` : 'Inbox: neconectat.');
  }
  if (d.lastDay) {
    parts.push(`Ultima zi de lucru (${dayLabel(d.lastDay.date)}): ${sessions.fmt(d.lastDay.totalSec)}, sesiuni: ${d.lastDay.sessions.map(x => x.title).join(', ')}; aplicații: ${d.lastDay.topApps.map(a => a.name).join(', ') || '-'}.`);
  } else {
    parts.push('Nu există sesiuni de lucru înregistrate.');
  }
  if (d.goalH) parts.push(`Săptămâna aceasta: ${sessions.fmt(d.weekSec)} lucrate din obiectivul de ${d.goalH}h.`);
  if (d.plan) parts.push(`Planul scris aseară în jurnal: intenție „${d.plan.intention || '-'}”; priorități: ${d.plan.top3.join('; ') || '-'}. Folosește-l pentru „Prioritatea zilei”.`);
  if (d.goal) parts.push(`Obiectivul principal în curs: ${goalLine(d.goal)}.`);
  return parts.join('\n');
}

let running = false;

async function generate() {
  if (running) return null;
  running = true;
  try {
    const s = settings();
    const d = await collect();
    let text;
    if ((s.aiProvider || 'demo') === 'demo') {
      text = templateBrief(d, s.buddyName);
    } else {
      try {
        text = await ai.complete(aiPrompt(d), s, store.getApiKey());
      } catch (err) {
        text = templateBrief(d, s.buddyName) + '\n\n' + t('(Modelul AI nu a răspuns: {e})', { e: err.message });
      }
    }
    const store_ = store.get();
    store_.lastBriefDate = todayKey();
    store_.chat.push({ role: 'assistant', content: text, at: Date.now(), brief: true });
    store.save();
    return { text, emails: d.emails ? d.emails.count : null };
  } finally {
    running = false;
  }
}

module.exports = { due, generate, templateBrief };
