import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
await p.goto('http://127.0.0.1:5055/pose', { waitUntil: 'networkidle' });
await p.waitForTimeout(800);
const info = await p.evaluate(() => {
  const wrap = document.querySelector('.table-wrap');
  const table = document.querySelector('.ntable');
  const thead = table.querySelector('thead tr');
  const th = table.querySelector('thead th');
  const rows = [...table.querySelectorAll('tbody tr')];
  const cs = getComputedStyle(table);
  const ths = getComputedStyle(th);
  const r = (el) => { const x = el.getBoundingClientRect(); return [Math.round(x.top), Math.round(x.bottom)]; };
  return {
    borderCollapse: cs.borderCollapse,
    thPosition: ths.position,
    thZIndex: ths.zIndex,
    wrapScrollTop: wrap.scrollTop,
    wrapOverflow: getComputedStyle(wrap).overflow,
    wrapBox: r(wrap),
    theadBox: r(thead),
    row0Box: r(rows[0]),
    row1Box: r(rows[1]),
    theadOffsetTop: thead.offsetTop,
    row0OffsetTop: rows[0].offsetTop
  };
});
console.log(JSON.stringify(info, null, 1));
await b.close();
