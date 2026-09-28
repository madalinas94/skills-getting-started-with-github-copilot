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

// ---------- tab-uri ----------

function showTab(name) {
  document.querySelectorAll('.tabs button').forEach(b => b.classList.toggle('active', b.dataset.tab === name));
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.id === `tab-${name}`));
  if (name === 'ai') setTimeout(() => $('#chatInput').focus(), 50);
  if (name === 'timer') loadHistory();
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
  if (!confirm('Ștergi tot istoricul clipboard (cu excepția celor fixate)?')) return;
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
    list.append(el('li', { className: 'item', onclick: () => openNote(n.id) }, [
      el('div', { className: 'title', textContent: n.title || 'Fără titlu' }),
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
$('#noteBack').addEventListener('click', closeNote);
$('#noteTitle').addEventListener('input', scheduleNoteSave);
$('#noteBody').addEventListener('input', scheduleNoteSave);
$('#noteSearch').addEventListener('input', renderNotes);
$('#noteDelete').addEventListener('click', async () => {
  if (currentNoteId) {
    if (!confirm('Ștergi această notiță?')) return;
    notes = await api.notes.remove(currentNoteId);
  }
  currentNoteId = null;
  $('#noteTitle').value = '';
  $('#noteBody').value = '';
  closeNote();
});
api.notes.onUpdate(list => { notes = list; if (!currentNoteId) renderNotes(); });

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
    const bubble = el('div', { className: `msg ${m.role}` });
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

function tickSession() {
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

$('#sessStart').addEventListener('click', async () => {
  setSession(await api.session.start($('#sessTitle').value));
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
  document.documentElement.dataset.theme = settings.theme;
  $('#title').textContent = settings.buddyName;
  $('#sProvider').value = settings.aiProvider;
  fillModelSelect();
  $('#sBaseUrl').value = settings.aiBaseUrl || '';
  $('#baseUrlRow').classList.toggle('hidden', settings.aiProvider !== 'custom');
  $('#sApiKeyStatus').textContent = settings.hasApiKey ? 'Cheie salvată · criptată' : 'Nicio cheie salvată';
  $('#sSystemPrompt').value = settings.aiSystemPrompt;
  $('#sMaxTokens').value = settings.aiMaxTokens;
  $('#sName').value = settings.buddyName;
  $('#sScale').value = settings.buddyScale;
  $('#sScaleVal').textContent = `${Math.round(settings.buddyScale * 100)}%`;
  $('#sOnTop').checked = settings.alwaysOnTop;
  $('#sStartup').checked = settings.startWithWindows;
  $('#sClipEnabled').checked = settings.clipboardEnabled;
  $('#sClipLimit').value = settings.clipboardLimit;
  $('#sTheme').value = settings.theme;
  $('#sHideOnBlur').checked = settings.hidePanelOnBlur;
  $('#sHourly').checked = settings.timerHourlyReminder;
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
  settings = await api.settings.set(patch);
  renderSettings();
  toast(msg);
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
  if (!confirm('Ștergi cheia API salvată?')) return;
  settings = await api.settings.setApiKey('');
  renderSettings();
  toast('Cheia API a fost ștearsă');
});

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
  if (!confirm('Resetezi toate setările la valorile implicite? (cheia API rămâne)')) return;
  settings = await api.settings.reset();
  renderSettings();
  toast('Setări resetate');
});
$('#sQuit').addEventListener('click', () => api.app.quit());
$('#sHourly').addEventListener('change', e => update({ timerHourlyReminder: e.target.checked }));
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
  if (!confirm('Ștergi parola de aplicație salvată?')) return;
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
  setInterval(renderClipboard, 60000);
})();
