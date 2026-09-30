// Scanare automată a inboxului: la fiecare N minute (implicit 60) numără emailurile
// necitite primite azi și cere modelului AI un rezumat al celor mai importante.
const store = require('./store');
const mail = require('./mail');
const ai = require('./ai');

const CHECK_EVERY_MS = 60 * 1000;

let timer = null;
let running = false;
let hooks = { onStart() {}, onResult() {} };

const settings = () => store.get().settings;

function configured() {
  return !!(settings().mailAddress && store.getMailPassword());
}

function intervalMs() {
  return Math.max(15, Number(settings().mailScanMinutes) || 60) * 60 * 1000;
}

function lastScan() {
  return store.get().mailLastScan || null;
}

function nextScanAt() {
  if (!settings().mailAutoScan || !configured()) return null;
  const last = lastScan();
  return last ? last.at + intervalMs() : Date.now() + CHECK_EVERY_MS;
}

async function scan({ manual = false } = {}) {
  if (running) return lastScan();
  if (!configured()) {
    return { at: Date.now(), count: null, important: [], summary: '', error: require('./i18n').t('Inboxul nu e configurat (Setări → Inbox).') };
  }
  running = true;
  hooks.onStart();
  const s = settings();
  let result;
  try {
    const msgs = await mail.fetchTodayUnread({
      host: s.mailHost, port: s.mailPort, user: s.mailAddress, pass: store.getMailPassword()
    });
    const important = mail.rankImportant(msgs).slice(0, 3).map(m => ({ uid: m.uid, from: m.from, subject: m.subject }));
    let summary = '';
    let summaryError = '';
    if (msgs.length) {
      try {
        summary = await ai.complete(mail.importantPrompt(msgs), s, store.getApiKey(), mail.demoImportant(msgs));
      } catch (err) {
        summaryError = err.message;
      }
    }
    result = { at: Date.now(), count: msgs.length, important, summary, summaryError, error: '' };
  } catch (err) {
    result = { at: Date.now(), count: null, important: [], summary: '', error: err.message };
  } finally {
    running = false;
  }
  store.get().mailLastScan = result;
  store.save();
  hooks.onResult(result, manual);
  return result;
}

function check() {
  const next = nextScanAt();
  if (next && Date.now() >= next) scan();
}

function init(h) {
  hooks = { ...hooks, ...h };
  clearInterval(timer);
  timer = setInterval(check, CHECK_EVERY_MS);
}

function shutdown() {
  clearInterval(timer);
}

function state() {
  return { last: lastScan(), next: nextScanAt(), running, configured: configured() };
}

module.exports = { init, scan, state, shutdown };
