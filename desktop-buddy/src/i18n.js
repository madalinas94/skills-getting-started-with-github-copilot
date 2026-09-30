// Limba interfeței în procesul principal (notificări, tray, replicile lui Mady, briefing).
// Aceleași chei ca în renderer: textul românesc este cheia, dicționarul dă traducerea.
const EN = require('../renderer/i18n-en.js');

const LOCALES = { ro: 'ro-RO', en: 'en-GB' };
const missing = new Set();

function lang() {
  try {
    return require('./store').get().settings.uiLang || 'en';
  } catch {
    return 'en';
  }
}

function t(s, vars) {
  let out = s;
  if (lang() === 'en') {
    if (EN[s] !== undefined) out = EN[s];
    else missing.add(s);
  }
  if (vars) out = String(out).replace(/\{(\w+)\}/g, (_, k) => (vars[k] ?? ''));
  return out;
}

const locale = () => LOCALES[lang()] || 'en-GB';

// Plural simplu: t1 pentru 1, altfel tn (ambele trec prin dicționar).
const plural = (n, one, many, vars = {}) => t(n === 1 ? one : many, { n, ...vars });

module.exports = { t, lang, locale, plural, missing };
