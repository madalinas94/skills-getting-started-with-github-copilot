const api = window.buddy;
const $ = sel => document.querySelector(sel);
const OPACITIES = [1, 0.75, 0.5, 0.3];
let state = null;
let offset = 0; // diferența dintre ceasul procesului principal și cel local

function elapsedMs() {
  if (!state) return 0;
  const now = Date.now() + offset;
  const pausedNow = state.pausedAt ? now - state.pausedAt : 0;
  return Math.max(0, now - state.start - state.pausedMs - pausedNow);
}

function fmt(ms) {
  const t = Math.floor(ms / 1000);
  const h = String(Math.floor(t / 3600)).padStart(2, '0');
  const m = String(Math.floor((t % 3600) / 60)).padStart(2, '0');
  const s = String(t % 60).padStart(2, '0');
  return `${h}:${m}:${s}`;
}

function render() {
  if (!state) return;
  const p = state.pomo;
  if (p) {
    const now = Date.now() + offset;
    const left = p.phaseEndsAt ? Math.max(0, p.phaseEndsAt - now) : (p.remainingMs ?? 0);
    const m = Math.floor(left / 60000), sec = Math.floor((left % 60000) / 1000);
    $('#title').textContent = p.phase === 'focus' ? `Focus · runda ${p.count + 1} · ${state.title}` : `Pauză · ${state.title}`;
    $('#time').textContent = `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
    $('#pill').classList.toggle('break', p.phase === 'break');
  } else {
    $('#title').textContent = state.title;
    $('#time').textContent = fmt(elapsedMs());
    $('#pill').classList.remove('break');
  }
  const paused = !!state.pausedAt && !(p && p.phase === 'break');
  $('#pill').classList.toggle('paused', paused);
  $('#toggleIcon').setAttribute('href', paused ? '#i-play' : '#i-pause');
  $('#toggle').title = paused ? 'Continuă' : 'Pauză';
}

function setState(s) {
  state = s;
  if (s) offset = s.now - Date.now();
  render();
}

$('#toggle').addEventListener('click', async () => {
  setState(state?.pausedAt ? await api.session.resume() : await api.session.pause());
});
$('#stop').addEventListener('click', () => api.session.stop());
$('#hide').addEventListener('click', () => api.timer.hide());
$('#opacity').addEventListener('click', async () => {
  const cur = await api.timer.getOpacity();
  const i = OPACITIES.findIndex(o => Math.abs(o - cur) < 0.01);
  await api.timer.setOpacity(OPACITIES[(i + 1) % OPACITIES.length]);
});

function applyTheme(s) { document.documentElement.dataset.theme = s.themeResolved || s.theme; }
api.settings.get().then(applyTheme);
api.settings.onUpdate(applyTheme);
api.session.current().then(setState);
api.session.onChange(setState);
setInterval(render, 500);
