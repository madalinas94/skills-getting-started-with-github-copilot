const { app, BrowserWindow, ipcMain, clipboard, screen, Tray, Menu, nativeImage, shell, Notification } = require('electron');
const path = require('path');
const crypto = require('crypto');
const store = require('./src/store');
const ai = require('./src/ai');
const sessions = require('./src/sessions');
const mail = require('./src/mail');

const BUDDY_W = 170;
const BUDDY_H = 210;
const PANEL_W = 440;
const PANEL_H = 620;
const TIMER_W = 310;
const TIMER_H = 66;

let buddyWin = null;
let panelWin = null;
let timerWin = null;
let timerHidden = false; // ascuns explicit de utilizator
let tray = null;
let clipboardTimer = null;
let lastClipboardText = '';

const settings = () => store.get().settings;

// ---------- Ferestre ----------

function buddySize() {
  const s = Number(settings().buddyScale) || 1;
  return { width: Math.round(BUDDY_W * s), height: Math.round(BUDDY_H * s) };
}

function createBuddyWindow() {
  const { width, height } = buddySize();
  const area = screen.getPrimaryDisplay().workArea;
  const saved = store.get().buddyPosition;
  const pos = saved && isOnScreen(saved.x, saved.y, width, height)
    ? saved
    : { x: area.x + area.width - width - 40, y: area.y + area.height - height - 20 };

  buddyWin = new BrowserWindow({
    width, height, x: pos.x, y: pos.y,
    frame: false,
    transparent: true,
    resizable: false,
    hasShadow: false,
    skipTaskbar: true,
    alwaysOnTop: settings().alwaysOnTop,
    maximizable: false,
    fullscreenable: false,
    backgroundColor: '#00000000',
    webPreferences: { preload: path.join(__dirname, 'preload.js') }
  });
  buddyWin.setAlwaysOnTop(settings().alwaysOnTop, 'floating');
  buddyWin.loadFile(path.join(__dirname, 'renderer', 'buddy.html'));
  buddyWin.on('closed', () => { buddyWin = null; });
}

function createPanelWindow() {
  panelWin = new BrowserWindow({
    width: PANEL_W, height: PANEL_H,
    show: false,
    frame: false,
    resizable: false,
    skipTaskbar: true,
    alwaysOnTop: true,
    maximizable: false,
    fullscreenable: false,
    transparent: true,
    backgroundColor: '#00000000',
    webPreferences: { preload: path.join(__dirname, 'preload.js') }
  });
  panelWin.loadFile(path.join(__dirname, 'renderer', 'panel.html'));
  panelWin.on('blur', () => {
    if (settings().hidePanelOnBlur && panelWin && !panelWin.webContents.isDevToolsOpened()) panelWin.hide();
  });
  panelWin.on('closed', () => { panelWin = null; });
}

function isOnScreen(x, y, w, h) {
  return screen.getAllDisplays().some(d => {
    const a = d.workArea;
    return x + w / 2 >= a.x && x + w / 2 <= a.x + a.width && y + h / 2 >= a.y && y + h / 2 <= a.y + a.height;
  });
}

// Panoul apare lângă roboțel, pe partea unde e loc.
function positionPanel() {
  if (!buddyWin || !panelWin) return;
  const b = buddyWin.getBounds();
  const area = screen.getDisplayMatching(b).workArea;
  let x = b.x - PANEL_W - 8;
  if (x < area.x) x = b.x + b.width + 8;
  if (x + PANEL_W > area.x + area.width) x = area.x + area.width - PANEL_W;
  let y = b.y + b.height - PANEL_H;
  y = Math.max(area.y, Math.min(y, area.y + area.height - PANEL_H));
  panelWin.setBounds({ x: Math.round(x), y: Math.round(y), width: PANEL_W, height: PANEL_H });
}

function togglePanel(tab) {
  if (!panelWin) createPanelWindow();
  if (panelWin.isVisible() && !tab) {
    panelWin.hide();
    return;
  }
  positionPanel();
  panelWin.show();
  panelWin.focus();
  if (tab) panelWin.webContents.send('panel:tab', tab);
}

function showBuddy() {
  if (!buddyWin) createBuddyWindow();
  buddyWin.show();
}

// ---------- Timer (fereastră mică, mereu deasupra, mutabilă) ----------

function createTimerWindow() {
  const area = screen.getPrimaryDisplay().workArea;
  const saved = store.get().timerPosition;
  const pos = saved && isOnScreen(saved.x, saved.y, TIMER_W, TIMER_H)
    ? saved
    : { x: Math.round(area.x + (area.width - TIMER_W) / 2), y: area.y + 16 };
  timerWin = new BrowserWindow({
    width: TIMER_W, height: TIMER_H, x: pos.x, y: pos.y,
    show: false,
    frame: false,
    transparent: true,
    resizable: false,
    hasShadow: false,
    skipTaskbar: true,
    alwaysOnTop: true,
    maximizable: false,
    minimizable: false,
    fullscreenable: false,
    focusable: true,
    backgroundColor: '#00000000',
    webPreferences: { preload: path.join(__dirname, 'preload.js') }
  });
  timerWin.setAlwaysOnTop(true, 'screen-saver');
  timerWin.setVisibleOnAllWorkspaces(true);
  timerWin.setOpacity(Number(store.get().timerOpacity) || 1);
  timerWin.loadFile(path.join(__dirname, 'renderer', 'timer.html'));
  // afișat fără să ia focusul, ca să nu se închidă panoul
  timerWin.once('ready-to-show', () => timerWin && !timerHidden && timerWin.showInactive());
  let moveTimer;
  timerWin.on('move', () => {
    clearTimeout(moveTimer);
    moveTimer = setTimeout(() => {
      if (!timerWin) return;
      const { x, y } = timerWin.getBounds();
      store.get().timerPosition = { x, y };
      store.save();
    }, 400);
  });
  timerWin.on('closed', () => { timerWin = null; });
}

function showTimer() {
  if (!sessions.current()) return;
  timerHidden = false;
  if (!timerWin) createTimerWindow();
  else timerWin.showInactive();
  broadcast('timer:visible', true);
}

function hideTimer() {
  timerHidden = true;
  if (timerWin) timerWin.hide();
  broadcast('timer:visible', false);
}

function notify(title, body) {
  if (Notification.isSupported()) new Notification({ title, body, icon: path.join(__dirname, 'assets', 'icon.png') }).show();
}

// ---------- Tray ----------

function createTray() {
  const img = nativeImage.createFromPath(path.join(__dirname, 'assets', 'icon.png')).resize({ width: 16, height: 16 });
  tray = new Tray(img);
  tray.setToolTip('Desktop Buddy');
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: 'Deschide panoul', click: () => togglePanel('clipboard') },
    { label: 'Arată roboțelul', click: showBuddy },
    { label: 'Ascunde roboțelul', click: () => buddyWin && buddyWin.hide() },
    { label: 'Timer și statistici', click: () => togglePanel('timer') },
    { label: 'Arată timerul', click: showTimer },
    { label: 'Inbox', click: () => togglePanel('inbox') },
    { label: 'Setări', click: () => togglePanel('settings') },
    { type: 'separator' },
    { label: 'Ieșire', click: () => app.quit() }
  ]));
  tray.on('click', () => togglePanel());
}

// ---------- Clipboard ----------

// În Electron 44 API-ul clipboard e asincron (Promise).
async function startClipboardWatcher() {
  lastClipboardText = await clipboard.readText();
  let busy = false;
  clearInterval(clipboardTimer);
  clipboardTimer = setInterval(async () => {
    if (busy || !settings().clipboardEnabled) return;
    busy = true;
    try {
      const text = await clipboard.readText();
      if (typeof text !== 'string' || !text || text === lastClipboardText) return;
      lastClipboardText = text;
      addClipboardItem(text);
    } catch {
      // clipboard ocupat de altă aplicație; reîncercăm la următorul tick
    } finally {
      busy = false;
    }
  }, 1000);
}

function addClipboardItem(text) {
  const d = store.get();
  const existing = d.clipboard.find(i => i.text === text);
  d.clipboard = d.clipboard.filter(i => i.text !== text);
  d.clipboard.unshift({
    id: existing?.id || crypto.randomUUID(),
    text,
    pinned: existing?.pinned || false,
    createdAt: Date.now()
  });
  trimClipboard();
  store.save();
  broadcast('clipboard:updated', d.clipboard);
}

function trimClipboard() {
  const d = store.get();
  const limit = Math.max(5, Number(settings().clipboardLimit) || 50);
  const pinned = d.clipboard.filter(i => i.pinned);
  const rest = d.clipboard.filter(i => !i.pinned).slice(0, limit);
  d.clipboard = d.clipboard.filter(i => pinned.includes(i) || rest.includes(i));
}

function broadcast(channel, payload) {
  for (const w of [buddyWin, panelWin, timerWin]) if (w && !w.isDestroyed()) w.webContents.send(channel, payload);
}

// ---------- Setări ----------

function applySettings() {
  const s = settings();
  if (buddyWin) {
    buddyWin.setAlwaysOnTop(!!s.alwaysOnTop, 'floating');
    const { width, height } = buddySize();
    const b = buddyWin.getBounds();
    buddyWin.setBounds({ x: b.x, y: b.y + b.height - height, width, height });
  }
  if (app.isPackaged) app.setLoginItemSettings({ openAtLogin: !!s.startWithWindows });
  broadcast('settings:updated', publicSettings());
}

function publicSettings() {
  return { ...settings(), hasApiKey: !!store.getApiKey(), hasMailPassword: !!store.getMailPassword() };
}

// ---------- IPC ----------

function registerIpc() {
  // roboțel
  ipcMain.on('buddy:move', (_e, { x, y }) => {
    if (!buddyWin) return;
    const { width, height } = buddySize();
    buddyWin.setBounds({ x: Math.round(x), y: Math.round(y), width, height });
    if (panelWin && panelWin.isVisible()) positionPanel();
  });
  ipcMain.on('buddy:moved', () => {
    if (!buddyWin) return;
    const { x, y } = buddyWin.getBounds();
    store.get().buddyPosition = { x, y };
    store.save();
  });
  ipcMain.handle('buddy:position', () => buddyWin ? buddyWin.getBounds() : null);
  ipcMain.on('buddy:click', () => togglePanel());
  ipcMain.on('buddy:menu', () => {
    Menu.buildFromTemplate([
      { label: 'Deschide panoul', click: () => togglePanel('clipboard') },
      { label: 'Notițe', click: () => togglePanel('notes') },
      { label: 'Asistent AI', click: () => togglePanel('ai') },
      { label: 'Timer și statistici', click: () => togglePanel('timer') },
      { label: 'Inbox', click: () => togglePanel('inbox') },
      { label: 'Setări', click: () => togglePanel('settings') },
      { type: 'separator' },
      { label: 'Ascunde roboțelul', click: () => buddyWin && buddyWin.hide() },
      { label: 'Ieșire', click: () => app.quit() }
    ]).popup({ window: buddyWin });
  });

  // panou
  ipcMain.on('panel:hide', () => panelWin && panelWin.hide());
  ipcMain.on('app:quit', () => app.quit());
  ipcMain.on('app:openExternal', (_e, url) => {
    if (/^https?:\/\//.test(url)) shell.openExternal(url);
  });

  // setări
  ipcMain.handle('settings:get', () => publicSettings());
  ipcMain.handle('settings:set', (_e, patch) => {
    const allowed = Object.keys(store.DEFAULT_DATA.settings);
    for (const k of Object.keys(patch || {})) if (allowed.includes(k)) settings()[k] = patch[k];
    store.save();
    applySettings();
    if ('clipboardLimit' in patch) { trimClipboard(); broadcast('clipboard:updated', store.get().clipboard); }
    if ('timerTrackApps' in patch) patch.timerTrackApps ? sessions.startTracking() : sessions.stopTracking();
    return publicSettings();
  });
  ipcMain.handle('settings:setApiKey', (_e, key) => {
    store.setApiKey(String(key || '').trim());
    broadcast('settings:updated', publicSettings());
    return publicSettings();
  });
  ipcMain.handle('settings:providers', () => ai.PROVIDERS);
  ipcMain.handle('settings:reset', () => {
    store.get().settings = { ...store.DEFAULT_DATA.settings };
    store.save();
    applySettings();
    return publicSettings();
  });

  // clipboard
  ipcMain.handle('clipboard:list', () => store.get().clipboard);
  ipcMain.handle('clipboard:copy', async (_e, id) => {
    const item = store.get().clipboard.find(i => i.id === id);
    if (!item) return false;
    lastClipboardText = item.text;
    await clipboard.writeText(item.text);
    return true;
  });
  ipcMain.handle('clipboard:pin', (_e, id) => {
    const item = store.get().clipboard.find(i => i.id === id);
    if (item) item.pinned = !item.pinned;
    store.save();
    return store.get().clipboard;
  });
  ipcMain.handle('clipboard:delete', (_e, id) => {
    const d = store.get();
    d.clipboard = d.clipboard.filter(i => i.id !== id);
    store.save();
    return d.clipboard;
  });
  ipcMain.handle('clipboard:clear', () => {
    const d = store.get();
    d.clipboard = d.clipboard.filter(i => i.pinned);
    store.save();
    return d.clipboard;
  });
  ipcMain.handle('clipboard:toNote', (_e, id) => {
    const item = store.get().clipboard.find(i => i.id === id);
    if (!item) return null;
    return saveNote({ title: item.text.split('\n')[0].slice(0, 40), body: item.text });
  });

  // notițe
  ipcMain.handle('notes:list', () => store.get().notes);
  ipcMain.handle('notes:save', (_e, note) => saveNote(note));
  ipcMain.handle('notes:delete', (_e, id) => {
    const d = store.get();
    d.notes = d.notes.filter(n => n.id !== id);
    store.save();
    return d.notes;
  });

  // sesiuni / timer
  ipcMain.handle('session:current', () => currentSessionState());
  ipcMain.handle('session:start', (_e, title) => { sessions.start(title); return currentSessionState(); });
  ipcMain.handle('session:pause', () => { sessions.pause(); return currentSessionState(); });
  ipcMain.handle('session:resume', () => { sessions.resume(); return currentSessionState(); });
  ipcMain.handle('session:stop', () => sessions.stop());
  ipcMain.handle('session:history', () => sessions.history());
  ipcMain.handle('session:report', (_e, id) => {
    const s = sessions.getSession(id);
    return s ? sessions.report(s) : null;
  });
  ipcMain.handle('session:feedback', async (_e, id) => {
    const prompt = sessions.feedbackPrompt(id);
    if (!prompt) return { ok: false, error: 'Sesiunea nu mai există.' };
    const r = sessions.report(sessions.getSession(id));
    try {
      const text = await ai.complete(prompt, settings(), store.getApiKey(),
        `Sesiunea „${r.title}”: ${sessions.fmt(r.durationSec)}, din care activ ${sessions.fmt(r.activeSec)}. ` +
        `Aplicația principală: ${r.apps[0]?.name || 'nedetectată'}. Continuă așa și pune-ți un obiectiv clar pentru mâine.`);
      sessions.setFeedback(id, text);
      return { ok: true, text };
    } catch (err) {
      return { ok: false, error: err.message };
    }
  });
  ipcMain.on('timer:show', showTimer);
  ipcMain.on('timer:hide', hideTimer);
  ipcMain.handle('timer:opacity', (_e, value) => {
    const v = Math.min(1, Math.max(0.2, Number(value) || 1));
    store.get().timerOpacity = v;
    store.save();
    if (timerWin) timerWin.setOpacity(v);
    return v;
  });
  ipcMain.handle('timer:getOpacity', () => Number(store.get().timerOpacity) || 1);
  ipcMain.on('timer:openPanel', () => togglePanel('timer'));

  // inbox
  ipcMain.handle('mail:setPassword', (_e, pass) => {
    store.setMailPassword(String(pass || '').replace(/\s+/g, ''));
    broadcast('settings:updated', publicSettings());
    return publicSettings();
  });
  ipcMain.handle('mail:fetch', async () => {
    const s = settings();
    try {
      await mail.fetchInbox({
        host: s.mailHost, port: s.mailPort, user: s.mailAddress, pass: store.getMailPassword(),
        count: s.mailCount, unreadOnly: s.mailUnreadOnly
      });
      return { ok: true, messages: mail.list() };
    } catch (err) {
      return { ok: false, error: err.message, messages: mail.list() };
    }
  });
  ipcMain.handle('mail:list', () => mail.list());
  ipcMain.handle('mail:summary', async (_e, uid) => {
    const m = mail.get(uid);
    if (!m) return { ok: false, error: 'Emailul nu mai e în listă. Apasă Actualizează.' };
    try {
      return { ok: true, text: await ai.complete(mail.summaryPrompt(m), settings(), store.getApiKey(), mail.demoSummary(m)) };
    } catch (err) {
      return { ok: false, error: err.message };
    }
  });
  ipcMain.handle('mail:brief', async () => {
    if (!mail.list().length) return { ok: false, error: 'Nu am emailuri încărcate. Apasă Actualizează.' };
    try {
      return { ok: true, text: await ai.complete(mail.briefPrompt(), settings(), store.getApiKey(), mail.demoBrief()) };
    } catch (err) {
      return { ok: false, error: err.message };
    }
  });

  // AI
  ipcMain.handle('ai:history', () => store.get().chat);
  ipcMain.handle('ai:clear', () => {
    store.get().chat = [];
    store.save();
    return [];
  });
  ipcMain.handle('ai:send', async (_e, text) => {
    const d = store.get();
    d.chat.push({ role: 'user', content: String(text), at: Date.now() });
    store.save();
    try {
      const reply = await ai.chat(d.chat.slice(-30), settings(), store.getApiKey());
      d.chat.push({ role: 'assistant', content: reply || '(răspuns gol)', at: Date.now() });
      store.save();
      return { ok: true, chat: d.chat };
    } catch (err) {
      // mesajul utilizatorului rămâne; eroarea nu intră în istoric ca să nu strice conversația
      return { ok: false, error: err.message, chat: d.chat };
    }
  });
}

function currentSessionState() {
  const s = sessions.current();
  if (!s) return null;
  return {
    id: s.id, title: s.title, start: s.start, pausedMs: s.pausedMs, pausedAt: s.pausedAt,
    activeSec: s.activeSec, now: Date.now(), timerVisible: !!timerWin && !timerHidden
  };
}

function initSessions() {
  sessions.init({
    onChange(s) {
      if (s && !timerWin) { timerHidden = false; createTimerWindow(); }
      if (!s && timerWin) timerWin.close();
      broadcast('session:changed', currentSessionState());
    },
    onHour(hours, s) {
      const text = hours === 1 ? '1 Hour has passed' : `${hours} Hours have passed`;
      notify(text, `„${s.title}” – ${hours === 1 ? 'o oră' : hours + ' ore'} de lucru. Ia o pauză scurtă și continuă.`);
      broadcast('session:hour', { hours, title: s.title });
    },
    onEnd(rep) {
      notify('Sesiune încheiată', `„${rep.title}”: ${sessions.fmt(rep.durationSec)} total, ${sessions.fmt(rep.activeSec)} activ.`);
      togglePanel('timer');
      broadcast('session:ended', rep);
    }
  });
  if (sessions.current()) createTimerWindow();
}

function saveNote(note) {
  const d = store.get();
  const now = Date.now();
  let existing = note.id && d.notes.find(n => n.id === note.id);
  if (existing) {
    Object.assign(existing, { title: note.title ?? existing.title, body: note.body ?? existing.body, updatedAt: now });
  } else {
    existing = { id: crypto.randomUUID(), title: note.title || '', body: note.body || '', createdAt: now, updatedAt: now };
    d.notes.unshift(existing);
  }
  d.notes.sort((a, b) => b.updatedAt - a.updatedAt);
  store.save();
  broadcast('notes:updated', d.notes);
  return existing;
}

// ---------- Pornire ----------

if (!app.requestSingleInstanceLock()) {
  app.quit();
} else {
  app.on('second-instance', () => { showBuddy(); togglePanel('clipboard'); });

  app.whenReady().then(() => {
    if (process.platform === 'win32') app.setAppUserModelId('com.madalinas94.desktopbuddy');
    store.get();
    registerIpc();
    createBuddyWindow();
    createPanelWindow();
    createTray();
    startClipboardWatcher();
    initSessions();
  });

  app.on('window-all-closed', e => e.preventDefault());
  app.on('before-quit', () => { sessions.shutdown(); store.flush(); });
}
