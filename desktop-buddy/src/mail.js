// Cititor de inbox prin IMAP (Gmail: imap.gmail.com:993 + parolă de aplicație).
// Deschide căsuța doar pentru citire, deci emailurile NU sunt marcate ca citite.
const { ImapFlow } = require('imapflow');
const { simpleParser } = require('mailparser');

const MAX_FULL_BYTES = 1024 * 1024; // mesajele mai mari (atașamente) sunt citite doar parțial
const MAX_SOURCE_BYTES = 200000;
const MAX_TEXT_CHARS = 4000;

let cache = []; // ultimele emailuri descărcate, doar în memorie

function cleanText(text) {
  return String(text || '')
    .replace(/\r/g, '')
    .replace(/[ \t]+\n/g, '\n')
    .replace(/\n{3,}/g, '\n\n')
    .trim()
    .slice(0, MAX_TEXT_CHARS);
}

function htmlToText(html) {
  return String(html || '')
    .replace(/<(style|script)[\s\S]*?<\/\1>/gi, ' ')
    .replace(/<br\s*\/?>/gi, '\n')
    .replace(/<\/(p|div|tr|li|h\d)>/gi, '\n')
    .replace(/<[^>]+>/g, ' ')
    .replace(/&nbsp;/g, ' ')
    .replace(/&amp;/g, '&')
    .replace(/&lt;/g, '<')
    .replace(/&gt;/g, '>')
    .replace(/&quot;/g, '"')
    .replace(/&#39;/g, "'");
}

async function fetchMessages({ host, port, user, pass, count, unreadOnly, since }) {
  if (!user || !pass) throw new Error('Completează adresa de email și parola de aplicație în Setări → Inbox.');
  const client = new ImapFlow({
    host: host || 'imap.gmail.com',
    port: Number(port) || 993,
    secure: true,
    auth: { user, pass },
    logger: false,
    socketTimeout: 30000
  });

  try {
    await client.connect();
  } catch (err) {
    const msg = err.authenticationFailed || /auth/i.test(err.responseText || err.message)
      ? 'Autentificare eșuată. Verifică adresa și parola de aplicație (nu parola obișnuită de Gmail).'
      : `Nu mă pot conecta la serverul de email: ${err.message}`;
    throw new Error(msg);
  }

  const n = Math.min(Math.max(Number(count) || 15, 1), 50);
  const messages = [];
  const lock = await client.getMailboxLock('INBOX', { readOnly: true });
  try {
    let range;
    let byUid = false;
    if (unreadOnly || since) {
      const query = {};
      if (unreadOnly) query.seen = false;
      if (since) query.since = since;
      const uids = (await client.search(query, { uid: true })) || [];
      if (!uids.length) return [];
      range = uids.slice(-n).join(',');
      byUid = true;
    } else {
      const total = client.mailbox.exists;
      if (!total) return [];
      range = `${Math.max(1, total - n + 1)}:*`;
    }

    // 1) antete + mărime; 2) conținutul: complet pentru mesaje mici, parțial pentru cele mari (atașamente)
    const heads = [];
    for await (const msg of client.fetch(range, { uid: true, envelope: true, flags: true, size: true }, { uid: byUid })) {
      heads.push(msg);
    }
    const sources = new Map();
    const small = heads.filter(h => (h.size || 0) <= MAX_FULL_BYTES).map(h => h.uid);
    const large = heads.filter(h => (h.size || 0) > MAX_FULL_BYTES).map(h => h.uid);
    if (small.length) {
      for await (const msg of client.fetch(small.join(','), { uid: true, source: true }, { uid: true })) {
        sources.set(msg.uid, msg.source);
      }
    }
    if (large.length) {
      for await (const msg of client.fetch(large.join(','), { uid: true, source: { start: 0, maxLength: MAX_SOURCE_BYTES } }, { uid: true })) {
        sources.set(msg.uid, msg.source);
      }
    }

    for (const msg of heads) {
      let text = '';
      try {
        const parsed = await simpleParser(sources.get(msg.uid) || '');
        text = parsed.text || htmlToText(parsed.html);
      } catch {
        text = '';
      }
      const from = msg.envelope.from?.[0] || {};
      messages.push({
        uid: msg.uid,
        from: from.name || from.address || 'Necunoscut',
        fromAddress: from.address || '',
        subject: msg.envelope.subject || '(fără subiect)',
        date: (msg.envelope.date || new Date()).getTime(),
        unread: !msg.flags?.has('\\Seen'),
        text: cleanText(text)
      });
    }
  } finally {
    lock.release();
    await client.logout().catch(() => {});
  }

  messages.sort((a, b) => b.date - a.date);
  return messages;
}

async function fetchInbox(opts) {
  cache = await fetchMessages(opts);
  return cache;
}

// Emailurile necitite primite azi (pentru scanarea automată). Nu modifică lista din panou.
async function fetchTodayUnread(opts) {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const msgs = await fetchMessages({ ...opts, unreadOnly: true, since: today, count: 50 });
  // SINCE e pe zile în fusul orar al serverului; filtrăm exact după ora locală
  return msgs.filter(m => m.date >= today.getTime());
}

function list() {
  return cache.map(({ text, ...m }) => ({ ...m, snippet: text.slice(0, 220) }));
}

function get(uid) {
  return cache.find(m => m.uid === uid);
}

function summaryPrompt(m) {
  return [
    'Rezumă emailul de mai jos în 2-4 puncte scurte. La final scrie „Acțiune necesară:” și ce trebuie să fac (sau „nimic”).',
    'Răspunde în limba în care e scris emailul, dacă nu e română, altfel în română.',
    '',
    `De la: ${m.from} <${m.fromAddress}>`,
    `Subiect: ${m.subject}`,
    `Data: ${new Date(m.date).toLocaleString('ro-RO')}`,
    '',
    m.text || '(fără text)'
  ].join('\n');
}

function briefPrompt() {
  const items = cache.slice(0, 25).map((m, i) =>
    `#${i + 1} | ${m.unread ? 'NECITIT' : 'citit'} | ${new Date(m.date).toLocaleString('ro-RO')} | De la: ${m.from} | Subiect: ${m.subject}\n${m.text.slice(0, 600)}`
  );
  return [
    'Fă-mi un quick brief al inboxului meu, pe baza emailurilor de mai jos:',
    '1) Urgent / important (cu ce trebuie să fac),',
    '2) De răspuns sau de programat,',
    '3) Restul pe scurt (newslettere, notificări) într-o singură frază.',
    'Fii concisă. Menționează numărul emailului (#) la fiecare punct.',
    '',
    ...items
  ].join('\n\n');
}

const AUTOMATED = /no-?reply|newsletter|notific|mailer-daemon|marketing|promo|news@|info@|updates?@/i;

function importantPrompt(msgs) {
  const items = msgs.slice(0, 30).map((m, i) =>
    `#${i + 1} | ${new Date(m.date).toLocaleTimeString('ro-RO', { hour: '2-digit', minute: '2-digit' })} | De la: ${m.from} <${m.fromAddress}> | Subiect: ${m.subject}\n${m.text.slice(0, 500)}`
  );
  return [
    `Am ${msgs.length} emailuri necitite primite azi. Alege cele mai importante (maxim 5) și ignoră newsletterele și notificările automate.`,
    'Pentru fiecare: „#număr Expeditor – Subiect”, apoi o frază despre ce e important și ce trebuie să fac.',
    'La final, o singură frază despre restul. Fii concisă.',
    '',
    ...items
  ].join('\n\n');
}

// Pentru modul demo și pentru textul notificării: o ordonare simplă (oameni reali înaintea mesajelor automate).
function rankImportant(msgs) {
  return msgs
    .map(m => ({ m, score: (AUTOMATED.test(m.fromAddress + ' ' + m.from) ? 0 : 2) + (/urgent|important|asap|deadline|până|confirm/i.test(m.subject) ? 1 : 0) }))
    .sort((a, b) => b.score - a.score || b.m.date - a.m.date)
    .map(x => x.m);
}

function demoImportant(msgs) {
  const top = rankImportant(msgs).slice(0, 5);
  return 'Cele mai importante (ordonare simplă, fără AI):\n' +
    top.map((m, i) => `#${i + 1} ${m.from} – ${m.subject}`).join('\n');
}

function demoSummary(m) {
  return `Email de la ${m.from}, subiect „${m.subject}”.\nÎnceput: ${m.text.slice(0, 160)}…`;
}

function demoBrief() {
  const unread = cache.filter(m => m.unread).length;
  return `Ai ${cache.length} emailuri, din care ${unread} necitite.\n` +
    cache.slice(0, 5).map((m, i) => `#${i + 1} ${m.from}: ${m.subject}`).join('\n');
}

module.exports = {
  fetchInbox, fetchTodayUnread, list, get, summaryPrompt, briefPrompt, importantPrompt,
  rankImportant, demoSummary, demoBrief, demoImportant
};
