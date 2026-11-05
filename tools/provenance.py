"""The facts that answer "are these two numbers about the same thing".

Printed together because five times in one day a figure was compared
against another that looked comparable and was not: a pre-filter manifest
against a post-filter queue, an atlas preview against an assembled scan, a
cost against a different parent. Every answer was already recorded
somewhere, so this is one command instead of five greps (F92).
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, ".")
from nobble.execute.campaign import latest
from nobble.validate import inputs

campaign = latest("campaign") or latest("benchmark")
if campaign is None:
    print("   no campaign assembled")
else:
    meta_path = campaign / "campaign.json"
    meta = json.loads(meta_path.read_text()) if meta_path.exists() else {}
    dropped = meta.get("conditioned_jobs_dropped_no_pocket")
    if dropped is not None:
        print(f"   {campaign.name}: {meta.get('jobs_emitted')} job(s) emitted, "
              f"{dropped} conditioned dropped for having no pocket")
    # Which Boltz the campaign recorded at assembly, and what to do when it
    # recorded none. A campaign assembled before F185 has no block, and the
    # honest line says that rather than measuring the environment now and
    # presenting it as what ran: the environment is probably the same and
    # "probably" is not provenance.
    from nobble.execute import software

    print(f"   model         {software.provenance_line(meta.get('software'))}")

    stale = inputs.stale_inputs(campaign)
    if stale:
        pairs = sorted({r["pair_id"] for r in stale if r.get("pair_id")})
        print(f"   stale inputs  {len(stale)} job(s) across {pairs}: the atlas "
              "build refuses while this holds")
    else:
        print("   stale inputs  none; the atlas build has nothing to refuse")

    superseded = inputs.superseded_substrates(campaign)
    if superseded:
        for row in superseded:
            print(f"   superseded    {row['pair_id']}: {row['submitted_length']} aa "
                  f"submitted, plan now says {row['planned_length']} "
                  f"({row['accession']} {row['planned_range']})")
    else:
        print("   superseded    no substrate differs from the current plan")

# Whether the published bundle is what the code builds. Reported here as
# well as gated in deploy.sh, because a drift noticed at deploy time is a
# refused deploy and a drift noticed in status is a rebuild (F97).
try:
    sys.path.insert(0, "tools")
    import atlas_drift

    report_ = atlas_drift.drift()
    moved = report_.get("moved") or []
    # Counted by the check and reported here, or the operator reading
    # status.sh sees "in step" and never learns that sixty-odd costs are
    # waiting for the next rebuild (F101).
    recomputed = report_.get("recomputed") or []
    tail = (f", {len(recomputed)} cost(s) recomputed from new timings"
            if recomputed else "")
    if moved:
        print(f"   atlas         DRIFTED from the code: {len(moved)} value(s), "
              f"first is {moved[0]['key']}{tail}")
    else:
        print(f"   atlas         {report_['status']}"
              f"{', ' + str(report_.get('compared')) + ' leaves' if report_.get('compared') else ''}"
              f"{tail}")
except Exception as problem:                        # noqa: BLE001
    print(f"   atlas         drift not checked: {type(problem).__name__}")

try:
    from nobble.app import data
    from nobble.design import report

    data.configure(str(campaign) if campaign else None)
    chosen = report._default_parent(report.candidate_parents())
    published = {}
    # Through atlas_drift.PUBLISHED, which honours NOBBLE_ATLAS_PUBLISHED.
    # This was a second, hardcoded spelling of the published atlas path,
    # `Path("deploy/atlas/design.json")`, sitting a few lines from the drift
    # check that reads the same bundle through its own constant. One thing
    # spelled twice: the override took effect for the drift line and not for
    # this one, so a test pointed at a copy still read the live site here
    # (F154).
    import atlas_drift as _drift

    atlas_design = _drift.PUBLISHED / "design.json"
    if atlas_design.exists():
        published = ((json.loads(atlas_design.read_text()).get("preview")
                      or {}).get("parent") or {})
    agree = published.get("peptide_id") == chosen["peptide_id"]
    mark = "" if agree else "   <- the site and the ranking disagree"
    print(f"   design target ranking says {chosen['peptide_id']} "
          f"({chosen.get('gene')}), site says "
          f"{published.get('peptide_id') or 'nothing published'}{mark}")
except Exception as problem:                        # noqa: BLE001
    print(f"   design target  not resolved: {type(problem).__name__}")
