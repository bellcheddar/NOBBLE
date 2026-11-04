import { chromium } from 'playwright';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
const require = createRequire(import.meta.url);
const axeSource = readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8');
const target = process.argv[2] || '/benchmark';
/* Was hardcoded to the live site while qc.mjs ran against localhost, so the
 * two reported different violations and neither said which host it had
 * looked at. That is F138 in a second file: a check whose subject is not
 * the thing you think you are checking. Defaults to the live site because
 * that is what it was for, and says so. */
const BASE = process.env.NOBBLE_BASE || 'https://nobble.mdeller.com';
console.log('axe ' + BASE + target);
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto(BASE + target, { waitUntil: 'networkidle' });
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
