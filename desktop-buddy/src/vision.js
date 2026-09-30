// Vision board: imagini (copiate în folderul aplicației) și carduri de text, în stil Pinterest.
const { app } = require('electron');
const path = require('path');
const fs = require('fs');
const crypto = require('crypto');
const store = require('./store');
const { AREAS, byId } = require('./lifeareas');
const images = require('./imagesearch');
const { t, locale, plural } = require('./i18n');

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
    // titlurile implicite apar în limba interfeței (cele scrise de utilizator rămân neschimbate)
    title: v.title === 'Vision board' ? t('Vision board') : v.title,
    subtitle: v.subtitle === 'Anul în care totul prinde formă' ? t('Anul în care totul prinde formă') : v.subtitle,
    areas: AREAS.map(a => ({ id: a.id, label: a.label, count: v.items.filter(i => i.category === a.id).length, query: queryFor(a.id) })),
    goals: require('./goals').byArea(),
    items: v.items
      .filter(i => i.type !== 'image' || fs.existsSync(path.join(dir(), i.file)))
      .map(i => (i.type === 'image' ? { ...i, url: 'file:///' + path.join(dir(), i.file).replace(/\\/g, '/') } : i))
  };
}

function tape(i) {
  return TAPES[i % TAPES.length];
}

function copyImage(f) {
  const ext = path.extname(f).toLowerCase();
  if (!IMAGE_EXT.includes(ext) || !fs.existsSync(f)) return null;
  if (fs.statSync(f).size > 25 * 1024 * 1024) return null;
  const id = crypto.randomUUID();
  const file = id + ext;
  fs.copyFileSync(f, path.join(dir(), file));
  return { id, file };
}

function addImages(files, category) {
  const v = data();
  for (const f of files || []) {
    const c = copyImage(f);
    if (!c) continue;
    v.items.push({ ...c, type: 'image', caption: '', category: byId(category) ? category : '', tape: tape(v.items.length), tilt: +(Math.random() * 3 - 1.5).toFixed(2) });
  }
  store.save();
  return view();
}

// Un cadru gol al unei arii devine fotografia aleasă (pe același loc).
function fillSlot(slotId, file) {
  const v = data();
  const i = v.items.findIndex(x => x.id === slotId && x.type === 'slot');
  const c = file && copyImage(file);
  if (i < 0 || !c) return view();
  const slot = v.items[i];
  v.items[i] = { ...c, type: 'image', caption: byId(slot.category)?.label || '', category: slot.category, tape: slot.tape, tilt: slot.tilt };
  store.save();
  return view();
}

// Creează secțiunile pentru ariile alese: un cadru pentru fotografie + o afirmație.
function addAreas(ids) {
  const v = data();
  const styles = ['noir', 'blush', 'ivory', 'sage'];
  let n = 0;
  for (const id of ids || []) {
    const a = byId(id);
    if (!a) continue;
    const tilt = () => +(Math.random() * 3 - 1.5).toFixed(2);
    v.items.push({ id: crypto.randomUUID(), type: 'slot', category: a.id, tape: tape(v.items.length), tilt: tilt() });
    v.items.push({ id: crypto.randomUUID(), type: 'text', category: a.id, text: a.affirmations[0], aff: 0, style: styles[n % styles.length], tape: tape(v.items.length), tilt: tilt() });
    n++;
  }
  store.save();
  return view();
}

// Următoarea afirmație a ariei, pentru un card de text.
function nextAffirmation(id) {
  const i = data().items.find(x => x.id === id);
  const a = i && byId(i.category);
  if (a) {
    i.aff = ((i.aff || 0) + 1) % a.affirmations.length;
    i.text = a.affirmations[i.aff];
    store.save();
  }
  return view();
}

function addText(text, style) {
  const v = data();
  v.items.push({
    id: crypto.randomUUID(), type: 'text', text: String(text || t('Scrie aici visul tău')).slice(0, 200),
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
  if (i && i.type === 'image' && i.file) fs.rmSync(path.join(dir(), i.file), { force: true });
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

// ---------- imagini reale de pe internet ----------

const cache = new Map(); // căutare → rezultate (în memorie)

function queryFor(area) {
  return data().queries?.[area] || images.QUERIES[area] || byId(area)?.label || 'elegant lifestyle';
}

function setQuery(area, q) {
  const v = data();
  if (!v.queries) v.queries = {};
  const t = String(q || '').trim().slice(0, 80);
  if (t) v.queries[area] = t;
  else delete v.queries[area];
  store.save();
  return view();
}

async function results(query, opts, page) {
  const k = `${opts.provider}|${query}|${page}`;
  if (!cache.has(k)) cache.set(k, await images.search(query, { ...opts, page }));
  return cache.get(k);
}

// Umple un cadru (sau înlocuiește o imagine) cu o fotografie reală pentru aria lui.
async function webFill(itemId, opts, { next = false } = {}) {
  const v = data();
  const idx = v.items.findIndex(x => x.id === itemId);
  if (idx < 0) throw new Error(t('Elementul nu mai există.'));
  const item = v.items[idx];
  const area = item.category;
  const query = queryFor(area);
  const used = new Set(v.items.map(i => i.source?.url).filter(Boolean));
  const per = images.PAGE_SIZE[opts.provider] || 20;
  let pos = next && item.source?.query === query ? (item.source.pos || 0) + 1 : 0;
  for (let tries = 0; tries < 12; tries++, pos++) {
    const page = 1 + Math.floor(pos / per);
    const list = await results(query, opts, page);
    if (!list.length) break;
    const r = list[pos % per];
    if (!r) break;
    if (used.has(r.url)) continue;
    try {
      const { buf, ext } = await images.download(r.url);
      const id = crypto.randomUUID();
      const file = id + ext;
      fs.writeFileSync(path.join(dir(), file), buf);
      if (item.type === 'image' && item.file) fs.rmSync(path.join(dir(), item.file), { force: true });
      v.items[idx] = {
        id, type: 'image', file, category: area,
        caption: item.type === 'image' ? item.caption : (byId(area)?.label || ''),
        tape: item.tape, tilt: item.tilt,
        source: { url: r.url, creator: r.creator, license: r.license, link: r.link, provider: r.provider, query, pos }
      };
      store.save();
      return view();
    } catch {
      // imaginea nu se poate descărca: trecem la următoarea
    }
  }
  throw new Error(t('Nu am găsit imagini pentru „{q}”. Încearcă altă căutare.', { q: query }));
}

// Pune pe board o imagine adusă de utilizator (link, „data:”, sau octeți din clipboard).
// Cu `itemId` umple/înlocuiește acel cadru; altfel adaugă o fotografie nouă în aria dată.
function saveBuffer({ buf, ext }, itemId, category, source) {
  const v = data();
  const id = crypto.randomUUID();
  const file = id + ext;
  fs.writeFileSync(path.join(dir(), file), buf);
  const idx = itemId ? v.items.findIndex(x => x.id === itemId) : -1;
  if (idx >= 0) {
    const old = v.items[idx];
    if (old.type === 'image' && old.file) fs.rmSync(path.join(dir(), old.file), { force: true });
    v.items[idx] = {
      id, type: 'image', file, category: old.category || '',
      caption: old.type === 'image' ? old.caption : (byId(old.category)?.label || ''),
      tape: old.tape, tilt: old.tilt, ...(source ? { source } : {})
    };
  } else {
    v.items.push({ id, type: 'image', file, caption: byId(category)?.label || '', category: byId(category) ? category : '', tape: tape(v.items.length), tilt: +(Math.random() * 3 - 1.5).toFixed(2), ...(source ? { source } : {}) });
  }
  store.save();
  return view();
}

async function fromSource(src, itemId, category) {
  const img = await images.fromAnywhere(src);
  let source = null;
  const s = String(src || '');
  if (/^https?:/i.test(s)) {
    const real = images.realUrl(s);
    let host = '';
    try { host = new URL(real).hostname.replace(/^www\./, ''); } catch {}
    source = { url: real, creator: host, license: t('din browser'), link: real, provider: 'Web' };
  }
  return saveBuffer(img, itemId, category, source);
}

function fromBuffer(buf, ext, itemId, category) {
  if (!buf || buf.length < 2000) throw new Error(t('În clipboard nu e o imagine. În Google: click dreapta pe poză → Copiază imaginea.'));
  return saveBuffer({ buf, ext }, itemId, category, null);
}

// Generează tot board-ul: creează ariile (dacă lipsesc) și umple cadrele goale cu imagini reale.
async function generate(opts, onProgress = () => {}) {
  const v = data();
  if (!v.items.some(i => i.category)) addAreas(AREAS.map(a => a.id));
  const slots = v.items.filter(i => i.type === 'slot');
  const errors = [];
  let done = 0;
  for (const s of slots) {
    onProgress({ done, total: slots.length, area: byId(s.category)?.label || '' });
    try {
      await webFill(s.id, opts);
    } catch (err) {
      errors.push(err.message);
      if (/internet|cheia|Prea multe/i.test(err.message)) break;
    }
    done++;
  }
  onProgress({ done, total: slots.length, area: '' });
  return { view: view(), errors };
}

// Ariile prezente pe board (pentru „Afirmația zilei”).
function boardAreas() {
  return [...new Set(data().items.map(i => i.category).filter(Boolean))];
}

module.exports = { view, addImages, addText, update, remove, move, setTitle, addAreas, fillSlot, nextAffirmation, boardAreas, webFill, generate, setQuery, fromSource, fromBuffer, queryFor, IMAGE_EXT, dir };
