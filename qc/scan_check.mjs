/* Measure that the design tab's scan profile actually plots, rather than
   reading the HTML and assuming. The chart has no data until a design scan
   has run, so this points at a server seeded with a synthetic profile:
   finding a broken chart after 4.9 hours of compute would be expensive.

   Usage: node qc/scan_check.mjs [base-url] */
import { chromium } from 'playwright';

const BASE = process.argv[2] || 'http://127.0.0.1:5056';
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const errors = [];
page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
page.on('pageerror', e => errors.push(String(e)));

await page.goto(`${BASE}/design`, { waitUntil: 'networkidle' });
const present = await page.locator('#scan').count();
const plotted = await page.evaluate(() => {
  const node = document.getElementById('scan');
  return node && node.data && node.data[0] ? node.data[0].x.length : 0;
});
const negatives = await page.evaluate(() => {
  const node = document.getElementById('scan');
  if (!node || !node.data || !node.data[0]) { return 0; }
  return node.data[0].y.filter(v => v < 0).length;
});
if (present) { await page.locator('#scan').screenshot({ path: 'qc/screenshots/design-scan.png' }); }
console.log(JSON.stringify({
  chartPresent: present, barsPlotted: plotted, negativeBars: negatives,
  consoleErrors: errors,
}, null, 2));
await browser.close();
process.exit(present && plotted ? 0 : 1);
