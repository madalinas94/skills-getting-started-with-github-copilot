const api = window.buddy;
const $ = sel => document.querySelector(sel);
const CUSTOM_MODEL = '__custom__';

let settings = {};
let providers = {};
let clipItems = [];
let notes = [];
let currentNoteId = null;

// ---------- utilitare ----------

function icon(name) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', 'ic');
  const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
  use.setAttribute('href', `#i-${name}`);
  svg.append(use);
  return svg;
}

function el(tag, props = {}, children = []) {
  const node = Object.assign(document.createElement(tag), props);
  for (const c of [].concat(children)) node.append(c);
  return node;
}

function timeAgo(ts) {
  const s = Math.floor((Date.now() - ts) / 1000);
  if (s < 60) return 'acum';
  if (s < 3600) return `acum ${Math.floor(s / 60)} min`;
  if (s < 86400) return `acum ${Math.floor(s / 3600)} h`;
  return new Date(ts).toLocaleDateString('ro-RO');
}

let toastTimer;
function toast(text) {
  const t = $('#toast');
  t.textContent = text;
  t.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => t.classList.remove('show'), 1500);
}

// Confirmare în interiorul panoului (un dialog de sistem ar lua focusul și ar închide panoul).
function askConfirm(text, ok = 'Da, șterge') {
  return new Promise(resolve => {
    const box = $('#confirm');
    $('#confirmText').textContent = text;
    $('#confirmOk').textContent = ok;
    box.classList.remove('hidden');
    const done = v => {
      box.classList.add('hidden');
      $('#confirmOk').onclick = $('#confirmCancel').onclick = null;
      resolve(v);
    };
    $('#confirmOk').onclick = () => done(true);
    $('#confirmCancel').onclick = () => done(false);
    $('#confirmOk').focus();
  });
}

// ---------- tab-uri ----------

function showTab(name) {
  document.querySelectorAll('.tabs button').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.id === `tab-${name}`));
  if (name === 'ai') setTimeout(() => $('#chatInput').focus(), 50);
  if (name === 'timer') loadHistory();
  if (name === 'today') { loadToday(); loadMantra(); }
  if (name === 'timer') loadMonth();
  if (name === 'inbox') api.mail.scanState().then(renderScan);
  if (name === 'inbox' && !mails.length) refreshMail();
}
document.querySelectorAll('.tabs button').forEach(b => b.addEventListener('click', () => showTab(b.dataset.tab)));
api.panel.onTab(showTab);
$('#closeBtn').addEventListener('click', () => api.panel.hide());
document.addEventListener('keydown', e => { if (e.key === 'Escape') api.panel.hide(); });

// ---------- clipboard ----------

function renderClipboard() {
  const q = $('#clipSearch').value.toLowerCase();
  const items = clipItems
    .filter(i => i.text.toLowerCase().includes(q))
    .sort((a, b) => (b.pinned - a.pinned) || (b.createdAt - a.createdAt));
  const list = $('#clipList');
  list.replaceChildren();
  for (const item of items) {
    const actions = el('span', { className: 'actions' }, [
      el('button', { className: item.pinned ? 'on' : '', title: item.pinned ? 'Anulează fixarea' : 'Fixează', onclick: async e => {
        e.stopPropagation();
        clipItems = await api.clipboard.pin(item.id);
        renderClipboard();
      } }, icon('pin')),
      el('button', { title: `Cere-i lui ${settings.buddyName}: corectează / rezumă / traduce`, onclick: e => {
        e.stopPropagation();
        api.quick.openFor(item.text);
      } }, icon('spark')),
      el('button', { title: 'Salvează ca notiță', onclick: async e => {
        e.stopPropagation();
        await api.clipboard.toNote(item.id);
        toast('Salvat în notițe');
      } }, icon('note')),
      el('button', { title: 'Șterge', onclick: async e => {
        e.stopPropagation();
        clipItems = await api.clipboard.remove(item.id);
        renderClipboard();
      } }, icon('trash'))
    ]);
    list.append(el('li', {
      className: 'item' + (item.pinned ? ' pinned' : ''),
      title: 'Click pentru a copia',
      onclick: async () => { await api.clipboard.copy(item.id); toast('Copiat în clipboard'); }
    }, [
      el('div', { className: 'text', textContent: item.text }),
      el('div', { className: 'meta' }, [el('span', { className: 'muted', textContent: timeAgo(item.createdAt) }), actions])
    ]));
  }
  $('#clipEmpty').classList.toggle('hidden', items.length > 0);
}

$('#clipSearch').addEventListener('input', renderClipboard);
$('#clipClear').addEventListener('click', async () => {
  if (!await askConfirm('Ștergi tot istoricul clipboard (cu excepția celor fixate)?')) return;
  clipItems = await api.clipboard.clear();
  renderClipboard();
});
api.clipboard.onUpdate(items => { clipItems = items; renderClipboard(); });

// ---------- notițe ----------

function renderNotes() {
  const q = $('#noteSearch').value.toLowerCase();
  const items = notes.filter(n => (n.title + ' ' + n.body).toLowerCase().includes(q));
  const list = $('#noteList');
  list.replaceChildren();
  for (const n of items) {
    const title = el('div', { className: 'title', textContent: n.title || 'Fără titlu' });
    if (n.sticky) {
      const tag = el('span', { className: 'sticky-tag', title: 'Lipită pe desktop' }, [icon('sticky')]);
      title.append(tag);
    }
    list.append(el('li', { className: 'item', onclick: () => openNote(n.id) }, [
      title,
      el('div', { className: 'text muted', textContent: n.body.slice(0, 200) || '…' }),
      el('div', { className: 'meta' }, [el('span', { className: 'muted', textContent: timeAgo(n.updatedAt) })])
    ]));
  }
  $('#noteEmpty').classList.toggle('hidden', items.length > 0);
}

function openNote(id) {
  const n = notes.find(x => x.id === id);
  currentNoteId = n ? n.id : null;
  $('#noteTitle').value = n ? n.title : '';
  $('#noteBody').value = n ? n.body : '';
  $('#noteStatus').textContent = '';
  renderPinButton();
  $('#notesListView').classList.add('hidden');
  $('#noteEditView').classList.remove('hidden');
  $(n ? '#noteBody' : '#noteTitle').focus();
}

function closeNote() {
  flushNote();
  currentNoteId = null;
  $('#noteEditView').classList.add('hidden');
  $('#notesListView').classList.remove('hidden');
  renderNotes();
}

let noteTimer;
function scheduleNoteSave() {
  $('#noteStatus').textContent = 'Se salvează…';
  clearTimeout(noteTimer);
  noteTimer = setTimeout(flushNote, 500);
}

async function flushNote() {
  clearTimeout(noteTimer);
  const title = $('#noteTitle').value;
  const body = $('#noteBody').value;
  if (!currentNoteId && !title.trim() && !body.trim()) return;
  const saved = await api.notes.save({ id: currentNoteId, title, body });
  currentNoteId = saved.id;
  $('#noteStatus').textContent = 'Salvat';
}

$('#noteNew').addEventListener('click', () => openNote(null));
$('#noteNewSticky').addEventListener('click', async () => {
  await api.sticky.create();
  toast('Notiță nouă pe desktop');
});

function renderPinButton() {
  const n = notes.find(x => x.id === currentNoteId);
  const pinned = !!n?.sticky;
  $('#notePin span').textContent = pinned ? 'Dezlipește' : 'Pe desktop';
  $('#notePin').title = pinned ? 'Scoate notița de pe desktop' : 'Lipește notița pe desktop';
}

$('#notePin').addEventListener('click', async () => {
  await flushNote();
  if (!currentNoteId) {
    const saved = await api.notes.save({ title: $('#noteTitle').value, body: $('#noteBody').value });
    currentNoteId = saved.id;
  }
  const n = notes.find(x => x.id === currentNoteId);
  if (n?.sticky) {
    api.sticky.unpin(currentNoteId);
    toast('Notița a fost scoasă de pe desktop');
  } else {
    await api.sticky.pin(currentNoteId);
    toast('Notița e acum pe desktop');
  }
});
$('#noteBack').addEventListener('click', closeNote);
$('#noteTitle').addEventListener('input', scheduleNoteSave);
$('#noteBody').addEventListener('input', scheduleNoteSave);
$('#noteSearch').addEventListener('input', renderNotes);
$('#noteDelete').addEventListener('click', async () => {
  if (currentNoteId) {
    if (!await askConfirm('Ștergi această notiță?')) return;
    notes = await api.notes.remove(currentNoteId);
  }
  currentNoteId = null;
  $('#noteTitle').value = '';
  $('#noteBody').value = '';
  closeNote();
});
api.notes.onUpdate(list => {
  notes = list;
  if (!currentNoteId) renderNotes();
  else {
    renderPinButton();
    // editată între timp pe desktop: actualizăm câmpurile care nu sunt în lucru
    const n = list.find(x => x.id === currentNoteId);
    if (!n) {
      // ștearsă de pe desktop: golim editorul ca să nu o recreăm la închidere
      clearTimeout(noteTimer);
      currentNoteId = null;
      $('#noteTitle').value = '';
      $('#noteBody').value = '';
      closeNote();
      return;
    }
    if (document.activeElement !== $('#noteTitle')) $('#noteTitle').value = n.title;
    if (document.activeElement !== $('#noteBody')) $('#noteBody').value = n.body;
  }
});

// ---------- asistent AI ----------

function renderChat(chat, { error, typing } = {}) {
  const box = $('#chat');
  box.replaceChildren();
  if (!chat.length) {
    box.append(el('div', { className: 'msg assistant' }, [
      el('span', { className: 'who', textContent: settings.buddyName }),
      'Bine ai revenit. Ce obiectiv atacăm azi?'
    ]));
  }
  for (const m of chat) {
    const bubble = el('div', { className: `msg ${m.role}` + (m.brief ? ' brief' : '') });
    if (m.role === 'assistant') bubble.append(el('span', { className: 'who', textContent: settings.buddyName }));
    bubble.append(m.content);
    if (m.role === 'assistant') {
      bubble.append(el('button', { className: 'copy', textContent: 'Copiază', onclick: () => {
        navigator.clipboard.writeText(m.content);
        toast('Copiat');
      } }));
    }
    box.append(bubble);
  }
  if (typing) box.append(el('div', { className: 'msg assistant typing', textContent: `${settings.buddyName} scrie…` }));
  if (error) box.append(el('div', { className: 'msg error', textContent: '⚠️ ' + error }));
  box.scrollTop = box.scrollHeight;
}

function renderModelChip() {
  const p = providers[settings.aiProvider];
  $('#aiModelChip').textContent = `${p ? p.label : settings.aiProvider} · ${settings.aiModel || 'fără model'}`;
  $('#aiModelChip').title = 'Schimbă din Setări';
}

$('#chatForm').addEventListener('submit', async e => {
  e.preventDefault();
  const input = $('#chatInput');
  const text = input.value.trim();
  if (!text) return;
  input.value = '';
  $('#chatSend').disabled = true;
  const workHistory = await api.ai.history();
  renderChat([...workHistory, { role: 'user', content: text }], { typing: true });
  const res = await api.ai.send(text);
  renderChat(res.chat, { error: res.ok ? null : res.error });
  $('#chatSend').disabled = false;
  input.focus();
});
$('#chatInput').addEventListener('keydown', e => {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    $('#chatForm').requestSubmit();
  }
});
$('#aiClear').addEventListener('click', async () => renderChat(await api.ai.clear()));
$('#aiBrief').addEventListener('click', async () => {
  $('#aiBrief').disabled = true;
  const history = await api.ai.history();
  renderChat(history, { typing: true });
  const res = await api.brief.now();
  renderChat(res.chat);
  $('#aiBrief').disabled = false;
});
api.ai.onUpdated(chat => renderChat(chat));

// citire cu voce (voce românească dacă e instalată în Windows)
function speak(text) {
  if (!('speechSynthesis' in window)) return;
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(text.replace(/[•–#*]/g, ' '));
  const voices = speechSynthesis.getVoices();
  const ro = voices.filter(v => /^ro/i.test(v.lang));
  u.voice = ro.find(v => /female|ioana|carmen|alina|elena/i.test(v.name)) || ro[0] || null;
  u.lang = u.voice ? u.voice.lang : 'ro-RO';
  u.rate = 1;
  speechSynthesis.speak(u);
}
api.tts.onSpeak(speak);
$('#aiModelChip').addEventListener('click', () => showTab('settings'));

// ---------- timer & sesiuni ----------

const DAY_NAMES = ['D', 'L', 'M', 'M', 'J', 'V', 'S'];
let session = null;
let sessOffset = 0;
let workHistory = {};
let selectedDay = null;
let currentReport = null;

function fmtDur(sec) {
  sec = Math.round(sec || 0);
  const h = Math.floor(sec / 3600);
  const m = Math.floor((sec % 3600) / 60);
  if (h) return `${h}h ${String(m).padStart(2, '0')}m`;
  return `${m}m`;
}

function fmtClock(ms) {
  const t = Math.floor(ms / 1000);
  return [Math.floor(t / 3600), Math.floor((t % 3600) / 60), t % 60].map(n => String(n).padStart(2, '0')).join(':');
}

function sessElapsed() {
  if (!session) return 0;
  const now = Date.now() + sessOffset;
  const pausedNow = session.pausedAt ? now - session.pausedAt : 0;
  return Math.max(0, now - session.start - session.pausedMs - pausedNow);
}

function dayKey(d) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function setSession(s) {
  session = s;
  if (s) sessOffset = s.now - Date.now();
  $('#sessIdle').classList.toggle('hidden', !!s);
  $('#sessActive').classList.toggle('hidden', !s);
  if (s) {
    $('#sessActiveTitle').textContent = s.title;
    $('#sessToggleIcon').setAttribute('href', s.pausedAt ? '#i-play' : '#i-pause');
    $('#sessToggle span').textContent = s.pausedAt ? 'Continuă' : 'Pauză';
    $('#sessActive').classList.toggle('paused', !!s.pausedAt);
    setTimerVisible(s.timerVisible);
  }
  tickSession();
}

function setTimerVisible(v) {
  if (session) session.timerVisible = v;
  $('#sessTimerVis span').textContent = v ? 'Ascunde timerul' : 'Arată timerul';
}

function renderPomo() {
  const p = session?.pomo;
  $('#pomoBox').classList.toggle('hidden', !p);
  if (!p) return;
  const now = Date.now() + sessOffset;
  const total = (p.phase === 'focus' ? p.focusMin : (p.count % 4 === 0 ? p.longBreakMin : p.breakMin)) * 60000;
  const left = p.phaseEndsAt ? Math.max(0, p.phaseEndsAt - now) : (p.remainingMs ?? total);
  const m = Math.floor(left / 60000), sec = Math.floor((left % 60000) / 1000);
  $('#pomoTime').textContent = `${String(m).padStart(2, '0')}:${String(sec).padStart(2, '0')}`;
  $('#pomoPhase').textContent = p.phase === 'focus' ? (p.phaseEndsAt ? 'Focus' : 'În pauză') : 'Pauză';
  $('#pomoBox').classList.toggle('break', p.phase === 'break');
  $('#pomoFill').style.strokeDashoffset = (326.7 * (1 - left / total)).toFixed(1);
  const rounds = Math.max(4, Math.ceil((p.count + 1) / 4) * 4);
  $('#pomoDots').replaceChildren(...[...Array(rounds)].map((_, i) => el('i', { className: i < p.count ? 'on' : '' })));
  $('#pomoNext').textContent = `${p.label} · ${p.focusMin}/${p.breakMin} min · ${p.count} ${p.count === 1 ? 'rundă' : 'runde'}`;
}

function tickSession() {
  renderPomo();
  if (!session) return;
  $('#sessElapsed').textContent = fmtClock(sessElapsed());
  $('#sessMeta').textContent = (session.pausedAt ? 'În pauză · ' : 'Început la ') +
    new Date(session.start).toLocaleTimeString('ro-RO', { hour: '2-digit', minute: '2-digit' });
}

function renderReport(rep) {
  currentReport = rep;
  const box = $('#sessReport');
  box.classList.toggle('hidden', !rep);
  if (!rep) return;
  const apps = rep.apps.length
    ? rep.apps.map(a => el('div', { className: 'app-row' }, [
        el('span', { textContent: a.name }),
        el('span', { className: 'muted', textContent: `${fmtDur(a.sec)} · ${a.pct}%` }),
        el('div', { className: 'bar' }, [el('i', { style: `width:${a.pct}%` })])
      ]))
    : [el('p', { className: 'muted', textContent: 'Nu am detectat aplicații (sesiune scurtă sau urmărirea e oprită).' })];
  const fb = el('div', { className: 'feedback' + (rep.feedback ? '' : ' hidden'), textContent: rep.feedback });
  const fbBtn = el('button', { className: 'btn', textContent: rep.feedback ? 'Feedback nou' : `Feedback de la ${settings.buddyName}` });
  fbBtn.prepend(icon('spark'));
  fbBtn.onclick = async () => {
    fbBtn.disabled = true;
    fb.classList.remove('hidden');
    fb.textContent = `${settings.buddyName} analizează…`;
    const res = await api.session.feedback(rep.id);
    fb.textContent = res.ok ? res.text : '⚠ ' + res.error;
    if (res.ok) rep.feedback = res.text;
    fbBtn.disabled = false;
  };
  box.replaceChildren(
    el('div', { className: 'kicker', textContent: 'Raport sesiune' }),
    el('div', { className: 'sess-title', textContent: rep.title }),
    el('div', { className: 'muted', textContent: `${new Date(rep.start).toLocaleString('ro-RO', { dateStyle: 'medium', timeStyle: 'short' })} – ${new Date(rep.end).toLocaleTimeString('ro-RO', { hour: '2-digit', minute: '2-digit' })}` }),
    el('div', { className: 'stats' }, [
      el('div', { className: 'stat' }, [el('b', { textContent: fmtDur(rep.durationSec) }), el('span', { textContent: 'Total' })]),
      el('div', { className: 'stat' }, [el('b', { textContent: fmtDur(rep.activeSec) }), el('span', { textContent: 'Activ' })]),
      el('div', { className: 'stat' }, [el('b', { textContent: fmtDur(rep.idleSec) }), el('span', { textContent: 'Inactiv' })])
    ]),
    el('div', { className: 'kicker', textContent: 'Aplicații folosite' }),
    el('div', { className: 'apps' }, apps),
    fb,
    el('div', { className: 'row' }, [
      fbBtn,
      el('button', { className: 'btn ghost', textContent: 'Închide', onclick: () => renderReport(null) })
    ])
  );
}

async function loadHistory() {
  workHistory = await api.session.history();
  renderWeek();
  renderCalendar();
  if (selectedDay) renderDay(selectedDay);
}

function renderWeek() {
  const today = new Date();
  const monday = new Date(today.getFullYear(), today.getMonth(), today.getDate() - ((today.getDay() + 6) % 7));
  const days = [...Array(7)].map((_, i) => new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() + i));
  const secs = days.map(d => workHistory[dayKey(d)]?.totalSec || 0);
  const lastWeek = [...Array(7)].reduce((sum, _, i) =>
    sum + (workHistory[dayKey(new Date(monday.getFullYear(), monday.getMonth(), monday.getDate() - 7 + i))]?.totalSec || 0), 0);
  const total = secs.reduce((a, b) => a + b, 0);
  const max = Math.max(4 * 3600, ...secs);
  const delta = total - lastWeek;
  $('#weekSum').replaceChildren(
    el('b', { textContent: fmtDur(total) }),
    ` săptămâna aceasta · ${fmtDur(lastWeek)} săptămâna trecută` +
      (lastWeek ? ` (${delta >= 0 ? '+' : '−'}${fmtDur(Math.abs(delta))})` : '')
  );
  const goalH = Number(settings.weeklyGoalHours) || 0;
  $('#weekGoal').classList.toggle('hidden', !goalH);
  if (goalH) {
    const pct = Math.round((total / (goalH * 3600)) * 100);
    $('#weekGoalFill').style.width = Math.min(100, pct) + '%';
    $('#weekGoalText').textContent = `Obiectiv: ${goalH}h · ${pct}% atins` + (pct >= 100 ? ' — bravo!' : '');
  }
  $('#weekBars').replaceChildren(...days.map((d, i) => el('div', {
    className: 'b' + (dayKey(d) === dayKey(today) ? ' today' : ''),
    title: `${d.toLocaleDateString('ro-RO', { weekday: 'long', day: 'numeric', month: 'short' })}: ${fmtDur(secs[i])}`
  }, [
    el('em', { textContent: secs[i] ? (secs[i] / 3600).toFixed(1) : '' }),
    el('i', { style: `height:${Math.round((secs[i] / max) * 70)}%` }),
    el('span', { textContent: DAY_NAMES[d.getDay()] })
  ])));
}

function renderCalendar() {
  const today = new Date();
  const first = new Date(today.getFullYear(), today.getMonth(), today.getDate() - 29);
  const cells = [];
  for (let i = 0; i < (first.getDay() + 6) % 7; i++) cells.push(el('div', { className: 'day blank' }));
  const max = Math.max(6 * 3600, ...Object.values(workHistory).map(d => d.totalSec));
  for (let i = 0; i < 30; i++) {
    const d = new Date(first.getFullYear(), first.getMonth(), first.getDate() + i);
    const key = dayKey(d);
    const info = workHistory[key];
    const lvl = info ? Math.min(1, info.totalSec / max) : 0;
    const cell = el('div', {
      className: 'day' + (key === dayKey(today) ? ' today' : '') + (key === selectedDay ? ' sel' : '') + (lvl > 0.55 ? ' dark' : ''),
      title: d.toLocaleDateString('ro-RO', { weekday: 'long', day: 'numeric', month: 'long' }) + (info ? ` · ${fmtDur(info.totalSec)}` : ''),
      onclick: () => renderDay(key)
    }, [
      el('span', { textContent: d.getDate() }),
      el('small', { textContent: info ? (info.totalSec / 3600).toFixed(1) + 'h' : '' })
    ]);
    cell.style.setProperty('--lvl', lvl.toFixed(2));
    cells.push(cell);
  }
  $('#calendar').replaceChildren(...cells);
}

function renderDay(key) {
  selectedDay = key;
  document.querySelectorAll('.day').forEach(c => c.classList.remove('sel'));
  renderCalendar();
  const info = workHistory[key];
  const [y, m, d] = key.split('-').map(Number);
  const date = new Date(y, m - 1, d);
  const box = $('#dayDetail');
  box.classList.remove('hidden');
  const head = [
    el('div', { className: 'kicker', textContent: date.toLocaleDateString('ro-RO', { weekday: 'long', day: 'numeric', month: 'long' }) })
  ];
  if (!info) {
    box.replaceChildren(...head, el('p', { className: 'muted', textContent: 'Nicio sesiune în această zi.' }));
    return;
  }
  box.replaceChildren(
    ...head,
    el('div', { className: 'stats' }, [
      el('div', { className: 'stat' }, [el('b', { textContent: fmtDur(info.totalSec) }), el('span', { textContent: 'Lucru' })]),
      el('div', { className: 'stat' }, [el('b', { textContent: fmtDur(info.activeSec) }), el('span', { textContent: 'Activ' })]),
      el('div', { className: 'stat' }, [el('b', { textContent: info.sessions.length }), el('span', { textContent: 'Sesiuni' })])
    ]),
    el('div', { className: 'kicker', textContent: 'Sesiuni' }),
    el('div', { className: 'sess-list' }, info.sessions.map(s => el('button', {
      onclick: async () => { renderReport(await api.session.report(s.id)); $('#tab-timer .scroll').scrollTop = 0; }
    }, [
      el('span', { textContent: `${new Date(s.start).toLocaleTimeString('ro-RO', { hour: '2-digit', minute: '2-digit' })} · ${s.title}` }),
      el('span', { className: 'muted', textContent: fmtDur(s.durationSec) })
    ]))),
    el('div', { className: 'kicker', textContent: 'Cele mai folosite aplicații' }),
    el('div', { className: 'apps' }, info.topApps.length ? info.topApps.map(a => el('div', { className: 'app-row' }, [
      el('span', { textContent: a.name }),
      el('span', { className: 'muted', textContent: `${fmtDur(a.sec)} · ${a.pct}%` }),
      el('div', { className: 'bar' }, [el('i', { style: `width:${a.pct}%` })])
    ])) : [el('p', { className: 'muted', textContent: '—' })])
  );
}

let focusMode = '';
$('#sessModes').addEventListener('click', e => {
  const b = e.target.closest('button');
  if (!b) return;
  focusMode = b.dataset.mode;
  $('#sessModes').querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b));
});
$('#sessStart').addEventListener('click', async () => {
  setSession(await api.session.start($('#sessTitle').value, focusMode || undefined));
  $('#sessTitle').value = '';
  renderReport(null);
});
$('#sessTitle').addEventListener('keydown', e => { if (e.key === 'Enter') $('#sessStart').click(); });
$('#sessToggle').addEventListener('click', async () => {
  setSession(session?.pausedAt ? await api.session.resume() : await api.session.pause());
});
$('#sessStop').addEventListener('click', () => api.session.stop());
$('#sessTimerVis').addEventListener('click', () => (session?.timerVisible ? api.timer.hide() : api.timer.show()));
api.session.onChange(setSession);
api.session.onEnded(rep => { renderReport(rep); loadHistory(); showTab('timer'); $('#tab-timer .scroll').scrollTop = 0; });
api.session.onPhase(({ phase }) => toast(phase === 'break' ? 'Pauză! Ridică-te și respiră.' : 'Înapoi la focus'));
api.session.onHour(({ hours }) => toast(hours === 1 ? '1 Hour has passed' : `${hours} Hours have passed`));
api.timer.onVisible(setTimerVisible);
setInterval(tickSession, 500);

// ---------- inbox ----------

let mails = [];

function mailConfigured() {
  return !!(settings.mailAddress && settings.hasMailPassword);
}

function renderMailSetup() {
  $('#mailSetup').classList.toggle('hidden', mailConfigured());
  if (!mailConfigured()) $('#mailStatus').textContent = 'Inbox neconfigurat';
}

function fmtMailDate(ts) {
  const d = new Date(ts);
  const today = new Date();
  return dayKey(d) === dayKey(today)
    ? d.toLocaleTimeString('ro-RO', { hour: '2-digit', minute: '2-digit' })
    : d.toLocaleDateString('ro-RO', { day: 'numeric', month: 'short' });
}

function renderMails() {
  const list = $('#mailList');
  list.replaceChildren(...mails.map(m => {
    const summary = el('div', { className: 'summary hidden' });
    const btn = el('button', { className: 'btn small ghost', textContent: 'Rezumat' });
    btn.prepend(icon('spark'));
    btn.onclick = async e => {
      e.stopPropagation();
      btn.disabled = true;
      summary.className = 'summary loading';
      summary.textContent = `${settings.buddyName} citește…`;
      const res = await api.mail.summary(m.uid);
      summary.className = 'summary' + (res.ok ? '' : ' error');
      summary.textContent = res.ok ? res.text : res.error;
      btn.disabled = false;
    };
    return el('li', { className: 'item mail' + (m.unread ? ' unread' : '') }, [
      el('div', { className: 'top' }, [
        el('span', { className: 'from', textContent: m.from, title: m.fromAddress }),
        el('span', { className: 'date', textContent: fmtMailDate(m.date) })
      ]),
      el('div', { className: 'subj', textContent: m.subject }),
      el('div', { className: 'snippet', textContent: m.snippet }),
      summary,
      el('div', { className: 'meta row' }, [btn])
    ]);
  }));
  $('#mailEmpty').classList.toggle('hidden', mails.length > 0 || !mailConfigured());
}

async function refreshMail() {
  renderMailSetup();
  if (!mailConfigured()) return;
  $('#mailRefresh').disabled = true;
  $('#mailStatus').textContent = 'Se încarcă emailurile…';
  const res = await api.mail.fetch();
  mails = res.messages;
  const unread = mails.filter(m => m.unread).length;
  $('#mailStatus').textContent = res.ok
    ? `${mails.length} emailuri · ${unread} necitite · ${new Date().toLocaleTimeString('ro-RO', { hour: '2-digit', minute: '2-digit' })}`
    : '⚠ ' + res.error;
  $('#mailStatus').title = $('#mailStatus').textContent;
  renderMails();
  $('#mailRefresh').disabled = false;
}

function fmtTime(ts) {
  return new Date(ts).toLocaleTimeString('ro-RO', { hour: '2-digit', minute: '2-digit' });
}

function renderScan(st) {
  const box = $('#scanBox');
  box.classList.toggle('hidden', !st.configured);
  if (!st.configured) return;
  const last = st.last;
  box.classList.toggle('error', !!last?.error);
  $('#scanNow').disabled = st.running;
  $('#scanTitle').textContent = settings.mailAutoScan ? 'Scanare automată' : 'Scanare (automată oprită)';
  if (st.running) {
    $('#scanCount').textContent = `${settings.buddyName} verifică inboxul…`;
  } else if (!last) {
    $('#scanCount').textContent = 'Încă nu am scanat inboxul azi.';
  } else if (last.error) {
    $('#scanCount').textContent = '⚠ ' + last.error;
  } else {
    const n = last.count;
    $('#scanCount').replaceChildren(el('b', { textContent: n }), ` ${n === 1 ? 'email necitit primit' : 'emailuri necitite primite'} azi`);
  }
  $('#scanMeta').textContent = [
    last ? `Ultima scanare: ${fmtTime(last.at)}` : '',
    st.next ? `următoarea: ${fmtTime(st.next)}` : ''
  ].filter(Boolean).join(' · ');
  const sum = $('#scanSummary');
  const text = last && !last.error ? (last.summary || (last.summaryError ? '⚠ Rezumat indisponibil: ' + last.summaryError : '')) : '';
  sum.textContent = text;
  sum.classList.toggle('hidden', !text || st.running);
}

$('#scanNow').addEventListener('click', async () => renderScan(await api.mail.scanNow()));
api.mail.onScanState(renderScan);

$('#mailRefresh').addEventListener('click', refreshMail);
$('#mailGoSettings').addEventListener('click', () => {
  showTab('settings');
  $('#sMailAddress').scrollIntoView({ block: 'center' });
});
$('#mailBrief').addEventListener('click', async () => {
  const box = $('#briefBox');
  if (!mails.length) await refreshMail();
  if (!mails.length) return toast('Nu am emailuri de analizat');
  $('#mailBrief').disabled = true;
  box.classList.remove('hidden');
  box.replaceChildren(el('div', { className: 'kicker', textContent: 'Quick brief' }),
    el('div', { className: 'summary loading', textContent: `${settings.buddyName} îți pregătește brief-ul…` }));
  const res = await api.mail.brief();
  box.replaceChildren(
    el('div', { className: 'kicker', textContent: `Quick brief · ${mails.length} emailuri` }),
    el('div', { className: 'feedback' + (res.ok ? '' : ' summary error'), textContent: res.ok ? res.text : res.error }),
    el('div', { className: 'row' }, [el('button', { className: 'btn small ghost', textContent: 'Închide', onclick: () => box.classList.add('hidden') })])
  );
  $('#mailBrief').disabled = false;
});

// ---------- Azi (planner) ----------

const MOODS = [['radiant', 'Radiantă'], ['bine', 'Bine'], ['ok', 'Ok'], ['obosit', 'Obosită'], ['stresat', 'Stresată']];
const WEEK_LETTERS = ['L', 'M', 'M', 'J', 'V', 'S', 'D'];
let td = null;
let tdSaveTimer = null;

function greetingLine() {
  const h = new Date().getHours();
  const g = h < 12 ? 'Bună dimineața' : h < 18 ? 'Bună ziua' : 'Bună seara';
  return settings.userName ? `${g}, ${settings.userName}.` : `${g}.`;
}

function renderToday() {
  if (!td) return;
  const day = td.day;
  $('#tdDate').textContent = new Date().toLocaleDateString('ro-RO', { weekday: 'long', day: 'numeric', month: 'long' });
  $('#tdHello').textContent = greetingLine();
  if (document.activeElement !== $('#tdIntention')) $('#tdIntention').value = day.intention;
  if (document.activeElement !== $('#tdGratitude')) $('#tdGratitude').value = day.gratitude;

  // Top 3
  const box = $('#tdTop3');
  if (!box.children.length) {
    for (let i = 0; i < 3; i++) {
      const chk = el('button', { className: 'check-round', title: 'Bifează' });
      const inp = el('input', { type: 'text', placeholder: ['Cel mai important lucru de azi', 'A doua prioritate', 'A treia prioritate'][i], maxLength: 80 });
      chk.onclick = () => {
        const top3 = td.day.top3.map((t, j) => (j === i ? { ...t, done: !t.done } : t));
        saveToday({ top3 }, true);
      };
      inp.oninput = () => {
        td.day.top3[i].text = inp.value;
        saveToday({ top3: td.day.top3 });
      };
      box.append(el('div', { className: 't' }, [el('span', { className: 'num', textContent: i + 1 }), chk, inp]));
    }
  }
  [...box.children].forEach((row, i) => {
    const t = day.top3[i];
    row.classList.toggle('done', t.done);
    row.children[1].classList.toggle('on', t.done);
    const inp = row.children[2];
    if (document.activeElement !== inp) inp.value = t.text;
  });

  // ritualuri
  const todayIdx = (new Date().getDay() + 6) % 7;
  $('#tdDays').replaceChildren(...WEEK_LETTERS.map((l, i) => el('span', { className: i === todayIdx ? 'today' : '', textContent: l })));
  $('#tdHabits').replaceChildren(...td.habits.map(hb => el('div', { className: 'habit' }, [
    el('span', { className: 'name', textContent: hb.name, title: hb.name }),
    el('span', { className: 'dots' }, hb.week.map((on, i) => el('button', {
      className: (on ? 'on' : '') + (i === todayIdx ? ' today' : '') + (i > todayIdx ? ' future' : ''),
      title: WEEK_LETTERS[i],
      disabled: i > todayIdx,
      onclick: async () => { td = await api.today.toggleHabit(hb.id, td.weekKeys[i]); renderToday(); }
    }))),
    el('span', { className: 'meta' }, [
      hb.streak > 1 ? `${hb.streak} zile` : '',
      el('button', { className: 'del', textContent: '×', title: 'Șterge ritualul', onclick: async () => {
        if (!await askConfirm(`Ștergi ritualul „${hb.name}”?`)) return;
        td = await api.today.removeHabit(hb.id);
        renderToday();
      } })
    ])
  ])));

  // apă
  $('#tdWater').replaceChildren(...[...Array(8)].map((_, i) => el('button', {
    className: i < day.water ? 'on' : '',
    title: `${i + 1} ${i ? 'pahare' : 'pahar'}`,
    onclick: () => saveToday({ water: day.water === i + 1 ? i : i + 1 }, true)
  })));
  $('#tdWaterText').textContent = `${day.water}/8 pahare`;

  // stare
  $('#tdMoods').replaceChildren(...MOODS.map(([k, label]) => el('button', {
    className: day.mood === k ? 'on' : '',
    textContent: label,
    onclick: () => saveToday({ mood: day.mood === k ? '' : k }, true)
  })));

}

// ---------- mantra zilei ----------
let mantraToday = null;
async function loadMantra() {
  mantraToday = await api.mantra.get();
  const m = mantraToday;
  $('#mLabel').textContent = m.label;
  $('#mTitle').textContent = m.title || '';
  $('#mText').textContent = m.type === 'citat' || m.type === 'vorba' ? `„${m.text}”` : m.text;
  $('#mAuthor').textContent = m.author || '';
  $('#mNote').textContent = m.note || '';
  $('#mFav').textContent = m.fav ? '♥ Favorită' : '♡';
  $('#mFav').classList.toggle('on', !!m.fav);
}
$('#mFav').addEventListener('click', async () => {
  if (!mantraToday) return;
  await api.mantra.fav(mantraToday.date, !mantraToday.fav);
  loadMantra();
});
$('#mShow').addEventListener('click', () => api.mantra.show());
$('#openVision').addEventListener('click', () => { api.vision.open(); api.panel.hide(); });

// ---------- raport lunar (rezumat în Timer) ----------
async function loadMonth() {
  const d = await api.month.data();
  $('#monthSum').replaceChildren(
    el('div', { className: 'stat' }, [el('b', { textContent: d.focus }), el('span', { textContent: 'Focus' })]),
    el('div', { className: 'stat' }, [el('b', { textContent: `${d.daysWorked}/${d.daysElapsed}` }), el('span', { textContent: 'Zile lucrate' })]),
    el('div', { className: 'stat' }, [el('b', { textContent: d.avg }), el('span', { textContent: 'Medie/zi' })]),
    el('div', { className: 'wide', textContent: [
      d.month,
      d.best ? `cea mai bună zi: ${d.best.label} (${d.best.focus})` : '',
      d.prioritiesTotal ? `priorități ${d.prioritiesDone}/${d.prioritiesTotal}` : '',
      d.pomodoros ? `${d.pomodoros} pomodoro` : ''
    ].filter(Boolean).join(' · ') })
  );
}

async function saveToday(patch, now = false) {
  Object.assign(td.day, patch);
  if (now) renderToday();
  clearTimeout(tdSaveTimer);
  const run = async () => {
    const res = await api.today.update(patch.top3 ? { ...patch, top3: td.day.top3 } : patch);
    td = { ...res, day: { ...res.day, ...pendingText() } };
    renderToday();
  };
  if (now) run();
  else tdSaveTimer = setTimeout(run, 500);
}

// păstrăm ce se scrie în timp ce salvarea e pe drum
function pendingText() {
  const out = {};
  if (document.activeElement === $('#tdIntention')) out.intention = $('#tdIntention').value;
  if (document.activeElement === $('#tdGratitude')) out.gratitude = $('#tdGratitude').value;
  return out;
}

async function loadToday() {
  td = await api.today.state();
  renderToday();
}

$('#tdIntention').addEventListener('input', e => saveToday({ intention: e.target.value }));
$('#tdGratitude').addEventListener('input', e => saveToday({ gratitude: e.target.value }));
$('#tdHabitForm').addEventListener('submit', async e => {
  e.preventDefault();
  const name = $('#tdHabitName').value.trim();
  if (!name) return;
  td = await api.today.addHabit(name);
  $('#tdHabitName').value = '';
  renderToday();
});

// carduri
function segValue(id) { return $(`#${id} button.on`).dataset.v; }
document.querySelectorAll('.seg').forEach(seg => seg.addEventListener('click', e => {
  const b = e.target.closest('button');
  if (!b) return;
  seg.querySelectorAll('button').forEach(x => x.classList.toggle('on', x === b));
}));
$('#cardMake').addEventListener('click', async () => {
  $('#cardMake').disabled = true;
  $('#cardMake').lastChild.textContent = 'Se creează…';
  const res = await api.card.make(segValue('cardKind'), segValue('cardFormat'));
  $('#cardMake').disabled = false;
  $('#cardMake').lastChild.textContent = 'Creează cardul';
  if (!res.ok) return toast('⚠ ' + res.error);
  $('#cardPreview').classList.remove('hidden');
  $('#cardImg').src = res.dataUrl;
  $('#cardPath').textContent = res.file;
  toast('Cardul e gata');
});
$('#cardCopy').addEventListener('click', async () => { if (await api.card.copy()) toast('Imaginea e în clipboard. Lipește-o în Instagram sau WhatsApp.'); });
$('#cardShow').addEventListener('click', () => api.card.show());

// ---------- sunete de focus (generate, fără fișiere audio) ----------

const sound = { ctx: null, master: null, nodes: [], current: '' };

function noiseBuffer(ctx, kind, seconds = 4) {
  const len = ctx.sampleRate * seconds;
  const buf = ctx.createBuffer(2, len, ctx.sampleRate);
  for (let ch = 0; ch < 2; ch++) {
    const d = buf.getChannelData(ch);
    let last = 0, b0 = 0, b1 = 0, b2 = 0, b3 = 0, b4 = 0, b5 = 0, b6 = 0;
    for (let i = 0; i < len; i++) {
      const w = Math.random() * 2 - 1;
      if (kind === 'brown') {
        last = (last + 0.02 * w) / 1.02;
        d[i] = last * 3.5;
      } else if (kind === 'pink') {
        b0 = 0.99886 * b0 + w * 0.0555179; b1 = 0.99332 * b1 + w * 0.0750759; b2 = 0.969 * b2 + w * 0.153852;
        b3 = 0.8665 * b3 + w * 0.3104856; b4 = 0.55 * b4 + w * 0.5329522; b5 = -0.7616 * b5 - w * 0.016898;
        d[i] = (b0 + b1 + b2 + b3 + b4 + b5 + b6 + w * 0.5362) * 0.11;
        b6 = w * 0.115926;
      } else if (kind === 'crackle') {
        d[i] = Math.random() < 0.0004 ? (Math.random() * 2 - 1) * 0.9 : d[i - 1] * 0.86 || 0;
      }
    }
  }
  return buf;
}

function loop(buf) {
  const src = sound.ctx.createBufferSource();
  src.buffer = buf;
  src.loop = true;
  src.start();
  sound.nodes.push(src);
  return src;
}

function filter(type, freq, q = 0.7) {
  const f = sound.ctx.createBiquadFilter();
  f.type = type;
  f.frequency.value = freq;
  f.Q.value = q;
  return f;
}

function stopSound() {
  sound.nodes.forEach(n => { try { n.stop ? n.stop() : n.disconnect(); } catch {} });
  sound.nodes = [];
  sound.current = '';
}

function playSound(kind) {
  if (!sound.ctx) {
    sound.ctx = new AudioContext();
    sound.master = sound.ctx.createGain();
    sound.master.connect(sound.ctx.destination);
  }
  stopSound();
  const ctx = sound.ctx;
  sound.master.gain.value = Number($('#soundVol').value);
  const out = ctx.createGain();
  out.connect(sound.master);
  sound.nodes.push(out);
  if (kind === 'rain') {
    const hp = filter('highpass', 400), lp = filter('lowpass', 6500);
    loop(noiseBuffer(ctx, 'pink')).connect(hp); hp.connect(lp); lp.connect(out);
    const g = ctx.createGain(); g.gain.value = 0.35;
    const drops = filter('bandpass', 2500, 1.2);
    loop(noiseBuffer(ctx, 'crackle', 3)).connect(drops); drops.connect(g); g.connect(out);
    out.gain.value = 0.9;
  } else if (kind === 'brown') {
    const lp = filter('lowpass', 900);
    loop(noiseBuffer(ctx, 'brown')).connect(lp); lp.connect(out);
    out.gain.value = 0.9;
  } else if (kind === 'ocean') {
    const lp = filter('lowpass', 650);
    const waveGain = ctx.createGain(); waveGain.gain.value = 0.55;
    loop(noiseBuffer(ctx, 'brown', 6)).connect(lp); lp.connect(waveGain); waveGain.connect(out);
    const lfo = ctx.createOscillator(); lfo.frequency.value = 0.09;
    const depth = ctx.createGain(); depth.gain.value = 0.45;
    lfo.connect(depth); depth.connect(waveGain.gain); lfo.start();
    sound.nodes.push(lfo);
    out.gain.value = 1;
  } else if (kind === 'fire') {
    const lp = filter('lowpass', 500);
    const base = ctx.createGain(); base.gain.value = 0.5;
    loop(noiseBuffer(ctx, 'brown')).connect(lp); lp.connect(base); base.connect(out);
    const crack = filter('highpass', 1200);
    const cg = ctx.createGain(); cg.gain.value = 0.8;
    loop(noiseBuffer(ctx, 'crackle', 5)).connect(crack); crack.connect(cg); cg.connect(out);
    out.gain.value = 0.9;
  }
  sound.current = kind;
}

$('#soundList').addEventListener('click', e => {
  const b = e.target.closest('button');
  if (!b) return;
  const kind = b.dataset.sound;
  if (sound.current === kind) stopSound();
  else playSound(kind);
  document.querySelectorAll('#soundList button').forEach(x => x.classList.toggle('on', x.dataset.sound === sound.current));
});
$('#soundVol').addEventListener('input', e => { if (sound.master) sound.master.gain.value = Number(e.target.value); });

// ---------- ghid de bun venit ----------

let obStep = 0;
function showOnboarding() {
  obStep = 0;
  $('#obName').value = settings.userName || '';
  $('#obGoal').value = settings.weeklyGoalHours ?? 40;
  $('#obBrief').checked = settings.morningBrief;
  $('#obSpeech').checked = settings.buddySpeech;
  renderOb();
  $('#onboard').classList.remove('hidden');
  setTimeout(() => $('#obName').focus(), 100);
}
function renderOb() {
  document.querySelectorAll('.ob-step').forEach(s => s.classList.toggle('hidden', Number(s.dataset.step) !== obStep));
  document.querySelectorAll('#obDots i').forEach((d, i) => d.classList.toggle('on', i === obStep));
  $('#obNext').textContent = obStep === 2 ? 'Începem' : 'Continuă';
}
async function finishOnboarding() {
  settings = await api.onboarding.done({
    userName: $('#obName').value.trim(),
    weeklyGoalHours: Math.max(0, Math.min(100, Number($('#obGoal').value) || 0)),
    morningBrief: $('#obBrief').checked,
    buddySpeech: $('#obSpeech').checked
  });
  $('#onboard').classList.add('hidden');
  renderSettings();
  renderToday();
}
$('#obNext').addEventListener('click', () => {
  if (obStep < 2) { obStep++; renderOb(); } else finishOnboarding();
});
$('#obSkip').addEventListener('click', finishOnboarding);
$('#obName').addEventListener('keydown', e => { if (e.key === 'Enter') $('#obNext').click(); });
api.onboarding.onShow(showOnboarding);

// ---------- setări ----------

function fillProviderSelect() {
  const sel = $('#sProvider');
  sel.replaceChildren(...Object.entries(providers).map(([id, p]) => el('option', { value: id, textContent: p.label })));
}

function fillModelSelect() {
  const models = providers[settings.aiProvider]?.models || [];
  const sel = $('#sModelSelect');
  sel.replaceChildren(
    ...models.map(m => el('option', { value: m, textContent: m })),
    el('option', { value: CUSTOM_MODEL, textContent: 'Alt model (scriu eu)…' })
  );
  const isPreset = models.includes(settings.aiModel);
  sel.value = isPreset ? settings.aiModel : CUSTOM_MODEL;
  $('#sModel').value = settings.aiModel || '';
  $('#sModel').classList.toggle('hidden', isPreset);
  sel.classList.toggle('hidden', models.length === 0);
}

function renderSettings() {
  document.documentElement.dataset.theme = settings.themeResolved || settings.theme;
  $('#title').textContent = settings.buddyName;
  $('#sProvider').value = settings.aiProvider;
  fillModelSelect();
  $('#sBaseUrl').value = settings.aiBaseUrl || '';
  $('#baseUrlRow').classList.toggle('hidden', settings.aiProvider !== 'custom');
  $('#sApiKeyStatus').textContent = settings.hasApiKey ? 'Cheie salvată · criptată' : 'Nicio cheie salvată';
  $('#sSystemPrompt').value = settings.aiSystemPrompt;
  $('#sMaxTokens').value = settings.aiMaxTokens;
  $('#sName').value = settings.buddyName;
  if (document.activeElement !== $('#sUserName')) $('#sUserName').value = settings.userName || '';
  $('#sScale').value = settings.buddyScale;
  $('#sScaleVal').textContent = `${Math.round(settings.buddyScale * 100)}%`;
  $('#sOnTop').checked = settings.alwaysOnTop;
  $('#sStartup').checked = settings.startWithWindows;
  $('#sClipEnabled').checked = settings.clipboardEnabled;
  $('#sClipLimit').value = settings.clipboardLimit;
  $('#sTheme').value = settings.theme;
  $('#sHideOnBlur').checked = settings.hidePanelOnBlur;
  $('#sHourly').checked = settings.timerHourlyReminder;
  $('#sWeeklyGoal').value = settings.weeklyGoalHours ?? 40;
  $('#sSpeech').checked = settings.buddySpeech;
  $('#sSpontaneous').checked = settings.buddySpontaneous;
  $('#sMorningBrief').checked = settings.morningBrief;
  $('#sBriefVoice').checked = settings.briefVoice;
  $('#sMantraStart').checked = settings.mantraOnStart;
  $('#sHair').value = settings.buddyHair || 'coc';
  $('#sVisionProvider').value = settings.visionProvider || 'openverse';
  const vp = settings.visionProvider || 'openverse';
  $('#visionKeyRow').classList.toggle('hidden', vp === 'openverse');
  $('#visionCxRow').classList.toggle('hidden', vp !== 'google');
  if (document.activeElement !== $('#sVisionCx')) $('#sVisionCx').value = settings.visionGoogleCx || '';
  $('#sVisionKeyStatus').textContent = settings.hasVisionKey ? 'Cheie salvată · criptată' : 'Nicio cheie salvată';
  $('#visionHint').replaceChildren(...({
    openverse: ['Imagini cu licențe Creative Commons; autorul apare sub fiecare fotografie.'],
    pexels: ['Cheie gratuită în 1 minut: ', el('a', { href: '#', textContent: 'pexels.com/api', onclick: e => { e.preventDefault(); api.app.openExternal('https://www.pexels.com/api/'); } }), '.'],
    google: ['Cheie API Google Cloud (Custom Search JSON API) și un motor de căutare cu „Căutare de imagini” activă: ', el('a', { href: '#', textContent: 'programmablesearchengine.google.com', onclick: e => { e.preventDefault(); api.app.openExternal('https://programmablesearchengine.google.com/'); } }), '. Fără cheie, butonul G de pe fiecare poză deschide Google Imagini în browser.'],
    unsplash: ['Cheie gratuită („Access Key”): ', el('a', { href: '#', textContent: 'unsplash.com/developers', onclick: e => { e.preventDefault(); api.app.openExternal('https://unsplash.com/developers'); } }), '.']
  })[vp]);
  $('#sMantraSec').value = settings.mantraSeconds || 30;
  if (document.activeElement !== $('#sHotkey')) $('#sHotkey').value = settings.quickHotkey || '';
  $('#sHotkeyStatus').textContent = settings.hotkeyActive
    ? `Activă: ${settings.hotkeyLabel}`
    : 'Inactivă (scurtătura e folosită de alt program sau nu e validă)';
  $('#sTrackApps').checked = settings.timerTrackApps;
  $('#sMailAddress').value = settings.mailAddress || '';
  $('#sMailHost').value = settings.mailHost || '';
  $('#sMailPort').value = settings.mailPort || 993;
  $('#sMailCount').value = settings.mailCount || 15;
  $('#sMailUnread').checked = settings.mailUnreadOnly;
  $('#sMailAutoScan').checked = settings.mailAutoScan;
  $('#sMailScanMinutes').value = String(settings.mailScanMinutes || 60);
  $('#sMailNotifyEmpty').checked = settings.mailNotifyEmpty;
  $('#sMailPassStatus').textContent = settings.hasMailPassword ? 'Parolă salvată · criptată' : 'Nicio parolă salvată';
  renderMailSetup();
  renderModelChip();
}

async function update(patch, msg = 'Setare salvată') {
  const res = await api.settings.set(patch);
  const { error, ...rest } = res;
  settings = rest;
  renderSettings();
  toast(error || msg);
}

$('#sProvider').addEventListener('change', e => {
  const id = e.target.value;
  update({ aiProvider: id, aiModel: providers[id]?.models[0] || '' });
});
$('#sModelSelect').addEventListener('change', e => {
  if (e.target.value === CUSTOM_MODEL) {
    $('#sModel').classList.remove('hidden');
    $('#sModel').focus();
  } else {
    update({ aiModel: e.target.value });
  }
});
$('#sModel').addEventListener('change', e => update({ aiModel: e.target.value.trim() }));
$('#sBaseUrl').addEventListener('change', e => update({ aiBaseUrl: e.target.value.trim() }));
$('#sSystemPrompt').addEventListener('change', e => update({ aiSystemPrompt: e.target.value }));
$('#sMaxTokens').addEventListener('change', e => update({ aiMaxTokens: Number(e.target.value) || 1024 }));

$('#sApiKeyToggle').addEventListener('click', () => {
  const i = $('#sApiKey');
  i.type = i.type === 'password' ? 'text' : 'password';
});
$('#sApiKeySave').addEventListener('click', async () => {
  const key = $('#sApiKey').value.trim();
  if (!key) return toast('Lipește întâi cheia');
  settings = await api.settings.setApiKey(key);
  $('#sApiKey').value = '';
  renderSettings();
  toast('Cheia API a fost salvată');
});
$('#sApiKeyDelete').addEventListener('click', async () => {
  if (!await askConfirm('Ștergi cheia API salvată?')) return;
  settings = await api.settings.setApiKey('');
  renderSettings();
  toast('Cheia API a fost ștearsă');
});

$('#sUserName').addEventListener('change', e => update({ userName: e.target.value.trim() }).then(renderToday));
$('#sGuide').addEventListener('click', showOnboarding);
$('#sName').addEventListener('change', e => update({ buddyName: e.target.value.trim() || 'Mady' }));
$('#sScale').addEventListener('input', e => { $('#sScaleVal').textContent = `${Math.round(e.target.value * 100)}%`; });
$('#sScale').addEventListener('change', e => update({ buddyScale: Number(e.target.value) }));
$('#sOnTop').addEventListener('change', e => update({ alwaysOnTop: e.target.checked }));
$('#sStartup').addEventListener('change', e => update({ startWithWindows: e.target.checked }));
$('#sClipEnabled').addEventListener('change', e => update({ clipboardEnabled: e.target.checked }));
$('#sClipLimit').addEventListener('change', e => update({ clipboardLimit: Number(e.target.value) || 50 }));
$('#sTheme').addEventListener('change', e => update({ theme: e.target.value }));
$('#sHideOnBlur').addEventListener('change', e => update({ hidePanelOnBlur: e.target.checked }));
$('#sReset').addEventListener('click', async () => {
  if (!await askConfirm('Resetezi toate setările la valorile implicite? (cheia API rămâne)', 'Da, resetează')) return;
  settings = await api.settings.reset();
  renderSettings();
  toast('Setări resetate');
});
$('#sQuit').addEventListener('click', () => api.app.quit());
$('#sHourly').addEventListener('change', e => update({ timerHourlyReminder: e.target.checked }));
$('#sWeeklyGoal').addEventListener('change', e => { update({ weeklyGoalHours: Math.max(0, Math.min(100, Number(e.target.value) || 0)) }).then(loadHistory); });
$('#sSpeech').addEventListener('change', e => update({ buddySpeech: e.target.checked }));
$('#sSpontaneous').addEventListener('change', e => update({ buddySpontaneous: e.target.checked }));
$('#sMorningBrief').addEventListener('change', e => update({ morningBrief: e.target.checked }));
$('#sBriefVoice').addEventListener('change', e => update({ briefVoice: e.target.checked }));
$('#sHair').addEventListener('change', e => update({ buddyHair: e.target.value }));
$('#sVisionCx').addEventListener('change', e => update({ visionGoogleCx: e.target.value.trim() }));
$('#sVisionProvider').addEventListener('change', e => update({ visionProvider: e.target.value }));
$('#sVisionKeySave').addEventListener('click', async () => {
  const k = $('#sVisionKey').value.trim();
  if (!k) return toast('Lipește întâi cheia');
  settings = await api.vision.setKey(k);
  $('#sVisionKey').value = '';
  renderSettings();
  toast('Cheia pentru imagini a fost salvată');
});
$('#sMantraStart').addEventListener('change', e => update({ mantraOnStart: e.target.checked }));
$('#sMantraSec').addEventListener('change', e => update({ mantraSeconds: Math.max(5, Math.min(300, Number(e.target.value) || 30)) }));
$('#sHotkeySave').addEventListener('click', () => update({ quickHotkey: $('#sHotkey').value.trim() }, 'Scurtătură activă'));
$('#sTrackApps').addEventListener('change', e => update({ timerTrackApps: e.target.checked }));
$('#sMailAddress').addEventListener('change', e => update({ mailAddress: e.target.value.trim() }));
$('#sMailHost').addEventListener('change', e => update({ mailHost: e.target.value.trim() || 'imap.gmail.com' }));
$('#sMailPort').addEventListener('change', e => update({ mailPort: Number(e.target.value) || 993 }));
$('#sMailCount').addEventListener('change', e => update({ mailCount: Math.min(50, Math.max(1, Number(e.target.value) || 15)) }));
$('#sMailUnread').addEventListener('change', e => update({ mailUnreadOnly: e.target.checked }));
$('#sMailAutoScan').addEventListener('change', e => update({ mailAutoScan: e.target.checked }));
$('#sMailScanMinutes').addEventListener('change', e => update({ mailScanMinutes: Number(e.target.value) || 60 }));
$('#sMailNotifyEmpty').addEventListener('change', e => update({ mailNotifyEmpty: e.target.checked }));
$('#sMailPassToggle').addEventListener('click', () => {
  const i = $('#sMailPass');
  i.type = i.type === 'password' ? 'text' : 'password';
});
$('#sMailPassSave').addEventListener('click', async () => {
  const pass = $('#sMailPass').value.trim();
  if (!pass) return toast('Lipește întâi parola de aplicație');
  settings = await api.mail.setPassword(pass);
  $('#sMailPass').value = '';
  renderSettings();
  toast('Parola de aplicație a fost salvată');
});
$('#sMailPassDelete').addEventListener('click', async () => {
  if (!await askConfirm('Ștergi parola de aplicație salvată?')) return;
  settings = await api.mail.setPassword('');
  renderSettings();
  toast('Parola a fost ștearsă');
});
$('#appPassLink').addEventListener('click', e => {
  e.preventDefault();
  api.app.openExternal('https://myaccount.google.com/apppasswords');
});

api.settings.onUpdate(s => { settings = s; renderSettings(); });

// ---------- inițializare ----------

(async () => {
  [settings, providers, clipItems, notes] = await Promise.all([
    api.settings.get(), api.settings.providers(), api.clipboard.list(), api.notes.list()
  ]);
  fillProviderSelect();
  renderSettings();
  renderClipboard();
  renderNotes();
  renderChat(await api.ai.history());
  setSession(await api.session.current());
  loadHistory();
  loadToday();
  loadMantra();
  loadMonth();
  setInterval(renderClipboard, 60000);
})();
