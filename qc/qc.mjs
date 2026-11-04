/* Phase 4 QC: screenshots at two viewports, console errors and axe-core.
 * Uses the preinstalled Chromium: never run `playwright install` here. */
import { chromium } from 'playwright';
import { readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { execFileSync } from 'node:child_process';

const BASE = process.env.NOBBLE_BASE || 'http://127.0.0.1:5055';
const PAGES = ['/', '/pose', '/interactions', '/delta', '/benchmark', '/design', '/about'];
const VIEWPORTS = [
  { name: 'desktop', width: 1440, height: 900 },
  { name: 'mobile', width: 390, height: 844 }
];

const require = createRequire(import.meta.url);
let axeSource = null;
try {
  axeSource = readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');
} catch (e) {
  console.log('axe-core not installed: accessibility check skipped');
}

/* Which build is answering on BASE. A server left running from earlier in
 * the build serves the old templates and the old routes, and this report
 * then comes back clean because the old build was clean: 14 pages, 0
 * non-200, 0 console errors, against a process started hours before the
 * change it was meant to be checking (F138).
 *
 * The expected value comes from tools/app_fingerprint.py rather than being
 * recomputed here. Two implementations of one hash drift, and the symptom of
 * that drift is this check refusing a server that is in fact current. */
const PY = process.env.NOBBLE_PY
  || '../BINMAN/.pixi/envs/default/bin/python';
let expected = null;
try {
  expected = execFileSync(PY, ['tools/app_fingerprint.py'],
    { encoding: 'utf8', env: { ...process.env, PYTHONPATH: '.' } }).trim();
} catch (e) {
  console.log('could not compute the expected fingerprint: ' + e.message);
}
if (expected) {
  /* Retried, and an unreachable server reported as unreachable.
   *
   * This fetched once and treated a failure the same as a missing field, so
   * a server still binding its port was reported as "does not report a
   * source fingerprint", which blames the build for an operator's timing.
   * It happened to me pointing QC at a server I had just started (F159).
   *
   * Three attempts over about two seconds: enough for a Flask process that
   * has printed its banner, and not a wait loop that hides a server which
   * is never coming up. */
  let health = null;
  let reached = false;
  let cause = 'no attempt made';
  for (let attempt = 0; attempt < 3 && !reached; attempt += 1) {
    if (attempt) { await new Promise((done) => setTimeout(done, 700)); }
    try {
      const response = await fetch(BASE + '/healthz');
      reached = true;
      health = await response.json().catch(() => null);
    } catch (e) {
      health = null;
      cause = (e.cause && (e.cause.code || e.cause.message)) || e.message;
    }
  }
  if (!reached) {
    /* The cause matters, because one of them is not about the server at all.
     * Node and Chromium refuse a list of unsafe ports, 5060 and 5061 among
     * them as SIP, and the failure is "bad port": the server is running, curl
     * reaches it, and this cannot. Told to start the server, an operator
     * restarts a server that was never down. The documented local port, 5055,
     * is not on the list, so this only bites someone who picked a port
     * (F159). */
    console.error('FAIL: nothing answered ' + BASE + '/healthz after three '
      + 'attempts (' + cause + ').');
    if (String(cause).includes('bad port')) {
      console.error('       That is node refusing the port, not the server '
        + 'being down: 5060 and 5061 are on the unsafe-port list. Use '
        + 'another port; 5055 is the one PROGRESS.md documents.');
    } else {
      console.error('       Start the server, or set NOBBLE_BASE. This says '
        + 'nothing about which build it would be running.');
    }
    process.exit(3);
  }
  const serving = health && health.source_fingerprint;
  if (!serving) {
    console.error('FAIL: ' + BASE + ' answered /healthz and reports no '
      + 'source_fingerprint, so it is running code from before that check '
      + 'and there is no way to tell which build it is.');
    process.exit(3);
  }
  if (serving !== expected) {
    console.error('FAIL: ' + BASE + ' is serving build ' + serving
      + ', the working tree is ' + expected
      + '. Restart the server before trusting this report. '
      + 'Run `' + PY + ' tools/app_fingerprint.py --detail` on both to see '
      + 'which files differ.');
    process.exit(3);
  }
  console.log('build          : ' + serving);
}

/* The UI copy budget, measured in the browser because the rule is about what
 * a reader sees: a static count of the templates sums paragraphs that are
 * mutually exclusive in the page and called the composite panel 124 words
 * when a reader sees 23 (F139). Run as its own process so the measurement
 * and this report stay separable. */
let copyBudget = 'not run';
try {
  execFileSync(process.execPath, ['qc/copy_budget.mjs'],
    { encoding: 'utf8', env: { ...process.env, NOBBLE_BASE: BASE } });
  copyBudget = 'within budget';
} catch (e) {
  if (e.status === 4) {
    copyBudget = 'OVER BUDGET';
    console.error((e.stdout || '').trim());
  } else {
    copyBudget = 'could not measure: ' + e.message.split('\n')[0];
  }
}

const report = { pages: [], consoleErrors: [], axe: [] };
const browser = await chromium.launch();

for (const viewport of VIEWPORTS) {
  const context = await browser.newContext({
    viewport: { width: viewport.width, height: viewport.height }
  });
  const page = await context.newPage();

  page.on('console', (message) => {
    if (message.type() === 'error') {
      report.consoleErrors.push({ viewport: viewport.name, url: page.url(), text: message.text() });
    }
  });
  page.on('pageerror', (error) => {
    report.consoleErrors.push({ viewport: viewport.name, url: page.url(), text: String(error) });
  });

  for (const path of PAGES) {
    const response = await page.goto(BASE + path, { waitUntil: 'networkidle', timeout: 45000 });
    await page.waitForTimeout(900);
    const slug = path === '/' ? 'campaign' : path.replace(/\//g, '');
    const file = `qc/screenshots/${slug}-${viewport.name}.png`;
    await page.screenshot({ path: file, fullPage: true });
    report.pages.push({
      path, viewport: viewport.name, status: response ? response.status() : null, file
    });

    if (axeSource && viewport.name === 'desktop') {
      await page.evaluate(axeSource);
      const results = await page.evaluate(async () => await window.axe.run(document, {
        runOnly: { type: 'tag', values: ['wcag2a', 'wcag2aa'] }
      }));
      const serious = results.violations.filter(
        (v) => v.impact === 'serious' || v.impact === 'critical'
      );
      report.axe.push({
        path,
        total: results.violations.length,
        serious: serious.length,
        detail: serious.map((v) => ({ id: v.id, impact: v.impact, nodes: v.nodes.length, help: v.help }))
      });
    }
  }
  await context.close();
}

await browser.close();
writeFileSync('qc/qc_report.json', JSON.stringify(report, null, 2));

console.log('pages captured :', report.pages.length);
console.log('non-200        :', report.pages.filter((p) => p.status !== 200).length);
console.log('copy budget    :', copyBudget);
console.log('console errors :', report.consoleErrors.length);
report.consoleErrors.slice(0, 8).forEach((e) => console.log('   ', e.viewport, e.text.slice(0, 150)));
if (report.axe.length) {
  const serious = report.axe.reduce((sum, a) => sum + a.serious, 0);
  console.log('axe serious    :', serious);
  report.axe.forEach((a) => {
    if (a.serious) {
      console.log('   ', a.path, a.detail.map((d) => `${d.id}(${d.nodes})`).join(' '));
    }
  });
}
