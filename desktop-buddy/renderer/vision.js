const api = window.buddy;
const $ = sel => document.querySelector(sel);
let board = null;
let filter = '';
const areaLabel = id => board?.areas.find(a => a.id === id)?.label || '';

function art(id) {
  const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
  svg.setAttribute('viewBox', '0 0 64 64');
  const use = document.createElementNS('http://www.w3.org/2000/svg', 'use');
  use.setAttribute('href', `#a-${id}`);
  svg.append(use);
  return svg;
}
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
  if (item.category && (item.type === 'slot' || item.type === 'image')) {
    box.prepend(el('button', {
      title: item.type === 'slot' ? 'Imagine reală de pe internet' : 'Altă imagine de pe internet',
      onclick: async e => {
        e.stopPropagation();
        const tile = e.currentTarget.closest('.tile');
        tile.classList.add('loading');
        const r = await api.vision.webFill(item.id, item.type === 'image');
        tile.classList.remove('loading');
        if (!r.ok) toast(r.error);
        set(r.view);
      }
    }, [icon(item.type === 'slot' ? 'globe' : 'refresh')]));
  }
  if (item.type === 'text' && item.category) {
    box.prepend(el('button', { title: 'Altă afirmație', onclick: async () => set(await api.vision.nextAff(item.id)) }, [icon('shuffle')]));
  }
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
  // filtre pe arii (doar ariile folosite)
  const used = board.areas.filter(a => a.count);
  $('#filters').replaceChildren(...(used.length ? [
    el('button', { className: filter ? '' : 'on', textContent: 'Toate', onclick: () => { filter = ''; render(); } }),
    ...used.map(a => el('button', { className: filter === a.id ? 'on' : '', onclick: () => { filter = a.id; render(); } }, [a.label, el('em', { textContent: a.count })]))
  ] : []));
  $('#querybar').classList.toggle('hidden', !filter);
  if (filter && document.activeElement !== $('#queryInput')) $('#queryInput').value = board.areas.find(a => a.id === filter)?.query || '';
  const items = board.items.filter(i => !filter || i.category === filter);
  const cols = el('div', { className: 'cols' });
  $('#board').replaceChildren(cols);
  cols.replaceChildren(...items.map(item => {
    const tile = el('div', { className: `tile ${item.type}` + (item.type === 'text' ? ' ' + item.style : '') });
    tile.style.setProperty('--tilt', `${item.tilt || 0}deg`);
    tile.append(el('span', { className: `tape ${item.tape}` }));
    if (item.category && item.type === 'text') tile.append(el('span', { className: 'area-tag', textContent: areaLabel(item.category) }));
    if (item.type === 'slot') {
      tile.append(el('div', { className: 'slot-art' }, [
        art(item.category),
        el('span', { className: 'slabel', textContent: areaLabel(item.category) }),
        el('span', { className: 'shint', textContent: '+ adaugă fotografia ta' })
      ]));
      tile.addEventListener('click', async e => { if (!e.target.closest('.ops')) set(await api.vision.fillSlot(item.id)); });
      tile.addEventListener('dragover', e => { e.preventDefault(); e.stopPropagation(); tile.classList.add('dragover'); });
      tile.addEventListener('dragleave', () => tile.classList.remove('dragover'));
      tile.addEventListener('drop', async e => {
        e.preventDefault();
        e.stopPropagation();
        tile.classList.remove('dragover');
        dragDepth = 0;
        $('#drop').classList.add('hidden');
        const f = e.dataTransfer.files[0];
        const p = f && api.vision.pathFor(f);
        if (p) set(await api.vision.fillSlot(item.id, p));
      });
    } else if (item.type === 'image') {
      const cap = el('input', { className: 'cap', value: item.caption || '', placeholder: 'adaugă o legendă…', maxLength: 80 });
      cap.addEventListener('change', () => api.vision.update(item.id, { caption: cap.value }));
      tile.append(el('img', { src: item.url, alt: item.caption || '' }), cap);
      if (item.source) {
        const src = item.source;
        tile.append(el('span', {
          className: 'credit',
          title: `${src.provider}${src.link ? ' · ' + src.link : ''}`,
          textContent: `Foto: ${src.creator || 'autor necunoscut'} · ${src.license}`,
          onclick: () => src.link && api.app.openExternal(src.link)
        }));
      }
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

$('#addImg').addEventListener('click', async () => set(await api.vision.pick(filter || undefined)));

// alegerea ariilor vieții
let picked = new Set();
function openPicker() {
  const existing = new Set(board.areas.filter(a => a.count).map(a => a.id));
  picked = new Set(board.areas.map(a => a.id).filter(id => !existing.has(id)));
  $('#pickerGrid').replaceChildren(...board.areas.map(a => el('button', {
    className: picked.has(a.id) ? 'on' : '',
    title: existing.has(a.id) ? 'Deja pe board' : '',
    onclick: e => {
      picked.has(a.id) ? picked.delete(a.id) : picked.add(a.id);
      e.currentTarget.classList.toggle('on', picked.has(a.id));
    }
  }, [art(a.id), a.label + (existing.has(a.id) ? ' ✓' : '')])));
  $('#picker').classList.remove('hidden');
}
$('#addAreas').addEventListener('click', openPicker);

async function generateAll() {
  $('#progress').classList.remove('hidden');
  $('#progressText').textContent = 'Pregătesc board-ul…';
  $('#progressBar').style.width = '0%';
  const r = await api.vision.generate();
  $('#progress').classList.add('hidden');
  set(r.view);
  if (!r.ok) toast(r.error);
  else if (r.errors.length) toast(r.errors[0]);
  else toast('Board-ul tău e gata');
}
api.vision.onProgress(p => {
  $('#progressText').textContent = p.area ? `${p.area} (${p.done + 1}/${p.total})` : 'Aproape gata…';
  $('#progressBar').style.width = (p.total ? Math.round((p.done / p.total) * 100) : 100) + '%';
});
$('#generate').addEventListener('click', generateAll);
$('#queryApply').addEventListener('click', async () => {
  if (!filter) return;
  set(await api.vision.setQuery(filter, $('#queryInput').value));
  const targets = board.items.filter(i => i.category === filter && (i.type === 'slot' || (i.type === 'image' && i.source)));
  for (const t of targets) {
    const r = await api.vision.webFill(t.id, false);
    if (!r.ok) { toast(r.error); break; }
    set(r.view);
  }
});
$('#queryInput').addEventListener('keydown', e => { if (e.key === 'Enter') $('#queryApply').click(); });
$('#startAreas').addEventListener('click', openPicker);
$('#pickCancel').addEventListener('click', () => $('#picker').classList.add('hidden'));
$('#pickAll').addEventListener('click', () => {
  picked = new Set(board.areas.map(a => a.id));
  document.querySelectorAll('#pickerGrid button').forEach(b => b.classList.add('on'));
});
$('#pickOk').addEventListener('click', async () => {
  $('#picker').classList.add('hidden');
  const order = board.areas.map(a => a.id).filter(id => picked.has(id));
  if (order.length) set(await api.vision.addAreas(order));
  if (order.length && $('#pickWeb').checked) generateAll();
});
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
  if (paths.length) set(await api.vision.add(paths, filter || undefined));
});
document.addEventListener('keydown', e => {
  if (e.key !== 'Escape' || ['INPUT', 'TEXTAREA'].includes(document.activeElement.tagName)) return;
  if (!$('#picker').classList.contains('hidden')) $('#picker').classList.add('hidden');
  else api.vision.close();
});

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
  const tiles = [...document.querySelectorAll('.tile')];
  // cadrele încă goale nu au ce căuta într-o imagine de împărtășit, dacă avem destul conținut
  if (tiles.filter(t => !t.classList.contains('slot')).length >= 6) tiles.filter(t => t.classList.contains('slot')).forEach(t => t.remove());
  let k = 1;
  b.style.zoom = 1;
  const over = () => b.scrollHeight > b.clientHeight + 1;
  while (over() && k > 0.62) {
    k -= 0.04;
    b.style.zoom = k;
  }
  // tot nu încape: păstrăm primele elemente, lizibile
  let rest = [...document.querySelectorAll('.tile')];
  while (over() && rest.length > 4) {
    rest.pop().remove();
  }
  await new Promise(r => setTimeout(r, 200));
  return true;
};
