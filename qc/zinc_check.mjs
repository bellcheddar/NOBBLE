/* Does a zinc-bearing Sievers pose render, and does the glue keep its own
   presentation beside it? The main campaign has 120 such pairs and the
   viewer has never seen one. Points at a static page serving a real
   smoke-test structure (chains A, P, Z=ZN, L=Y70). */
import { chromium } from 'playwright';
const BASE = process.argv[2];
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1000, height: 700 } });
const errors = [];
page.on('console', m => { if (m.type() === 'error') errors.push(m.text()); });
page.on('pageerror', e => errors.push(String(e)));
await page.goto(BASE, { waitUntil: 'networkidle' });
await page.waitForFunction(() => window.__ready === true || window.__err, null, { timeout: 60000 });
await page.waitForTimeout(3000);
const info = await page.evaluate(() => {
  const v = window.__viewer;
  const p = v && (v.plugin && (v.plugin.plugin || v.plugin));
  if (!p) { return { error: window.__err || 'no plugin' }; }
  const structures = p.managers.structure.hierarchy.current.structures || [];
  const comps = structures.flatMap(s => (s.components || []).map(c => {
    let label = ''; try { label = String(c.cell.obj.label || ''); } catch (e) {}
    return { key: String(c.key || ''), label,
             reprs: (c.representations || []).map(r => {
               try { return r.cell.obj.data.repr.label || r.cell.transform.params.type.name; }
               catch (e) { return '?'; } }) };
  }));
  return { error: window.__err, components: comps };
});
await page.screenshot({ path: 'qc/screenshots/zinc-pose.png' });
console.log(JSON.stringify({ ...info, consoleErrors: errors }, null, 2));
await browser.close();
