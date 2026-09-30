const api = window.buddy;
const $ = sel => document.querySelector(sel);
const PAGES = 4; // + pagina finală
let ctx = null;
let page = 0;
let rating = 0;

function el(tag, props = {}, children = []) {
  const n = Object.assign(document.createElement(tag), props);
  for (const c of [].concat(children)) if (c !== null && c !== undefined && c !== false) n.append(c);
  return n;
}
let toastTimer;
function toast(t) {
  $('#toast').textContent = t;
  $('#toast').classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $('#toast').classList.remove('show'), 2600);
}
function fmtDur(sec) {
  const h = Math.floor(sec / 3600), m = Math.round((sec % 3600) / 60);
  return h ? `${h}h ${String(m).padStart(2, '0')}m` : `${m} min`;
}
function autoGrow(t) {
  t.style.height = 'auto';
  t.style.height = Math.max(t.scrollHeight, t.rows * 32) + 'px';
}

function go(i) {
  const prev = page;
  page = Math.max(0, Math.min(PAGES, i));
  document.querySelectorAll('.page').forEach(p => {
    const n = Number(p.dataset.page);
    p.classList.toggle('on', n === page);
    p.classList.toggle('left', n < page);
  });
  document.querySelectorAll('#steps button').forEach(b => {
    const n = Number(b.dataset.i);
    b.classList.toggle('on', n === page);
    b.classList.toggle('seen', n < page);
  });
  $('#steps').classList.toggle('hidden', page === PAGES);
  $('#nav').classList.toggle('hidden-nav', page === PAGES);
  $('#prev').disabled = page === 0;
  $('#next').textContent = t(page === PAGES - 1 ? 'Închide ziua' : 'Mai departe');
  $('#dots').textContent = [...Array(PAGES)].map((_, n) => (n === page ? '●' : '○')).join('');
  const first = document.querySelector(`.page[data-page="${page}"] textarea, .page[data-page="${page}"] input:not([type=checkbox])`);
  if (first && prev !== page) setTimeout(() => first.focus(), 200);
}

function stars() {
  const labels = ['grea', 'așa și așa', 'bună', 'foarte bună', 'excelentă'];
  $('#stars').replaceChildren(...labels.map((l, i) => el('button', {
    className: i < rating ? 'on' : '', textContent: '★', title: t('Zi {l}', { l: t(l) }),
    onclick: () => { rating = rating === i + 1 ? 0 : i + 1; stars(); }
  })));
}

function renderStats() {
  const s = ctx.stats;
  const chip = (v, label) => el('span', { className: 'stat' }, [el('b', { textContent: v }), label]);
  const list = [];
  if (s.focus.sec >= 60) list.push(chip(fmtDur(s.focus.sec), t(s.focus.count === 1 ? 'de focus (o sesiune)' : 'de focus ({n} sesiuni)', { n: s.focus.count })));
  if (s.focus.pomodoros) list.push(chip(s.focus.pomodoros, 'pomodoro'));
  if (s.top3.total) list.push(chip(`${s.top3.done}/${s.top3.total}`, 'priorități'));
  if (s.habits.total) list.push(chip(`${s.habits.done}/${s.habits.total}`, 'ritualuri'));
  if (s.water) list.push(chip(s.water, s.water === 1 ? 'pahar de apă' : 'pahare de apă'));
  if (s.stepsToday.length) list.push(chip(s.stepsToday.length, s.stepsToday.length === 1 ? 'pas spre obiective' : 'pași spre obiective'));
  for (const c of s.contribToday) list.push(chip(`+${new Intl.NumberFormat(I18N.locale).format(c.amount)}${c.unit ? ' ' + c.unit : ''}`, c.title));
  if (!list.length) list.push(el('span', { className: 'stat' }, ['O zi liniștită. Și acestea contează.']));
  $('#stats').replaceChildren(...list);
}

// Sugestii pentru „Ce a mers bine”: prioritățile bifate și pașii făcuți azi.
function winsStarter() {
  const s = ctx.stats;
  const bits = [...s.top3.items.filter(t => t.done).map(t => t.text), ...s.stepsToday.map(x => x.text)];
  return bits.length ? bits.map(b => '• ' + b).join('\n') + '\n' : '';
}

function fill() {
  $('#date').textContent = ctx.dateLabel;
  $('#prayerAff').textContent = `„${ctx.prayer}”`;
  $('#sign').textContent = '— ' + ctx.buddyName;
  renderStats();
  const e = ctx.evening;
  $('#wins').value = e?.wins ?? winsStarter();
  $('#learned').value = e?.learned || '';
  $('#gratitude').value = e?.gratitude ?? ctx.gratitude ?? '';
  $('#prayed').checked = !!e?.prayed;
  rating = e?.rating || 0;
  stars();
  $('#tIntention').value = ctx.tomorrow.intention || '';
  ctx.tomorrow.top3.forEach((t, i) => { $('#t' + i).value = t || ''; });
  const carried = ctx.stats.top3.items.filter(t => !t.done).length;
  $('#carry').textContent = carried && !e ? t(carried === 1 ? 'Am mutat pe mâine prioritatea nebifată de azi. Schimbă-o liniștit.' : 'Am mutat pe mâine cele {n} priorități nebifate de azi. Schimbă-le liniștit.', { n: carried }) : '';
  document.querySelectorAll('textarea').forEach(autoGrow);
  if (e) {
    $('#note').textContent = e.note;
    go(PAGES);
  } else go(0);
}

async function finish() {
  $('#next').disabled = true;
  $('#next').textContent = 'Scriu…';
  const r = await api.evening.save({
    wins: $('#wins').value, learned: $('#learned').value, gratitude: $('#gratitude').value, prayed: $('#prayed').checked, rating,
    tomorrowIntention: $('#tIntention').value, tomorrowTop3: [0, 1, 2].map(i => $('#t' + i).value)
  });
  $('#next').disabled = false;
  ctx = r.context;
  $('#note').textContent = r.note;
  go(PAGES);
}

const LEARN = [
  ['Despre mine', 'Despre mine am observat că '],
  ['Din ce am citit', 'Din ce am citit azi rețin că '],
  ['Despre bani și piețe', 'Despre bani și piețe am înțeles că '],
  ['Despre oameni', 'Despre oameni am învățat că '],
  ['Aș face altfel', 'Mâine aș face altfel: ']
];
$('#learnChips').replaceChildren(...LEARN.map(([label, start]) => el('button', {
  textContent: label,
  onclick: () => {
    const box = $('#learned');
    box.value = (box.value.trim() ? box.value.trimEnd() + '\n' : '') + t(start.trim()) + ' ';
    autoGrow(box);
    box.focus();
    box.setSelectionRange(box.value.length, box.value.length);
  }
})));

document.querySelectorAll('textarea').forEach(t => t.addEventListener('input', () => autoGrow(t)));
$('#next').addEventListener('click', () => (page === PAGES - 1 ? finish() : go(page + 1)));
$('#prev').addEventListener('click', () => go(page - 1));
$('#steps').addEventListener('click', e => { const b = e.target.closest('button'); if (b) go(Number(b.dataset.i)); });
$('#edit').addEventListener('click', () => go(0));
$('#done').addEventListener('click', () => api.evening.close());
$('#close').addEventListener('click', () => api.evening.close());
$('#dayCard').addEventListener('click', async () => {
  const r = await api.card.make('day', 'post');
  if (!r.ok) return toast(t('Nu am putut crea cardul: {e}', { e: r.error }));
  await api.card.copy();
  toast('Cardul zilei e salvat în Imagini și copiat');
});

$('#openHistory').addEventListener('click', async () => {
  const list = await api.evening.history();
  $('#hList').replaceChildren(...(list.length ? list.map(h => el('div', { className: 'h-item' }, [
    el('div', { className: 'd' }, [el('span', { textContent: h.label }), el('span', { textContent: h.rating ? '★'.repeat(h.rating) : '' })]),
    h.wins ? el('p', {}, [el('b', { textContent: 'Bine' }), h.wins]) : null,
    h.learned ? el('p', {}, [el('b', { textContent: 'Învățat' }), h.learned]) : null,
    h.gratitude ? el('p', {}, [el('b', { textContent: 'Mulțumesc' }), h.gratitude]) : null
  ])) : [el('div', { className: 'h-empty', textContent: 'Primul tău jurnal de seară se scrie azi.' })]));
  $('#history').classList.remove('hidden');
});
$('#closeHistory').addEventListener('click', () => $('#history').classList.add('hidden'));
document.addEventListener('keydown', e => {
  if (e.key !== 'Escape') return;
  if (!$('#history').classList.contains('hidden')) $('#history').classList.add('hidden');
  else api.evening.close();
});

function applyTheme(s) { document.documentElement.dataset.theme = s.themeResolved || s.theme; }
api.settings.get().then(applyTheme);
api.settings.onUpdate(applyTheme);
api.evening.context().then(c => { ctx = c; fill(); });
