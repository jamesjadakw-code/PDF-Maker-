/* BAM inventory hub — V02 picker. Second option between Command (v01) and Jobsite (v03).
   V02 uses the desk font: Arial, gold, ink. Loads V02.css from the same folder.
   Stores the choice in localStorage (bam-hub-theme).
   Does not POST /inventory/api/theme.php — that allow-list is still v01 and v03, and a rejected
   save makes the desk picker revert. Saved account themes stay as they are. */
(function () {
  'use strict';
  if (window.BAM_V02) return;
  var KEY = 'bam-hub-theme';
  var THEMES = [
    { id: 'v01', label: 'Command' },
    { id: 'v02', label: 'V02' },
    { id: 'v03', label: 'Jobsite' }
  ];

  function loadCss() {
    if (document.querySelector('link[data-v02],style[data-v02]')) return;
    var src = document.currentScript && document.currentScript.src;
    if (!src) return;
    var link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = src.replace(/\.js(\?.*)?$/, '.css$1');
    link.setAttribute('data-v02', '');
    document.head.appendChild(link);
  }

  function saved() {
    try {
      var v = localStorage.getItem(KEY);
      return v === 'v01' || v === 'v02' || v === 'v03' ? v : '';
    } catch (e) { return ''; }
  }

  function pageTheme() {
    var htmlTheme = document.documentElement.getAttribute('data-hub-theme');
    if (htmlTheme === 'v01' || htmlTheme === 'v02' || htmlTheme === 'v03') return htmlTheme;
    var wrap = document.querySelector('.ul-wrap');
    var ui = wrap && wrap.getAttribute('data-ui-theme');
    if (ui === 'v01' || ui === 'v02' || ui === 'v03') return ui;
    var body = document.body && document.body.getAttribute('data-theme');
    if (body === 'v01' || body === 'v02' || body === 'v03') return body;
    return 'v01';
  }

  function paintPressed(id) {
    document.querySelectorAll('[data-hub-theme-set]').forEach(function (b) {
      var on = b.getAttribute('data-hub-theme-set') === id;
      b.setAttribute('aria-pressed', on ? 'true' : 'false');
    });
  }

  function apply(id, persist) {
    if (id !== 'v01' && id !== 'v02' && id !== 'v03') id = 'v01';
    var root = document.documentElement;
    if (id === 'v02') root.setAttribute('data-hub-theme', 'v02');
    else root.removeAttribute('data-hub-theme');
    document.querySelectorAll('.ul-wrap').forEach(function (el) {
      el.setAttribute('data-ui-theme', id);
    });
    var bodyTheme = document.body.getAttribute('data-theme');
    // The Lead Desk picker rewrites data-theme itself. Only mirror V02 onto the body
    // when that React picker is not on the page (the inventory hub).
    if (!document.querySelector('[data-testid=um-theme]') &&
        (bodyTheme === 'v01' || bodyTheme === 'v02' || bodyTheme === 'v03')) {
      document.body.setAttribute('data-theme', id);
    }
    if (persist) {
      try { localStorage.setItem(KEY, id); } catch (e) {}
    }
    paintPressed(id);
  }

  function picker() {
    var bar = document.createElement('div');
    bar.className = 'hub-v02-pick';
    bar.setAttribute('role', 'group');
    bar.setAttribute('aria-label', 'Theme');
    bar.setAttribute('data-testid', 'hub-theme');
    bar.innerHTML = '<span class="hub-v02-lab">Theme</span>' + THEMES.map(function (t) {
      return '<button type="button" data-hub-theme-set="' + t.id + '" data-testid="hub-theme-' + t.id + '">' + t.label + '</button>';
    }).join('');
    bar.addEventListener('click', function (e) {
      var b = e.target.closest('[data-hub-theme-set]');
      if (!b) return;
      e.preventDefault();
      apply(b.getAttribute('data-hub-theme-set'), true);
    });
    return bar;
  }

  function mount() {
    if (document.querySelector('[data-testid=hub-theme]')) return;
    var host = document.querySelector('.content') || document.querySelector('.main') || document.body;
    var bar = picker();
    if (host.firstChild) host.insertBefore(bar, host.firstChild);
    else host.appendChild(bar);
    apply(saved() || pageTheme(), false);
  }

  loadCss();
  window.BAM_V02 = { apply: apply, themes: THEMES };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', mount);
  else mount();
})();
