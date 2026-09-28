const { app, BrowserWindow, ipcMain, clipboard, ClipboardItem, screen, Tray, Menu, nativeImage, shell, Notification, globalShortcut } = require('electron');
const path = require('path');
const crypto = require('crypto');
const store = require('./src/store');
const ai = require('./src/ai');
const sessions = require('./src/sessions');
const mail = require('./src/mail');
const mailscan = require('./src/mailscan');
const mood = require('./src/mood');
const briefing = require('./src/briefing');
const today = require('./src/today');
const cards = require('./src/cards');

const BUDDY_W = 170;
const BUDDY_H = 210;
const PANEL_W = 480;
const PANEL_H = 640;
const TIMER_W = 310;
const TIMER_H = 66;
const BUBBLE_W = 280;
const QUICK_W = 620;
const QUICK_H = 460;
const STICKY_W = 270;
const STICKY_H = 290;
const STICKY_COLORS = ['ivory', 'blush', 'sage', 'champagne', 'powder', 'noir'];
const STICKY_DECOS = ['tape', 'pin', 'clip', 'none'];

let buddyWin = null;
let panelWin = null;
let timerWin = null;
let timerHidden = false; // ascuns explicit de utilizator
let bubbleWin = null;
let bubbleTimer = null;
let bubbleTab = null;
let bubbleHeight = 90;
let quickWin = null;
let lastSessionId = null;
let lastCard = null;
const stickyWins = new Map(); // id notiță → fereastră
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

// ---------- Bula de dialog a lui Mady ----------

function createBubbleWindow() {
  bubbleWin = new BrowserWindow({
    width: BUBBLE_W, height: bubbleHeight,
    show: false,
    frame: false,
    transparent: true,
    resizable: false,
    hasShadow: false,
    skipTaskbar: true,
    alwaysOnTop: true,
    focusable: false,
    maximizable: false,
    fullscreenable: false,
    backgroundColor: '#00000000',
    webPreferences: { preload: path.join(__dirname, 'preload.js') }
  });
  bubbleWin.setAlwaysOnTop(true, 'floating');
  bubbleWin.loadFile(path.join(__dirname, 'renderer', 'bubble.html'));
  bubbleWin.on('closed', () => { bubbleWin = null; });
}

// Deasupra lui Mady; dacă nu e loc sus, în lateral.
function positionBubble() {
  if (!bubbleWin || !buddyWin) return;
  const b = buddyWin.getBounds();
  const area = screen.getDisplayMatching(b).workArea;
  let x = Math.round(b.x + b.width / 2 - BUBBLE_W / 2);
  let y = b.y - bubbleHeight + 14;
  let side = 'bottom';
  if (y < area.y) {
    y = b.y + 10;
    x = b.x - BUBBLE_W + 6;
    side = 'right';
    if (x < area.x) { x = b.x + b.width - 6; side = 'left'; }
  }
  x = Math.max(area.x, Math.min(x, area.x + area.width - BUBBLE_W));
  bubbleWin.setBounds({ x, y: Math.round(y), width: BUBBLE_W, height: bubbleHeight });
  bubbleWin.webContents.send('bubble:side', side);
}

function say(text, { tab = null, ms = 9000, state = null } = {}) {
  if (!settings().buddySpeech || !text) return;
  if (!buddyWin || !buddyWin.isVisible()) return;
  mood.noteSpoke();
  if (state) mood.flash(state, Math.min(ms, 8000));
  bubbleTab = tab;
  if (!bubbleWin) createBubbleWindow();
  const show = () => {
    if (!bubbleWin) return;
    bubbleWin.webContents.send('bubble:show', { text, name: settings().buddyName, clickable: !!tab });
    positionBubble();
    bubbleWin.showInactive();
    broadcast('buddy:talking', true);
  };
  if (bubbleWin.webContents.isLoading()) bubbleWin.webContents.once('did-finish-load', show);
  else show();
  clearTimeout(bubbleTimer);
  bubbleTimer = setTimeout(hideBubble, ms);
}

function hideBubble() {
  clearTimeout(bubbleTimer);
  if (bubbleWin) bubbleWin.hide();
  broadcast('buddy:talking', false);
}

// ---------- Sticky notes (notițe lipite pe desktop) ----------

function findNote(id) {
  return store.get().notes.find(n => n.id === id);
}

function defaultStickyBounds() {
  const area = screen.getPrimaryDisplay().workArea;
  const k = stickyWins.size % 6;
  return {
    x: Math.round(area.x + area.width - STICKY_W - 260 - k * 34),
    y: Math.round(area.y + 70 + k * 34),
    w: STICKY_W,
    h: STICKY_H
  };
}

function createStickyWindow(note) {
  const st = note.sticky;
  const pos = isOnScreen(st.x, st.y, st.w, st.h) ? st : { ...st, ...defaultStickyBounds() };
  const w = new BrowserWindow({
    width: pos.w, height: pos.h, x: pos.x, y: pos.y,
    show: false,
    frame: false,
    transparent: true,
    resizable: false, // redimensionare proprie (colțul din dreapta-jos), ca fereastra să rămână transparentă
    hasShadow: false,
    skipTaskbar: true,
    alwaysOnTop: !!st.onTop,
    maximizable: false,
    minimizable: false,
    fullscreenable: false,
    backgroundColor: '#00000000',
    webPreferences: { preload: path.join(__dirname, 'preload.js') }
  });
  w.loadFile(path.join(__dirname, 'renderer', 'sticky.html'), { query: { id: note.id } });
  w.once('ready-to-show', () => w.showInactive());
  let t;
  w.on('move', () => {
    clearTimeout(t);
    t = setTimeout(() => saveStickyBounds(note.id), 400);
  });
  w.on('closed', () => stickyWins.delete(note.id));
  stickyWins.set(note.id, w);
  return w;
}

function saveStickyBounds(id) {
  const n = findNote(id);
  const w = stickyWins.get(id);
  if (!n || !n.sticky || !w || w.isDestroyed()) return;
  const b = w.getBounds();
  if (!n.sticky.collapsed) Object.assign(n.sticky, { x: b.x, y: b.y, w: b.width, h: b.height });
  else Object.assign(n.sticky, { x: b.x, y: b.y });
  store.save();
}

function pinNote(id, opts = {}) {
  const n = findNote(id);
  if (!n) return null;
  if (!n.sticky) {
    // revine cu aspectul și locul de dinainte, dacă a mai fost pe desktop
    n.sticky = n.lastSticky
      ? { ...n.lastSticky, collapsed: false }
      : { ...defaultStickyBounds(), color: opts.color || 'ivory', deco: opts.deco || 'tape', onTop: false, collapsed: false };
    store.save();
  }
  const w = stickyWins.get(id);
  if (w && !w.isDestroyed()) w.show();
  else createStickyWindow(n);
  broadcast('notes:updated', store.get().notes);
  return n;
}

function unpinNote(id) {
  const n = findNote(id);
  if (n) {
    // o notiță lipită goală nu merită păstrată
    if (!n.title.trim() && !n.body.trim()) store.get().notes = store.get().notes.filter(x => x.id !== id);
    else {
      if (n.sticky) n.lastSticky = { ...n.sticky, collapsed: false };
      n.sticky = null;
    }
    store.save();
  }
  const w = stickyWins.get(id);
  if (w && !w.isDestroyed()) w.close();
  broadcast('notes:updated', store.get().notes);
}

function newSticky() {
  const n = saveNote({ title: '', body: '' });
  pinNote(n.id);
  return n;
}

function showAllStickies() {
  for (const n of store.get().notes) if (n.sticky) pinNote(n.id);
  for (const w of stickyWins.values()) { w.showInactive(); w.moveTop(); }
}

function restoreStickies() {
  for (const n of store.get().notes) if (n.sticky) createStickyWindow(n);
}

// ---------- Fereastra rapidă (scurtătura globală) ----------

function createQuickWindow() {
  quickWin = new BrowserWindow({
    width: QUICK_W, height: QUICK_H,
    show: false,
    frame: false,
    transparent: true,
    resizable: false,
    hasShadow: false,
    skipTaskbar: true,
    alwaysOnTop: true,
    maximizable: false,
    fullscreenable: false,
    backgroundColor: '#00000000',
    webPreferences: { preload: path.join(__dirname, 'preload.js') }
  });
  quickWin.setAlwaysOnTop(true, 'pop-up-menu');
  quickWin.loadFile(path.join(__dirname, 'renderer', 'quick.html'));
  quickWin.on('blur', () => quickWin && quickWin.hide());
  quickWin.on('closed', () => { quickWin = null; });
}

async function openQuick(prefill) {
  if (!quickWin) createQuickWindow();
  const cursor = screen.getCursorScreenPoint();
  const area = screen.getDisplayNearestPoint(cursor).workArea;
  quickWin.setBounds({
    x: Math.round(area.x + (area.width - QUICK_W) / 2),
    y: Math.round(area.y + area.height * 0.18),
    width: QUICK_W, height: QUICK_H
  });
  const text = typeof prefill === 'string' ? prefill : await clipboard.readText();
  const send = () => quickWin && quickWin.webContents.send('quick:open', { clipboard: text || '', fromItem: typeof prefill === 'string' });
  if (quickWin.webContents.isLoading()) quickWin.webContents.once('did-finish-load', send);
  else send();
  quickWin.show();
  quickWin.focus();
}

function toggleQuick() {
  if (quickWin && quickWin.isVisible()) quickWin.hide();
  else openQuick();
}

let registeredHotkey = null;
function registerHotkey(accel) {
  if (registeredHotkey) globalShortcut.unregister(registeredHotkey);
  registeredHotkey = null;
  if (!accel) return true;
  try {
    if (globalShortcut.register(accel, toggleQuick)) {
      registeredHotkey = accel;
      return true;
    }
  } catch {
    // acceleratorul nu e valid
  }
  return false;
}

function hotkeyLabel(accel) {
  return String(accel || '').replace('CommandOrControl', process.platform === 'darwin' ? 'Cmd' : 'Ctrl');
}

function notify(title, body, onClick) {
  if (!Notification.isSupported()) return;
  const n = new Notification({ title, body, icon: path.join(__dirname, 'assets', 'icon.png') });
  if (onClick) n.on('click', onClick);
  n.show();
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
    { label: `Întreab-o pe Mady (${hotkeyLabel(settings().quickHotkey)})`, click: () => openQuick() },
    { label: 'Azi (planner)', click: () => togglePanel('today') },
    { label: 'Notiță nouă pe desktop', click: newSticky },
    { label: 'Arată notițele lipite', click: showAllStickies },
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
  for (const w of [buddyWin, panelWin, timerWin, bubbleWin, quickWin, ...stickyWins.values()]) if (w && !w.isDestroyed()) w.webContents.send(channel, payload);
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
  return {
    ...settings(), hasApiKey: !!store.getApiKey(), hasMailPassword: !!store.getMailPassword(),
    hotkeyActive: registeredHotkey === settings().quickHotkey, hotkeyLabel: hotkeyLabel(settings().quickHotkey)
  };
}

// ---------- IPC ----------

function registerIpc() {
  // roboțel
  ipcMain.on('buddy:move', (_e, { x, y }) => {
    if (!buddyWin) return;
    const { width, height } = buddySize();
    buddyWin.setBounds({ x: Math.round(x), y: Math.round(y), width, height });
    if (panelWin && panelWin.isVisible()) positionPanel();
    if (bubbleWin && bubbleWin.isVisible()) positionBubble();
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
      { label: 'Notiță nouă pe desktop', click: newSticky },
      { label: `Întreab-o pe Mady (${hotkeyLabel(settings().quickHotkey)})`, click: () => openQuick() },
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
    if (patch && 'quickHotkey' in patch) {
      const old = settings().quickHotkey;
      if (!registerHotkey(patch.quickHotkey)) {
        registerHotkey(old);
        return { ...publicSettings(), error: `Scurtătura „${hotkeyLabel(patch.quickHotkey)}” nu e validă sau e folosită de alt program.` };
      }
    }
    const allowed = Object.keys(store.DEFAULT_DATA.settings);
    for (const k of Object.keys(patch || {})) if (allowed.includes(k)) settings()[k] = patch[k];
    store.save();
    applySettings();
    if ('clipboardLimit' in patch) { trimClipboard(); broadcast('clipboard:updated', store.get().clipboard); }
    if (Object.keys(patch).some(k => k.startsWith('mail'))) broadcast('mail:scanState', mailscan.state());
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
    const sw = stickyWins.get(id);
    if (sw && !sw.isDestroyed()) sw.close();
    const d = store.get();
    d.notes = d.notes.filter(n => n.id !== id);
    store.save();
    return d.notes;
  });

  // sesiuni / timer
  ipcMain.handle('session:current', () => currentSessionState());
  ipcMain.handle('session:start', (_e, title, mode) => { sessions.start(title, mode); return currentSessionState(); });
  ipcMain.handle('session:modes', () => sessions.FOCUS_MODES);
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
    broadcast('mail:scanState', mailscan.state());
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
  ipcMain.handle('mail:scanState', () => mailscan.state());
  ipcMain.handle('mail:scanNow', async () => {
    await mailscan.scan({ manual: true });
    return mailscan.state();
  });
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

  // planner-ul zilei
  ipcMain.handle('today:state', () => today.state());
  ipcMain.handle('today:update', (_e, patch) => {
    const before = today.getDay();
    const day = today.updateDay(patch || {});
    const filled = day.top3.filter(t => t.text.trim());
    const wasAll = before.top3.filter(t => t.text.trim()).every(t => t.done);
    if (filled.length === 3 && filled.every(t => t.done) && !(wasAll && before.top3.filter(t => t.text.trim()).length === 3)) {
      say(mood.line('top3Done'), { state: 'celebrate', ms: 10000 });
    }
    if (patch && 'water' in patch && day.water === 8 && before.water < 8) say(mood.line('waterDone'), { state: 'happy', ms: 7000 });
    return today.state();
  });
  ipcMain.handle('habit:toggle', (_e, id, k) => {
    const res = today.toggleHabit(id, k);
    const h = res.find(x => x.id === id);
    if (h && h.streak >= 3 && (!k || k === today.key()) && h.week[(new Date().getDay() + 6) % 7]) {
      say(mood.line('streak', { n: h.streak, name: h.name }), { state: 'happy', ms: 7000 });
    }
    return today.state();
  });
  ipcMain.handle('habit:add', (_e, name) => { today.addHabit(name); return today.state(); });
  ipcMain.handle('habit:remove', (_e, id) => { today.removeHabit(id); return today.state(); });

  // carduri de împărtășit
  ipcMain.handle('card:make', async (_e, kind, format) => {
    try {
      lastCard = await cards.render(kind, format);
      return { ok: true, file: lastCard.file, dataUrl: lastCard.dataUrl };
    } catch (err) {
      return { ok: false, error: err.message };
    }
  });
  ipcMain.handle('card:copy', async () => {
    if (!lastCard) return false;
    // Electron 44: clipboard-ul primește imaginea ca ClipboardItem (PNG)
    const png = lastCard.image.toPNG();
    await clipboard.write([new ClipboardItem({ 'image/png': new Blob([png], { type: 'image/png' }) })]);
    return true;
  });
  ipcMain.on('card:show', () => { if (lastCard) shell.showItemInFolder(lastCard.file); });

  // ghidul de bun venit
  ipcMain.handle('onboarding:done', (_e, patch) => {
    const allowed = ['userName', 'weeklyGoalHours', 'morningBrief', 'buddySpeech'];
    for (const k of allowed) if (patch && k in patch) settings()[k] = patch[k];
    store.get().onboarded = true;
    store.save();
    broadcast('settings:updated', publicSettings());
    const n = settings().userName;
    say(`${n ? `Încântată, ${n}.` : 'Încântată.'} De acum mă ocup eu de ordine, tu de strălucire.`, { state: 'celebrate', ms: 9000 });
    return publicSettings();
  });

  // sticky notes
  ipcMain.handle('sticky:get', (_e, id) => findNote(id) || null);
  ipcMain.handle('sticky:pin', (_e, id) => pinNote(id));
  ipcMain.handle('sticky:new', () => newSticky());
  ipcMain.on('sticky:unpin', (_e, id) => unpinNote(id));
  ipcMain.handle('sticky:delete', (_e, id) => {
    store.get().notes = store.get().notes.filter(n => n.id !== id);
    store.save();
    const w = stickyWins.get(id);
    if (w && !w.isDestroyed()) w.close();
    broadcast('notes:updated', store.get().notes);
    return true;
  });
  ipcMain.handle('sticky:style', (_e, id, patch) => {
    const n = findNote(id);
    if (!n || !n.sticky) return null;
    if (STICKY_COLORS.includes(patch.color)) n.sticky.color = patch.color;
    if (STICKY_DECOS.includes(patch.deco)) n.sticky.deco = patch.deco;
    if ('onTop' in patch) {
      n.sticky.onTop = !!patch.onTop;
      const w = stickyWins.get(id);
      if (w) w.setAlwaysOnTop(n.sticky.onTop, 'floating');
    }
    store.save();
    broadcast('notes:updated', store.get().notes);
    return n;
  });
  ipcMain.on('sticky:resize', (e, id, width, height) => {
    const w = stickyWins.get(id);
    if (!w) return;
    const b = w.getBounds();
    w.setBounds({ x: b.x, y: b.y, width: Math.max(200, Math.min(700, Math.round(width))), height: Math.max(170, Math.min(800, Math.round(height))) });
  });
  ipcMain.on('sticky:resized', (_e, id) => saveStickyBounds(id));
  ipcMain.handle('sticky:collapse', (_e, id, collapsed) => {
    const n = findNote(id);
    const w = stickyWins.get(id);
    if (!n || !n.sticky || !w) return null;
    const b = w.getBounds();
    if (collapsed && !n.sticky.collapsed) {
      Object.assign(n.sticky, { w: b.width, h: b.height });
      w.setBounds({ x: b.x, y: b.y, width: b.width, height: 76 });
    } else if (!collapsed) {
      w.setBounds({ x: b.x, y: b.y, width: n.sticky.w, height: n.sticky.h });
    }
    n.sticky.collapsed = !!collapsed;
    store.save();
    return n;
  });

  // bula
  ipcMain.on('bubble:size', (_e, h) => {
    bubbleHeight = Math.max(60, Math.min(260, Math.round(h)));
    positionBubble();
  });
  ipcMain.on('bubble:click', () => {
    const tab = bubbleTab;
    hideBubble();
    if (tab) togglePanel(tab);
  });
  ipcMain.on('bubble:close', hideBubble);

  // fereastra rapidă
  ipcMain.on('quick:hide', () => quickWin && quickWin.hide());
  ipcMain.on('quick:openFor', (_e, text) => openQuick(String(text || '')));
  ipcMain.handle('quick:action', async (_e, { action, text, lang }) => {
    try {
      return { ok: true, text: await ai.runAction(action, text, lang, settings(), store.getApiKey()) };
    } catch (err) {
      return { ok: false, error: err.message };
    }
  });
  ipcMain.handle('quick:ask', async (_e, question) => {
    try {
      return { ok: true, text: await ai.complete(String(question), settings(), store.getApiKey(),
        `Întrebarea ta: „${String(question).slice(0, 200)}”. În modul demo nu pot răspunde cu adevărat.`) };
    } catch (err) {
      return { ok: false, error: err.message };
    }
  });
  ipcMain.handle('quick:copy', async (_e, text) => {
    lastClipboardText = String(text);
    await clipboard.writeText(String(text));
    return true;
  });
  ipcMain.on('quick:toChat', (_e, { question, answer }) => {
    const d = store.get();
    d.chat.push({ role: 'user', content: String(question), at: Date.now() });
    d.chat.push({ role: 'assistant', content: String(answer), at: Date.now() });
    store.save();
    broadcast('ai:updated', d.chat);
    if (quickWin) quickWin.hide();
    togglePanel('ai');
  });

  // briefing
  ipcMain.handle('brief:now', async () => {
    const r = await runBriefing(true);
    return { chat: store.get().chat, ok: !!r };
  });
  ipcMain.handle('buddy:state', () => mood.current());

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
    activeSec: s.activeSec, now: Date.now(), timerVisible: !!timerWin && !timerHidden,
    pomo: s.pomo ? { ...s.pomo } : null
  };
}

function initSessions() {
  sessions.init({
    onChange(s) {
      if (s && !timerWin) { timerHidden = false; createTimerWindow(); }
      if (!s && timerWin) timerWin.close();
      if (s && s.id !== lastSessionId) say(mood.line('sessionStart'), { tab: 'timer', ms: 6000 });
      lastSessionId = s ? s.id : null;
      mood.refresh();
      broadcast('session:changed', currentSessionState());
    },
    onHour(hours, s) {
      const text = hours === 1 ? '1 Hour has passed' : `${hours} Hours have passed`;
      notify(text, `„${s.title}” – ${hours === 1 ? 'o oră' : hours + ' ore'} de lucru. Ia o pauză scurtă și continuă.`);
      broadcast('session:hour', { hours, title: s.title });
      if (s.pomo) return; // în modul Pomodoro pauzele vin oricum la timp
      say(mood.line('hour'), { state: 'happy', ms: 9000 });
    },
    onPhase(phase, s) {
      const p = s.pomo;
      if (phase === 'break') {
        const long = p.count % 4 === 0;
        const min = long ? p.longBreakMin : p.breakMin;
        notify(`Pauză${long ? ' lungă' : ''}: ${min} minute`, `Runda ${p.count} de focus e gata. Ridică-te, respiră, bea apă.`);
        say(mood.line(long ? 'longBreak' : 'breakStart', { min, n: p.count }), { state: 'celebrate', ms: 12000 });
      } else {
        notify('Înapoi la focus', `Runda ${p.count + 1}: ${p.focusMin} minute pentru „${s.title}”.`);
        say(mood.line('focusBack', { min: p.focusMin }), { ms: 8000 });
      }
      broadcast('session:phase', { phase, pomo: { ...p } });
    },
    onEnd(rep) {
      notify('Sesiune încheiată', `„${rep.title}”: ${sessions.fmt(rep.durationSec)} total, ${sessions.fmt(rep.activeSec)} activ.`);
      togglePanel('timer');
      broadcast('session:ended', rep);
      const long = rep.durationSec >= 25 * 60;
      const dur = rep.durationSec < 60 ? 'sub un minut' : sessions.fmt(rep.durationSec);
      say(mood.line(long ? 'sessionEndLong' : 'sessionEndShort', { dur }),
        { tab: 'timer', state: long ? 'celebrate' : 'happy', ms: 9000 });
    }
  });
  if (sessions.current()) createTimerWindow();
  lastSessionId = sessions.current()?.id || null;
}

function initMailScan() {
  mailscan.init({
    onStart() {
      broadcast('mail:scanState', mailscan.state());
    },
    onResult(r, manual) {
      broadcast('mail:scanState', mailscan.state());
      if (r.error) {
        if (!manual) notify('Inbox: scanarea a eșuat', r.error, () => togglePanel('inbox'));
        return;
      }
      if (!r.count && !manual && !settings().mailNotifyEmpty) return;
      const title = r.count
        ? `${r.count} ${r.count === 1 ? 'email necitit' : 'emailuri necitite'} primite azi`
        : 'Inbox curat: niciun email necitit azi';
      const body = r.important.length
        ? 'Important: ' + r.important.map(m => `${m.from} – ${m.subject}`).join('; ')
        : `${settings().buddyName} a verificat inboxul.`;
      notify(title, body, () => togglePanel('inbox'));
      broadcast('mail:scanToast', r.count);
      if (r.count) {
        const top = r.important[0];
        say(`Ai ${r.count} ${r.count === 1 ? 'email necitit' : 'emailuri necitite'} azi.` +
          (top ? ` Cel mai important: ${top.from} – „${top.subject}”.` : ''), { tab: 'inbox', state: 'alert', ms: 12000 });
      }
    }
  });
}

function initMood() {
  mood.init({
    getSession: () => sessions.current(),
    settings,
    onState(state) { broadcast('buddy:state', state); },
    onWake(sleptMin) {
      if (briefing.due()) runBriefing();
      else if (sleptMin >= 10) say(mood.line('wake'), { state: 'happy', ms: 7000 });
    },
    say: text => say(text, { ms: 10000 })
  });
}

async function runBriefing(manual = false) {
  if (!manual && !briefing.due()) return null;
  const r = await briefing.generate();
  if (!r) return null;
  broadcast('ai:updated', store.get().chat);
  if (!manual) {
    say(`${new Date().getHours() < 12 ? 'Bună dimineața' : 'Bună ziua'}! Ți-am pregătit briefingul zilei.` +
      (r.emails ? ` Ai ${r.emails} ${r.emails === 1 ? 'email nou' : 'emailuri noi'}.` : ''), { tab: 'ai', state: 'celebrate', ms: 12000 });
  }
  if (settings().briefVoice && panelWin) panelWin.webContents.send('tts:speak', r.text);
  return r;
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
    initMailScan();
    initMood();
    registerHotkey(settings().quickHotkey);
    restoreStickies();
    // la pornire: briefingul zilei (dacă n-a fost încă) sau un salut
    setTimeout(async () => {
      if (!store.get().onboarded) {
        togglePanel('today');
        panelWin.webContents.send('onboarding:show');
        say('Bună! Sunt Mady, noua ta asistentă. Hai să ne cunoaștem.', { state: 'happy', ms: 9000 });
        return;
      }
      if (briefing.due()) await runBriefing();
      else say(mood.line('welcome'), { state: 'happy', ms: 7000 });
    }, 4000);
    // pentru calculatoarele lăsate pornite peste noapte
    setInterval(() => { if (briefing.due()) runBriefing(); }, 10 * 60 * 1000);
  });

  app.on('window-all-closed', e => e.preventDefault());
  app.on('before-quit', () => { sessions.shutdown(); mailscan.shutdown(); mood.shutdown(); store.flush(); });
  app.on('will-quit', () => globalShortcut.unregisterAll());
}
