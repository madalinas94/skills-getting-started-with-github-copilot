const api = window.buddy;
const bubble = document.getElementById('bubble');

function reportSize() {
  // înălțimea conținutului + marginile body, ca fereastra să aibă exact mărimea bulei
  api.bubble.size(Math.ceil(bubble.getBoundingClientRect().height) + 22);
}

api.bubble.onShow(({ text, name, clickable }) => {
  document.getElementById('name').textContent = name;
  document.getElementById('text').textContent = text;
  bubble.classList.toggle('clickable', !!clickable);
  bubble.style.animation = 'none';
  void bubble.offsetWidth;
  bubble.style.animation = '';
  reportSize();
});
api.bubble.onSide(side => { bubble.dataset.side = side; });

bubble.addEventListener('click', e => {
  if (e.target.id === 'close') return api.bubble.close();
  api.bubble.click();
});

function applyTheme(s) { document.documentElement.dataset.theme = s.themeResolved || s.theme; }
api.settings.get().then(applyTheme);
api.settings.onUpdate(applyTheme);
