import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
await p.goto('http://127.0.0.1:5055/pose', { waitUntil: 'networkidle' });
await p.waitForTimeout(500);
const measure = () => p.evaluate(() => {
  const t = document.querySelector('.ledger');
  const th = t.querySelector('thead tr'), r0 = t.querySelector('tbody tr');
  const bb = (e) => { const x = e.getBoundingClientRect(); return [Math.round(x.top), Math.round(x.bottom)]; };
  return { thead: bb(th), row0: bb(r0), overlap: bb(th)[1] > bb(r0)[0] };
});
console.log('with sticky     :', JSON.stringify(await measure()));
await p.addStyleTag({ content: '.ledger th { position: static !important; }' });
await p.waitForTimeout(300);
console.log('sticky disabled :', JSON.stringify(await measure()));
// and the display of thead
const d = await p.evaluate(() => {
  const th = document.querySelector('.ledger thead');
  const cs = getComputedStyle(th);
  return { display: cs.display, position: cs.position, theadHeight: Math.round(th.getBoundingClientRect().height) };
});
console.log('thead           :', JSON.stringify(d));
await b.close();
