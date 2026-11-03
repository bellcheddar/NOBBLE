import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
await p.goto('http://127.0.0.1:5055/pose', { waitUntil: 'networkidle' });
const d = await p.evaluate(() => {
  const t = document.querySelector('.ledger');
  const out = { table: getComputedStyle(t).display, thead: getComputedStyle(t.querySelector('thead')).display, tbody: getComputedStyle(t.querySelector('tbody')).display };
  const rules = [];
  for (const sheet of document.styleSheets) {
    let rs; try { rs = sheet.cssRules; } catch (e) { continue; }
    const walk = (list) => { for (const r of list) { if (r.cssRules) { walk(r.cssRules); continue; } if (!r.selectorText) continue; let m=false; try { m = t.matches(r.selectorText); } catch(e){continue;} if (m && /display/.test(r.style.cssText)) rules.push({ sel: r.selectorText, css: r.style.cssText.slice(0,100), sheet: (sheet.href||'inline').split('/').pop() }); } };
    walk(rs);
  }
  out.tableDisplayRules = rules;
  return out;
});
console.log(JSON.stringify(d, null, 1));
await b.close();
