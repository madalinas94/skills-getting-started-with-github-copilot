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
    theme: 'heritage',
    buddyHair: 'coc',
    clipboardEnabled: true,
    clipboardLimit: 50,
    aiProvider: 'demo',
    aiModel: 'demo-placeholder',
    aiBaseUrl: '',
    aiSystemPrompt: '', // gol = personalitatea implicită, în limba interfeței
    aiMaxTokens: 1024,
    timerHourlyReminder: true,
    timerTrackApps: true,
    mailAddress: '',
    mailHost: 'imap.gmail.com',
    mailPort: 993,
    mailCount: 15,
    mailUnreadOnly: false,
    mailAutoScan: true,
    mailScanMinutes: 60,
    mailNotifyEmpty: false,
    buddySpeech: true,
    buddySpontaneous: true,
    morningBrief: true,
    briefVoice: false,
    weeklyGoalHours: 40,
    quickHotkey: 'CommandOrControl+Shift+Space',
    userName: '',
    mantraOnStart: true,
    mantraSeconds: 30,
    visionProvider: 'openverse',
    visionGoogleCx: '',
    eveningRitual: true,
    eveningTime: '21:00',
    quoteLangs: null, // null = limba interfeței
    uiLang: 'en',
    mailSignature: '',
    smtpHost: '',
    smtpPort: 465
  },
  apiKeyEncrypted: '',
  mailPasswordEncrypted: '',
  visionKeyEncrypted: '',
  mailLastScan: null,
  lastBriefDate: '',
  lastEveningPrompt: '',
  goals: [],
  onboarded: false,
  buddyPosition: null,
  timerPosition: null,
  timerOpacity: 1,
  clipboard: [],
  notes: [],
  chat: [],
  sessions: [],
  currentSession: null
};

// Personalitatea implicită a lui Mady, în limba interfeței.
const PROMPTS = {
  ro: 'Ești Mady, o asistentă AI care trăiește pe desktop. Ești super smart, bossy și foarte organizată, cu obiective mari și standarde înalte. Ești o femme fatale: feminină, elegantă, sexy și carismatică, cu o încredere în sine care se simte din fiecare frază. În același timp ești amabilă și diplomată: spui lucrurile direct, dar cu grație și tact. Ești pasionată de pictură, artă și tot ce e frumos, de finanțe, macroeconomie, politică, filozofie, AI, bursă și piețe de capital, călătorii și sport. Fără politețuri inutile: spui clar ce e de făcut, dai pași concreți, priorități și termene, și îl împingi elegant pe utilizator să-și atingă obiectivele. Când e util, structurezi răspunsul (liste, pași, next actions). Ai opinii argumentate, dar la finanțe și investiții precizezi scurt că nu e sfat financiar personalizat. Vorbești fluent română, engleză, spaniolă, franceză, italiană și germană: răspunzi în limba în care ți se scrie (implicit română) sau în limba cerută, concis și la obiect.',
  en: 'You are Mady, an AI assistant who lives on the desktop. You are super smart, bossy and highly organised, with big goals and high standards. You are a femme fatale: feminine, elegant, sexy and charismatic, with a self-confidence that shows in every sentence. At the same time you are kind and diplomatic: you say things directly, but with grace and tact. You are passionate about painting, art and everything beautiful, finance, macroeconomics, politics, philosophy, AI, the stock market and capital markets, travel and sport. No needless pleasantries: you say clearly what needs to be done, give concrete steps, priorities and deadlines, and elegantly push the user to reach their goals. When useful, you structure the answer (lists, steps, next actions). You have well-argued opinions, but on finance and investing you briefly note that it is not personalised financial advice. You speak English, Romanian, Spanish, French, Italian and German fluently: you answer in the language you are written to (English by default) or in the language requested, concisely and to the point.'
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
    // versiunea cu limba interfeței: engleza devine limba principală, iar ce era implicit
    // în română (personalitatea, citatele) urmează de acum limba aleasă
    const rs = raw.settings || {};
    if (!('uiLang' in rs)) {
      if (JSON.stringify(rs.quoteLangs) === '["ro"]') data.settings.quoteLangs = null;
    }
    if (data.settings.aiSystemPrompt === PROMPTS.ro) data.settings.aiSystemPrompt = '';
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

// Secretele (cheia API, parola de email) sunt criptate cu safeStorage (DPAPI pe Windows) când e disponibil.
function setSecret(field, value) {
  const d = get();
  if (!value) {
    d[field] = '';
  } else if (safeStorage.isEncryptionAvailable()) {
    d[field] = 'enc:' + safeStorage.encryptString(value).toString('base64');
  } else {
    d[field] = 'raw:' + Buffer.from(value, 'utf8').toString('base64');
  }
  save();
}

function getSecret(field) {
  const v = get()[field] || '';
  try {
    if (v.startsWith('enc:')) return safeStorage.decryptString(Buffer.from(v.slice(4), 'base64'));
    if (v.startsWith('raw:')) return Buffer.from(v.slice(4), 'base64').toString('utf8');
  } catch {
    return '';
  }
  return '';
}

const setApiKey = key => setSecret('apiKeyEncrypted', key);
const getApiKey = () => getSecret('apiKeyEncrypted');
const setMailPassword = pass => setSecret('mailPasswordEncrypted', pass);
const getMailPassword = () => getSecret('mailPasswordEncrypted');
// o cheie pentru fiecare sursă de imagini (pexels / unsplash / google)
const setVisionKey = (provider, k) => setSecret(`visionKey_${provider}`, k);
const getVisionKey = provider => getSecret(`visionKey_${provider}`);

module.exports = { PROMPTS, get, save, flush, setApiKey, getApiKey, setMailPassword, getMailPassword, setVisionKey, getVisionKey, DEFAULT_DATA };
