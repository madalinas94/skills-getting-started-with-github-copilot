const api = window.buddy;
const $ = sel => document.querySelector(sel);
const id = api.sticky.id();
const COLORS = ['ivory', 'blush', 'sage', 'champagne', 'powder', 'noir', 'bordeaux'];
const DECOS = [['tape', 'Bandă'], ['pin', 'Pioneză'], ['clip', 'Agrafă'], ['none', 'Simplu']];
let note = null;
let saveTimer = null;

function applyStyle() {
  const st = note.sticky || {};
  $('#paper').dataset.color = st.color || 'ivory';
  $('#paper').dataset.deco = st.deco || 'tape';
  $('#btnTop').classList.toggle('on', !!st.onTop);
  $('#btnTop').title = st.onTop ? 'Nu mai sta deasupra' : 'Mereu deasupra';
  $('#paper').classList.toggle('collapsed', !!st.collapsed);
  $('#collapseIcon').setAttribute('href', st.collapsed ? '#i-max' : '#i-min');
  document.querySelectorAll('.swatches button').forEach(b => b.classList.toggle('sel', b.dataset.color === st.color));
  document.querySelectorAll('.decos button').forEach(b => b.classList.toggle('sel', b.dataset.deco === st.deco));
}

function applyText() {
  if (document.activeElement !== $('#title')) $('#title').value = note.title;
  if (document.activeElement !== $('#body')) $('#body').value = note.body;
  $('#date').textContent = new Date(note.updatedAt || Date.now()).toLocaleDateString('ro-RO', { day: 'numeric', month: 'short' });
  document.title = note.title || 'Notiță';
}

function scheduleSave() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(async () => {
    note = { ...note, ...(await api.notes.save({ id, title: $('#title').value, body: $('#body').value })) };
    applyText();
  }, 400);
}

$('#title').addEventListener('input', scheduleSave);
$('#body').addEventListener('input', scheduleSave);
$('#title').addEventListener('keydown', e => { if (e.key === 'Enter') { e.preventDefault(); $('#body').focus(); } });

// meniul de stil
for (const c of COLORS) {
  const b = document.createElement('button');
  b.dataset.color = c;
  b.title = c;
  b.addEventListener('click', async () => { note = await api.sticky.style(id, { color: c }); applyStyle(); });
  $('#swatches').append(b);
}
for (const [d, label] of DECOS) {
  const b = document.createElement('button');
  b.dataset.deco = d;
  b.textContent = label;
  b.addEventListener('click', async () => { note = await api.sticky.style(id, { deco: d }); applyStyle(); });
  $('#decos').append(b);
}
// culoarea fiecărui cerc = culoarea hârtiei respective
const probe = document.createElement('div');
probe.className = 'paper';
probe.style.cssText = 'position:absolute;visibility:hidden';
document.body.append(probe);
document.querySelectorAll('.swatches button').forEach(b => {
  probe.dataset.color = b.dataset.color;
  b.style.background = getComputedStyle(probe).getPropertyValue('--paper');
});
probe.remove();

function toggleMenu(force) {
  const open = force ?? $('#popover').classList.contains('hidden');
  $('#popover').classList.toggle('hidden', !open);
  $('#paper').classList.toggle('menu', open);
}
$('#btnStyle').addEventListener('click', e => { e.stopPropagation(); toggleMenu(); });
document.addEventListener('click', e => { if (!$('#popover').contains(e.target)) toggleMenu(false); });

$('#btnTop').addEventListener('click', async () => { note = await api.sticky.style(id, { onTop: !note.sticky.onTop }); applyStyle(); });
$('#btnCollapse').addEventListener('click', async () => { note = await api.sticky.collapse(id, !note.sticky.collapsed); applyStyle(); });
$('#btnClose').addEventListener('click', async () => {
  clearTimeout(saveTimer);
  await api.notes.save({ id, title: $('#title').value, body: $('#body').value });
  api.sticky.unpin(id);
});
$('#btnNew').addEventListener('click', () => api.sticky.create());
$('#btnDelete').addEventListener('click', () => {
  if (confirm('Ștergi definitiv această notiță?')) api.sticky.remove(id);
});

// redimensionare din colțul din dreapta-jos
$('#grip').addEventListener('pointerdown', e => {
  e.preventDefault();
  $('#grip').setPointerCapture(e.pointerId);
  const start = { x: e.screenX, y: e.screenY, w: window.innerWidth, h: window.innerHeight };
  const move = ev => api.sticky.resize(id, start.w + ev.screenX - start.x, start.h + ev.screenY - start.y);
  const up = () => {
    $('#grip').removeEventListener('pointermove', move);
    $('#grip').removeEventListener('pointerup', up);
    api.sticky.resized(id);
  };
  $('#grip').addEventListener('pointermove', move);
  $('#grip').addEventListener('pointerup', up);
});

api.notes.onUpdate(list => {
  const n = list.find(x => x.id === id);
  if (!n) return;
  note = n;
  applyText();
  applyStyle();
});

(async () => {
  note = await api.sticky.get(id);
  if (!note) return;
  applyText();
  applyStyle();
  if (!note.title && !note.body) $('#title').focus();
})();
