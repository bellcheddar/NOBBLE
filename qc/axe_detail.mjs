import { chromium } from 'playwright';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const axeSource = readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');
const target = process.argv[2] || '/benchmark';
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto('https://nobble.mdeller.com' + target, { waitUntil: 'networkidle' });
await page.evaluate(axeSource);
const res = await page.evaluate(async () => await window.axe.run(document, { runOnly: { type: 'tag', values: ['wcag2a','wcag2aa'] } }));
res.violations.filter(v => ['serious','critical'].includes(v.impact)).forEach(v => {
  console.log('==', v.id, v.impact, v.nodes.length, 'nodes');
  v.nodes.slice(0, 6).forEach(n => {
    console.log('  target:', n.target.join(' '));
    const summary = (n.failureSummary || '').replace(/\n+/g, ' | ');
    console.log('  ', summary.slice(0, 220));
  });
});
await browser.close();
