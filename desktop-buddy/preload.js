const { contextBridge, ipcRenderer, webUtils } = require('electron');

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
    menu: () => ipcRenderer.send('buddy:menu'),
    state: () => ipcRenderer.invoke('buddy:state'),
    onState: on('buddy:state'),
    onTalking: on('buddy:talking')
  },
  today: {
    state: () => ipcRenderer.invoke('today:state'),
    update: patch => ipcRenderer.invoke('today:update', patch),
    toggleHabit: (id, k) => ipcRenderer.invoke('habit:toggle', id, k),
    addHabit: name => ipcRenderer.invoke('habit:add', name),
    removeHabit: id => ipcRenderer.invoke('habit:remove', id)
  },
  card: {
    make: (kind, format) => ipcRenderer.invoke('card:make', kind, format),
    copy: () => ipcRenderer.invoke('card:copy'),
    show: () => ipcRenderer.send('card:show')
  },
  mantra: {
    get: () => ipcRenderer.invoke('mantra:get'),
    fav: (k, fav) => ipcRenderer.invoke('mantra:fav', k, fav),
    favorites: () => ipcRenderer.invoke('mantra:favorites'),
    close: () => ipcRenderer.send('mantra:close'),
    show: () => ipcRenderer.send('mantra:show'),
    openToday: () => ipcRenderer.send('mantra:openToday'),
    size: h => ipcRenderer.send('mantra:size', h),
    image: () => ipcRenderer.invoke('mantra:image')
  },
  vision: {
    open: () => ipcRenderer.send('vision:open'),
    close: () => ipcRenderer.send('vision:close'),
    get: () => ipcRenderer.invoke('vision:get'),
    add: (paths, category) => ipcRenderer.invoke('vision:add', paths, category),
    pick: category => ipcRenderer.invoke('vision:pick', category),
    fillSlot: (id, file) => ipcRenderer.invoke('vision:fillSlot', id, file),
    addAreas: ids => ipcRenderer.invoke('vision:addAreas', ids),
    nextAff: id => ipcRenderer.invoke('vision:nextAff', id),
    addText: (text, style) => ipcRenderer.invoke('vision:addText', text, style),
    update: (id, patch) => ipcRenderer.invoke('vision:update', id, patch),
    remove: id => ipcRenderer.invoke('vision:remove', id),
    move: (id, delta) => ipcRenderer.invoke('vision:move', id, delta),
    setTitle: (t, st) => ipcRenderer.invoke('vision:setTitle', t, st),
    exportImage: () => ipcRenderer.invoke('vision:export'),
    pathFor: file => { try { return webUtils.getPathForFile(file); } catch { return ''; } }
  },
  month: {
    data: () => ipcRenderer.invoke('month:data')
  },
  onboarding: {
    onShow: on('onboarding:show'),
    done: patch => ipcRenderer.invoke('onboarding:done', patch)
  },
  sticky: {
    id: () => new URLSearchParams(location.search).get('id'),
    get: id => ipcRenderer.invoke('sticky:get', id),
    pin: id => ipcRenderer.invoke('sticky:pin', id),
    create: () => ipcRenderer.invoke('sticky:new'),
    unpin: id => ipcRenderer.send('sticky:unpin', id),
    remove: id => ipcRenderer.invoke('sticky:delete', id),
    style: (id, patch) => ipcRenderer.invoke('sticky:style', id, patch),
    resize: (id, w, h) => ipcRenderer.send('sticky:resize', id, w, h),
    resized: id => ipcRenderer.send('sticky:resized', id),
    collapse: (id, c) => ipcRenderer.invoke('sticky:collapse', id, c)
  },
  bubble: {
    onShow: on('bubble:show'),
    onSide: on('bubble:side'),
    size: h => ipcRenderer.send('bubble:size', h),
    click: () => ipcRenderer.send('bubble:click'),
    close: () => ipcRenderer.send('bubble:close')
  },
  quick: {
    onOpen: on('quick:open'),
    hide: () => ipcRenderer.send('quick:hide'),
    openFor: text => ipcRenderer.send('quick:openFor', text),
    action: (action, text, lang) => ipcRenderer.invoke('quick:action', { action, text, lang }),
    ask: question => ipcRenderer.invoke('quick:ask', question),
    copy: text => ipcRenderer.invoke('quick:copy', text),
    toChat: (question, answer) => ipcRenderer.send('quick:toChat', { question, answer })
  },
  brief: {
    now: () => ipcRenderer.invoke('brief:now')
  },
  tts: {
    onSpeak: on('tts:speak')
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
    start: (title, mode) => ipcRenderer.invoke('session:start', title, mode),
    modes: () => ipcRenderer.invoke('session:modes'),
    onPhase: on('session:phase'),
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
    clear: () => ipcRenderer.invoke('ai:clear'),
    onUpdated: on('ai:updated')
  }
});
