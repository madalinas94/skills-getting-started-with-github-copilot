// Agentul AI. Providerii sunt placeholdere configurabile din Setări:
// alegi providerul, modelul și cheia API, iar la final îl legi de serviciul dorit.

const PROVIDERS = {
  demo: {
    label: 'Demo (fără API, placeholder)',
    models: ['demo-placeholder'],
    needsKey: false
  },
  anthropic: {
    label: 'Anthropic (Claude)',
    models: ['claude-opus-5-5', 'claude-sonnet-5', 'claude-haiku-4-5-20251001'],
    needsKey: true
  },
  openai: {
    label: 'OpenAI',
    models: ['gpt-4o', 'gpt-4o-mini'],
    needsKey: true
  },
  custom: {
    label: 'Custom (API compatibil OpenAI)',
    models: [],
    needsKey: false
  }
};

async function readError(res) {
  let detail = '';
  try {
    const body = await res.json();
    detail = body?.error?.message || JSON.stringify(body);
  } catch {
    detail = await res.text().catch(() => '');
  }
  return new Error(`Eroare API (${res.status}): ${detail}`);
}

async function callAnthropic({ apiKey, model, system, messages, maxTokens }) {
  const res = await fetch('https://api.anthropic.com/v1/messages', {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'x-api-key': apiKey,
      'anthropic-version': '2023-06-01'
    },
    body: JSON.stringify({ model, max_tokens: maxTokens, system, messages })
  });
  if (!res.ok) throw await readError(res);
  const body = await res.json();
  return (body.content || []).filter(b => b.type === 'text').map(b => b.text).join('\n');
}

async function callOpenAICompatible({ baseUrl, apiKey, model, system, messages, maxTokens }) {
  const url = (baseUrl || 'https://api.openai.com/v1').replace(/\/+$/, '') + '/chat/completions';
  const headers = { 'content-type': 'application/json' };
  if (apiKey) headers.authorization = `Bearer ${apiKey}`;
  const res = await fetch(url, {
    method: 'POST',
    headers,
    body: JSON.stringify({
      model,
      max_tokens: maxTokens,
      messages: [{ role: 'system', content: system }, ...messages]
    })
  });
  if (!res.ok) throw await readError(res);
  const body = await res.json();
  return body.choices?.[0]?.message?.content || '';
}

function demoReply(messages, settings) {
  const last = messages[messages.length - 1]?.content || '';
  return `Sunt ${settings.buddyName} și momentan rulez în modul demo.\n\n` +
    `Mi-ai scris: „${last.slice(0, 200)}”\n\n` +
    'Next action pentru tine: Setări → Asistent AI → alege providerul, modelul și pune cheia API. ' +
    'Apoi ne apucăm serios de treabă.';
}

// Conversația trimisă la API trebuie să înceapă cu utilizatorul și să alterneze rolurile
// (briefingul de dimineață apare în chat ca mesaj al lui Mady, fără întrebare înainte).
function normalize(messages) {
  const out = [];
  for (const m of messages) {
    if (!m.content) continue;
    if (!out.length && m.role !== 'user') continue;
    const prev = out[out.length - 1];
    if (prev && prev.role === m.role) prev.content += '\n\n' + m.content;
    else out.push({ role: m.role, content: m.content });
  }
  return out;
}

async function chat(messages, settings, apiKey, systemOverride) {
  const provider = settings.aiProvider || 'demo';
  const opts = {
    apiKey,
    model: settings.aiModel,
    system: systemOverride || (settings.aiSystemPrompt + (settings.userName ? `\n\nUtilizatorul se numește ${settings.userName}.` : '')),
    messages: normalize(messages),
    maxTokens: Number(settings.aiMaxTokens) || 1024,
    baseUrl: settings.aiBaseUrl
  };

  if (provider === 'demo') {
    await new Promise(r => setTimeout(r, 500));
    return demoReply(messages, settings);
  }
  if (PROVIDERS[provider]?.needsKey && !apiKey) {
    throw new Error('Lipsește cheia API. Adaug-o în Setări → Asistent AI.');
  }
  if (!opts.model) throw new Error('Alege un model în Setări → Asistent AI.');
  if (provider === 'anthropic') return callAnthropic(opts);
  if (provider === 'openai') return callOpenAICompatible({ ...opts, baseUrl: '' });
  if (provider === 'custom') {
    if (!opts.baseUrl) throw new Error('Completează Base URL pentru providerul custom.');
    return callOpenAICompatible(opts);
  }
  throw new Error(`Provider necunoscut: ${provider}`);
}

// O singură cerere (rezumat email, brief, feedback sesiune) cu personalitatea din Setări.
// `system` înlocuiește personalitatea (pentru corectură/traducere, unde vrem doar textul).
async function complete(prompt, settings, apiKey, demoText, { system, demoNote = true } = {}) {
  if ((settings.aiProvider || 'demo') === 'demo') {
    await new Promise(r => setTimeout(r, 400));
    return (demoText || 'Rezultat demo.') +
      (demoNote ? '\n\n(Mod demo: conectează un model din Setări → Asistent AI pentru analiza reală.)' : '');
  }
  return chat([{ role: 'user', content: prompt }], settings, apiKey, system);
}

// Acțiuni rapide pe text (scurtătura globală).
const LANGS = { ro: 'română', en: 'engleză', es: 'spaniolă', fr: 'franceză', it: 'italiană', de: 'germană' };
const TEXT_ONLY = 'Ești un editor de text precis. Returnezi DOAR rezultatul cerut, fără introducere, explicații sau ghilimele.';

function actionPrompt(action, text, lang) {
  switch (action) {
    case 'correct':
      return 'Corectează gramatica, ortografia (inclusiv diacriticele) și punctuația textului de mai jos. ' +
        'Păstrează limba, sensul și tonul. Returnează doar textul corectat.\n\n' + text;
    case 'summarize':
      return 'Rezumă textul de mai jos în 3-5 puncte scurte, în limba textului.\n\n' + text;
    case 'translate':
      return `Tradu textul de mai jos în limba ${LANGS[lang] || 'engleză'}. Păstrează formatarea. Returnează doar traducerea.\n\n` + text;
    case 'elegant':
      return 'Rescrie textul de mai jos mai elegant și profesionist, potrivit pentru un email de business. ' +
        'Păstrează limba și sensul. Returnează doar textul rescris.\n\n' + text;
    default:
      throw new Error('Acțiune necunoscută.');
  }
}

function demoAction(action, text, lang) {
  const labels = { correct: 'corectat', summarize: 'rezumat', translate: `tradus (${LANGS[lang] || 'engleză'})`, elegant: 'rescris elegant' };
  return `[Demo · textul ${labels[action] || ''} apare aici după ce conectezi un model AI]\n\n${text}`;
}

async function runAction(action, text, lang, settings, apiKey) {
  if (!String(text || '').trim()) throw new Error('Nu am niciun text. Copiază (Ctrl+C) textul și încearcă din nou.');
  const system = action === 'summarize' ? undefined : TEXT_ONLY;
  return complete(actionPrompt(action, text.slice(0, 12000), lang), settings, apiKey, demoAction(action, text, lang), { system, demoNote: false });
}

module.exports = { PROVIDERS, LANGS, chat, complete, runAction, normalize };
