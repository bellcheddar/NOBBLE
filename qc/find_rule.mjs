import { chromium } from 'playwright';
const b = await chromium.launch();
const p = await b.newPage({ viewport: { width: 1440, height: 900 } });
await p.goto('http://127.0.0.1:5055/pose', { waitUntil: 'networkidle' });
const hits = await p.evaluate(() => {
  const el = document.querySelector('.ledger thead');
  const out = [];
  for (const sheet of document.styleSheets) {
    let rules; try { rules = sheet.cssRules; } catch (e) { out.push({ error: 'blocked', sheet: sheet.href }); continue; }
    const walk = (list, media) => {
      for (const rule of list) {
        if (rule.cssRules) { walk(rule.cssRules, rule.conditionText || rule.media?.mediaText || media); continue; }
        if (!rule.selectorText) continue;
        let m = false; try { m = el.matches(rule.selectorText); } catch (e) { continue; }
        if (m) out.push({ sheet: (sheet.href || 'inline').split('/').pop(), media: media || null, selector: rule.selectorText, css: rule.style.cssText.slice(0, 160) });
      }
    };
    walk(rules, null);
  }
  return out;
});
console.log(JSON.stringify(hits, null, 1));
await b.close();
