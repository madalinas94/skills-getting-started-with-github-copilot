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

async function chat(messages, settings, apiKey) {
  const provider = settings.aiProvider || 'demo';
  const opts = {
    apiKey,
    model: settings.aiModel,
    system: settings.aiSystemPrompt,
    messages: messages.map(m => ({ role: m.role, content: m.content })),
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

module.exports = { PROVIDERS, chat };
