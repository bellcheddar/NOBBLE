import { chromium } from 'playwright';
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
await page.goto('http://127.0.0.1:5055/', { waitUntil: 'networkidle' });
await page.waitForTimeout(600);
const info = await page.evaluate(() => {
  const table = document.querySelector('#ledger');
  const wrap = document.querySelector('.table-wrap');
  const ths = [...table.querySelectorAll('thead th')].length;
  const rows = [...table.querySelectorAll('tbody tr')];
  return {
    headerCells: ths,
    rowCount: rows.length,
    cellsPerRow: rows.map(r => r.querySelectorAll('td').length),
    tableWidth: table.scrollWidth,
    wrapWidth: wrap.clientWidth,
    overflowing: table.scrollWidth > wrap.clientWidth,
    firstRowHTML: rows[0] ? rows[0].outerHTML.slice(0, 400) : null,
    colWidths: [...table.querySelectorAll('thead th')].map(th => Math.round(th.getBoundingClientRect().width))
  };
});
console.log(JSON.stringify(info, null, 1));
await browser.close();
