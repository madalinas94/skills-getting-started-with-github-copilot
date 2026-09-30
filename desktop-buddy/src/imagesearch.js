// Căutare de imagini reale pentru vision board.
// - Openverse: fără cheie, imagini cu licențe libere (Creative Commons), cu autor și licență.
// - Pexels / Unsplash: fotografii editoriale de calitate, cu o cheie API gratuită.
const { t } = require('./i18n');
const OPENVERSE = process.env.BUDDY_OPENVERSE_URL || 'https://api.openverse.org/v1/images/';
const PEXELS = 'https://api.pexels.com/v1/search';
const UNSPLASH = 'https://api.unsplash.com/search/photos';
const GOOGLE = process.env.BUDDY_GOOGLE_URL || 'https://www.googleapis.com/customsearch/v1';

// Câte rezultate întoarce o pagină, per sursă.
const PAGE_SIZE = { google: 10, pexels: 20, unsplash: 20, openverse: 20 };

// Căutări implicite, în registrul „old money”: rafinat, matur, atemporal.
const QUERIES = {
  calatorii: 'Amalfi coast villa terrace',
  succes: 'elegant mahogany office desk',
  carti: 'classic library leather books',
  bani: 'private banking elegant',
  masina: 'vintage Mercedes convertible',
  casa: 'English country manor house',
  iubire: 'elegant wedding couple',
  credinta: 'candles old church prayer',
  frumusete: 'vanity perfume pearls',
  fit: 'tennis court country club',
  eleganta: 'pearl necklace silk',
  familie: 'family dinner garden table'
};

async function getJson(url, headers = {}) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 20000);
  try {
    const res = await fetch(url, { headers: { 'user-agent': 'DesktopBuddy/1.0', ...headers }, signal: ctrl.signal });
    if (res.status === 401 || res.status === 403) throw new Error(t('Cheia API pentru imagini nu e validă (sau lipsește).'));
    if (res.status === 429) throw new Error(t('Prea multe căutări într-un timp scurt. Mai încearcă peste un minut.'));
    if (!res.ok) throw new Error(t('Căutarea de imagini a eșuat ({s}).', { s: res.status }));
    return await res.json();
  } catch (err) {
    if (err.name === 'AbortError') throw new Error(t('Căutarea de imagini durează prea mult. Verifică internetul.'));
    if (/fetch failed|ENOTFOUND|ECONN/i.test(err.message)) throw new Error(t('Nu am acces la internet pentru căutarea de imagini.'));
    throw err;
  } finally {
    clearTimeout(timer);
  }
}

// Rezultat comun: { url, thumb, creator, license, link, provider, title }
async function search(query, { provider = 'openverse', key = '', cx = '', page = 1 } = {}) {
  const q = encodeURIComponent(query);
  if (provider === 'google') {
    if (!key || !cx) throw new Error(t('Pentru Google adaugă cheia API și ID-ul motorului de căutare în Setări → Vision board.'));
    const start = (page - 1) * 10 + 1;
    if (start > 91) return [];
    const j = await getJson(`${GOOGLE}?key=${encodeURIComponent(key)}&cx=${encodeURIComponent(cx)}&q=${q}&searchType=image&num=10&start=${start}&imgSize=large&safe=active`);
    return (j.items || []).map(i => ({
      url: i.link, thumb: i.image?.thumbnailLink || i.link, creator: i.displayLink || '', license: t('Google Imagini'),
      link: i.image?.contextLink || i.link, provider: 'Google', title: i.title || ''
    }));
  }
  if (provider === 'pexels') {
    if (!key) throw new Error(t('Adaugă cheia Pexels în Setări → Vision board.'));
    const j = await getJson(`${PEXELS}?query=${q}&per_page=20&page=${page}&orientation=portrait`, { authorization: key });
    return (j.photos || []).map(p => ({ url: p.src.large2x || p.src.large, thumb: p.src.medium, creator: p.photographer, license: 'Pexels', link: p.url, provider: 'Pexels', title: p.alt || '' }));
  }
  if (provider === 'unsplash') {
    if (!key) throw new Error(t('Adaugă cheia Unsplash în Setări → Vision board.'));
    const j = await getJson(`${UNSPLASH}?query=${q}&per_page=20&page=${page}&orientation=portrait`, { authorization: `Client-ID ${key}` });
    return (j.results || []).map(p => ({ url: p.urls.regular, thumb: p.urls.small, creator: p.user?.name || '', license: 'Unsplash', link: p.links?.html || '', provider: 'Unsplash', title: p.alt_description || '' }));
  }
  const j = await getJson(`${OPENVERSE}?q=${q}&page_size=20&page=${page}&mature=false`);
  return (j.results || [])
    .filter(r => r.url && (!r.width || r.width >= 600))
    .map(r => ({
      url: r.url,
      thumb: r.thumbnail || r.url,
      creator: r.creator || '',
      license: `CC ${String(r.license || '').toUpperCase()}${r.license_version ? ' ' + r.license_version : ''}`.trim(),
      link: r.foreign_landing_url || r.url,
      provider: 'Openverse',
      title: r.title || ''
    }));
}

// Imagine din orice sursă primită de la utilizator: link (inclusiv linkuri Google „imgres?imgurl=”),
// imagine „data:” (miniaturile Google) sau octeții unei imagini copiate.
function fromDataUri(uri) {
  const m = /^data:image\/(png|jpe?g|webp);base64,(.+)$/i.exec(uri || '');
  if (!m) return null;
  const buf = Buffer.from(m[2], 'base64');
  if (buf.length < 2000) throw new Error(t('Imaginea e prea mică. Deschide poza mare în Google, apoi copiaz-o.'));
  return { buf, ext: m[1].toLowerCase() === 'png' ? '.png' : m[1].toLowerCase() === 'webp' ? '.webp' : '.jpg' };
}

function realUrl(url) {
  try {
    const u = new URL(url);
    const direct = u.searchParams.get('imgurl') || u.searchParams.get('mediaurl');
    if (direct) return direct;
  } catch {}
  return url;
}

async function fromAnywhere(src) {
  const s = String(src || '').trim();
  if (s.startsWith('data:')) {
    const d = fromDataUri(s);
    if (!d) throw new Error(t('Formatul imaginii nu e acceptat.'));
    return d;
  }
  if (!/^https?:\/\//i.test(s)) throw new Error(t('Nu am găsit o imagine. Copiază imaginea (click dreapta → Copiază imaginea) sau trage-o aici.'));
  try {
    return await download(realUrl(s));
  } catch {
    throw new Error(t('Nu am putut descărca imaginea de la acest link. Încearcă „Copiază imaginea” și apoi „Lipește”.'));
  }
}

async function download(url) {
  const ctrl = new AbortController();
  const timer = setTimeout(() => ctrl.abort(), 30000);
  try {
    const res = await fetch(url, { headers: { 'user-agent': 'DesktopBuddy/1.0' }, signal: ctrl.signal, redirect: 'follow' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const type = res.headers.get('content-type') || '';
    if (!/^image\/(jpeg|png|webp)/.test(type)) throw new Error('nu e imagine');
    const buf = Buffer.from(await res.arrayBuffer());
    if (buf.length < 8000 || buf.length > 20 * 1024 * 1024) throw new Error('mărime neobișnuită');
    return { buf, ext: type.includes('png') ? '.png' : type.includes('webp') ? '.webp' : '.jpg' };
  } finally {
    clearTimeout(timer);
  }
}

module.exports = { QUERIES, PAGE_SIZE, search, download, fromAnywhere, realUrl };
