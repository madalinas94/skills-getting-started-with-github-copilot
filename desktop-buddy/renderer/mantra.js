const api = window.buddy;
const $ = sel => document.querySelector(sel);
let m = null;
let total = 30000;
let left = total;
let last = performance.now();
let hovering = false;
let closing = false;

function fit() {
  api.mantra.size(Math.ceil($('#card').getBoundingClientRect().height) + 70);
}

function render() {
  const date = new Date().toLocaleDateString(m.locale || I18N.locale, { weekday: 'long', day: 'numeric', month: 'long' });
  const [qo, qc] = m.q || ['„', '”'];
  $('#kicker').textContent = `${m.kicker || t('Mantra zilei')} · ${date}`;
  $('#label').textContent = m.label;
  $('#title').textContent = m.title || '';
  $('#text').textContent = m.type === 'citat' || m.type === 'vorba' ? `${qo}${m.text}${qc}` : m.text;
  $('#author').textContent = m.author ? `— ${m.author}` : '';
  $('#note').textContent = m.note || '';
  $('#fav').classList.toggle('on', !!m.fav);
  fit();
}

function close() {
  if (closing) return;
  closing = true;
  $('#card').classList.add('leaving');
  setTimeout(() => api.mantra.close(), 600);
}

function tick(now) {
  if (!hovering && !closing) left -= now - last;
  last = now;
  $('#bar').style.transform = `scaleX(${Math.max(0, left / total)})`;
  if (left <= 0) close();
  else requestAnimationFrame(tick);
}

$('#card').addEventListener('mouseenter', () => { hovering = true; });
$('#card').addEventListener('mouseleave', () => { hovering = false; });
$('#close').addEventListener('click', close);
$('#fav').addEventListener('click', async () => {
  m = await api.mantra.fav(m.date, !m.fav);
  render();
});
$('#save').addEventListener('click', async () => {
  const span = $('#save span');
  span.textContent = 'Se creează…';
  const res = await api.mantra.image();
  span.textContent = res.ok ? 'Copiată ✓' : 'Eroare';
  setTimeout(() => { span.textContent = 'Imagine'; }, 2500);
  left = Math.max(left, 10000); // mai lăsăm cardul puțin
});
$('#open').addEventListener('click', () => { api.mantra.openToday(); close(); });

function applyTheme(s) { document.documentElement.dataset.theme = s.themeResolved || s.theme; }

(async () => {
  const s = await api.settings.get();
  applyTheme(s);
  total = left = (Number(s.mantraSeconds) || 30) * 1000;
  m = await api.mantra.get();
  render();
  await document.fonts.ready;
  fit();
  last = performance.now();
  requestAnimationFrame(tick);
})();
api.settings.onUpdate(applyTheme);
