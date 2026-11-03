import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
await p.goto('http://127.0.0.1:5055/pose', { waitUntil: 'networkidle' });
await p.waitForTimeout(1200);
const d = await p.evaluate(() => {
  const t = document.querySelector('.ntable');
  const thead = t.querySelector('thead');
  const tr = thead.querySelector('tr');
  const r0 = t.querySelector('tbody tr');
  const box = (e) => { const x = e.getBoundingClientRect(); return { top: +x.top.toFixed(1), bottom: +x.bottom.toFixed(1), h: +x.height.toFixed(1) }; };
  return {
    theadDisplay: getComputedStyle(thead).display,
    thDisplay: getComputedStyle(thead.querySelector('th')).display,
    thPosition: getComputedStyle(thead.querySelector('th')).position,
    theadBox: box(thead), trBox: box(tr), row0Box: box(r0),
    overlap: box(tr).bottom > box(r0).top + 0.5
  };
});
console.log(JSON.stringify(d, null, 1));
await b.close();
