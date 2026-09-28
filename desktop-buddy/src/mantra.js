// Mantra zilei: în fiecare zi un alt tip de mesaj (citat, vorbă de duh, cuvântul zilei,
// motivație, idee filozofică). Cu un model AI conectat, Mady o scrie în stilul ei; altfel alege
// dintr-o colecție atent aleasă. Se păstrează pe zile, ca să rămână aceeași toată ziua.
const store = require('./store');
const ai = require('./ai');

const TYPES = {
  citat: 'Citatul zilei',
  vorba: 'Vorba de duh',
  cuvant: 'Cuvântul zilei',
  motivatie: 'Motivația zilei',
  filozofie: 'Ideea zilei'
};
const ORDER = ['citat', 'cuvant', 'motivatie', 'filozofie', 'vorba'];

const LIBRARY = {
  citat: [
    { text: 'Nu pentru că e greu nu îndrăznim, ci pentru că nu îndrăznim e greu.', author: 'Seneca' },
    { text: 'Simplitatea este sofisticarea supremă.', author: 'Leonardo da Vinci' },
    { text: 'Eleganța nu înseamnă să fii observată, ci să fii ținută minte.', author: 'Giorgio Armani' },
    { text: 'Suntem ceea ce facem în mod repetat.', author: 'Will Durant, despre Aristotel' },
    { text: 'Viitorul aparține celor care cred în frumusețea visurilor lor.', author: 'Eleanor Roosevelt' },
    { text: 'Arta spală din suflet praful vieții de zi cu zi.', author: 'Pablo Picasso' },
    { text: 'Riscul vine din a nu ști ce faci.', author: 'Warren Buffett' },
    { text: 'Fericirea vieții tale depinde de calitatea gândurilor tale.', author: 'Marcus Aurelius' }
  ],
  vorba: [
    { text: 'Nu te grăbi să fii ocupată. Grăbește-te să fii importantă pentru ce contează.', author: 'Mady' },
    { text: 'Un „nu” elegant valorează mai mult decât zece „da” obosite.', author: 'Mady' },
    { text: 'Perfecțiunea e amânarea purtată în haine scumpe.', author: 'Mady' },
    { text: 'Rujul se retușează; o oportunitate ratată, mai greu.', author: 'Mady' },
    { text: 'Calendarul tău arată ce iubești cu adevărat.', author: 'Mady' },
    { text: 'Inboxul e lista de priorități a altora. Ai grijă cine îți scrie ziua.', author: 'Mady' },
    { text: 'Cafeaua deschide ochii; focusul deschide uși.', author: 'Mady' }
  ],
  cuvant: [
    { title: 'Sprezzatura', text: 'Arta de a face lucrurile grele să pară ușoare.', note: 'Azi: pregătește-te temeinic, apoi prezintă relaxat.' },
    { title: 'Ikigai', text: 'Motivul pentru care te trezești dimineața.', note: 'Azi: scrie într-o frază de ce contează munca ta.' },
    { title: 'Kaizen', text: 'Îmbunătățire continuă, prin pași mici.', note: 'Azi: fă un singur lucru cu 1% mai bine decât ieri.' },
    { title: 'Ataraxia', text: 'Liniștea minții pe care nimic din afară nu o tulbură.', note: 'Azi: nu reacționa la primul impuls. Respiră, apoi alege.' },
    { title: 'Hygge', text: 'Confortul cald al lucrurilor simple.', note: 'Azi: o lumânare, o carte, zece minute doar pentru tine.' },
    { title: 'Meraki', text: 'A pune suflet, creativitate și dragoste în ceea ce faci.', note: 'Azi: lasă-ți amprenta într-un lucru mărunt.' },
    { title: 'Wabi-sabi', text: 'Frumusețea imperfecțiunii și a lucrurilor trecătoare.', note: 'Azi: „suficient de bun” e uneori perfect.' },
    { title: 'Eudaimonia', text: 'Înflorirea: o viață trăită la potențialul ei cel mai bun.', note: 'Azi: întreabă-te ce te-ar face mândră diseară.' }
  ],
  motivatie: [
    { text: 'Nu aștepta să te simți pregătită. Pregătirea vine din mers.' },
    { text: 'Fă azi ce „tu de peste un an” îți va mulțumi că ai făcut.' },
    { text: 'Două ore de focus adevărat bat opt ore de agitație.' },
    { text: 'Disciplina e forma cea mai înaltă de iubire de sine.' },
    { text: 'Nu trebuie să fie ușor. Trebuie doar să merite.' },
    { text: 'Standardele tale îți construiesc viața. Ține-le sus, cu grație.' },
    { text: 'Încrederea nu e să știi că vei reuși; e să știi că vei fi bine oricum.' }
  ],
  filozofie: [
    { title: 'Dihotomia controlului', text: 'Unele lucruri depind de noi, altele nu.', author: 'Epictet', note: 'Azi: pune energia doar în primele.' },
    { title: 'Amor fati', text: 'Iubește-ți destinul, cu tot ce aduce.', author: 'Nietzsche', note: 'Azi: găsește lecția din obstacolul zilei.' },
    { title: 'Memento mori', text: 'Timpul e resursa pe care nu o poți recupera.', author: 'Stoicii', note: 'Azi: nu-l risipi pe lucruri care nu contează.' },
    { title: 'Calea de mijloc', text: 'Virtutea stă între două extreme.', author: 'Aristotel', note: 'Azi: nici prea mult, nici prea puțin. Echilibru.' },
    { title: 'Carpe diem', text: 'Culege ziua, încrezându-te cât mai puțin în ziua de mâine.', author: 'Horațiu', note: 'Azi: fă primul pas la lucrul pe care îl tot amâni.' },
    { title: 'Premeditatio malorum', text: 'Imaginează-ți obstacolele dinainte, ca să nu te surprindă.', author: 'Seneca', note: 'Azi: ce ar putea merge prost? Pregătește planul B.' }
  ]
};

function key(d = new Date()) {
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
}

function dayIndex(k) {
  const [y, m, d] = k.split('-').map(Number);
  return Math.floor(Date.UTC(y, m - 1, d) / 86400000);
}

function typeFor(k) {
  return ORDER[dayIndex(k) % ORDER.length];
}

function fromLibrary(type, k) {
  const list = LIBRARY[type];
  const item = list[Math.floor(dayIndex(k) / ORDER.length) % list.length];
  return { type, label: TYPES[type], title: item.title || '', text: item.text, author: item.author || '', note: item.note || '', source: 'library' };
}

function aiPrompt(type) {
  const what = {
    citat: 'un citat real și verificabil al unei personalități (artă, filozofie, business, modă, finanțe), cu autorul corect',
    vorba: 'o vorbă de duh originală, scurtă, spirituală și elegantă, în stilul tău',
    cuvant: 'un cuvânt frumos (din orice limbă) cu sensul lui și cum îl aplic azi',
    motivatie: 'o idee de motivație scurtă și puternică, fără clișee',
    filozofie: 'o idee filozofică (stoici, Aristotel, filozofie orientală etc.), cu autorul/școala și cum o aplic azi'
  }[type];
  return `Scrie mantra mea de azi: ${what}. Maximum 25 de cuvinte pentru text.
Răspunde DOAR cu JSON valid, fără alt text: {"titlu": "", "text": "", "autor": "", "nota": ""}
- „titlu”: doar pentru cuvântul zilei sau ideea filozofică (altfel gol)
- „nota”: o frază scurtă „Azi: …” despre cum o aplic (opțional)`;
}

function parseJson(text) {
  const m = String(text).match(/\{[\s\S]*\}/);
  if (!m) return null;
  try {
    const j = JSON.parse(m[0]);
    if (!j.text || String(j.text).length > 300) return null;
    return j;
  } catch {
    return null;
  }
}

let pending = null;

// Mantra de azi (o generează o singură dată pe zi).
async function today() {
  const d = store.get();
  if (!d.mantras) d.mantras = {};
  const k = key();
  if (d.mantras[k]) return d.mantras[k];
  if (pending) return pending;
  pending = (async () => {
    const type = typeFor(k);
    let m = fromLibrary(type, k);
    const s = d.settings;
    if ((s.aiProvider || 'demo') !== 'demo') {
      try {
        const j = parseJson(await ai.complete(aiPrompt(type), s, store.getApiKey()));
        if (j) m = { type, label: TYPES[type], title: j.titlu || '', text: j.text, author: j.autor || '', note: j.nota || '', source: 'ai' };
      } catch {
        // fără conexiune sau cheie invalidă: rămâne varianta din colecție
      }
    }
    m.date = k;
    m.fav = false;
    d.mantras[k] = m;
    const keys = Object.keys(d.mantras).sort();
    while (keys.length > 400) {
      const old = keys.shift();
      if (!d.mantras[old].fav) delete d.mantras[old];
    }
    store.save();
    return m;
  })();
  try {
    return await pending;
  } finally {
    pending = null;
  }
}

function setFav(k, fav) {
  const m = store.get().mantras?.[k];
  if (m) {
    m.fav = !!fav;
    store.save();
  }
  return m;
}

function favorites() {
  return Object.values(store.get().mantras || {}).filter(m => m.fav).sort((a, b) => b.date.localeCompare(a.date));
}

module.exports = { today, setFav, favorites, key, TYPES, fromLibrary, typeFor };
