// Trimiterea de emailuri din notițe, prin SMTP (Gmail: smtp.gmail.com:465), cu aceeași
// adresă și parolă de aplicație ca inboxul.
const nodemailer = require('nodemailer');
const store = require('./store');
const ai = require('./ai');
const { t } = require('./i18n');

const EMAIL = /^[^\s@<>,;]+@[^\s@<>,;]+\.[^\s@<>,;]+$/;

function settings() {
  return store.get().settings;
}

// „ana@x.ro, Ion <ion@y.ro>; z@w.com” → listă de adrese valide + ce n-a putut fi citit
function parseAddresses(text) {
  const ok = [], bad = [];
  for (const part of String(text || '').split(/[,;]/).map(s => s.trim()).filter(Boolean)) {
    const m = /<([^>]+)>/.exec(part);
    const addr = (m ? m[1] : part).trim();
    if (EMAIL.test(addr)) ok.push(m ? part : addr);
    else bad.push(part);
  }
  return { ok, bad };
}

function smtpConfig() {
  const s = settings();
  if (process.env.BUDDY_SMTP) {
    const [host, port] = process.env.BUDDY_SMTP.split(':');
    return { host, port: Number(port), secure: false, ignoreTLS: true };
  }
  const host = s.smtpHost || (/gmail/i.test(s.mailHost || '') || !s.mailHost ? 'smtp.gmail.com' : String(s.mailHost).replace(/^imap\./i, 'smtp.'));
  const port = Number(s.smtpPort) || 465;
  return { host, port, secure: port === 465 };
}

// Notița → email: un rând „Către: …” / „To: …” la început devine destinatarul,
// titlul devine subiectul (sau primul rând, dacă nu are titlu).
function fromNote(note) {
  let body = String(note?.body || '').replace(/\r/g, '');
  let to = '';
  const m = /^\s*(?:to|către|catre|pentru|à|para|a|an)\s*:\s*(.+)\n?/i.exec(body);
  if (m && parseAddresses(m[1]).ok.length) {
    to = m[1].trim();
    body = body.slice(m[0].length);
  }
  let subject = String(note?.title || '').trim();
  if (!subject) {
    const first = body.split('\n').find(l => l.trim()) || '';
    subject = first.trim().slice(0, 90);
  }
  return { to, subject, body: body.trim() };
}

function recents() {
  return (store.get().sentMail || []).flatMap(x => x.to).filter((v, i, a) => a.indexOf(v) === i).slice(0, 12);
}

function withSignature(body) {
  const sig = String(settings().mailSignature || '').trim();
  return sig && !body.includes(sig) ? `${body.trimEnd()}\n\n${sig}` : body;
}

function escapeHtml(s) {
  return s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
}

function toHtml(text) {
  const paras = text.split(/\n{2,}/).map(p => `<p style="margin:0 0 12px">${escapeHtml(p).replace(/\n/g, '<br>')}</p>`).join('');
  return `<div style="font-family:Georgia,'Times New Roman',serif;font-size:15px;line-height:1.55;color:#222">${paras}</div>`;
}

async function send({ to, cc, subject, body, noteId }) {
  const s = settings();
  const pass = store.getMailPassword();
  if (!s.mailAddress || !pass) throw new Error(t('Conectează întâi Gmail în Setări → Inbox (adresa și parola de aplicație). Aceeași parolă se folosește și pentru trimitere.'));
  const rcpt = parseAddresses(to);
  const copy = parseAddresses(cc);
  if (rcpt.bad.length || copy.bad.length) throw new Error(t('Adresă de email invalidă: {a}', { a: [...rcpt.bad, ...copy.bad].join(', ') }));
  if (!rcpt.ok.length) throw new Error(t('Adaugă cel puțin un destinatar.'));
  const text = withSignature(String(body || '').trim());
  if (!text) throw new Error(t('Emailul nu are conținut.'));
  const transport = nodemailer.createTransport({
    ...smtpConfig(),
    auth: process.env.BUDDY_SMTP ? undefined : { user: s.mailAddress, pass },
    connectionTimeout: 20000, greetingTimeout: 15000, socketTimeout: 30000
  });
  const from = s.userName ? `"${s.userName.replace(/"/g, '')}" <${s.mailAddress}>` : s.mailAddress;
  try {
    const info = await transport.sendMail({
      from, to: rcpt.ok.join(', '), cc: copy.ok.join(', ') || undefined,
      subject: String(subject || '').trim() || t('(fără subiect)'), text, html: toHtml(text)
    });
    const rec = { at: Date.now(), to: rcpt.ok, cc: copy.ok, subject: String(subject || '').trim(), noteId: noteId || null, id: info.messageId };
    const d = store.get();
    d.sentMail = [rec, ...(d.sentMail || [])].slice(0, 200);
    const note = noteId && d.notes.find(n => n.id === noteId);
    if (note) note.sent = [...(note.sent || []), { at: rec.at, to: rec.to }].slice(-20);
    store.save();
    return rec;
  } catch (err) {
    if (/Invalid login|535|EAUTH/i.test(err.message)) throw new Error(t('Gmail a refuzat autentificarea. Verifică parola de aplicație din Setări → Inbox.'));
    if (/ENOTFOUND|ECONNREFUSED|ETIMEDOUT|ESOCKET|Greeting never received/i.test(err.message)) throw new Error(t('Nu mă pot conecta la serverul de email. Verifică internetul.'));
    throw new Error(t('Trimiterea a eșuat: {e}', { e: err.message }));
  } finally {
    transport.close();
  }
}

function polishPrompt({ to, subject, body }) {
  return [
    t('Transformă notița de mai jos într-un email clar, elegant și profesionist, gata de trimis.'),
    t('Păstrează limba notiței, toate faptele, cifrele și datele. Adaugă un salut și o încheiere potrivite, fără semnătură cu nume.'),
    t('Răspunde DOAR cu JSON valid: {"subject": "", "body": ""}'),
    '',
    to ? `To: ${to}` : '',
    `Subject: ${subject || '-'}`,
    '',
    body
  ].filter(x => x !== null).join('\n');
}

// Varianta fără AI: salut, conținutul notiței, încheiere.
function templatePolish({ subject, body }) {
  const s = settings();
  const lines = String(body || '').trim();
  const greet = t('Bună ziua,');
  const close = t('Cu drag,');
  return {
    subject: subject || lines.split('\n')[0].slice(0, 80),
    body: `${greet}\n\n${lines}\n\n${close}${s.userName ? '\n' + s.userName : ''}`
  };
}

async function polish(draft) {
  const s = settings();
  if ((s.aiProvider || 'demo') === 'demo') return { ...templatePolish(draft), demo: true };
  const out = await ai.complete(polishPrompt(draft), s, store.getApiKey());
  const m = String(out).match(/\{[\s\S]*\}/);
  try {
    const j = JSON.parse(m[0]);
    if (j.body) return { subject: j.subject || draft.subject, body: j.body };
  } catch {}
  return { subject: draft.subject, body: String(out).trim() };
}

module.exports = { send, fromNote, recents, parseAddresses, polish, smtpConfig };
