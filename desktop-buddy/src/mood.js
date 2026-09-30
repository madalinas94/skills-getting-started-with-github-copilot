// Starea lui Mady (expresia de pe desktop) și replicile ei.
// Stări de bază: idle, focus (sesiune activă), sleep (fără activitate 5+ minute).
// Stări de moment (câteva secunde): celebrate, alert, happy.
const { powerMonitor } = require('electron');

const SLEEP_AFTER_SEC = 5 * 60;
const CHECK_MS = 10 * 1000;

const LINES = {
  welcome: [
    'Bine ai revenit. Ce cucerim azi?',
    'Sunt aici. Spune-mi ce avem pe agendă.',
    'Revenirea ta îmi place. Hai să facem ziua memorabilă.'
  ],
  sessionStart: [
    'Focus mode. Te las să strălucești.',
    'Perfect. Telefonul deoparte, obiectivul în față.',
    'Începem. Elegant, concentrat, fără scuze.'
  ],
  hour: [
    'O oră de focus. Impresionant. Ridică-te, bea apă, revino.',
    'Încă o oră bifată. Umerii jos, spatele drept, continuăm.',
    'Ritmul tău e de invidiat. Cinci minute de pauză și revenim.'
  ],
  sessionEndLong: [
    'Sesiune încheiată: {dur}. Asta da disciplină.',
    '{dur} de lucru serios. Sunt mândră de tine.',
    'Gata, {dur}. Așa se construiesc lucrurile mari.'
  ],
  sessionEndShort: [
    'Sesiune scurtă ({dur}). Și pașii mici contează.',
    'Sesiune scurtă ({dur}). Un început. Data viitoare mergem mai departe.'
  ],
  wake: [
    'Ah, te-ai întors. Hai să terminăm ce am început.',
    'Pauza a fost binemeritată. Acum, înapoi la treabă.',
    'Te așteptam. Continuăm?'
  ],
  breakStart: [
    'Runda {n} gata. {min} minute de pauză: ridică-te, respiră, bea apă.',
    'Excelent. Pauză de {min} minute, fără telefon dacă poți.',
    'Focus bifat. Acum {min} minute doar pentru tine.'
  ],
  longBreak: [
    'Patru runde! Meriți o pauză lungă de {min} minute. O cafea ca lumea?',
    'Impresionant. {min} minute de pauză lungă. Plimbă-te puțin.'
  ],
  focusBack: [
    'Pauza s-a terminat. Încă {min} minute de focus, elegant și concentrat.',
    'Înapoi la treabă. Următoarele {min} minute sunt ale obiectivului tău.'
  ],
  top3Done: [
    'Toate cele trei priorități bifate. Asta e o zi de manual.',
    'Top 3 complet. Restul zilei e bonus. Sunt mândră de tine.'
  ],
  waterDone: [
    'Opt pahare. Hidratată și strălucitoare.',
    'Obiectivul de apă atins. Pielea ta îți mulțumește.'
  ],
  streak: [
    '{n} zile la rând: „{name}”. Așa se construiește un stil de viață.',
    'Seria continuă: {n} zile de „{name}”. Nu o rupe.'
  ],
  goalMilestone: [
    '{pct}% din „{title}”. Vezi? Planul funcționează.',
    'Ai trecut de {pct}% la „{title}”. Continuăm în același ritm, elegant și constant.'
  ],
  goalDone: [
    '„{title}”: atins. Brava! Asta merită sărbătorit, apoi următorul vis.',
    'Obiectiv îndeplinit: „{title}”. Știam că poți.'
  ],
  goalStep: [
    'Un pas mai aproape de „{title}”. Așa se construiește.',
    'Pas bifat la „{title}”. Mic azi, mare peste un an.'
  ],
  eveningInvite: [
    'E seară. Cinci minute pentru jurnal: ce a mers bine, ce ai învățat și planul de mâine?',
    'Hai să închidem ziua frumos. Te aștept în jurnalul de seară.',
    'Înainte de somn: recunoștință, o rugăciune și Top 3 pentru mâine. Deschid jurnalul?'
  ],
  spontaneous: [
    'Monet spunea că pictează așa cum cântă o pasăre. Tu lucrezi la fel de natural azi?',
    'Randamentul compus e a opta minune a lumii. Valabil și pentru obiceiuri.',
    'Seneca: „Nu pentru că e greu nu îndrăznim, ci pentru că nu îndrăznim e greu.”',
    'Un portofoliu bun e ca o garderobă bună: câteva piese solide, nimic impulsiv.',
    'Ai băut apă în ultima oră? Eleganța începe cu hidratarea.',
    'Piețele răsplătesc răbdarea. Proiectele tale la fel.',
    'Florența, Luvru, Prado… Care e următoarea destinație pe lista ta?',
    'Prioritatea numărul unu de azi e încă prioritatea numărul unu?',
    'Un email amânat e o decizie amânată. Vrei să aruncăm o privire în inbox?',
    'Postura, te rog. O femeie elegantă stă dreaptă, un om productiv la fel.'
  ]
};

// Aceleași replici, în engleză (limba interfeței).
const LINES_EN = {
  welcome: [
    'Welcome back. What are we conquering today?',
    'I’m here. Tell me what’s on the agenda.',
    'I like it when you come back. Let’s make today memorable.'
  ],
  sessionStart: [
    'Focus mode. I’ll let you shine.',
    'Perfect. Phone away, goal in front.',
    'Here we go. Elegant, focused, no excuses.'
  ],
  hour: [
    'One hour of focus. Impressive. Stand up, drink some water, come back.',
    'Another hour done. Shoulders down, back straight, let’s keep going.',
    'Your pace is enviable. Five minutes of rest and we’re back.'
  ],
  sessionEndLong: [
    'Session done: {dur}. Now that’s discipline.',
    '{dur} of serious work. I’m proud of you.',
    'Done, {dur}. This is how big things get built.'
  ],
  sessionEndShort: [
    'Short session ({dur}). Small steps count too.',
    'Short session ({dur}). A start. Next time we go further.'
  ],
  wake: [
    'Ah, you’re back. Let’s finish what we started.',
    'That break was well deserved. Now, back to work.',
    'I was waiting for you. Shall we continue?'
  ],
  breakStart: [
    'Round {n} done. {min} minutes of rest: stand up, breathe, drink water.',
    'Excellent. A {min}-minute break, no phone if you can.',
    'Focus done. Now {min} minutes just for you.'
  ],
  longBreak: [
    'Four rounds! You deserve a long {min}-minute break. A proper coffee?',
    'Impressive. {min} minutes of long break. Take a little walk.'
  ],
  focusBack: [
    'Break’s over. {min} more minutes of focus, elegant and sharp.',
    'Back to work. The next {min} minutes belong to your goal.'
  ],
  top3Done: [
    'All three priorities done. A textbook day.',
    'Top 3 complete. The rest of the day is a bonus. I’m proud of you.'
  ],
  waterDone: [
    'Eight glasses. Hydrated and glowing.',
    'Water goal reached. Your skin thanks you.'
  ],
  streak: [
    '{n} days in a row: “{name}”. That’s how a lifestyle is built.',
    'The streak goes on: {n} days of “{name}”. Don’t break it.'
  ],
  goalMilestone: [
    '{pct}% of “{title}”. See? The plan works.',
    'You’re past {pct}% on “{title}”. Same pace, elegant and steady.'
  ],
  goalDone: [
    '“{title}”: achieved. Brava! Celebrate it, then on to the next dream.',
    'Goal reached: “{title}”. I knew you could.'
  ],
  goalStep: [
    'One step closer to “{title}”. That’s how it’s built.',
    'Step ticked on “{title}”. Small today, big a year from now.'
  ],
  eveningInvite: [
    'It’s evening. Five minutes for your journal: what went well, what you learned and tomorrow’s plan?',
    'Let’s close the day beautifully. I’ll be waiting in your evening journal.',
    'Before bed: gratitude, a prayer and a Top 3 for tomorrow. Shall I open the journal?'
  ],
  spontaneous: [
    'Monet said he painted the way a bird sings. Are you working that naturally today?',
    'Compound interest is the eighth wonder of the world. It works for habits too.',
    'Seneca: “It is not because things are difficult that we do not dare; it is because we do not dare that they are difficult.”',
    'A good portfolio is like a good wardrobe: a few solid pieces, nothing impulsive.',
    'Have you had water in the last hour? Elegance starts with hydration.',
    'Markets reward patience. So do your projects.',
    'Florence, the Louvre, the Prado… What’s the next destination on your list?',
    'Is today’s number one priority still number one?',
    'A postponed email is a postponed decision. Shall we take a look at the inbox?',
    'Posture, please. An elegant woman sits up straight, and so does a productive one.'
  ]
};

let lastPick = {};
function line(kind, vars = {}) {
  const en = require('./i18n').lang() === 'en';
  const list = (en ? LINES_EN[kind] : null) || LINES[kind] || [''];
  let i = Math.floor(Math.random() * list.length);
  if (list.length > 1 && i === lastPick[kind]) i = (i + 1) % list.length;
  lastPick[kind] = i;
  return list[i].replace(/\{(\w+)\}/g, (_, k) => vars[k] ?? '');
}

let base = 'idle';
let transient = null;
let transientTimer = null;
let sleptSince = null;
let timer = null;
let lastSpontaneous = Date.now();
let hooks = { getSession: () => null, settings: () => ({}), onState() {}, onWake() {}, say() {} };

function current() {
  return transient || base;
}

function computeBase() {
  if (powerMonitor.getSystemIdleTime() >= SLEEP_AFTER_SEC) return 'sleep';
  const s = hooks.getSession();
  if (s && !s.pausedAt) return 'focus';
  return 'idle';
}

function update() {
  const prev = current();
  const next = computeBase();
  if (next === 'sleep' && base !== 'sleep') sleptSince = Date.now();
  if (base === 'sleep' && next !== 'sleep') {
    const sleptMin = sleptSince ? (Date.now() - sleptSince) / 60000 : 0;
    sleptSince = null;
    base = next;
    hooks.onWake(sleptMin);
  }
  base = next;
  if (current() !== prev) hooks.onState(current());
  maybeSpontaneous();
}

function maybeSpontaneous() {
  const s = hooks.settings();
  if (!s.buddySpeech || !s.buddySpontaneous || base !== 'idle' || transient) return;
  const every = 60 * 60 * 1000;
  if (Date.now() - lastSpontaneous < every) return;
  lastSpontaneous = Date.now();
  hooks.say(line('spontaneous'));
}

// Stare de moment (celebrate / alert / happy), apoi revine la starea de bază.
function flash(state, ms = 6000) {
  transient = state;
  clearTimeout(transientTimer);
  hooks.onState(current());
  transientTimer = setTimeout(() => {
    transient = null;
    hooks.onState(current());
  }, ms);
}

function init(h) {
  hooks = { ...hooks, ...h };
  base = computeBase();
  clearInterval(timer);
  timer = setInterval(update, CHECK_MS);
}

function refresh() {
  update();
}

function noteSpoke() {
  lastSpontaneous = Date.now();
}

function shutdown() {
  clearInterval(timer);
  clearTimeout(transientTimer);
}

module.exports = { init, current, flash, refresh, line, noteSpoke, shutdown };
