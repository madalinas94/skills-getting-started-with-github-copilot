// Limba interfeței. Textele sursă sunt în română; în altă limbă se înlocuiesc din dicționar:
// - t('Text {n}', { n }) pentru textele construite în cod;
// - textele statice din pagină (și cele puse ulterior din cod) se traduc automat.
(function () {
  const DICT = { en: self.I18N_EN || {} };
  const LOCALES = { ro: 'ro-RO', en: 'en-GB' };
  let lang = (self.buddy && self.buddy.i18n && self.buddy.i18n.lang) || 'ro';
  const missing = new Set();
  const ATTRS = ['placeholder', 'title', 'aria-label'];

  function t(s, vars) {
    let out = s;
    if (lang !== 'ro') {
      const v = DICT[lang] && DICT[lang][s];
      if (v !== undefined) out = v;
      else missing.add(s);
    }
    if (vars) out = String(out).replace(/\{(\w+)\}/g, (_, k) => (vars[k] ?? ''));
    return out;
  }

  function lookup(s) {
    if (lang === 'ro' || !s) return undefined;
    const k = s.trim().replace(/\s+/g, ' ');
    return k ? DICT[lang][k] : undefined;
  }

  function trText(node) {
    const p = node.parentNode;
    if (!p || /^(SCRIPT|STYLE|TEXTAREA)$/.test(p.nodeName) || (p.closest && p.closest('[translate="no"]'))) return;
    const raw = node.nodeValue;
    const v = lookup(raw);
    if (v === undefined) return;
    const lead = raw.match(/^\s*/)[0], trail = raw.match(/\s*$/)[0];
    const next = lead + v + trail;
    if (next !== raw) node.nodeValue = next;
  }

  function trEl(el) {
    if (el.closest && el.closest('[translate="no"]')) return;
    for (const a of ATTRS) {
      const cur = el.getAttribute(a);
      const v = cur && lookup(cur);
      if (v !== undefined && v !== cur) el.setAttribute(a, v);
    }
  }

  function walk(root) {
    if (lang === 'ro' || !root) return;
    if (root.nodeType === 3) return trText(root);
    if (root.nodeType !== 1 && root.nodeType !== 11) return;
    if (root.nodeType === 1) trEl(root);
    const w = document.createTreeWalker(root, NodeFilter.SHOW_ELEMENT | NodeFilter.SHOW_TEXT);
    for (let n = w.nextNode(); n; n = w.nextNode()) n.nodeType === 3 ? trText(n) : trEl(n);
  }

  let observer = null;
  function start() {
    document.documentElement.lang = lang;
    const tt = lookup(document.title);
    if (tt !== undefined) document.title = tt;
    walk(document.body);
    if (observer || lang === 'ro') return;
    observer = new MutationObserver(list => {
      for (const m of list) {
        if (m.type === 'childList') m.addedNodes.forEach(walk);
        else if (m.type === 'characterData') trText(m.target);
        else if (m.type === 'attributes') trEl(m.target);
      }
    });
    observer.observe(document.body, { childList: true, subtree: true, characterData: true, attributes: true, attributeFilter: ATTRS });
  }

  self.t = t;
  self.I18N = {
    get lang() { return lang; },
    get locale() { return LOCALES[lang] || 'en-GB'; },
    missing,
    // ferestrele fără preload (cardurile) primesc limba odată cu datele
    setLang(l) { lang = l || 'ro'; start(); }
  };
  if (document.body) start();
  else document.addEventListener('DOMContentLoaded', start);
})();
