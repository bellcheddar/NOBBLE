# NOBBLE decision log

Seeded from BUILD_SPEC.md Section 8. Decisions D-NOB-008 onward are made during
the unattended build: each records the decision, the alternatives, the reason and
how to reverse it.

| ID | Decision | Date |
|---|---|---|
| D-NOB-001 | Tier 1 runs ternaries and retains full scoring, rather than binary-only triage with ternaries reserved for survivors | 2026-11-03 |
| D-NOB-002 | Tier B (ligandable unproven) is included in the first campaign rather than deferred until Tier A calibration completes | 2026-11-03 |
| D-NOB-003 | GSPT1 and BRD4 are mandatory benchmark panel members, as community standards. BRD4 runs on both VHL and CRBN arms | 2026-11-03 |
| D-NOB-004 | Token cap of 400 for tier 1, with VHL (VCB trimer) and DCAF15 (DDB1 BPA-BPC + DDA1) as declared structural exceptions | 2026-11-03 |
| D-NOB-005 | Affinity head is recorded for the small-molecule chain only and is never a ranking key. No peptide affinity is reported | 2026-11-03 |
| D-NOB-006 | Composite weights are fitted on the benchmark panel and the Sievers matched set, not hand-set | 2026-11-03 |
| D-NOB-007 | NOBBLE is a BoltzMaker campaign preset plus a fifth BINMAN module, not a standalone stack. Shared code is widened in place in those repositories, never forked | 2026-11-03 |

---

## D-NOB-008: consume BINMAN's stores as SQLite plus TSV, not DuckDB

**Date:** 2026-11-03

**Decision.** Spec 2 states NOBBLE consumes "BINMAN's DuckDB store". BINMAN has no
DuckDB file: it ships `data/atlas/binman.sqlite` (12 tables, the serve-time atlas,
including `bridge` at 285,996 rows and `ligase` at 650 rows, both exactly as the
spec expects) and the curated source datasets as TSV under `data/validation/`.
NOBBLE reads the SQLite atlas read-only (`mode=ro`) and the TSVs directly, and
keeps its own analytical store at `data/nobble.duckdb`.

**Alternatives.** Convert BINMAN's atlas to DuckDB first (adds a copy that can
drift from the source of truth); or ask Marc (forbidden in unattended mode).

**Reason.** The spec's intent is "do not re-acquire, read what BINMAN already
curated". The file format was an incidental assumption in the spec. Reading the
real store read-only honours the intent and cannot corrupt BINMAN.

**Reversal.** Change `nobble/curate/binman_store.py`; the table and column names
are unchanged either way.

---

## D-NOB-009: benchmark resolver matches composite accessions by token, and uses PROTAC-DB for the bivalent arms

**Date:** 2026-11-03

**Decision.** The benchmark resolver (spec 3.1) splits MGTbind's
`protein_*_uniprot_id` on underscore and matches by set membership, and it
resolves the two BRD4 PROTAC arms from `protacdb_protacs` rather than MGTbind.

**Reason.** Two findings from the real data, both of which make the literal spec
reading fail:

1. MGTbind encodes multi-protein receptors as underscore-joined composites
   (`ELOB_ELOC_VHL`, `DDB1_CRBN`, `DDB1_DCAF15_DDA1`, `Q9NYV4_O75909`). Exact
   accession equality returns zero rows for every panel member whose receptor is
   a complex, which is most of them. Token matching resolves 5 of 7 immediately,
   and as a side effect encodes the VCB and DCAF15 trimer exceptions of spec 1.1
   directly from the deposited stoichiometry rather than by assertion.
2. MGTbind is a molecular-glue database and deliberately carries no PROTACs: MZ1,
   dBET, ARV and AT1 all return zero rows. `protacdb_protacs` carries both, with
   PDB identifiers, which is consistent with spec 2.1 listing PROTAC-DB as the
   bivalent class source.

Resolved panel: GSPT1/CRBN/CC-885 **5HXB**; BRD4/VHL/MZ1 **5T35**;
BRD4-BD1/CRBN/dBET57 **6BNB**; IKZF1/CRBN **6H0F** and five others;
CK1alpha/CRBN/lenalidomide **5FQD**; RBM39/DCAF15/indisulam **6PAI** and six
others; cyclin K/DDB1/CR-8 **6TD3** and 29 others. All seven resolve, so the
Phase 1 gate is satisfiable.

**Alternatives.** Hardcode the accessions (spec 3.1 forbids it, and it is the
named source of silent error); or query RCSB for every pair (slower, and the
local data already answers it).

**Reversal.** `nobble/curate/benchmark.py`, functions `_accession_tokens` and
`resolve_panel`.

---

## D-NOB-010: Degronopedia and ProtCID are unavailable, so the furniture veto is reported as not computed

**Date:** 2026-11-03

**Decision.** BINMAN's own Gate G7 records that `degronopedia` and
`protcid_interfaces` could not be acquired automatically (both publish through a
JavaScript front end with no bulk-export endpoint). NOBBLE therefore:

- assigns degron motif classes from `degron.motif_family` in BINMAN's atlas and
  the Koren 2018 C-degron rules, not from Degronopedia;
- computes every other score, and reports the ProtCID packing-only veto of spec
  4.7 as `furniture: null` with status `not_computed: protcid_unavailable`,
  never as `false`.

**Reason.** Spec 4.7 makes the furniture veto a flag, not a ranking key, so its
absence degrades one column rather than blocking the campaign. Recording it as
`false` would assert a check that was never run, which is the failure mode the
spec's own validation section is written against.

**Alternatives.** Substitute a hand-written packing control (BINMAN spec 4.1b
forbids this, for good reason); block the build (disproportionate for a flag).

**Reversal.** Place the two files under `BINMAN/data/validation/raw/` and re-run
BINMAN's `pipeline/acquire_validation.py --refresh`, then NOBBLE's scoring stage.

---

## D-NOB-011: nobble.mdeller.com resolves but is not yet serving NOBBLE

**Date:** 2026-11-03

**Decision.** Recorded as a Gate G3 item rather than treated as done.

**Finding.** `nobble.mdeller.com` resolves to the droplet (45.55.102.228, the same
host as binman.mdeller.com) and answers HTTP 200 on port 80, but with nginx's
default welcome page: there is no NOBBLE vhost. HTTPS fails certificate
verification because the only certificate presented covers
`alphabetti.mdeller.com`. So the DNS half of "live" is done and the server half
is not.

**Consequence.** The deploy script is written but not run. G3 needs an nginx
vhost for the subdomain and a certbot certificate, both root actions on the
droplet.

**Reversal.** Not applicable: this is a finding, not a choice.
