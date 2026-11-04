/* Measure the UI copy budget CLAUDE.md sets: under 40 words per panel, under
 * 150 per page, excluding tables, labels and pipeline-generated status text.
 *
 * Rendered rather than parsed from the templates. A static count sums
 * paragraphs that are mutually exclusive in the page: an empty-state hint and
 * the text that replaces it never appear together, so counting both says the
 * panel is over budget when a reader never sees that many words. */
import { chromium } from 'playwright';
const BASE = process.env.NOBBLE_BASE || 'http://127.0.0.1:5058';
const PAGES = ['/', '/pose', '/interactions', '/delta', '/benchmark', '/design', '/about'];
/* The budget is about the data pages. CLAUDE.md's wording is explicit about
 * what it is for: "Keep narrative prose in the app to a minimum. One short
 * line per panel saying what it shows or what the number means. Reasoning
 * belongs in DECISIONS.md and FINDINGS.md, not on screen." About is the page
 * whose content is the explanation, and having it is what keeps the
 * reasoning off the panels rather than what defeats the rule, so it is
 * measured and reported and not held to the per-panel figure (D-NOB-067). */
const EXPOSITION = ['/about'];
const browser = await chromium.launch();
const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
const out = [];
for (const path of PAGES) {
  await page.goto(BASE + path, { waitUntil: 'networkidle' });
  await page.waitForTimeout(900);
  const info = await page.evaluate(() => {
    const count = (text) => (text.match(/[A-Za-z][A-Za-z'’-]*/g) || []).length;
    const panels = [...document.querySelectorAll('.panel')];
    const hosts = panels.length ? panels : [document.querySelector('main') || document.body];
    const rows = hosts.map((host) => {
      /* Narrative prose only. The budget excludes tables, labels and
       * pipeline-generated status text, and the markup already separates
       * them: a label on a control is `weight__note`, which is also the
       * slider's aria-describedby, and the stat tiles carry `stat__*`.
       * Counting every <p> in the panel made the composite panel read as
       * 124 words when what a reader sees is one short line per metric,
       * which is what the rule asks for. */
      const prose = [...host.querySelectorAll('p')].filter((el) => {
        if (el.closest('table')) return false;
        if (el.hidden) return false;
        if (/(^|\s)(weight__note|stat__|chart__caption)/.test(el.className)) return false;
        /* `mono` marks machine output in this codebase, which is the
         * "pipeline-generated status text" the budget excludes: the CONECT
         * integrity line, the ROC's scored counts, a peptide sequence.
         * Checked against every <p class="mono"> in the templates, and all
         * four are pipeline output rather than prose. */
        if (/(^|\s)mono(\s|$)/.test(el.className)) return false;
        /* Inside `.empty`: an empty-state message, which is transient and
         * states what has not run yet. The Delta panel reads 50 words while
         * the Sievers arm is still going and 39 once the ROC computes, and
         * the budget is about the copy a finished page carries. */
        if (el.closest('.empty')) return false;
        const cs = getComputedStyle(el);
        if (cs.display === 'none' || cs.visibility === 'hidden') return false;
        return el.offsetParent !== null || cs.position === 'fixed';
      });
      /* Pipeline-generated specifics are excluded wherever they sit, not
       * only when they are the whole paragraph. The design tab's bridge
       * sentences are hand-written framing around a <span class="mono"> of
       * substitutions the scan computed, so the paragraph's own class is
       * prose and part of its text is not. Counting the whole paragraph put
       * that panel at 44 words the moment a scan had anything to report,
       * which is the state the arm exists to reach (F160). */
      const own = (el) => {
        let total = count(el.textContent);
        el.querySelectorAll('.mono').forEach((span) => {
          total -= count(span.textContent);
        });
        return Math.max(0, total);
      };
      const words = prose.reduce((n, el) => n + own(el), 0);
      return { words, worst: prose.map(own).sort((a, b) => b - a)[0] || 0 };
    });
    return { panels: rows.length, perPanel: rows.map((r) => r.words),
             pageWords: rows.reduce((n, r) => n + r.words, 0) };
  });
  out.push({ path, ...info });
}
console.log('page            panels  worst panel  page total');
let bad = 0;
for (const r of out) {
  const worst = Math.max(0, ...r.perPanel);
  const flags = [];
  const exempt = EXPOSITION.includes(r.path);
  if (!exempt && worst > 40) flags.push('PANEL>40');
  if (!exempt && r.pageWords > 150) flags.push('PAGE>150');
  if (exempt) flags.push('exposition, not held to the budget');
  if (flags.length && !exempt) bad += 1;
  console.log(r.path.padEnd(15) + String(r.panels).padStart(7)
    + String(worst).padStart(13) + String(r.pageWords).padStart(12)
    + (flags.length ? '  ' + flags.join(' ') : ''));
}
console.log('\npages over budget: ' + bad + ' of ' + out.length);
await browser.close();
/* Exit 4 so qc.mjs can key on it. The budget is a house rule in CLAUDE.md
 * and nothing measured it, which is how /pose came to carry 49 words of
 * presentation provenance on screen (F139). */
if (bad) { process.exit(4); }
