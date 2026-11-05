/* Run delta.html's own ROC construction outside a browser, so the Python and
 * the JavaScript AUCs can be compared by running both rather than by reading
 * them.
 *
 * The Delta tab shows two AUCs for one curve: the sentence above it carries
 * `roc_summary.auc`, computed in Python and rank-based, and the chart's title
 * carries a trapezoid integrated in the browser over points the browser
 * built. They agree, and nothing compared them, which is the pair
 * `qc/composite_harness.mjs` exists for one statistic down (F123, F204).
 *
 *     node qc/roc_harness.mjs <delta.html> <pairs.json> <minimum-per-side>
 *
 * The minimum is passed in rather than defaulted here, because the template
 * injects it from `config/thresholds.toml` and a second copy in this file
 * would be a cutoff written in JavaScript.
 *
 * where pairs.json is the PAIRS payload. Prints one JSON line:
 * {"auc": <number>, "points": <count>} or {"empty": "<reason>"}.
 */
import { readFileSync } from 'node:fs';

const [templatePath, payloadPath, minimumPerSide] = process.argv.slice(2);
const template = readFileSync(templatePath, 'utf8');
const PAIRS = JSON.parse(readFileSync(payloadPath, 'utf8'));

const match = template.match(/  function buildRoc\(\) \{[\s\S]*?\n  \}\n/);
if (!match) {
  console.log(JSON.stringify({ error: 'buildRoc is no longer a named function' }));
  process.exit(2);
}

/* The smallest stubs that let the real function run: it writes to two
 * elements and hands its points to Plotly. Capturing the Plotly call is how
 * the AUC is read, because the title is where the browser puts it. */
let captured = null;
let emptyReason = null;
const stubs = {
  document: {
    getElementById: (id) => ({
      set hidden(_v) {},
      get hidden() { return false; },
      set textContent(v) { if (id === 'roc-counts') { emptyReason = v; } },
      get textContent() { return ''; },
    }),
  },
  Plotly: {
    newPlot: (_node, _traces, layout) => { captured = layout; },
  },
  /* `buildRoc` hands its layout through nobble.js's shared helper, which
   * applies the Depot palette and fonts. Returned unchanged here: this
   * harness is about the number in the title, not about presentation. */
  NOBBLE: {
    plotLayout: (layout) => layout,
  },
};

const run = new Function(
  'document', 'Plotly', 'PAIRS', 'ROC_MINIMUM_PER_SIDE', 'NOBBLE',
  match[0] + '\nreturn buildRoc();'
);
run(stubs.document, stubs.Plotly, PAIRS, Number(minimumPerSide), stubs.NOBBLE);

if (!captured) {
  console.log(JSON.stringify({ empty: emptyReason || 'no curve drawn' }));
} else {
  const title = String(captured.title?.text ?? '');
  const found = title.match(/AUC\s+([0-9.]+)/);
  console.log(JSON.stringify({
    auc: found ? Number(found[1]) : null,
    title,
  }));
}
