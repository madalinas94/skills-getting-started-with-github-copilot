const el = document.getElementById('buddy');
const toastEl = document.getElementById('toast');
let drag = null;

el.addEventListener('pointerdown', e => {
  if (e.button !== 0) return;
  el.setPointerCapture(e.pointerId);
  drag = {
    startX: e.screenX,
    startY: e.screenY,
    winX: e.screenX - e.clientX,
    winY: e.screenY - e.clientY,
    moved: false
  };
});

el.addEventListener('pointermove', e => {
  if (!drag) return;
  const dx = e.screenX - drag.startX;
  const dy = e.screenY - drag.startY;
  if (!drag.moved && Math.hypot(dx, dy) < 5) return;
  drag.moved = true;
  el.classList.add('dragging');
  window.buddy.buddy.move(drag.winX + dx, drag.winY + dy);
});

el.addEventListener('pointerup', e => {
  if (!drag) return;
  el.releasePointerCapture(e.pointerId);
  el.classList.remove('dragging');
  if (drag.moved) window.buddy.buddy.moved();
  else window.buddy.buddy.click();
  drag = null;
});

el.addEventListener('contextmenu', e => {
  e.preventDefault();
  window.buddy.buddy.menu();
});

let toastTimer;
// când Mady vorbește prin bule, etichetele mici ar dubla mesajul
let speechOn = true;
window.buddy.settings.get().then(s => { speechOn = !!s.buddySpeech; });
window.buddy.settings.onUpdate(s => { speechOn = !!s.buddySpeech; });
function toast(text, ms = 1600) {
  toastEl.textContent = text;
  toastEl.classList.add('show');
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => toastEl.classList.remove('show'), ms);
}

window.buddy.clipboard.onUpdate(() => toast('Salvat'));

window.buddy.settings.get().then(s => { el.title = `${s.buddyName} — click pentru meniu, trage ca să mă muți`; });
window.buddy.settings.onUpdate(s => { el.title = `${s.buddyName} — click pentru meniu, trage ca să mă muți`; });

function applyTheme(s) { document.documentElement.dataset.theme = s.theme; }
window.buddy.settings.get().then(applyTheme);
window.buddy.settings.onUpdate(applyTheme);

window.buddy.session.onHour(({ hours }) => speechOn || toast(hours === 1 ? '1 Hour has passed' : `${hours} Hours have passed`, 8000));
window.buddy.mail.onScanToast(n => { if (n && !speechOn) toast(`✉ ${n} ${n === 1 ? 'email nou' : 'emailuri noi'}`, 8000); });

function setState(state) { el.dataset.state = state || 'idle'; }
window.buddy.buddy.state().then(setState);
window.buddy.buddy.onState(setState);
window.buddy.buddy.onTalking(t => el.classList.toggle('talking', !!t));
