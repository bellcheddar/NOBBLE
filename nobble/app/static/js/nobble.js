/* NOBBLE shared behaviour: pinned selection, tooltips, theme, weights.
 *
 * The pin model is BINMAN's, extended with a PEPTIDE slot (spec Phase 4).
 * Pinning anywhere updates everywhere: the state lives in one place, is
 * mirrored into the URL so a view can be linked, and is persisted per viewer so
 * a reload does not lose it.
 */
(function () {
  'use strict';

  const SLOTS = ['E3', 'GLUE', 'TARGET', 'PEPTIDE'];
  const STORE_KEY = 'nobble-pins';
  const WEIGHT_KEY = 'nobble-weights';

  /* ---------------------------------------------------------------- state */

  const listeners = [];
  let pins = {};

  function readStored(key, fallback) {
    try {
      const raw = localStorage.getItem(key);
      return raw ? JSON.parse(raw) : fallback;
    } catch (e) {
      /* Private mode or blocked site data: the page must still work. */
      return fallback;
    }
  }

  function writeStored(key, value) {
    try { localStorage.setItem(key, JSON.stringify(value)); } catch (e) { /* ignore */ }
  }

  function loadPins() {
    const fromUrl = {};
    const params = new URLSearchParams(window.location.search);
    SLOTS.forEach(function (slot) {
      const value = params.get(slot.toLowerCase());
      if (value) { fromUrl[slot] = value; }
    });
    pins = Object.keys(fromUrl).length ? fromUrl : readStored(STORE_KEY, {});
  }

  function syncUrl() {
    const params = new URLSearchParams(window.location.search);
    SLOTS.forEach(function (slot) {
      const key = slot.toLowerCase();
      if (pins[slot]) { params.set(key, pins[slot]); } else { params.delete(key); }
    });
    const query = params.toString();
    const next = window.location.pathname + (query ? '?' + query : '');
    window.history.replaceState({}, '', next);
  }

  function renderPins() {
    document.querySelectorAll('[data-pin-slot]').forEach(function (node) {
      const slot = node.getAttribute('data-pin-slot');
      const value = pins[slot];
      const valueNode = node.querySelector('[data-pin-value]');
      const clearNode = node.querySelector('[data-pin-clear]');
      if (valueNode) { valueNode.textContent = value || 'none'; }
      node.classList.toggle('pin--empty', !value);
      node.classList.toggle('pin--set', !!value);
      if (clearNode) { clearNode.hidden = !value; }
    });
  }

  function notify() {
    listeners.forEach(function (fn) {
      try { fn(pins); } catch (e) { console.error('pin listener failed', e); }
    });
  }

  const api = {
    slots: SLOTS,
    get: function () { return Object.assign({}, pins); },
    set: function (slot, value) {
      if (SLOTS.indexOf(slot) < 0) { return; }
      if (value) { pins[slot] = String(value); } else { delete pins[slot]; }
      writeStored(STORE_KEY, pins);
      syncUrl();
      renderPins();
      notify();
    },
    setMany: function (next) {
      Object.keys(next || {}).forEach(function (slot) {
        if (SLOTS.indexOf(slot) < 0) { return; }
        if (next[slot]) { pins[slot] = String(next[slot]); } else { delete pins[slot]; }
      });
      writeStored(STORE_KEY, pins);
      syncUrl();
      renderPins();
      notify();
    },
    clear: function () {
      pins = {};
      writeStored(STORE_KEY, pins);
      syncUrl();
      renderPins();
      notify();
    },
    onChange: function (fn) { listeners.push(fn); return fn; },
    /* A pair matches the pins when every set slot agrees. An unset slot does
     * not filter: pinning only an E3 should show all of its pairs. */
    matches: function (pair) {
      return SLOTS.every(function (slot) {
        if (!pins[slot]) { return true; }
        const value = {
          E3: pair.e3_gene,
          GLUE: pair.ligand_key,
          TARGET: pair.peptide_gene,
          PEPTIDE: pair.peptide_id
        }[slot];
        return String(value) === pins[slot];
      });
    }
  };

  /* -------------------------------------------------------------- tooltip */

  const tip = document.getElementById('tip');

  function showTip(html, x, y) {
    if (!tip) { return; }
    tip.innerHTML = html;
    tip.setAttribute('aria-hidden', 'false');
    tip.classList.add('tip--on');
    const box = tip.getBoundingClientRect();
    let left = x + 14;
    let top = y + 14;
    if (left + box.width > window.innerWidth - 8) { left = x - box.width - 14; }
    if (top + box.height > window.innerHeight - 8) { top = y - box.height - 14; }
    tip.style.left = Math.max(8, left) + 'px';
    tip.style.top = Math.max(8, top) + 'px';
  }

  function hideTip() {
    if (!tip) { return; }
    tip.classList.remove('tip--on');
    tip.setAttribute('aria-hidden', 'true');
  }

  /* Every numeric cell carries its raw value, units, percentile and source
   * (spec Phase 4). The markup supplies them as data attributes so the same
   * handler serves tables, cards and chart points. */
  function bindTips(root) {
    (root || document).querySelectorAll('[data-tip]').forEach(function (node) {
      if (node.dataset.tipBound) { return; }
      node.dataset.tipBound = '1';
      const show = function (event) {
        const parts = [];
        if (node.dataset.tipTitle) {
          parts.push('<strong>' + node.dataset.tipTitle + '</strong>');
        }
        parts.push(node.dataset.tip);
        if (node.dataset.tipValue) {
          parts.push('<span class="tip__row">value <b class="mono">' +
            node.dataset.tipValue + '</b>' +
            (node.dataset.tipUnits ? ' ' + node.dataset.tipUnits : '') + '</span>');
        }
        if (node.dataset.tipPercentile) {
          parts.push('<span class="tip__row">percentile <b class="mono">' +
            node.dataset.tipPercentile + '</b></span>');
        }
        if (node.dataset.tipSource) {
          parts.push('<span class="tip__src">' + node.dataset.tipSource + '</span>');
        }
        showTip(parts.join(''), event.clientX, event.clientY);
      };
      node.addEventListener('mouseenter', show);
      node.addEventListener('mousemove', show);
      node.addEventListener('mouseleave', hideTip);
      node.addEventListener('focus', function () {
        const box = node.getBoundingClientRect();
        show({ clientX: box.left, clientY: box.bottom });
      });
      node.addEventListener('blur', hideTip);
    });
  }

  /* -------------------------------------------------------------- weights */

  function loadWeights(defaults) {
    const stored = readStored(WEIGHT_KEY, null);
    return stored || Object.assign({}, defaults);
  }

  function saveWeights(weights) { writeStored(WEIGHT_KEY, weights); }

  /* The composite is recomputed in the browser, which is why the sliders
   * re-rank without a server round trip. It is only ever a re-weighting of
   * components the pipeline already measured: nothing new is computed here. */
  function composite(pair, weights) {
    let total = 0;
    let used = 0;
    Object.keys(weights).forEach(function (key) {
      const weight = Number(weights[key]);
      if (!weight) { return; }
      let value = pair[key];
      if (value === null || value === undefined) { return; }
      if (key === 'bridge_percentile') { value = value / 100; }
      if (key === 'delta_iptm') { value = Math.max(0, Math.min(1, (value + 1) / 2)); }
      total += weight * value;
      used += weight;
    });
    return used ? total / used : null;
  }

  /* ---------------------------------------------------------------- theme */

  function bindTheme() {
    const button = document.querySelector('[data-theme-toggle]');
    if (!button) { return; }
    button.addEventListener('click', function () {
      const root = document.documentElement;
      const current = root.getAttribute('data-theme');
      const dark = current === 'dark' ||
        (!current && window.matchMedia('(prefers-color-scheme: dark)').matches);
      const next = dark ? 'light' : 'dark';
      root.setAttribute('data-theme', next);
      try { localStorage.setItem('nobble-theme', next); } catch (e) { /* ignore */ }
      window.dispatchEvent(new CustomEvent('nobble:theme', { detail: next }));
    });
  }

  /* ----------------------------------------------------------------- init */

  function init() {
    loadPins();
    renderPins();
    bindTips(document);
    bindTheme();
    document.querySelectorAll('[data-pin-clear]').forEach(function (node) {
      node.addEventListener('click', function () {
        api.set(node.getAttribute('data-pin-clear'), null);
      });
    });
    const reset = document.querySelector('[data-pin-reset]');
    if (reset) { reset.addEventListener('click', api.clear); }
  }

  window.NOBBLE = {
    pins: api,
    tip: { show: showTip, hide: hideTip, bind: bindTips },
    weights: { load: loadWeights, save: saveWeights, composite: composite },
    plotLayout: function (extra) {
      const styles = getComputedStyle(document.documentElement);
      return Object.assign({
        autosize: true,
        margin: { l: 56, r: 18, t: 28, b: 52 },
        font: {
          family: "'Spline Sans', system-ui, sans-serif",
          size: 12,
          color: styles.getPropertyValue('--ink').trim() || '#15171A'
        },
        paper_bgcolor: 'rgba(0,0,0,0)',
        plot_bgcolor: 'rgba(0,0,0,0)',
        hoverlabel: { font: { family: "'IBM Plex Mono', monospace", size: 11 } }
      }, extra || {});
    },
    plotConfig: {
      responsive: true,
      displaylogo: false,
      modeBarButtonsToRemove: ['autoScale2d'],
      toImageButtonOptions: { format: 'png', scale: 2 }
    }
  };

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
