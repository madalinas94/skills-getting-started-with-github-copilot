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

const cap = s => (s ? s[0].toUpperCase() + s.slice(1) : s);

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
  const [qo, qc] = d.quote.q || ['„', '”'];
  return h('div', { class: 'quote' }, [`${qo}${d.quote.text}${qc}`, h('span', { text: d.quote.author })]);
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
      x.streak > 1 ? h('span', { class: 'streak', text: t('{n} zile', { n: x.streak }) }) : null
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
    d.gratitude ? h('div', { class: 'grat', text: t('Recunoscătoare pentru: {g}', { g: d.gratitude }) }) : null,
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
        h('div', { class: 'big-label', text: d.goal ? t('de focus · obiectiv {h}h', { h: d.goal }) : t('de focus') })
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

function renderMonth(d) {
  const card = document.getElementById('card');
  const max = Math.max(4 * 3600, ...d.days.map(x => x.sec));
  const cal = h('div', { class: 'mcal' }, [
    ...(I18N.lang === 'en' ? ['M', 'T', 'W', 'T', 'F', 'S', 'S'] : ['L', 'M', 'M', 'J', 'V', 'S', 'D']).map(l => h('span', { class: 'mh', text: l })),
    ...[...Array(d.firstWeekday)].map(() => h('i', { class: 'blank' })),
    ...d.days.map(x => {
      const c = h('i', { class: (x.future ? 'future' : '') + (x.today ? ' today' : ''), text: x.day });
      c.style.setProperty('--lvl', x.sec ? (0.18 + 0.82 * x.sec / max).toFixed(2) : 0);
      if (x.sec / max > 0.5) c.classList.add('dark');
      return c;
    })
  ]);
  card.replaceChildren(
    header({ ...d, kind: 'week', range: d.month }, 'Luna mea'),
    h('div', { class: 'stats' }, [
      h('div', {}, [h('div', { class: 'big', text: d.focus }), h('div', { class: 'big-label', text: 'de focus' })]),
      h('div', { class: 'mini' }, [
        h('div', {}, [h('b', { text: d.daysWorked }), t('zile lucrate din {n}', { n: d.daysElapsed })]),
        h('div', {}, [h('b', { text: d.avg }), 'în medie pe zi']),
        h('div', {}, [h('b', { text: d.pomodoros }), 'pomodoro'])
      ])
    ]),
    h('div', { class: 'cols' }, [
      h('div', { class: 'section' }, [h('h3', { text: 'Calendar' }), cal]),
      h('div', { class: 'section' }, [
        h('h3', { text: 'Ritualuri' }),
        h('div', { class: 'hbars' }, d.habits.slice(0, 5).map(x => h('div', { class: 'hb' }, [
          h('div', { class: 'hbn' }, [h('span', { text: x.name }), h('em', { text: `${x.pct}%` })]),
          (() => { const b = h('div', { class: 'hbar' }, [h('i')]); b.firstChild.style.width = x.pct + '%'; return b; })()
        ])))
      ])
    ]),
    h('div', { class: 'cols' }, [
      h('div', { class: 'section' }, [
        h('h3', { text: 'Repere' }),
        h('div', { class: 'list small' }, [
          d.best ? h('div', {}, [h('b', { text: 'Cea mai bună zi: ' }), `${d.best.label}, ${d.best.focus}`]) : null,
          d.prioritiesTotal ? h('div', {}, [h('b', { text: 'Priorități: ' }), t('{d}/{n} bifate', { d: d.prioritiesDone, n: d.prioritiesTotal })]) : null,
          d.topApps.length ? h('div', {}, [h('b', { text: 'Top: ' }), d.topApps.join(', ')]) : null,
          d.water ? h('div', {}, [h('b', { text: 'Apă: ' }), t('{n} pahare/zi', { n: d.water })]) : null
        ])
      ]),
      h('div', { class: 'section' }, [
        h('h3', { text: 'Stări' }),
        h('div', { class: 'moods-l' }, d.moods.length ? d.moods.slice(0, 4).map(x => h('span', {}, [x.label, h('b', { text: ` ×${x.n}` })])) : [h('span', { text: '—' })])
      ])
    ]),
    d.mantra ? h('div', { class: 'quote' }, [`${(d.mantra.q || ['„'])[0]}${d.mantra.text}${(d.mantra.q || ['„', '”'])[1]}`, h('span', { text: d.mantra.author || d.mantra.label })]) : quote(d),
    foot(d)
  );
}

function renderMantra(d) {
  const card = document.getElementById('card');
  const m = d.mantra;
  const [qo, qc] = m.q || ['„', '”'];
  const text = m.type === 'citat' || m.type === 'vorba' ? `${qo}${m.text}${qc}` : m.text;
  card.replaceChildren(
    h('div', { class: 'mantra' }, [
      h('img', { class: 'medal', src: '../assets/icon.svg' }),
      h('div', { class: 'kicker', text: `${m.kicker || t('Mantra zilei')} · ${d.date}` }),
      h('div', { class: 'mlabel', text: m.label }),
      m.title ? h('div', { class: 'mtitle', text: m.title }) : null,
      h('div', { class: 'mtext', text }),
      m.author ? h('div', { class: 'mauthor', text: `— ${m.author}` }) : null,
      m.note ? h('div', { class: 'mnote', text: m.note }) : null,
      h('div', { class: 'orn', text: '✦' })
    ]),
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
  I18N.setLang(d.lang);
  document.body.className = d.format === 'story' ? 'story' : '';
  if (d.kind === 'week') renderWeek(d);
  else if (d.kind === 'month') renderMonth(d);
  else if (d.kind === 'mantra') renderMantra(d);
  else renderDay(d);
  fit();
  return document.fonts.ready.then(fit);
}
window.render = render;
