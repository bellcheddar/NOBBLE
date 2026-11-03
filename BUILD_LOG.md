# NOBBLE build log

2026-11-03T18:39:32Z  Phase 0: hardware probe written and run. Apple M2 Ultra, 16P/8E cores, 128 GB, 60 GPU cores, 507 GB free, MPS available on torch 2.10.0.
2026-11-03T18:53:39Z  Phase 1: BINMAN store reader. All 12 curated sources present; row counts match spec 2.1 exactly. Degronopedia and ProtCID confirmed unavailable (BINMAN G7).
2026-11-03T18:53:39Z  Phase 1: benchmark panel resolver. 7/7 resolve. MGTbind encodes multi-protein receptors as underscore-joined composite accessions, so matching is by token set; MGTbind carries no PROTACs, so the two BRD4 arms resolve from PROTAC-DB (5T35, 6BNB).
2026-11-03T18:53:39Z  Phase 1: all seven benchmark depositions already present in BINMAN's assembly cache. Ligand CCDs read from structure: 85C, 759, Y70, LVY, EF6, RC8.
2026-11-03T18:53:39Z  Phase 1: GSPT1 degron gate failed, then resolved. Root cause was a numbering frame mismatch of 138 residues, not a Degron Scan bug: deposited G575 is canonical 437, which is exactly the scan's second-ranked hairpin tip. Added nobble/curate/numbering.py. Gate now 2/2.
2026-11-03T18:53:39Z  Phase 1: receptor constructs from InterPro boundaries. Six constructs, token counts measured. DDB1 reduced to BPC alone on measured CR-8 contacts, avoiding a third exception. DCAF15 measures 1229 tokens against the spec's ~900 estimate.
2026-11-03T18:53:39Z  Phase 1: tests/test_phase1.py, 9 passed. All three testable Phase 1 gates pass.
