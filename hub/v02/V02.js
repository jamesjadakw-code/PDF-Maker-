/* BAM inventory hub — V02 picker and URL-listing workspace.
   Second option between Command (v01) and Jobsite (v03).
   Light only: Inter, white cards, indigo #5b5bd6. Works in Safari and every other browser.
   Stores the choice in localStorage (bam-hub-theme).
   Does not POST /inventory/api/theme.php — that allow-list is still v01 and v03.
   On the Inventory URL listings tab, V02 opens the match workspace for the live units:
   location, specs, serial, top buyers, and draft actions. Nothing is sent. */
(function () {
  'use strict';
  if (window.BAM_V02 && window.BAM_V02.workspace) return;
  var KEY = 'bam-hub-theme';
  var THEMES = [
    { id: 'v01', label: 'Command' },
    { id: 'v02', label: 'V02' },
    { id: 'v03', label: 'Jobsite' }
  ];
  var JUNK = /^(close|closed|equipment manuals|manuals|home|menu|search|login|sign in|log in|facebook|marketplace|details|listing|item|photo|photos|share|save|contact|call|email|back|next|previous|more|untitled|n\/a|null|undefined|loading|document|documents)$/i;

  function esc(s) {
    return String(s == null ? '' : s).replace(/[&<>"']/g, function (c) {
      return { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c];
    });
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

  function ensureLight() {
    var root = document.documentElement;
    if (!document.querySelector('meta[name="color-scheme"]')) {
      var meta = document.createElement('meta');
      meta.name = 'color-scheme';
      meta.content = 'light only';
      document.head.appendChild(meta);
    }
    if (!document.querySelector('meta[name="darkreader-lock"]')) {
      var lock = document.createElement('meta');
      lock.name = 'darkreader-lock';
      document.head.appendChild(lock);
    }
    root.style.colorScheme = 'light only';
    root.style.backgroundColor = '#fbfbfc';
  }

  function dropLight() {
    document.documentElement.style.colorScheme = '';
    document.documentElement.style.backgroundColor = '';
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

  function mountPicker() {
    if (document.querySelector('[data-testid=hub-theme]')) return;
    var host = document.querySelector('.content') || document.querySelector('.main') || document.body;
    var bar = picker();
    if (host.firstChild) host.insertBefore(bar, host.firstChild);
    else host.appendChild(bar);
  }

  /* ------------------------------------------------------------------ workspace */
  var W = {
    rows: [],
    feed: {},
    units: {},
    matches: {},
    failed: {},
    sel: 0,
    buyer: 0,
    tab: 'ov',
    drawer: false,
    note: '',
    busy: false,
    wired: false
  };

  function hostEl() {
    return document.querySelector('[data-bam-uploader]') || document.querySelector('[data-api]');
  }

  function endpoint() {
    var el = hostEl();
    if (el && el.dataset.api) return el.dataset.api;
    var path = location.pathname.indexOf('/inventory/') >= 0 ? 'api/hub.php' : '/inventory/api/hub.php';
    return path;
  }

  function csrf() {
    var el = hostEl();
    return (el && el.dataset.csrf) || '';
  }

  function api(a, params, post) {
    params = params || {};
    var url = endpoint();
    if (post) {
      var fd = new URLSearchParams();
      fd.set('a', a);
      fd.set('_csrf', csrf());
      Object.keys(params).forEach(function (k) {
        var v = params[k];
        if (Array.isArray(v)) v.forEach(function (x) { fd.append(k, x); });
        else if (v != null) fd.set(k, v);
      });
      return fetch(url, {
        method: 'POST',
        body: fd,
        credentials: 'same-origin',
        headers: { Accept: 'application/json', 'X-CSRF-Token': csrf() }
      }).then(function (res) {
        return res.json().catch(function () { return { ok: false, error: 'HTTP ' + res.status }; });
      }).catch(function () { return { ok: false, error: 'Network error' }; });
    }
    var u = new URL(url, location.href);
    u.searchParams.set('a', a);
    Object.keys(params).forEach(function (k) {
      if (params[k] !== '' && params[k] != null) u.searchParams.set(k, params[k]);
    });
    return fetch(u, { credentials: 'same-origin', headers: { Accept: 'application/json' }, cache: 'no-store' })
      .then(function (res) { return res.json().catch(function () { return { ok: false, error: 'HTTP ' + res.status }; }); })
      .catch(function () { return { ok: false, error: 'Network error' }; });
  }

  function textOf(el) {
    return el ? (el.textContent || '').replace(/\s+/g, ' ').trim() : '';
  }

  function cell(tr, name) {
    var heads = Array.prototype.map.call(tr.closest('table').querySelectorAll('thead th'), function (th) {
      return textOf(th).toLowerCase();
    });
    var tds = tr.children;
    for (var i = 0; i < heads.length && i < tds.length; i++) {
      if (heads[i].indexOf(name) >= 0) return tds[i];
    }
    return null;
  }

  function readRows() {
    var rows = [];
    document.querySelectorAll('.ul-tbl tbody tr[data-ul-row]').forEach(function (tr) {
      var link = tr.querySelector('.ul-t a');
      var img = tr.querySelector('img');
      var catCell = cell(tr, 'category');
      var hours = '';
      var category = '';
      if (catCell) {
        var sub = catCell.querySelector('.ul-s');
        hours = sub ? textOf(sub).replace(/\s*hrs$/i, '') : '';
        category = textOf(catCell).replace(sub ? textOf(sub) : '', '').trim();
      }
      var src = cell(tr, 'source');
      var price = cell(tr, 'price');
      var ask = cell(tr, 'seller');
      rows.push({
        id: +tr.getAttribute('data-ul-row'),
        title: link ? textOf(link) : textOf(tr.querySelector('.ul-t')),
        meta: textOf(tr.querySelector('.ul-s')),
        href: link ? link.getAttribute('href') : ('unit.php?id=' + tr.getAttribute('data-ul-row')),
        photo: img ? img.getAttribute('src') : '',
        category: category,
        hours: hours,
        source: src ? textOf(src) : '',
        price: price ? textOf(price) : 'Call for Price',
        ask: ask ? textOf(ask) : '',
        verified: !!tr.querySelector('.ul-b.v'),
        status: (tr.querySelector('.ul-b.d, .ul-b.l') || {}).textContent || '',
        brochure: (tr.querySelector('[data-testid=ul-brochure]') || {}).href || ''
      });
    });
    return rows;
  }

  function junkTitle(title) {
    var t = String(title || '').trim();
    return !t || JUNK.test(t) || t.length < 3;
  }

  function composed(unit) {
    if (!unit) return '';
    return [unit.year, unit.make, unit.model].filter(Boolean).join(' ').trim();
  }

  function shownTitle(row, unit) {
    var raw = (unit && unit.title) || row.title || '';
    var built = composed(unit);
    if (built && junkTitle(raw)) return { title: built, scraped: raw };
    return { title: raw, scraped: '' };
  }

  function place(unit, feed) {
    var geo = (unit && unit.geo) || (feed && feed.geo) || null;
    if (!geo) return '';
    return geo.label || geo.place || '';
  }

  function specEntries(unit) {
    var specs = (unit && unit.specs) || {};
    return Object.keys(specs).filter(function (k) { return specs[k] != null && String(specs[k]).trim() !== ''; })
      .map(function (k) { return [k, specs[k]]; });
  }

  function leadsOf(id) {
    var m = W.matches[id];
    return (m && m.leads) || [];
  }

  function currentRow() {
    for (var i = 0; i < W.rows.length; i++) if (W.rows[i].id === W.sel) return W.rows[i];
    return W.rows[0] || null;
  }

  function toast(msg) {
    W.note = msg;
    var el = document.querySelector('[data-v02-toast]');
    if (el) {
      el.textContent = msg;
      el.hidden = !msg;
    }
  }

  function ensureCss() {
    if (!document.querySelector('link[data-v02-font]')) {
      var font = document.createElement('link');
      font.rel = 'stylesheet';
      font.href = 'https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap';
      font.setAttribute('data-v02-font', '');
      document.head.appendChild(font);
    }
    if (document.querySelector('style[data-v02-work]')) return;
    var css = document.createElement('style');
    css.setAttribute('data-v02-work', '');
    css.textContent = [
      'html[data-hub-theme=v02]{color-scheme:light only;background:#fbfbfc;color:#1c1d22}',
      '.v02-work{color-scheme:light only;background:#fbfbfc;color:#1c1d22;font:13px/1.45 Inter,system-ui,sans-serif;border:1px solid #ececf0;border-radius:12px;margin:14px 0 8px;overflow:hidden}',
      '.v02-work *{box-sizing:border-box}',
      '.v02-bar{display:flex;align-items:center;gap:8px;padding:8px 12px;background:#fff;border-bottom:1px solid #ececf0}',
      '.v02-bar b{font-size:12px;letter-spacing:.04em;color:#6f7180;font-weight:650}',
      '.v02-bar button,.v02-act{border:1px solid #e2e2e8;background:#fff;border-radius:7px;padding:6px 10px;font:500 12.5px/1 Inter,system-ui,sans-serif;color:#1c1d22;cursor:pointer}',
      '.v02-act.pri,.v02-bar .pri{background:#5b5bd6;border-color:#5b5bd6;color:#fff}',
      '.v02-split{display:grid;grid-template-columns:40% 60%;min-height:560px;background:#fff}',
      '.v02-list{border-right:1px solid #ececf0;overflow:auto;max-height:78vh;background:#fff}',
      '.v02-grp{position:sticky;top:0;background:#f8f8fa;border-bottom:1px solid #ececf0;padding:6px 14px;font-size:12px;color:#6f7180;font-weight:600;z-index:1}',
      '.v02-row{display:grid;grid-template-columns:18px 52px 1fr auto;gap:10px;padding:10px 14px;border-bottom:1px solid #f2f2f5;cursor:pointer;align-items:center;width:100%;text-align:left;background:#fff;font:inherit;color:inherit}',
      '.v02-row:hover{background:#fafafc}.v02-row.sel{background:#eeeefc;box-shadow:inset 2px 0 #5b5bd6}',
      '.v02-row img,.v02-ph{width:52px;height:40px;border-radius:6px;object-fit:cover;background:#f3f3f6;border:1px solid #ececf0}',
      '.v02-rt{font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}',
      '.v02-rm{color:#6f7180;font-size:12px;margin-top:2px}',
      '.v02-score{font-weight:700;font-size:12px;border-radius:20px;padding:2px 8px;background:#f1f1f4;color:#6f7180}',
      '.v02-score.hot{background:#e7f7ee;color:#18a957}.v02-score.warm{background:#fdf3e2;color:#d97706}',
      '.v02-detail{overflow:auto;max-height:78vh;padding:0 0 88px;position:relative;background:#fff}',
      '.v02-tabs{position:sticky;top:0;z-index:2;display:flex;gap:2px;padding:0 18px;background:#fff;border-bottom:1px solid #ececf0}',
      '.v02-tabs button{border:0;background:transparent;padding:11px 12px;color:#6f7180;font:550 13px/1 Inter,system-ui,sans-serif;border-bottom:2px solid transparent;cursor:pointer}',
      '.v02-tabs button.on{color:#1c1d22;border-bottom-color:#5b5bd6}',
      '.v02-pad{padding:16px 20px 0}',
      '.v02-hero{display:grid;grid-template-columns:200px 1fr;gap:16px}',
      '.v02-hero img{width:200px;height:140px;object-fit:cover;border-radius:10px;background:#f3f3f6;border:1px solid #ececf0}',
      '.v02-hero h3{font:650 22px/1.2 Inter,system-ui,sans-serif;letter-spacing:-.02em;margin:4px 0}',
      '.v02-props{display:grid;grid-template-columns:110px 1fr 110px 1fr;gap:6px 12px;margin:12px 0}',
      '.v02-props dt{color:#6f7180}',
      '.v02-sec{font-size:12px;font-weight:650;color:#6f7180;text-transform:uppercase;letter-spacing:.05em;margin:16px 0 8px}',
      '.v02-ing{display:flex;gap:8px;align-items:flex-start;background:#fff7f7;border:1px solid #ffd9da;color:#9f1d22;border-radius:10px;padding:8px 10px;margin-bottom:10px}',
      '.v02-mc{display:grid;grid-template-columns:repeat(3,1fr);gap:10px}',
      '.v02-buyer{border:1px solid #ececf0;border-radius:10px;padding:12px;cursor:pointer;position:relative;background:#fff;text-align:left;font:inherit;color:inherit;width:100%}',
      '.v02-buyer.on{border-color:#5b5bd6;box-shadow:0 0 0 3px #5b5bd622}',
      '.v02-buyer .n{font-weight:650}.v02-buyer .c{color:#6f7180;font-size:12px}',
      '.v02-ring{position:absolute;right:10px;top:10px;width:42px;height:42px}',
      '.v02-why{display:flex;flex-wrap:wrap;gap:4px;margin-top:8px}.v02-why span{font-size:11px;background:#f4f4f7;border-radius:4px;padding:1px 6px;color:#4b4d5a}',
      '.v02-card{border:1px solid #ececf0;border-radius:12px;padding:12px;background:#fff}',
      '.v02-cols{display:grid;grid-template-columns:1fr 1fr;gap:12px}',
      '.v02-abar{position:fixed;left:50%;transform:translateX(-50%);bottom:18px;display:flex;gap:4px;background:#1c1d22;color:#fff;border-radius:12px;padding:6px;box-shadow:0 10px 30px #0003;z-index:40;max-width:calc(100% - 24px);overflow:auto}',
      '.v02-abar button{background:transparent;border:0;color:#e9e9ee;font:500 12.5px Inter,system-ui,sans-serif;padding:7px 10px;border-radius:8px;cursor:pointer;white-space:nowrap}',
      '.v02-abar button:hover{background:#ffffff1a}',
      '.v02-toast{position:fixed;right:16px;bottom:78px;z-index:41;background:#fff;border:1px solid #ececf0;border-radius:10px;box-shadow:0 8px 24px #0000001f;padding:10px 12px;max-width:360px}',
      '.v02-scrim{position:fixed;inset:0;background:#0f0f1a33;z-index:42}',
      '.v02-sheet{position:fixed;top:10px;right:10px;bottom:10px;width:min(500px,calc(100% - 20px));background:#fff;color:#1c1d22;border-radius:14px;box-shadow:0 20px 60px #0003;z-index:43;display:flex;flex-direction:column}',
      '.v02-sheet header{display:flex;align-items:center;gap:8px;padding:12px 14px;border-bottom:1px solid #ececf0}',
      '.v02-sheet .fb{padding:16px;overflow:auto}',
      '.v02-sheet textarea,.v02-sheet input{width:100%;border:1px solid #e2e2e8;border-radius:8px;padding:8px 10px;font:13px Inter,system-ui,sans-serif;color:#1c1d22;background:#fff}',
      '.v02-sheet textarea{height:140px;resize:vertical}',
      '.v02-sheet .sf{padding:12px 14px;border-top:1px solid #ececf0;display:flex;gap:8px;justify-content:flex-end}',
      '.ul-loc{color:#1c1d22;font-size:13px}',
      '@media(max-width:900px){.v02-split{grid-template-columns:1fr}.v02-list{max-height:42vh;border-right:0;border-bottom:1px solid #ececf0}.v02-hero,.v02-props,.v02-mc,.v02-cols{grid-template-columns:1fr}.v02-abar{left:12px;right:12px;transform:none}}'
    ].join('');
    document.head.appendChild(css);
  }

  function ring(score) {
    var s = Math.max(0, Math.min(100, +score || 0));
    var c = 2 * Math.PI * 17;
    var col = s >= 80 ? '#18a957' : s >= 60 ? '#d97706' : '#9a9cab';
    return '<svg class="v02-ring" viewBox="0 0 42 42" aria-hidden="true"><circle cx="21" cy="21" r="17" fill="none" stroke="#efeff3" stroke-width="4"></circle><circle cx="21" cy="21" r="17" fill="none" stroke="' + col + '" stroke-width="4" stroke-linecap="round" stroke-dasharray="' + (c * s / 100) + ' ' + c + '" transform="rotate(-90 21 21)"></circle><text x="21" y="25" text-anchor="middle" font-size="11" font-weight="700" fill="#1c1d22">' + s + '</text></svg>';
  }

  function scoreClass(s) {
    s = +s || 0;
    return s >= 80 ? 'hot' : s >= 60 ? 'warm' : '';
  }

  function shell() {
    if (document.querySelector('[data-v02-work]')) return;
    var box = document.querySelector('.ul-box') || document.querySelector('.ul-wrap');
    if (!box) return;
    ensureCss();
    var work = document.createElement('section');
    work.className = 'v02-work';
    work.setAttribute('data-v02-work', '');
    work.setAttribute('data-testid', 'v02-work');
    work.innerHTML = '<div class="v02-bar"><b>MATCH WORKSPACE</b><span style="color:#6f7180">Location, specs, and top buyers for these URL listings.</span><span style="margin-left:auto"></span><button type="button" data-v02-table data-testid="v02-table">Show table</button></div><div class="v02-split"><div class="v02-list" data-v02-list></div><div class="v02-detail" data-v02-detail></div></div>';
    var head = box.querySelector('.ul-head');
    if (head && head.nextSibling) box.insertBefore(work, head.nextSibling);
    else box.insertBefore(work, box.firstChild);
    var table = box.querySelector('.ul-tbl');
    if (table) table.hidden = true;
    var note = box.querySelector('.ul-note');
    if (note) note.hidden = true;
    work.addEventListener('click', onClick);
    var abar = document.createElement('div');
    abar.className = 'v02-abar';
    abar.setAttribute('data-v02-abar', '');
    abar.setAttribute('data-testid', 'v02-abar');
    abar.innerHTML = '<button type="button" data-act="text">Text</button><button type="button" data-act="email">Email</button><button type="button" data-act="call">Call</button><button type="button" data-act="quote">Quote</button><button type="button" data-act="link">Link</button><button type="button" data-act="stage">Stage</button>';
    abar.addEventListener('click', onBar);
    document.body.appendChild(abar);
    var toastEl = document.createElement('div');
    toastEl.className = 'v02-toast';
    toastEl.setAttribute('data-v02-toast', '');
    toastEl.hidden = true;
    document.body.appendChild(toastEl);
  }

  function unmountWork() {
    document.querySelectorAll('[data-v02-work],[data-v02-abar],[data-v02-toast],[data-v02-scrim],[data-v02-sheet],.ul-loc-h,.ul-loc').forEach(function (el) { el.remove(); });
    document.querySelectorAll('.ul-tbl,.ul-note').forEach(function (el) { el.hidden = false; });
  }

  function addLocationColumn() {
    var table = document.querySelector('.ul-tbl');
    if (!table || table.querySelector('.ul-loc-h')) return;
    var heads = table.querySelectorAll('thead th');
    var statusHead = null;
    heads.forEach(function (th) { if (textOf(th).toLowerCase().indexOf('status') >= 0) statusHead = th; });
    if (!statusHead) return;
    var th = document.createElement('th');
    th.className = 'ul-loc-h';
    th.textContent = 'Location';
    statusHead.parentNode.insertBefore(th, statusHead);
    table.querySelectorAll('tbody tr[data-ul-row]').forEach(function (tr) {
      var td = document.createElement('td');
      td.className = 'ul-loc';
      td.setAttribute('data-loc-for', tr.getAttribute('data-ul-row'));
      td.textContent = '—';
      var statusCell = cell(tr, 'status');
      if (statusCell) tr.insertBefore(td, statusCell);
    });
  }

  function paintLocations() {
    W.rows.forEach(function (row) {
      var td = document.querySelector('[data-loc-for="' + row.id + '"]');
      if (!td) return;
      var loc = place(W.units[row.id], W.feed[row.id]);
      td.textContent = loc || 'No location';
    });
  }

  function rowHtml(row) {
    var unit = W.units[row.id];
    var names = shownTitle(row, unit);
    var loc = place(unit, W.feed[row.id]);
    var specs = specEntries(unit);
    var leads = leadsOf(row.id);
    var top = leads.length ? leads[0].score : '';
    var bits = [row.category, row.hours ? row.hours + ' hrs' : '', loc || 'No location'].filter(Boolean);
    if (specs.length) bits.push(specs.length + ' specs');
    return '<button type="button" class="v02-row' + (row.id === W.sel ? ' sel' : '') + '" data-pick="' + row.id + '" data-testid="v02-row">' +
      '<span class="v02-dot" aria-hidden="true"></span>' +
      (row.photo ? '<img src="' + esc(row.photo) + '" alt="">' : '<span class="v02-ph"></span>') +
      '<span style="min-width:0"><span class="v02-rt">' + esc(names.title) + '</span><span class="v02-rm">' + esc(bits.join(' · ')) + '</span></span>' +
      (top !== '' ? '<span class="v02-score ' + scoreClass(top) + '">' + esc(top) + '</span>' : '<span></span>') +
      '</button>';
  }

  function facts(row, unit) {
    var sheet = (unit && unit.sheet) || {};
    var loc = place(unit, W.feed[row.id]) || 'No location on this unit';
    var zip = (unit && (unit.zip || (unit.geo && unit.geo.zip))) || '';
    var buyer = (unit && unit.buyerSees) || row.price || 'Call for Price';
    var ask = (unit && unit.sellerAsk) || row.ask || '';
    var pairs = [
      ['Asking', buyer || 'Call for Price'],
      ['Seller ask', ask ? ask + ' · internal' : 'None · internal'],
      ['Hours', (unit && unit.hours != null ? unit.hours : row.hours) || '—'],
      ['Location', loc],
      ['ZIP', zip || '—'],
      ['Serial', sheet.serial || '—'],
      ['Condition', sheet.condition || '—'],
      ['Source', (unit && unit.site) || row.source || '—']
    ];
    return '<dl class="v02-props">' + pairs.map(function (p) {
      return '<dt>' + esc(p[0]) + '</dt><dd>' + esc(p[1]) + '</dd>';
    }).join('') + '</dl>';
  }

  function buyersHtml(row) {
    var leads = leadsOf(row.id).slice(0, 3);
    if (!leads.length) {
      return '<p class="v02-rm">' + (row.verified ? 'No matched buyers for this unit yet.' : 'Verify this draft to put it into lead matching. Specs and location stay on the unit either way.') + '</p>';
    }
    return '<div class="v02-mc">' + leads.map(function (lead, i) {
      var where = (lead.geo && lead.geo.place) || [lead.city, lead.state].filter(Boolean).join(', ');
      var why = (lead.reasons || []).slice(0, 4);
      return '<button type="button" class="v02-buyer' + (i === W.buyer ? ' on' : '') + '" data-buyer="' + i + '" data-testid="v02-buyer">' +
        ring(lead.score) +
        '<div class="n">' + esc(lead.name || 'Buyer') + '</div>' +
        '<div class="c">' + esc(lead.company || '') + '</div>' +
        '<div class="c">' + esc(where || 'No location') + (lead.miles != null ? ' · ' + lead.miles + ' mi' : '') + '</div>' +
        (lead.wants ? '<div class="c">Wants ' + esc(lead.wants) + '</div>' : '') +
        (why.length ? '<div class="v02-why">' + why.map(function (w) { return '<span>' + esc(w) + '</span>'; }).join('') + '</div>' : '') +
        '</button>';
    }).join('') + '</div>';
  }

  function selectedHtml(row) {
    var lead = leadsOf(row.id)[W.buyer];
    if (!lead) return '';
    var where = (lead.geo && lead.geo.place) || [lead.city, lead.state].filter(Boolean).join(', ');
    return '<div class="v02-cols"><div class="v02-card"><div class="n" style="font-weight:650">' + esc(lead.name || '') + '</div><div class="v02-rm">' + esc([lead.company, where, lead.phone].filter(Boolean).join(' · ')) + '</div>' +
      '<dl class="v02-props" style="grid-template-columns:90px 1fr"><dt>Score</dt><dd>' + esc(lead.score) + '</dd><dt>Wants</dt><dd>' + esc(lead.wants || '—') + '</dd><dt>Linked</dt><dd>' + (lead.linked ? 'Linked to this unit' : 'Not linked') + '</dd></dl></div>' +
      '<div class="v02-card"><div style="font-weight:650;margin-bottom:6px">Why this buyer</div><div class="v02-why">' + ((lead.reasons || []).map(function (w) { return '<span>' + esc(w) + '</span>'; }).join('') || '<span>No reasons from the matcher</span>') + '</div></div></div>';
  }

  function activityHtml(row, unit) {
    var sheet = (unit && unit.sheet) || {};
    var lines = [row.meta, unit && unit.verified ? 'Verified' + (unit.verifiedBy ? ' by ' + unit.verifiedBy : '') : 'Not verified', sheet.photoCount ? sheet.photoCount + ' photos on the unit' : ''].filter(Boolean);
    return '<div class="v02-card">' + lines.map(function (line) { return '<div style="padding:4px 0">' + esc(line) + '</div>'; }).join('') + '</div>';
  }

  function detailHtml() {
    var row = currentRow();
    if (!row) return '<div class="v02-pad"><p>No URL listings on this tab yet. Paste a listing link in the uploader above.</p></div>';
    var unit = W.units[row.id];
    var names = shownTitle(row, unit);
    var specs = specEntries(unit);
    var specBody = specs.length
      ? '<dl class="v02-props">' + specs.map(function (p) { return '<dt>' + esc(p[0]) + '</dt><dd>' + esc(p[1]) + '</dd>'; }).join('') + '</dl>'
      : '<p class="v02-rm">No specs stored yet.</p>';
    var banner = names.scraped
      ? '<div class="v02-ing"><b>PAGE TITLE</b><span>The listing page title was “' + esc(names.scraped) + '”. Photos are saved. Fill specs, or open the unit if the year, make, and model are still empty.</span></div>'
      : '';
    var waiting = unit ? '' : (W.failed[row.id]
      ? '<p class="v02-rm">' + esc(W.failed[row.id]) + '</p>'
      : '<p class="v02-rm">Loading location, specs, and buyers…</p>');
    var overview = waiting + banner +
      '<div class="v02-hero">' + (row.photo ? '<img src="' + esc(row.photo) + '" alt="">' : '<span class="v02-ph" style="width:200px;height:140px"></span>') +
      '<div><div class="v02-rm">' + esc(row.category || (unit && unit.category) || '') + (row.meta ? ' · ' + esc(row.meta) : '') + '</div><h3>' + esc(names.title) + '</h3>' + facts(row, unit) +
      '<div style="display:flex;gap:8px;flex-wrap:wrap">' +
      (row.verified ? '' : '<button type="button" class="v02-act pri" data-verify="' + row.id + '" data-testid="v02-verify">Verify</button>') +
      '<button type="button" class="v02-act" data-fill="' + row.id + '" data-testid="v02-fill">Fill specs</button>' +
      '<a class="v02-act" href="' + esc(row.href) + '">Open unit</a>' +
      (row.brochure ? '<a class="v02-act" href="' + esc(row.brochure) + '">Brochure</a>' : '') +
      '</div></div></div>' +
      '<div class="v02-sec">Specs</div>' + specBody +
      '<div class="v02-sec">Top buyers</div>' + buyersHtml(row) +
      '<div class="v02-sec">Selected buyer</div>' + (selectedHtml(row) || '<p class="v02-rm">No buyer selected.</p>');
    var loc = place(unit, W.feed[row.id]);
    var sheet = (unit && unit.sheet) || {};
    var location = '<div class="v02-card"><b>Unit location</b><p>' + esc(loc || 'No location on this unit. Add a ZIP in the unit editor.') + '</p>' +
      '<p class="v02-rm">Seller location stays internal' + (sheet.sellerLocation ? ': ' + esc(sheet.sellerLocation) : '') + '.</p>' +
      '<p><a class="v02-act" href="hub.php?unit=' + row.id + '">Open map in Inventory Hub</a></p></div>';
    var tab = W.tab === 'map' ? location : W.tab === 'act' ? activityHtml(row, unit) : overview;
    var tabs = '<div class="v02-tabs" role="tablist"><button type="button" data-tab="ov" class="' + (W.tab === 'ov' ? 'on' : '') + '">Overview</button><button type="button" data-tab="map" class="' + (W.tab === 'map' ? 'on' : '') + '">Map · dealers &amp; service</button><button type="button" data-tab="act" class="' + (W.tab === 'act' ? 'on' : '') + '">Activity</button></div>';
    return tabs + '<div class="v02-pad" data-testid="v02-detail">' + tab + '</div>';
  }

  function render() {
    var list = document.querySelector('[data-v02-list]');
    var detail = document.querySelector('[data-v02-detail]');
    if (!list || !detail) return;
    var fresh = W.rows.filter(function (r) { return !r.verified; });
    var older = W.rows.filter(function (r) { return r.verified; });
    list.innerHTML = (fresh.length ? '<div class="v02-grp">New URL drafts · ' + fresh.length + '</div>' + fresh.map(rowHtml).join('') : '') +
      '<div class="v02-grp">On this tab · ' + older.length + '</div>' + (older.map(rowHtml).join('') || (fresh.length ? '' : '<p class="v02-pad">No rows.</p>'));
    detail.innerHTML = detailHtml();
    paintLocations();
    paintDrawer();
  }

  function focusedLead() {
    var row = currentRow();
    if (!row) return null;
    return leadsOf(row.id)[W.buyer] || null;
  }

  function quoteText(row, unit, lead) {
    var title = shownTitle(row, unit).title;
    var price = (unit && unit.buyerSees) || row.price || 'Call for Price';
    var who = lead && lead.name ? lead.name.split(' ')[0] : 'there';
    return 'Big Ass Motors\n' + title + '\n' + price + '\n' + who + ', this is the unit we matched. Photos are ready. Reply and we will send the brochure.';
  }

  function paintDrawer() {
    var sheet = document.querySelector('[data-v02-sheet]');
    var scrim = document.querySelector('[data-v02-scrim]');
    if (!W.drawer) {
      if (sheet) sheet.remove();
      if (scrim) scrim.remove();
      return;
    }
    var row = currentRow();
    var unit = row && W.units[row.id];
    var lead = focusedLead();
    if (!scrim) {
      scrim = document.createElement('div');
      scrim.className = 'v02-scrim';
      scrim.setAttribute('data-v02-scrim', '');
      scrim.addEventListener('click', function () { W.drawer = false; paintDrawer(); });
      document.body.appendChild(scrim);
    }
    if (!sheet) {
      sheet = document.createElement('aside');
      sheet.className = 'v02-sheet';
      sheet.setAttribute('data-v02-sheet', '');
      sheet.setAttribute('data-testid', 'v02-sheet');
      document.body.appendChild(sheet);
    }
    var name = lead ? (lead.name + (lead.company ? ' — ' + lead.company : '')) : 'No buyer selected';
    sheet.innerHTML = '<header><b>Deal' + (row ? ' · ' + esc(shownTitle(row, unit).title) : '') + '</b><button type="button" class="v02-act" data-close-sheet style="margin-left:auto">Close</button></header><div class="fb"><label>Buyer</label><input readonly value="' + esc(name) + '"><label style="display:block;margin-top:10px">Quote sheet message · SMS</label><textarea data-quote>' + esc(row ? quoteText(row, unit, lead) : '') + '</textarea><p class="v02-rm" style="margin-top:8px">Email and text here create drafts only. Nothing is sent. Seller ask stays off this message.</p></div><div class="sf"><button type="button" class="v02-act" data-act="link">Link</button><button type="button" class="v02-act" data-act="email">Email quote</button><button type="button" class="v02-act pri" data-act="text">Text draft</button></div>';
  }

  function onClick(e) {
    var tab = e.target.closest('[data-tab]');
    if (tab) { W.tab = tab.getAttribute('data-tab'); render(); return; }
    var pick = e.target.closest('[data-pick]');
    if (pick) { W.sel = +pick.getAttribute('data-pick'); W.buyer = 0; W.tab = 'ov'; render(); ensureUnit(W.sel); return; }
    var buyer = e.target.closest('[data-buyer]');
    if (buyer) { W.buyer = +buyer.getAttribute('data-buyer'); render(); return; }
    var tableBtn = e.target.closest('[data-v02-table]');
    if (tableBtn) {
      var table = document.querySelector('.ul-tbl');
      if (table) {
        table.hidden = !table.hidden;
        tableBtn.textContent = table.hidden ? 'Show table' : 'Hide table';
      }
      return;
    }
    var verify = e.target.closest('[data-verify]');
    if (verify) { doVerify(+verify.getAttribute('data-verify')); return; }
    var fill = e.target.closest('[data-fill]');
    if (fill) { doFill(+fill.getAttribute('data-fill')); return; }
    if (e.target.closest('[data-close-sheet]')) { W.drawer = false; paintDrawer(); }
  }

  function onBar(e) {
    var btn = e.target.closest('[data-act]');
    if (!btn) return;
    runAct(btn.getAttribute('data-act'));
  }

  function runAct(name) {
    var row = currentRow();
    if (!row) return;
    var lead = focusedLead();
    if (name === 'quote' || name === 'stage') {
      W.drawer = true;
      paintDrawer();
      return;
    }
    if (name === 'call') {
      var phone = lead && (lead.phone || lead.mobile);
      if (!phone) { toast(lead ? 'No phone on this buyer.' : 'Select a buyer first.'); return; }
      location.href = 'tel:' + String(phone).replace(/[^\d+]/g, '');
      return;
    }
    if (!lead) { toast('Select a buyer first.'); return; }
    var action = name === 'text' ? 'draft_text' : name === 'email' ? 'draft_email' : name === 'link' ? 'link' : '';
    if (!action) return;
    if ((action === 'draft_text' || action === 'draft_email') && !row.verified) {
      toast('Verify the unit first. The draft is not created.');
      return;
    }
    var due = new Date(Date.now() + 86400000).toISOString().slice(0, 10);
    W.busy = true;
    api('bulk_leads', { unit_id: String(row.id), lead_ids: [String(lead.id)], actions: [action], due: due }, true).then(function (j) {
      W.busy = false;
      if (!j.ok) { toast(j.error || 'Could not save the draft.'); return; }
      var word = { draft_text: 'Text draft saved. Nothing was sent.', draft_email: 'Email draft saved. Nothing was sent.', link: 'Buyer linked to this unit.' }[action];
      toast(word);
    });
  }

  function doVerify(id) {
    api('verify', { id: String(id) }, true).then(function (j) {
      if (!j.ok) { toast(j.error || 'Verify failed.'); return; }
      toast('Verified. Reloading the listings.');
      location.reload();
    });
  }

  function doFill(id) {
    toast('Pulling specs…');
    api('fill_specs', { id: String(id) }, true).then(function (j) {
      if (!j.ok) { toast(j.error || 'Could not fill specs.'); return; }
      if (j.unit) W.units[id] = j.unit;
      else if (j.specs && W.units[id]) W.units[id].specs = j.specs;
      var n = Number(j.specs_added) || 0;
      toast(n ? n + ' spec' + (n === 1 ? '' : 's') + ' added.' : (j.specs_note || 'No new specs.'));
      render();
    });
  }

  function ensureUnit(id) {
    if (!id || W.units[id] || W.failed[id]) return Promise.resolve();
    return Promise.all([
      api('unit', { id: id }),
      api('matches', { id: id, limit: 12 })
    ]).then(function (pair) {
      if (pair[0] && pair[0].ok && pair[0].unit) W.units[id] = pair[0].unit;
      else W.failed[id] = (pair[0] && pair[0].error) || 'Could not load this unit.';
      if (pair[1] && pair[1].ok) W.matches[id] = pair[1];
      if (W.sel === id || W.units[id]) render();
    });
  }

  function warm() {
    var pending = W.rows.slice(0, 12).map(function (r) { return r.id; });
    var i = 0;
    function next() {
      if (i >= pending.length) return;
      var id = pending[i++];
      ensureUnit(id).then(next);
    }
    next();
  }

  function loadFeed() {
    return api('feed', { status: 'url', limit: 100 }).then(function (j) {
      if (!j || !j.ok) return;
      (j.units || []).forEach(function (u) { W.feed[u.id] = u; });
      paintLocations();
      render();
    });
  }

  function wireSheet() {
    if (W.wired) return;
    W.wired = true;
    document.addEventListener('click', function (e) {
      var act = e.target.closest('[data-v02-sheet] [data-act]');
      if (act) runAct(act.getAttribute('data-act'));
      if (e.target.closest('[data-close-sheet]')) { W.drawer = false; paintDrawer(); }
    });
  }

  function mountWork() {
    if (!document.querySelector('.ul-tbl')) return;
    if (document.querySelector('[data-v02-work]')) return;
    W.rows = readRows();
    if (!W.rows.length) return;
    wireSheet();
    shell();
    addLocationColumn();
    if (!W.sel) W.sel = W.rows[0].id;
    render();
    loadFeed();
    warm();
  }

  function apply(id, persist) {
    if (id !== 'v01' && id !== 'v02' && id !== 'v03') id = 'v01';
    var root = document.documentElement;
    if (id === 'v02') {
      root.setAttribute('data-hub-theme', 'v02');
      ensureLight();
    } else {
      root.removeAttribute('data-hub-theme');
      dropLight();
      unmountWork();
    }
    document.querySelectorAll('.ul-wrap').forEach(function (el) {
      el.setAttribute('data-ui-theme', id);
    });
    var bodyTheme = document.body && document.body.getAttribute('data-theme');
    if (!document.querySelector('[data-testid=um-theme]') &&
        (bodyTheme === 'v01' || bodyTheme === 'v02' || bodyTheme === 'v03')) {
      document.body.setAttribute('data-theme', id);
    }
    if (persist) {
      try { localStorage.setItem(KEY, id); } catch (e) {}
    }
    paintPressed(id);
    if (id === 'v02') mountWork();
  }

  function boot() {
    mountPicker();
    apply(saved() || pageTheme(), false);
  }

  window.BAM_V02 = { apply: apply, themes: THEMES, workspace: true, readRows: readRows };
  if (document.readyState === 'loading') document.addEventListener('DOMContentLoaded', boot);
  else boot();
})();
