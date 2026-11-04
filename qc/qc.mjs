/* Phase 4 QC: screenshots at two viewports, console errors and axe-core.
 * Uses the preinstalled Chromium: never run `playwright install` here. */
import { chromium } from 'playwright';
import { readFileSync, writeFileSync } from 'node:fs';
import { createRequire } from 'node:module';

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
