import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
await p.goto('http://127.0.0.1:5055/pose', { waitUntil: 'networkidle' });
await p.waitForTimeout(800);
const info = await p.evaluate(() => {
  /* The first `.ntable` on /pose is the tier-2 refinement comparison,
   * which sits inside a `hidden` #refinement wrapper until a refinement
   * exists, so it has no body rows and `rows[0]` was undefined: this
   * harness crashed with "Cannot read properties of undefined" against
   * every atlas, at seven pairs and at 158 alike. It measures a sticky
   * header against scrolled rows, so it wants the table that has some.
   * Nothing runs this script, which is why the rot went unnoticed; a
   * diagnostic that crashes is worse than none, because the crash reads
   * as a fault in the page. */
  const table = Array.from(document.querySelectorAll('.ntable'))
    .find((t) => t.offsetParent !== null && t.querySelectorAll('tbody tr').length > 1);
  if (!table) { return { skipped: 'no visible table with rows on /pose' }; }
  const wrap = table.closest('.table-wrap') || document.querySelector('.table-wrap');
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
