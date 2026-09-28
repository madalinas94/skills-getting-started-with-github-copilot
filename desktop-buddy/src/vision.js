// Vision board: imagini (copiate în folderul aplicației) și carduri de text, în stil Pinterest.
const { app } = require('electron');
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');
const store = require('./store');

const IMAGE_EXT = ['.png', '.jpg', '.jpeg', '.webp', '.gif'];
const TAPES = ['gold', 'blush', 'sage', 'powder', 'champagne'];

function dir() {
  const d = path.join(app.getPath('userData'), 'vision');
  fs.mkdirSync(d, { recursive: true });
  return d;
}

function data() {
  const d = store.get();
  if (!d.vision) d.vision = { title: 'Vision board', subtitle: 'Anul în care totul prinde formă', items: [] };
  return d.vision;
}

function view() {
  const v = data();
  return {
    ...v,
    items: v.items
      .filter(i => i.type !== 'image' || fs.existsSync(path.join(dir(), i.file)))
      .map(i => (i.type === 'image' ? { ...i, url: 'file:///' + path.join(dir(), i.file).replace(/\\/g, '/') } : i))
  };
}

function tape(i) {
  return TAPES[i % TAPES.length];
}

function addImages(files) {
  const v = data();
  for (const f of files || []) {
    const ext = path.extname(f).toLowerCase();
    if (!IMAGE_EXT.includes(ext) || !fs.existsSync(f)) continue;
    if (fs.statSync(f).size > 25 * 1024 * 1024) continue;
    const id = crypto.randomUUID();
    const file = id + ext;
    fs.copyFileSync(f, path.join(dir(), file));
    v.items.push({ id, type: 'image', file, caption: '', tape: tape(v.items.length), tilt: +(Math.random() * 3 - 1.5).toFixed(2) });
  }
  store.save();
  return view();
}

function addText(text, style) {
  const v = data();
  v.items.push({
    id: crypto.randomUUID(), type: 'text', text: String(text || 'Scrie aici visul tău').slice(0, 200),
    style: ['noir', 'blush', 'ivory', 'sage'].includes(style) ? style : 'noir', tape: tape(v.items.length), tilt: +(Math.random() * 3 - 1.5).toFixed(2)
  });
  store.save();
  return view();
}

function update(id, patch) {
  const i = data().items.find(x => x.id === id);
  if (i) {
    if ('caption' in patch) i.caption = String(patch.caption).slice(0, 80);
    if ('text' in patch) i.text = String(patch.text).slice(0, 200);
    if ('style' in patch) i.style = patch.style;
  }
  store.save();
  return view();
}

function remove(id) {
  const v = data();
  const i = v.items.find(x => x.id === id);
  if (i && i.type === 'image') fs.rmSync(path.join(dir(), i.file), { force: true });
  v.items = v.items.filter(x => x.id !== id);
  store.save();
  return view();
}

function move(id, delta) {
  const items = data().items;
  const i = items.findIndex(x => x.id === id);
  const j = i + delta;
  if (i < 0 || j < 0 || j >= items.length) return view();
  [items[i], items[j]] = [items[j], items[i]];
  store.save();
  return view();
}

function setTitle(title, subtitle) {
  const v = data();
  if (title != null) v.title = String(title).slice(0, 60);
  if (subtitle != null) v.subtitle = String(subtitle).slice(0, 100);
  store.save();
  return view();
}

module.exports = { view, addImages, addText, update, remove, move, setTitle, IMAGE_EXT, dir };
