// Căutare de imagini reale pentru vision board.
// - Openverse: fără cheie, imagini cu licențe libere (Creative Commons), cu autor și licență.
// - Pexels / Unsplash: fotografii editoriale de calitate, cu o cheie API gratuită.
const OPENVERSE = process.env.BUDDY_OPENVERSE_URL || 'https://api.openverse.org/v1/images/';
const PEXELS = 'https://api.pexels.com/v1/search';
const UNSPLASH = 'https://api.unsplash.com/search/photos';

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
  const t = setTimeout(() => ctrl.abort(), 20000);
  try {
    const res = await fetch(url, { headers: { 'user-agent': 'DesktopBuddy/1.0', ...headers }, signal: ctrl.signal });
    if (res.status === 401 || res.status === 403) throw new Error('Cheia API pentru imagini nu e validă (sau lipsește).');
    if (res.status === 429) throw new Error('Prea multe căutări într-un timp scurt. Mai încearcă peste un minut.');
    if (!res.ok) throw new Error(`Căutarea de imagini a eșuat (${res.status}).`);
    return await res.json();
  } catch (err) {
    if (err.name === 'AbortError') throw new Error('Căutarea de imagini durează prea mult. Verifică internetul.');
    if (/fetch failed|ENOTFOUND|ECONN/i.test(err.message)) throw new Error('Nu am acces la internet pentru căutarea de imagini.');
    throw err;
  } finally {
    clearTimeout(t);
  }
}

// Rezultat comun: { url, thumb, creator, license, link, provider, title }
async function search(query, { provider = 'openverse', key = '', page = 1 } = {}) {
  const q = encodeURIComponent(query);
  if (provider === 'pexels') {
    if (!key) throw new Error('Adaugă cheia Pexels în Setări → Vision board.');
    const j = await getJson(`${PEXELS}?query=${q}&per_page=20&page=${page}&orientation=portrait`, { authorization: key });
    return (j.photos || []).map(p => ({ url: p.src.large2x || p.src.large, thumb: p.src.medium, creator: p.photographer, license: 'Pexels', link: p.url, provider: 'Pexels', title: p.alt || '' }));
  }
  if (provider === 'unsplash') {
    if (!key) throw new Error('Adaugă cheia Unsplash în Setări → Vision board.');
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

async function download(url) {
  const ctrl = new AbortController();
  const t = setTimeout(() => ctrl.abort(), 30000);
  try {
    const res = await fetch(url, { headers: { 'user-agent': 'DesktopBuddy/1.0' }, signal: ctrl.signal, redirect: 'follow' });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const type = res.headers.get('content-type') || '';
    if (!/^image\/(jpeg|png|webp)/.test(type)) throw new Error('nu e imagine');
    const buf = Buffer.from(await res.arrayBuffer());
    if (buf.length < 8000 || buf.length > 20 * 1024 * 1024) throw new Error('mărime neobișnuită');
    return { buf, ext: type.includes('png') ? '.png' : type.includes('webp') ? '.webp' : '.jpg' };
  } finally {
    clearTimeout(t);
  }
}

module.exports = { QUERIES, search, download };
