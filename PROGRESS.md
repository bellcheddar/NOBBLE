# NOBBLE progress

Rewritten after every phase and at least every 30 minutes during long compute.

| Phase | State | Notes |
|---|---|---|
| 0 Probe | **complete** | Apple M2 Ultra, 16 performance + 8 efficiency cores, 128 GB, 60 GPU cores, 507 GB free, MPS on torch 2.10.0 |
| 1 Curation and manifest | in progress | Benchmark panel resolved (7/7). Receptor constructs, tier selection, peptide library, MSA cache next |
| 2 Execution | not started | Throughput benchmark then the tier-1 queue |
| 3 Scoring and validation | not started | |
| 4 Application | not started | |

## Gates

- G3 Deploy: **open in advance**. nobble.mdeller.com resolves to the droplet but
  serves nginx's default page and has no certificate. See DECISIONS.md D-NOB-011.
- All other gates closed.
