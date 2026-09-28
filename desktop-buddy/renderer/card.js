// Construiește cardul „Ziua mea” / „Săptămâna mea” din datele primite de la procesul principal.
const MOODS = { radiant: 'radiantă', bine: 'bine', ok: 'ok', obosit: 'obosită', stresat: 'stresată' };

function h(tag, attrs = {}, children = []) {
  const n = document.createElement(tag);
  for (const [k, v] of Object.entries(attrs)) {
    if (k === 'text') n.textContent = v;
    else if (k === 'class') n.className = v;
    else n.setAttribute(k, v);
  }
  for (const c of [].concat(children)) if (c != null && c !== false) n.append(c);
  return n;
}

const cap = t => (t ? t[0].toUpperCase() + t.slice(1) : t);

function header(d, title) {
  return h('div', { class: 'head' }, [
    h('img', { class: 'medal', src: '../assets/icon.svg' }),
    h('div', {}, [
      h('div', { class: 'kicker', text: title }),
      h('div', { class: 'date', text: cap(d.kind === 'week' ? d.range : d.date) })
    ])
  ]);
}

function quote(d) {
  return h('div', { class: 'quote' }, [`„${d.quote.text}”`, h('span', { text: d.quote.author })]);
}

function foot(d) {
  return h('div', { class: 'foot' }, [h('span', { text: `${d.name} · Desktop Buddy` }), h('span', { text: '✦' })]);
}

function renderDay(d) {
  const card = document.getElementById('card');
  const pomo = Math.min(d.pomodoros, 12);
  const left = h('div', { class: 'section' }, [
    h('h3', { text: 'Top 3' }),
    h('div', { class: 'list' }, d.top3.length
      ? d.top3.map(t => h('div', { class: 'row' }, [h('span', { class: 'chk' + (t.done ? ' on' : '') }), h('span', { class: t.done ? 'done' : '', text: t.text })]))
      : [h('div', { class: 'grat', text: 'O zi liberă de liste.' })])
  ]);
  const right = h('div', { class: 'section' }, [
    h('h3', { text: 'Ritualuri' }),
    h('div', { class: 'list' }, d.habits.slice(0, 5).map(x => h('div', { class: 'row' }, [
      h('span', { class: 'chk' + (x.done ? ' on' : '') }),
      h('span', { text: x.name }),
      x.streak > 1 ? h('span', { class: 'streak', text: `${x.streak} zile` }) : null
    ])))
  ]);
  const extra = h('div', { class: 'cols' }, [
    h('div', { class: 'section' }, [
      h('h3', { text: 'Apă' }),
      h('div', { class: 'water' }, [...Array(8)].map((_, i) => h('i', { class: i < d.water ? 'on' : '' })))
    ]),
    h('div', { class: 'section' }, [
      h('h3', { text: 'Stare' }),
      h('div', { class: 'mood', text: d.mood ? MOODS[d.mood] || d.mood : '—' })
    ])
  ]);
  card.replaceChildren(
    header(d, 'Ziua mea'),
    d.intention ? h('div', { class: 'intention', text: `„${d.intention}”` }) : null,
    h('div', { class: 'stats' }, [
      h('div', {}, [h('div', { class: 'big', text: d.focus }), h('div', { class: 'big-label', text: 'de focus' })]),
      h('div', { class: 'mini' }, [
        h('div', {}, [h('b', { text: d.sessions }), d.sessions === 1 ? 'sesiune' : 'sesiuni']),
        h('div', {}, [h('b', { text: d.pomodoros }), 'pomodoro', pomo ? h('span', { class: 'dots' }, [...Array(pomo)].map(() => h('i'))) : null])
      ])
    ]),
    h('div', { class: 'rule' }),
    h('div', { class: 'cols' }, [left, right]),
    extra,
    d.gratitude ? h('div', { class: 'grat', text: `Recunoscătoare pentru: ${d.gratitude}` }) : null,
    quote(d),
    foot(d)
  );
}

function renderWeek(d) {
  const card = document.getElementById('card');
  const max = Math.max(4 * 3600, ...d.days.map(x => x.sec));
  const pct = Math.min(100, d.pct);
  const C = 2 * Math.PI * 90;
  const ring = h('div', { class: 'ring' });
  ring.innerHTML = `<svg viewBox="0 0 220 220"><circle cx="110" cy="110" r="90" fill="none" stroke="#e8dcc2" stroke-width="16"/>
    <circle cx="110" cy="110" r="90" fill="none" stroke="#b8955a" stroke-width="16" stroke-linecap="round" stroke-dasharray="${(C * pct / 100).toFixed(1)} ${C.toFixed(1)}"/></svg><b>${d.goal ? d.pct + '%' : '—'}</b>`;
  card.replaceChildren(
    header(d, 'Săptămâna mea'),
    h('div', { class: 'stats' }, [
      ring,
      h('div', {}, [
        h('div', { class: 'big', text: d.focus }),
        h('div', { class: 'big-label', text: d.goal ? `de focus · obiectiv ${d.goal}h` : 'de focus' })
      ])
    ]),
    h('div', { class: 'bars' }, d.days.map(x => h('div', { class: 'bar' + (x.today ? ' today' : '') }, [
      h('em', { text: x.sec ? (x.sec / 3600).toFixed(1) : '' }),
      (() => { const i = h('i'); i.style.height = Math.round((x.sec / max) * 78) + '%'; return i; })(),
      h('span', { text: x.label })
    ]))),
    h('div', { class: 'rule' }),
    h('div', { class: 'cols' }, [
      h('div', { class: 'section' }, [
        h('h3', { text: 'Ritualuri' }),
        h('div', { class: 'hgrid' }, d.habits.slice(0, 5).map(x => h('div', { class: 'row' }, [
          h('span', { class: 'name', text: x.name }),
          h('span', { class: 'hdots' }, x.week.map(on => h('i', { class: on ? 'on' : '' })))
        ])))
      ]),
      h('div', { class: 'section' }, [
        h('h3', { text: 'Bilanț' }),
        h('div', { class: 'mini' }, [
          h('div', {}, [h('b', { text: d.pomodoros }), 'pomodoro']),
          h('div', {}, [h('b', { text: `${d.prioritiesDone}/${d.prioritiesTotal}` }), 'priorități']),
          d.topApps.length ? h('div', { class: 'grat', text: `Top: ${d.topApps.join(', ')}` }) : null
        ])
      ])
    ]),
    quote(d),
    foot(d)
  );
}

// Micșorează conținutul până încape în format (zilele pline au mult conținut).
function fit() {
  const inner = document.getElementById('card');
  const box = inner.parentElement;
  const avail = box.clientHeight - parseFloat(getComputedStyle(box).paddingTop) - parseFloat(getComputedStyle(box).paddingBottom);
  let k = 1;
  inner.style.zoom = 1;
  inner.style.height = avail + 'px';
  while (inner.scrollHeight > inner.clientHeight + 1 && k > 0.62) {
    k -= 0.03;
    inner.style.zoom = k;
    inner.style.height = avail / k + 'px';
  }
}

function render(d) {
  document.body.className = d.format === 'story' ? 'story' : '';
  if (d.kind === 'week') renderWeek(d);
  else renderDay(d);
  fit();
  return document.fonts.ready.then(fit);
}
window.render = render;
