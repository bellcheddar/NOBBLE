/* Run nobble.js's real `composite` outside a browser, so the Python and the
 * JavaScript implementations of spec 4.8 can be compared by running both
 * rather than by reading them.
 *
 * Two implementations of one formula agree until they do not, and the page
 * recomputes the composite on every slider move while the pipeline stores
 * its own. `tests/test_composite_agreement.py` drives this (F123).
 *
 *     node qc/composite_harness.mjs <nobble.js> <input.json>
 *
 * where input.json is {"rows": [...], "weights": {...}} and the output is one
 * JSON line per row.
 */
import { readFileSync } from 'node:fs';
import vm from 'node:vm';

const store = new Map();
const noop = () => {};
const element = {
  addEventListener: noop, removeEventListener: noop, setAttribute: noop,
  getAttribute: () => null, querySelector: () => null,
  querySelectorAll: () => [], classList: { add: noop, remove: noop, toggle: noop },
  style: {}, dataset: {}, textContent: '', innerHTML: ''
};
const sandbox = {
  console,
  window: {},
  document: {
    readyState: 'complete',
    addEventListener: noop,
    querySelector: () => null,
    querySelectorAll: () => [],
    getElementById: () => null,
    getElementsByClassName: () => [],
    getElementsByTagName: () => [],
    documentElement: element,
    body: element,
    createElement: () => element
  },
  localStorage: {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k)
  },
  location: { search: '', hash: '', href: 'http://localhost/' },
  history: { replaceState: noop },
  matchMedia: () => ({ matches: false, addEventListener: noop }),
  CustomEvent: class { constructor(t, o) { this.type = t; this.detail = o && o.detail; } },
  URLSearchParams
};
sandbox.window = sandbox;
sandbox.globalThis = sandbox;

const source = readFileSync(process.argv[2], 'utf8');
vm.createContext(sandbox);
new vm.Script(source).runInContext(sandbox);

const composite = sandbox.window.NOBBLE.weights.composite;
const payload = JSON.parse(readFileSync(process.argv[3], 'utf8'));
const out = payload.rows.map(row => {
  const result = composite(row, payload.weights);
  return { pair_id: row.pair_id, score: result.score,
           components: result.components, requested: result.requested,
           complete: result.complete };
});
console.log(JSON.stringify(out));
