const api = window.buddy;
const $ = sel => document.querySelector(sel);
let board = null;
let titleTimer;

function icon(name) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('class', 'ic');
  const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
  use.setAttribute('href', `#i-${name}`);
  svg.append(use);
  return svg;
}
function el(tag, props = {}, children = []) {
  const n = Object.assign(document.createElement(tag), props);
  for (const c of [].concat(children)) if (c) n.append(c);
  return n;
}
let toastTimer;
function toast(t) {
  $('#toast').textContent = t;
  $('#toast').classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => $('#toast').classList.remove('show'), 2200);
}

function autoGrow(t) { t.style.height = 'auto'; t.style.height = t.scrollHeight + 'px'; }

function ops(item) {
  const box = el('div', { className: 'ops' }, [
    el('button', { title: 'Mută mai devreme', onclick: async () => set(await api.vision.move(item.id, -1)) }, [icon('left')]),
    el('button', { title: 'Mută mai târziu', onclick: async () => set(await api.vision.move(item.id, 1)) }, [icon('right')])
  ]);
  if (item.type === 'text') {
    for (const [st, c] of [['noir', '#1f3a2e'], ['blush', '#f6e1dd'], ['ivory', '#fbf6ea'], ['sage', '#e3e9dc']]) {
      box.append(el('button', { className: 'dot', title: st, style: `background:${c}`, onclick: async () => set(await api.vision.update(item.id, { style: st })) }));
    }
  }
  box.append(el('button', { title: 'Șterge', onclick: async () => set(await api.vision.remove(item.id)) }, [icon('trash')]));
  return box;
}

function render() {
  if (document.activeElement !== $('#title')) $('#title').value = board.title;
  if (document.activeElement !== $('#subtitle')) $('#subtitle').value = board.subtitle;
  $('#empty').classList.toggle('hidden', board.items.length > 0);
  const cols = el('div', { className: 'cols' });
  $('#board').replaceChildren(cols);
  cols.replaceChildren(...board.items.map(item => {
    const tile = el('div', { className: `tile ${item.type}` + (item.type === 'text' ? ' ' + item.style : '') });
    tile.style.setProperty('--tilt', `${item.tilt || 0}deg`);
    tile.append(el('span', { className: `tape ${item.tape}` }));
    if (item.type === 'image') {
      const cap = el('input', { className: 'cap', value: item.caption || '', placeholder: 'adaugă o legendă…', maxLength: 80 });
      cap.addEventListener('change', () => api.vision.update(item.id, { caption: cap.value }));
      tile.append(el('img', { src: item.url, alt: item.caption || '' }), cap);
    } else {
      const ta = el('textarea', { value: item.text, rows: 1, maxLength: 200 });
      ta.addEventListener('input', () => autoGrow(ta));
      ta.addEventListener('change', () => api.vision.update(item.id, { text: ta.value }));
      tile.append(ta);
      requestAnimationFrame(() => autoGrow(ta));
    }
    tile.append(ops(item));
    return tile;
  }));
}

function set(v) { board = v; render(); }

$('#addImg').addEventListener('click', async () => set(await api.vision.pick()));
$('#addText').addEventListener('click', async () => {
  set(await api.vision.addText('Scrie aici visul tău', ['noir', 'blush', 'ivory', 'sage'][board.items.length % 4]));
  const tas = document.querySelectorAll('.tile.text textarea');
  const last = tas[tas.length - 1];
  if (last) { last.focus(); last.select(); last.scrollIntoView({ block: 'center' }); }
});
$('#export').addEventListener('click', async () => {
  const res = await api.vision.exportImage();
  toast(res.ok ? 'Salvat în Imagini\\Desktop Buddy și copiat' : 'Nu am putut exporta: ' + res.error);
});
$('#close').addEventListener('click', () => api.vision.close());
for (const id of ['title', 'subtitle']) {
  $('#' + id).addEventListener('input', () => {
    clearTimeout(titleTimer);
    titleTimer = setTimeout(() => api.vision.setTitle($('#title').value, $('#subtitle').value), 400);
  });
}

// trage imagini din Explorer
let dragDepth = 0;
window.addEventListener('dragenter', e => { e.preventDefault(); dragDepth++; $('#drop').classList.remove('hidden'); });
window.addEventListener('dragleave', () => { if (--dragDepth <= 0) { dragDepth = 0; $('#drop').classList.add('hidden'); } });
window.addEventListener('dragover', e => e.preventDefault());
window.addEventListener('drop', async e => {
  e.preventDefault();
  dragDepth = 0;
  $('#drop').classList.add('hidden');
  const paths = [...e.dataTransfer.files].map(f => api.vision.pathFor(f)).filter(Boolean);
  if (paths.length) set(await api.vision.add(paths));
});
document.addEventListener('keydown', e => { if (e.key === 'Escape' && !['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) api.vision.close(); });

function applyTheme(s) { document.documentElement.dataset.theme = s.themeResolved || s.theme; }
api.settings.get().then(applyTheme);
api.settings.onUpdate(applyTheme);
api.vision.get().then(set);

// ---------- export ca imagine (randat offscreen la 1080×1350) ----------
const EXPORT = new URLSearchParams(location.search).has('export');
if (EXPORT) document.body.classList.add('export');
window.__exportReady = async () => {
  await Promise.all([...document.images].map(i => (i.complete ? null : i.decode().catch(() => null))));
  await document.fonts.ready;
  const b = $('#board');
  let k = 1;
  b.style.zoom = 1;
  while (b.scrollHeight > b.clientHeight + 1 && k > 0.35) {
    k -= 0.05;
    b.style.zoom = k;
  }
  await new Promise(r => setTimeout(r, 200));
  return true;
};
