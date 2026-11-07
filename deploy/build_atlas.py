#!/usr/bin/env python3
"""Build the read-only slice the droplet serves.

Two jobs, and the second is the one that matters.

1. Keep the bundle small. The droplet serves a precomputed atlas and does no
   compute at request time, so it needs the scored records and the predicted
   structures, not the 77 MB of Boltz working output around them.

2. **Redistribute nothing that may not be redistributed.** Publishing to a
   public website is redistribution exactly as a public repository is. Spec 2
   makes PROTAC-DB internal-use only, and benchmark member 3's dBET57 structure
   came from it, so its SMILES is stripped here and the field is replaced with
   an explicit note rather than silently dropped. CCD codes and their SMILES
   are not affected: those come from the PDB Chemical Component Dictionary,
   which is public.
"""
from __future__ import annotations

import json
import os
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble import paths  # noqa: E402
from nobble.execute.campaign import latest  # noqa: E402

# The published atlas, overridable so a test can exercise this script
# without writing to it. A test that runs the real build against the real
# atlas is safe only while the build refuses: mutating the refusal away to
# check that the test catches it let the build run, and it rebuilt the
# published atlas from a campaign with 54 of 2360 jobs scored. Recoverable,
# because the atlas is tracked, but a check should not be able to do that.
OUT = Path(os.environ.get("NOBBLE_ATLAS_OUT") or ROOT / "deploy" / "atlas")

# Ligand records whose chemistry came from PROTAC-DB. Keyed by the encoding the
# resolver recorded, so a CCD-sourced ligand is never touched.
REDACT_WHEN_SOURCE = {"protacdb"}
REDACTION = (
    "withheld: PROTAC-DB is licensed for internal use and is never "
    "redistributed (spec 2.1). The structure prediction used it; the record "
    "does not travel."
)


# Every field this build withheld. A list rather than a counter so the
# summary can say which records were affected, and reset per build rather
# than accumulated across calls.
#
# `summary["redactions"]` was initialised to 0 and incremented nowhere, so
# the published ATLAS.json reported "redactions: 0" while the atlas it
# described contained a `smiles_withheld` field. A count that is zero
# whatever happened is not a count, and on a licensing guarantee it reads
# as "no PROTAC-DB chemistry was present" rather than "one record was
# withheld" (F72).
_WITHHELD: list[str] = []


def reset_redactions() -> None:
    _WITHHELD.clear()


def redactions() -> list[str]:
    return list(_WITHHELD)


def redact(value):
    """Strip PROTAC-DB chemistry anywhere it appears in a nested record."""
    if isinstance(value, dict):
        source = str(value.get("source", ""))
        out = {key: redact(item) for key, item in value.items()}
        # The encoding is deliberately not part of this test. What makes a
        # record unpublishable is where the chemistry came from, not how it
        # happens to be written: a CCD-sourced SMILES is wwPDB's and travels
        # freely, and a PROTAC-DB record would still be theirs if it arrived
        # with a CCD code attached. This used to read
        # `source in REDACT_WHEN_SOURCE or (encoding == "smiles" and source in
        # REDACT_WHEN_SOURCE)`, whose second clause is a subset of the first
        # and so never decided anything, while implying the encoding mattered.
        if source in REDACT_WHEN_SOURCE:
            if "smiles" in out:
                out["smiles"] = None
                out["smiles_withheld"] = REDACTION
                _WITHHELD.append(str(value.get("ccd") or value.get("key")
                                     or value.get("ligand_key") or source))
        return out
    if isinstance(value, list):
        return [redact(item) for item in value]
    return value


# Sources whose chemistry may be published, each with the reason it may.
#
# An allow-list, where redact() has a deny-list, and that is the whole point
# of it rather than a stylistic preference. redact() nulls a SMILES when
# `source in REDACT_WHEN_SOURCE`, so a record arriving with its source spelled
# `PROTAC-DB`, or blank, or as something nobody has thought of yet, is
# published untouched. A verifier keyed on the same field could only confirm
# redact() agreed with itself. Keyed the other way round, an unrecognised
# source fails closed.
PUBLISHABLE_SMILES_SOURCES = {
    "deposited_ternary": "wwPDB CCD chemistry, read from a deposited structure",
}

_verification_scope = "not run"


def _published_smiles(root: Path) -> list[tuple[str, str, str, str]]:
    """Every published SMILES, as (file, trail, source, smiles).

    `source` is read from the record that carries the SMILES, which is where
    redact() reads it from too, so the two are deciding on the same field and
    disagreeing about it is possible rather than ruled out by construction.
    """
    found: list[tuple[str, str, str, str]] = []

    def walk(node, name: str, trail: str):
        if isinstance(node, dict):
            smiles = node.get("smiles")
            if isinstance(smiles, str) and smiles.strip():
                found.append((name, trail, str(node.get("source") or ""),
                              smiles.strip()))
            for key, value in node.items():
                walk(value, name, f"{trail}.{key}")
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, name, f"{trail}[{index}]")

    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix not in (".json", ".jsonl"):
            continue
        text = path.read_text(errors="replace")
        try:
            if path.suffix == ".jsonl":
                documents = [json.loads(line) for line in text.splitlines()
                             if line.strip()]
            else:
                documents = [json.loads(text)]
        except json.JSONDecodeError:
            continue
        for document in documents:
            walk(document, path.name, "")
    return found


def unattributable_chemistry_in(root: Path) -> list[tuple[str, str, str, str]]:
    """Published SMILES whose provenance is not one that may be redistributed.

    Provenance is the test, not the molecule. A molecule can sit in PROTAC-DB
    and in the PDB at once: CCD 759 is MZ1 and so is PROTAC-DB 335, and
    publishing wwPDB's version of it redistributes wwPDB's data. Checking the
    chemistry against PROTAC-DB's table instead flags every such molecule and
    catches nothing that this does not, which is how the first version of
    this check came to refuse a clean bundle (F218).
    """
    global _verification_scope
    published = _published_smiles(root)
    if not published:
        _verification_scope = "no SMILES published at all"
        return []
    _verification_scope = (
        f"{len(published)} published SMILES against "
        f"{len(PUBLISHABLE_SMILES_SOURCES)} permitted source(s)")
    return [row for row in published
            if row[2] not in PUBLISHABLE_SMILES_SOURCES]


def _project_relative(value: str) -> str:
    """An absolute path under the project root, made relative to it.

    The bundle goes to a public host, so a build-machine path in it puts a
    home directory on a public page. The top-level `structure` field was
    already rewritten, to the flattened copy published beside it, and four
    others were not: `results.jsonl`'s `yaml` and `output_dir`, and
    `scores.jsonl`'s nested `seed_records[].structure` and
    `plip.conect.pdb_path`, 307 occurrences between them.

    Made relative rather than dropped. These are provenance, which YAML
    produced a record and where Boltz wrote it, and a reader of the bundle
    has a use for that; what they have no use for is the name of the
    directory it was built in. Nothing reads them on the droplet either way:
    the seed overlay builds its URLs from `job_id` (F128).
    """
    try:
        return str(Path(value).resolve().relative_to(ROOT.resolve()))
    except (ValueError, OSError):
        return Path(value).name


def _relocate(node):
    """Rewrite every absolute project path in a record, at any depth."""
    if isinstance(node, dict):
        return {key: _relocate(item) for key, item in node.items()}
    if isinstance(node, list):
        return [_relocate(item) for item in node]
    if isinstance(node, str) and node.startswith("/") and str(ROOT) in node:
        return _project_relative(node)
    return node


def main() -> int:
    # Takes the campaign to publish. It used to hard-code latest("benchmark"),
    # which meant the main campaign could run for 52 hours and never reach the
    # site: refresh.sh accepted a campaign, scored it, then called this with
    # no argument and published a different one. Nothing failed, and the
    # published atlas simply stayed on the benchmark panel.
    import argparse

    parser = argparse.ArgumentParser(description="Publish a campaign as the atlas.")
    parser.add_argument("campaign", nargs="?", default=None)
    args = parser.parse_args()

    if args.campaign:
        campaign = Path(args.campaign)
        if not campaign.exists():
            print(f"no campaign at {campaign}", file=sys.stderr)
            return 2
    else:
        campaign = latest("campaign") or latest("benchmark")
    if campaign is None:
        print("no campaign to publish", file=sys.stderr)
        return 2
    print(f"publishing {campaign.name}")

    # Configured here, before anything is built, rather than part way down.
    #
    # F89 found the design report taking its fallback because nothing had
    # configured the data layer. The call that fixed it sat immediately
    # above that one section, which left every section built earlier
    # depending on not needing it. Whether that is true is a question this
    # ordering stops anyone having to ask again (F90).
    from nobble.app import data as app_data

    app_data.configure(str(campaign))

    # Before anything is written or removed. A campaign holds two
    # descriptions of every job, the queue row and the YAML Boltz actually
    # reads, and a disagreement between them is invisible from either side:
    # the results look like results for the job the queue describes. Fifteen
    # of the main campaign's jobs ran on a YAML carrying a hydroxyproline
    # the fixed rule no longer asks for (F47), and nothing compared the two
    # until this did. Refusing leaves the previously published atlas in
    # place, which is stale rather than wrong (F59).
    from nobble.validate import inputs as input_check

    stale = input_check.stale_inputs(campaign)
    if stale:
        print(input_check.refusal(stale), file=sys.stderr)
        return 1

    # And what was actually folded, which the check above cannot see.
    #
    # `stale_inputs` compares a YAML against the queue row that describes it,
    # so it answers "is the input on disk the one we meant to run". It cannot
    # answer "is the input on disk the one that was run", and those came
    # apart on 6 November: tools/rerun_pair.py replaced fifteen YAMLs and
    # cleared their results, Boltz re-ran them against its own cached
    # featurisation, and the campaign then passed every stale-input check
    # while its poses still held the hydroxyproline (F219). The atlas built
    # for the first time in two days because the guard had been satisfied
    # rather than because the defect was gone.
    sys.path.insert(0, str(ROOT / "tools"))
    import stale_featurisation as featurisation_check

    folded = featurisation_check.disagreements(campaign)
    if folded:
        print("\nREFUSED: the cached featurisation does not match the YAML "
              "for these jobs, so the poses were folded from an input that is "
              "no longer on disk (F219):", file=sys.stderr)
        for row in folded[:10]:
            print(f"    {row['job_id']} chain {row['chain']}: YAML asks "
                  f"{row['yaml_asks']}, folded {row['folded']}",
                  file=sys.stderr)
        print(f"    {len(folded)} job(s). tools/rerun_pair.py now removes the "
              "cached output directory, so re-running the correction "
              "featurises the YAML.", file=sys.stderr)
        return 1

    # And whether that check could see the campaign at all.
    #
    # It skipped three cases silently and the caller read "no disagreements"
    # as "every job agrees". Two of the three are the guard being blind: a
    # job that ran with no `processed/structures/*.npz` under it, and an npz
    # with no `chains` or `residues` array, which is what a change in Boltz's
    # cache format would look like. Either one turns the refusal above into a
    # pass for the whole campaign, which re-enables F219 through a guard
    # reporting success: exactly the shape F218 and F232 record.
    #
    # Refusing rather than warning, because this is the guard that stands
    # between a superseded input and a published pose, and because it costs
    # nothing today: all three run campaigns check every queued job, 2,360 of
    # 2,360 for the main one, with no skip of any kind.
    seen = featurisation_check.coverage(campaign)
    if seen["blind"]:
        print(f"\nREFUSED: the featurisation check could not compare "
              f"{seen['blind']} job(s) that ran, so whether their poses came "
              "from a superseded input is unknown rather than fine:",
              file=sys.stderr)
        print(f"    {seen['no_cache']} with no cached featurisation, "
              f"{seen['unreadable_cache']} whose cache could not be read, "
              f"{seen['missing_yaml']} with no YAML on disk",
              file=sys.stderr)
        for job_id in seen["blind_examples"]:
            print(f"    {job_id}", file=sys.stderr)
        print(f"    {seen['checked']} of {seen['queued']} queued job(s) were "
              f"compared, {seen['no_output']} have not run.", file=sys.stderr)
        return 1

    # And the third link of the chain, which nothing checked.
    #
    # `stale_inputs` compares a YAML against the job record that describes
    # it; the two checks above compare the cached featurisation against the
    # YAML. Neither compares the YAML against the code that emits it, which
    # is the link F262 broke: the ligand resolution dropped a SMILES-only
    # glue, so scr_bench03_BRD4_CRBN's ternary YAMLs were wrong from the
    # moment they were written and agreed with their own record and their own
    # cache all the way down. Every guard reported the campaign clean.
    #
    # Refusing rather than warning, for the reason the comment above gives:
    # this stands between a superseded input and a published pose. It costs
    # about two seconds, and it reports "unavailable" rather than "clean"
    # when it cannot compare, so a failure here cannot read as a pass.
    from nobble.validate import inputs as input_check

    regenerated, regenerated_status = input_check._regenerated_scan(campaign)
    if regenerated:
        print("\nREFUSED: these jobs hold a YAML the current code would not "
              "write, so their poses came from an input the assembler no "
              "longer produces (F262, F266):", file=sys.stderr)
        for row in regenerated[:10]:
            print(f"    {row['job_id']}: {row['problem']}", file=sys.stderr)
        print(f"    {len(regenerated)} job(s). {regenerated_status}.",
              file=sys.stderr)
        print("    tools/rerun_pair.py --regenerate rewrites them from the "
              "current code and clears their results.", file=sys.stderr)
        return 1
    if regenerated_status.startswith("unavailable"):
        print(f"\nREFUSED: {regenerated_status}, so whether the inputs on "
              "disk are the ones the code would write is unknown rather than "
              "fine.", file=sys.stderr)
        return 1

    if OUT.exists():
        shutil.rmtree(OUT)
    (OUT / "structures").mkdir(parents=True)

    reset_redactions()
    summary = {"campaign": campaign.name, "files": {}, "redactions": 0}

    # What else was assembled or running when this slice was built. The
    # droplet cannot see the Studio's queues, so without this the header
    # says COMPLETE while the main campaign is still to run and a visitor
    # concludes the science is finished. Recorded as a fact about build
    # time, not a live feed: it is only as fresh as the last deploy, and
    # the note on the panel says so.
    outstanding = []
    for other in sorted(paths.CAMPAIGNS.glob("*")):
        if not other.is_dir():
            continue
        # Both tiers, and the published campaign along with the rest.
        #
        # This read `queue.jsonl` only, and skipped the campaign being
        # published. Those two omissions met in the worst place: the main
        # campaign's tier 1 was complete and 76 of its 225 refinements were
        # still to run, and because it was the campaign being published it
        # was skipped, so the header asserted "published campaign finished"
        # about the one campaign that was mid-stage. Liveness is per tier is
        # F216's finding, made in the watchdog, then missed in tools/status.sh
        # (F237) and again here, which is the surface a visitor reads once
        # this slice is deployed, and so the
        # only one a visitor reads.
        #
        # The published campaign is reported for its unfinished tiers alone.
        # Its tier 1 is what the slice is built from, so a slice built before
        # that finished is a different problem, and `jobs_done` against
        # `jobs_total` in the header already says so.
        for tier, (queue_name, state_name) in enumerate(
                (("queue.jsonl", "state.jsonl"),
                 ("queue_tier2.jsonl", "state_tier2.jsonl")), start=1):
            queue = other / queue_name
            if not queue.exists():
                continue
            total = sum(1 for line in queue.read_text().splitlines()
                        if line.strip())
            state = other / state_name
            done = 0
            if state.exists():
                import json as _json
                done = len({
                    _json.loads(line)["job_id"]
                    for line in state.read_text().splitlines()
                    if line.strip()
                    and _json.loads(line).get("status") == "done"
                })
            if done < total:
                outstanding.append({
                    "campaign": other.name, "tier": tier,
                    "jobs_done": done, "jobs_total": total,
                    "published": other.name == campaign.name,
                })
    summary["outstanding"] = outstanding

    # Flat JSON documents.
    for name in ("campaign.json", "validation.json", "weights.json"):
        source = campaign / name
        if not source.exists():
            continue
        payload = redact(json.loads(source.read_text()))
        # Campaigns assembled before F185 carry no model version, and the
        # one on the GPU is one of them: it was assembled before this
        # existed and will not be reassembled. Measuring at publish time is
        # the best available answer for those, and it is labelled as a
        # different claim rather than written in as though the assembler had
        # recorded it. The distinction matters because a publish-time
        # reading describes the environment now, and only the assembler's
        # describes the one the jobs ran in.
        if name == "campaign.json" and not payload.get("software"):
            from nobble.execute import software as _software

            payload["software"] = dict(_software.versions(),
                                       recorded="at publish, not at assembly")
        text = json.dumps(payload, indent=2)
        (OUT / name).write_text(text)
        summary["files"][name] = len(text)

    # JSONL records. results.jsonl carries absolute structure paths from the
    # build machine, which are meaningless on the droplet, so they are
    # rewritten to the flattened names published beside them.
    # Tier 2 refines the top decile and writes its own three files. Without
    # publishing them the refinement is invisible: hours of compute whose
    # only product is a better set of coordinates nobody can open.
    for name in ("scores.jsonl", "results.jsonl",
                 "scores_tier2.jsonl", "results_tier2.jsonl"):
        source = campaign / name
        if not source.exists():
            continue
        rows = []
        for line in source.read_text().splitlines():
            if not line.strip():
                continue
            row = redact(json.loads(line))
            structure = row.get("structure")
            if structure:
                origin = Path(structure)
                if origin.exists():
                    published = f"{row['job_id']}.cif"
                    shutil.copy(origin, OUT / "structures" / published)
                    row["structure"] = f"structures/{published}"
                else:
                    row["structure"] = None
            # Every other absolute path in the record, at any depth. The
            # rewrite above reaches one field; these records carry four more
            # (F128).
            published_structure = row.get("structure")
            row = _relocate(row)
            row["structure"] = published_structure
            rows.append(row)
        (OUT / name).write_text("\n".join(json.dumps(r) for r in rows) + "\n")
        summary["files"][name] = len(rows)

    # Verify the redaction actually happened, rather than trusting it.
    leaked = []
    for path in OUT.rglob("*"):
        if path.is_file() and path.suffix in (".json", ".jsonl"):
            body = path.read_text(errors="replace")
            if "CC1=C(C)C2=C(S1)" in body:
                leaked.append(str(path.relative_to(OUT)))
    if leaked:
        print(f"REFUSING TO PUBLISH: PROTAC-DB chemistry still present in {leaked}",
              file=sys.stderr)
        return 1

    # Precompute everything the Benchmark and About pages need. Those two
    # routes previously imported nobble.curate at request time, which pulls in
    # gemmi, pandas and BINMAN's store. None of that exists on the droplet, so
    # both returned 500 there while working locally. Spec Phase 4 is explicit
    # that the droplet serves a precomputed atlas with no compute at request
    # time, and this is what that means in practice.
    from nobble.curate import binman_store, constructs
    from nobble.curate import peptides as peptide_module
    from nobble.score import lysine

    benchmark = {
        "members": [
            {
                "index": item["index"], "gene": item["gene"], "e3": item["e3"],
                "pdb_id": item["pdb_id"], "accession": item["accession"],
            }
            for item in peptide_module.BENCHMARK_CHAINS
        ],
        "substrate_plan": redact(peptide_module.benchmark_substrate_constructs()),
        # Which deposited structure each pair is compared against, so the app
        # can offer the crystal overlay without importing nobble.validate.
        "crystal_by_pair": {
            pair_id: target["pdb_id"]
            for pair_id, target in __import__(
                "nobble.validate.layers", fromlist=["RECOVERY_TARGETS"]
            ).RECOVERY_TARGETS.items()
        },
    }
    (OUT / "benchmark.json").write_text(json.dumps(benchmark, indent=2, default=str))
    summary["files"]["benchmark.json"] = len(benchmark["members"])

    # The deposited assemblies the benchmark page names, copied as the
    # gzip they are already stored as. `/crystal/<id>.cif` served these by
    # importing `nobble.curate.structures`, which imports gemmi, and the
    # droplet has flask and gunicorn: the route returned 500 there for
    # every pair while passing every local check, and the pose page loads
    # it to superpose a prediction on its crystal (F196).
    #
    # Published rather than fetched at request time for the same reason the
    # crystal *mapping* already is. Nothing restricted travels with them:
    # an assembly carries coordinates and no SMILES or InChI, and spec
    # 2.1's restrictions name PROTAC-DB, UbiBrowser and BioLiP2.
    # Read from the document just written above, not from `summary`. The
    # first version of this sat 58 lines earlier, before benchmark.json
    # existed, so its guard was falsy and the whole step was skipped in
    # silence: a step that does nothing and says nothing, which is the bug
    # this session has been chasing in other people's code.
    crystal_map = benchmark.get("crystal_by_pair") or {}
    if not crystal_map:
        print("  no crystal mapping in benchmark.json, so no assemblies "
              "published and /crystal/<id>.cif will 404", file=sys.stderr)
    else:
        from nobble.curate import structures as _structures

        (OUT / "crystals").mkdir(exist_ok=True)
        published_crystals = 0
        for pdb_id in sorted({str(v) for v in crystal_map.values() if v}):
            source = _structures.assembly_path(pdb_id)
            if source.exists():
                shutil.copy(source, OUT / "crystals" / f"{pdb_id}.cif.gz")
                published_crystals += 1
            else:
                print(f"  crystal {pdb_id} is not in the assembly cache, so "
                      f"/crystal/{pdb_id}.cif will 404", file=sys.stderr)
        summary["files"]["crystals"] = published_crystals


    about = {
        "sources": binman_store.available(),
        "unavailable": list(binman_store.UNAVAILABLE),
        "bridge_reference": binman_store.bridge_reference_count(),
        "construct_budget": constructs.budget_report(),
        "reach_auc": lysine.BINMAN_REACH_AUC,
    }
    (OUT / "about.json").write_text(json.dumps(about, indent=2, default=str))
    summary["files"]["about.json"] = len(about["sources"])

    # The design arm (DESIGN_ARM.md). Built here rather than at request time
    # like everything else: the generator imports the curation stack, and the
    # droplet has no gemmi.
    from nobble.design import report as design_report

    # The data layer is configured at the top of this function. It was not
    # configured at all until F89, and the reason that mattered here:
    #
    # `_default_parent` ranks the candidate degrons by measured Delta-ipTM
    # and falls back to the shortest glue parent when nothing is scored, so
    # the tab has something to show before a campaign runs. With no
    # campaign configured, `data.scores()` returns an empty list and the
    # fallback fires unconditionally: every atlas ever published chose its
    # scan target by peptide length, which is the tiebreak a previous
    # finding replaced for landing on a PROTAC pair in an arm about glue
    # dependence.
    #
    # The chain does configure before assembling the scan, so the published
    # target was GSPT1 and the scan that runs is IKZF1: two answers to the
    # design arm's headline question, one on the page and one in the queue
    # (F89).
    # The campaign is passed explicitly so the design arm's validation
    # caveat comes from the same campaign every other section is built from,
    # rather than from whichever file a global lookup happened to find
    # (F105).
    design = design_report.build(campaign=campaign)
    (OUT / "design.json").write_text(json.dumps(design, indent=2, default=str))
    summary["files"]["design.json"] = len(design.get("parents", []))

    # Bridge rate against pose recovery (FINDINGS.md F9). Computed here, with
    # the correlation, so the application renders a static result and does no
    # statistics at request time.
    try:
        from scipy import stats as _stats

        validation = json.loads((campaign / "validation.json").read_text())
        recovery = validation["layers"]["pose_recovery"]["summary"]["by_pair"]
        scored = {
            json.loads(line)["pair_id"]: json.loads(line)
            for line in (campaign / "scores.jsonl").read_text().splitlines() if line.strip()
        }
        points = []
        for pair_id, stats_row in sorted(recovery.items()):
            row = scored.get(pair_id, {})
            total = row.get("bridging_seeds_total") or 0
            if not total:
                continue
            points.append({
                "pair_id": pair_id,
                "gene": row.get("peptide_gene") or pair_id,
                "e3": row.get("e3_gene"),
                "bridge_rate": round((row.get("bridging_seeds_with_bridge") or 0) / total, 3),
                "bridging": f"{row.get('bridging_seeds_with_bridge') or 0}/{total}",
                "median_rmsd": stats_row["median_rmsd"],
                "best_rmsd": stats_row["best_rmsd"],
                "convergence": row.get("convergence_score"),
            })
        payload = {"points": points, "n": len(points)}
        # From config, because it decides whether a correlation is published
        # at all, which is what makes a number a threshold (F184).
        minimum_points = int(paths.thresholds()["validation"]
                             ["recovery_correlation_minimum_points"])
        if len(points) >= minimum_points:
            xs = [item["bridge_rate"] for item in points]
            ys = [item["median_rmsd"] for item in points]
            r_value, p_value = _stats.pearsonr(xs, ys)
            rho, rho_p = _stats.spearmanr(xs, ys)
            payload |= {
                "pearson_r": round(float(r_value), 3), "pearson_p": round(float(p_value), 4),
                "spearman_rho": round(float(rho), 3), "spearman_p": round(float(rho_p), 4),
            }
        (OUT / "recovery_vs_bridge.json").write_text(json.dumps(payload, indent=2))
        summary["files"]["recovery_vs_bridge.json"] = len(points)
    except Exception as problem:                   # noqa: BLE001
        summary["recovery_vs_bridge_error"] = f"{type(problem).__name__}: {problem}"

    # If a corrected-construct campaign exists, publish the comparison that
    # answers F6. Computed here, on the build machine, because the droplet
    # computes nothing: the app renders a static verdict.
    corrected = sorted(
        (item for item in (ROOT / "campaigns").iterdir()
         if item.is_dir() and item.name.startswith("corrected_")),
        key=lambda item: item.name,
    )
    if corrected:
        from nobble.validate.compare import compare

        try:
            report = compare(campaign, corrected[-1])
            (OUT / "comparison.json").write_text(
                json.dumps(redact(report), indent=2, default=str)
            )
            summary["files"]["comparison.json"] = len(report.get("comparisons", []))
            summary["comparison_conclusion"] = report.get("conclusion")
        except Exception as problem:               # noqa: BLE001
            summary["comparison_error"] = f"{type(problem).__name__}: {problem}"

    # The queue itself is not published (it is large and carries the YAML
    # paths of the build machine), but its size must be, or the deployed app
    # has no denominator: it then reads 75 of 0 jobs and reports a running
    # campaign as complete, which is a status panel telling a lie.
    source_queue = campaign / "queue.jsonl"
    if source_queue.exists():
        summary["jobs_total"] = sum(
            1 for line in source_queue.read_text().splitlines() if line.strip()
        )
        pair_ids = set()
        for line in source_queue.read_text().splitlines():
            if line.strip():
                pair_ids.add(json.loads(line).get("pair_id"))
        summary["pairs_total"] = len(pair_ids)

    structures = list((OUT / "structures").glob("*.cif"))
    summary["structures"] = len(structures)
    summary["bytes"] = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())

    # Written at the end, from what redact() actually did, rather than left
    # at the zero it was initialised to. Both the count and the ligands are
    # recorded: a count alone cannot distinguish "nothing needed
    # withholding" from "the detection stopped firing" (F72).
    withheld = redactions()
    summary["redactions"] = len(withheld)
    summary["redacted_ligands"] = sorted(set(withheld))
    (OUT / "ATLAS.json").write_text(json.dumps(summary, indent=2))

    print(json.dumps(summary, indent=2))

    # Verified, now. This line used to be printed unconditionally, with
    # nothing behind it: an f-string with no interpolation and no condition,
    # claiming the project's one verbatim licensing guarantee every time the
    # build reached the end. F72 fixed a redaction *count* that was always
    # zero; this was the same shape one level up, and worse, because a count
    # of zero at least invites the question (F218).
    #
    # The check deliberately does not read `source`. redact() keys on it, so
    # a scan that also keys on it can only confirm redact() agreed with
    # itself: a record arriving with the source spelled differently would be
    # published by redact() and then pronounced clean by the verifier. This
    # compares the chemistry itself against PROTAC-DB's own table, which is
    # the only thing that cannot be got wrong by a spelling.
    leaked = unattributable_chemistry_in(OUT)
    if leaked:
        print("\nREFUSED: the built bundle publishes chemistry whose "
              "provenance is not one that may be redistributed (spec 2.1):",
              file=sys.stderr)
        for name, trail, source, smiles in leaked[:10]:
            print(f"    {name}{trail}: source={source or '(none)'} "
                  f"{smiles[:50]}", file=sys.stderr)
        print(f"    {len(leaked)} record(s). Permitted sources: "
              f"{sorted(PUBLISHABLE_SMILES_SOURCES)}. The bundle is on disk "
              "and is not publishable; redact these or add the source with "
              "its licensing reason.", file=sys.stderr)
        return 1
    print(f"\nverified: every published SMILES has a redistributable "
          f"provenance ({_verification_scope})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
