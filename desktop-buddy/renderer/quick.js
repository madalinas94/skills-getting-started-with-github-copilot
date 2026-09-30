const api = window.buddy;
const $ = sel => document.querySelector(sel);
const TITLES = { correct: 'Text corectat', summarize: 'Rezumat', translate: 'Traducere', elegant: 'Varianta elegantă' };
let source = '';
let lastQuestion = '';
let lastAnswer = '';
let busy = false;

function showResult(title, { text = '', loading = false, error = false, chat = false } = {}) {
  $('.card').classList.remove('compact');
  $('#result').classList.remove('hidden');
  $('#resultTitle').textContent = title;
  $('#resultText').textContent = text;
  $('#resultText').className = 'result-text' + (loading ? ' loading' : '') + (error ? ' error' : '');
  $('#copyBtn').classList.toggle('hidden', loading || error);
  $('#chatBtn').classList.toggle('hidden', !chat || loading || error);
}

function setBusy(b) {
  busy = b;
  document.querySelectorAll('.actions button').forEach(btn => { btn.disabled = b; });
}

api.quick.onOpen(({ clipboard }) => {
  source = clipboard || '';
  $('#clipPreview').textContent = source;
  $('#clipBox').classList.toggle('hidden', !source.trim());
  $('#clipEmpty').classList.toggle('hidden', !!source.trim());
  $('#result').classList.add('hidden');
  $('.card').classList.add('compact');
  $('#askInput').value = '';
  setBusy(false);
  setTimeout(() => $('#askInput').focus(), 30);
});

document.querySelectorAll('.actions button[data-action]').forEach(btn => btn.addEventListener('click', async () => {
  if (busy) return;
  const action = btn.dataset.action;
  const lang = $('#lang').value;
  const title = action === 'translate' ? `${TITLES.translate} · ${$('#lang').selectedOptions[0].textContent}` : TITLES[action];
  setBusy(true);
  showResult(title, { text: 'Mady lucrează…', loading: true });
  const res = await api.quick.action(action, source, lang);
  showResult(title, res.ok ? { text: res.text } : { text: res.error, error: true });
  setBusy(false);
}));

$('#askForm').addEventListener('submit', async e => {
  e.preventDefault();
  const q = $('#askInput').value.trim();
  if (!q || busy) return;
  lastQuestion = q;
  setBusy(true);
  showResult('Răspuns', { text: 'Mady se gândește…', loading: true });
  const res = await api.quick.ask(q);
  lastAnswer = res.ok ? res.text : '';
  showResult('Răspuns', res.ok ? { text: res.text, chat: true } : { text: res.error, error: true });
  setBusy(false);
});

$('#copyBtn').addEventListener('click', async () => {
  await api.quick.copy($('#resultText').textContent);
  $('#copyBtn').lastChild.textContent = 'Copiat';
  setTimeout(() => { $('#copyBtn').lastChild.textContent = 'Copiază'; }, 1200);
});
$('#chatBtn').addEventListener('click', () => api.quick.toChat(lastQuestion, lastAnswer));

document.addEventListener('keydown', e => { if (e.key === 'Escape') api.quick.hide(); });

function applyTheme(s) {
  document.documentElement.dataset.theme = s.themeResolved || s.theme;
  $('#askInput').placeholder = t('Întreab-o pe {name}…', { name: s.buddyName });
  $('.monogram').textContent = (s.buddyName || 'M')[0].toUpperCase();
}
api.settings.get().then(applyTheme);
api.settings.onUpdate(applyTheme);
