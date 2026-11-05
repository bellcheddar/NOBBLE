# Browser QC

Two entry points are supported and run as a gate:

| Script | What it does |
|---|---|
| `qc.mjs` | The gate. Fourteen captures at two viewports, every page's status, console errors, axe-core serious violations, and it runs `copy_budget.mjs`. Reports the build fingerprint it tested, so a clean report cannot describe a server started hours earlier (F138). |
| `copy_budget.mjs` | CLAUDE.md's copy budget, measured on the rendered page rather than parsed from templates. Exits 4 when over, which `qc.mjs` keys on (F139). |

Both read `NOBBLE_BASE`, default `http://127.0.0.1:5055`, so either runs
against the live site. Pointed at production they are clean; pointed at a
158-pair atlas they found F202.

Three probes still work and answer a live question: `webgl.mjs`,
`axe_detail.mjs`, `find_rule.mjs`, and `table_check.mjs` after F202 repaired
it. That repair was worth making because the question it asks, whether the
sticky header holds its geometry against scrolled rows, is still a property
of the page.

Five do not run against the current markup: `sticky_test.mjs`,
`dom_check.mjs`, `clean_measure.mjs`, `scan_check.mjs`, `zinc_check.mjs`.
They were written against `.ledger` and `#ledger`, which were BINMAN's
classes in the shared `depot.css` before NOBBLE renamed its table to
`.ntable` to stop colliding with the design system, and `nobble.css` records
that rename. They are kept because they record how a question was answered
at the time, and they are not repaired because the elements they measured no
longer exist: restoring them would mean inventing a new measurement rather
than reviving an old one, and a probe that measures something nobody asked
about is worse than one that is plainly historical.

So: run `qc.mjs`. If one of the five crashes with a TypeError on a null
element, that is this, not a fault in the page.
