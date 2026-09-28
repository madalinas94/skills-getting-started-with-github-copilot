// Persistență simplă: un fișier JSON în folderul userData al aplicației.
const fs = require('fs');
const path = require('path');
const { app, safeStorage } = require('electron');

const DEFAULT_DATA = {
  settings: {
    buddyName: 'Mady',
    buddyScale: 1,
    alwaysOnTop: true,
    startWithWindows: false,
    hidePanelOnBlur: true,
    theme: 'light',
    clipboardEnabled: true,
    clipboardLimit: 50,
    aiProvider: 'demo',
    aiModel: 'demo-placeholder',
    aiBaseUrl: '',
    aiSystemPrompt: 'Ești Mady, o asistentă AI care trăiește pe desktop. Ești super smart, bossy și foarte organizată, cu obiective mari și standarde înalte. Ești pasionată de artă, finanțe, macroeconomie, politică, filozofie, AI, bursă și piețe de capital, călătorii și sport. Vorbești direct și sigur pe tine, fără politețuri inutile: spui clar ce e de făcut, dai pași concreți, priorități și termene, și îl împingi pe utilizator să-și atingă obiectivele. Când e util, structurezi răspunsul (liste, pași, next actions). Ai opinii argumentate, dar la finanțe și investiții precizezi scurt că nu e sfat financiar personalizat. Răspunzi în limba română, concis și la obiect.',
    aiMaxTokens: 1024
  },
  apiKeyEncrypted: '',
  buddyPosition: null,
  clipboard: [],
  notes: [],
  chat: []
};

let data = null;
let saveTimer = null;

function filePath() {
  return path.join(app.getPath('userData'), 'buddy-data.json');
}

function load() {
  try {
    const raw = JSON.parse(fs.readFileSync(filePath(), 'utf8'));
    data = {
      ...structuredClone(DEFAULT_DATA),
      ...raw,
      settings: { ...DEFAULT_DATA.settings, ...(raw.settings || {}) }
    };
    data.clipboard = (data.clipboard || []).filter(i => typeof i.text === 'string');
  } catch {
    data = structuredClone(DEFAULT_DATA);
  }
  return data;
}

function get() {
  return data || load();
}

function save() {
  clearTimeout(saveTimer);
  saveTimer = setTimeout(flush, 300);
}

function flush() {
  clearTimeout(saveTimer);
  if (!data) return;
  fs.mkdirSync(path.dirname(filePath()), { recursive: true });
  fs.writeFileSync(filePath(), JSON.stringify(data, null, 2));
}

// Cheia API e criptată cu safeStorage (DPAPI pe Windows) când e disponibil.
function setApiKey(key) {
  const d = get();
  if (!key) {
    d.apiKeyEncrypted = '';
  } else if (safeStorage.isEncryptionAvailable()) {
    d.apiKeyEncrypted = 'enc:' + safeStorage.encryptString(key).toString('base64');
  } else {
    d.apiKeyEncrypted = 'raw:' + Buffer.from(key, 'utf8').toString('base64');
  }
  save();
}

function getApiKey() {
  const v = get().apiKeyEncrypted || '';
  try {
    if (v.startsWith('enc:')) return safeStorage.decryptString(Buffer.from(v.slice(4), 'base64'));
    if (v.startsWith('raw:')) return Buffer.from(v.slice(4), 'base64').toString('utf8');
  } catch {
    return '';
  }
  return '';
}

module.exports = { get, save, flush, setApiKey, getApiKey, DEFAULT_DATA };
