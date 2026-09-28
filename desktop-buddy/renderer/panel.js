const api = window.buddy;
const $ = sel => document.querySelector(sel);
const CUSTOM_MODEL = '__custom__';

let settings = {};
let providers = {};
let clipItems = [];
let notes = [];
let currentNoteId = null;

// ---------- utilitare ----------

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
      el('button', { title: item.pinned ? 'Anulează fixarea' : 'Fixează', textContent: item.pinned ? '📌' : '📍', onclick: async e => {
        e.stopPropagation();
        clipItems = await api.clipboard.pin(item.id);
        renderClipboard();
      } }),
      el('button', { title: 'Salvează ca notiță', textContent: '📝', onclick: async e => {
        e.stopPropagation();
        await api.clipboard.toNote(item.id);
        toast('Salvat în notițe');
      } }),
      el('button', { title: 'Șterge', textContent: '🗑️', onclick: async e => {
        e.stopPropagation();
        clipItems = await api.clipboard.remove(item.id);
        renderClipboard();
      } })
    ]);
    list.append(el('li', {
      className: 'item' + (item.pinned ? ' pinned' : ''),
      title: 'Click pentru a copia',
      onclick: async () => { await api.clipboard.copy(item.id); toast('Copiat în clipboard ✓'); }
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
  $('#noteStatus').textContent = 'Salvat ✓';
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
    box.append(el('div', { className: 'msg assistant', textContent: `Bună! Sunt ${settings.buddyName} 💕 Cu ce te pot ajuta?` }));
  }
  for (const m of chat) {
    const bubble = el('div', { className: `msg ${m.role}`, textContent: m.content });
    if (m.role === 'assistant') {
      bubble.append(el('button', { className: 'copy', textContent: 'Copiază', onclick: () => {
        navigator.clipboard.writeText(m.content);
        toast('Copiat ✓');
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
  const history = await api.ai.history();
  renderChat([...history, { role: 'user', content: text }], { typing: true });
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
  $('#sApiKeyStatus').textContent = settings.hasApiKey ? '🔒 Cheie salvată (criptată)' : 'Nicio cheie salvată';
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
  renderModelChip();
}

async function update(patch, msg = 'Setare salvată ✓') {
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
  toast('Cheia API a fost salvată 🔒');
});
$('#sApiKeyDelete').addEventListener('click', async () => {
  if (!confirm('Ștergi cheia API salvată?')) return;
  settings = await api.settings.setApiKey('');
  renderSettings();
  toast('Cheia API a fost ștearsă');
});

$('#sName').addEventListener('change', e => update({ buddyName: e.target.value.trim() || 'Robi' }));
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
  setInterval(renderClipboard, 60000);
})();
