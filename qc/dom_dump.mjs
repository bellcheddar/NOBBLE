import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage();
await p.goto('http://127.0.0.1:5055/pose', { waitUntil: 'networkidle' });
const d = await p.evaluate(() => {
  const t = document.querySelector('.ledger');
  const thead = t.querySelector('thead');
  return {
    tableTag: t.tagName,
    tableParent: t.parentElement.className,
    theadParent: thead.parentElement.tagName,
    theadChildren: [...thead.children].map(c => c.tagName),
    tableChildren: [...t.children].map(c => c.tagName),
    headSnippet: thead.outerHTML.slice(0, 200),
    tableOpen: t.outerHTML.slice(0, 160)
  };
});
console.log(JSON.stringify(d, null, 1));
await b.close();
