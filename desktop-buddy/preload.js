const { contextBridge, ipcRenderer } = require('electron');

const on = channel => cb => {
  const listener = (_e, payload) => cb(payload);
  ipcRenderer.on(channel, listener);
  return () => ipcRenderer.removeListener(channel, listener);
};

contextBridge.exposeInMainWorld('buddy', {
  buddy: {
    move: (x, y) => ipcRenderer.send('buddy:move', { x, y }),
    moved: () => ipcRenderer.send('buddy:moved'),
    position: () => ipcRenderer.invoke('buddy:position'),
    click: () => ipcRenderer.send('buddy:click'),
    menu: () => ipcRenderer.send('buddy:menu')
  },
  panel: {
    hide: () => ipcRenderer.send('panel:hide'),
    onTab: on('panel:tab')
  },
  app: {
    quit: () => ipcRenderer.send('app:quit'),
    openExternal: url => ipcRenderer.send('app:openExternal', url)
  },
  settings: {
    get: () => ipcRenderer.invoke('settings:get'),
    set: patch => ipcRenderer.invoke('settings:set', patch),
    setApiKey: key => ipcRenderer.invoke('settings:setApiKey', key),
    providers: () => ipcRenderer.invoke('settings:providers'),
    reset: () => ipcRenderer.invoke('settings:reset'),
    onUpdate: on('settings:updated')
  },
  clipboard: {
    list: () => ipcRenderer.invoke('clipboard:list'),
    copy: id => ipcRenderer.invoke('clipboard:copy', id),
    pin: id => ipcRenderer.invoke('clipboard:pin', id),
    remove: id => ipcRenderer.invoke('clipboard:delete', id),
    clear: () => ipcRenderer.invoke('clipboard:clear'),
    toNote: id => ipcRenderer.invoke('clipboard:toNote', id),
    onUpdate: on('clipboard:updated')
  },
  notes: {
    list: () => ipcRenderer.invoke('notes:list'),
    save: note => ipcRenderer.invoke('notes:save', note),
    remove: id => ipcRenderer.invoke('notes:delete', id),
    onUpdate: on('notes:updated')
  },
  session: {
    current: () => ipcRenderer.invoke('session:current'),
    start: title => ipcRenderer.invoke('session:start', title),
    pause: () => ipcRenderer.invoke('session:pause'),
    resume: () => ipcRenderer.invoke('session:resume'),
    stop: () => ipcRenderer.invoke('session:stop'),
    history: () => ipcRenderer.invoke('session:history'),
    report: id => ipcRenderer.invoke('session:report', id),
    feedback: id => ipcRenderer.invoke('session:feedback', id),
    onChange: on('session:changed'),
    onHour: on('session:hour'),
    onEnded: on('session:ended')
  },
  timer: {
    show: () => ipcRenderer.send('timer:show'),
    hide: () => ipcRenderer.send('timer:hide'),
    setOpacity: v => ipcRenderer.invoke('timer:opacity', v),
    getOpacity: () => ipcRenderer.invoke('timer:getOpacity'),
    openPanel: () => ipcRenderer.send('timer:openPanel'),
    onVisible: on('timer:visible')
  },
  mail: {
    setPassword: pass => ipcRenderer.invoke('mail:setPassword', pass),
    fetch: () => ipcRenderer.invoke('mail:fetch'),
    list: () => ipcRenderer.invoke('mail:list'),
    summary: uid => ipcRenderer.invoke('mail:summary', uid),
    brief: () => ipcRenderer.invoke('mail:brief'),
    scanState: () => ipcRenderer.invoke('mail:scanState'),
    scanNow: () => ipcRenderer.invoke('mail:scanNow'),
    onScanState: on('mail:scanState'),
    onScanToast: on('mail:scanToast')
  },
  ai: {
    history: () => ipcRenderer.invoke('ai:history'),
    send: text => ipcRenderer.invoke('ai:send', text),
    clear: () => ipcRenderer.invoke('ai:clear')
  }
});
