const { app, BrowserWindow, ipcMain, clipboard, screen, Tray, Menu, nativeImage, shell } = require('electron');
const path = require('path');
const crypto = require('crypto');
const store = require('./src/store');
const ai = require('./src/ai');

const BUDDY_W = 170;
const BUDDY_H = 210;
const PANEL_W = 400;
const PANEL_H = 560;

let buddyWin = null;
let panelWin = null;
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

// ---------- Tray ----------

function createTray() {
  const img = nativeImage.createFromPath(path.join(__dirname, 'assets', 'icon.png')).resize({ width: 16, height: 16 });
  tray = new Tray(img);
  tray.setToolTip('Desktop Buddy');
  tray.setContextMenu(Menu.buildFromTemplate([
    { label: 'Deschide panoul', click: () => togglePanel('clipboard') },
    { label: 'Arată roboțelul', click: showBuddy },
    { label: 'Ascunde roboțelul', click: () => buddyWin && buddyWin.hide() },
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
  for (const w of [buddyWin, panelWin]) if (w && !w.isDestroyed()) w.webContents.send(channel, payload);
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
  return { ...settings(), hasApiKey: !!store.getApiKey() };
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
  });

  app.on('window-all-closed', e => e.preventDefault());
  app.on('before-quit', () => store.flush());
}
