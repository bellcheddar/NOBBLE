"""Read-only access to a campaign's scored output, for the app.

The app never computes a score. Everything it shows is produced by
`nobble.score.run` and read from disk here, so a number on screen can always be
traced to the record that produced it. Spec Phase 4's tooltip requirement
depends on that: every value carries its own provenance.

Loaded lazily and cached by file modification time, so the app can be left
running while a campaign is still executing and will pick up new results
without a restart.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from nobble import paths

_CAMPAIGN: Path | None = None
_CACHE: dict = {}


def configure(campaign: str | None = None) -> Path | None:
    """Pin the app to a campaign directory, or the most recent one.

    NOBBLE_CAMPAIGN points the deployed app at the published atlas, which has
    the same layout as a campaign directory but holds only the scored records
    and the predicted structures: the droplet serves a precomputed slice and
    does no compute at request time.
    """
    global _CAMPAIGN
    import os

    if campaign:
        _CAMPAIGN = Path(campaign)
    elif os.environ.get("NOBBLE_CAMPAIGN"):
        _CAMPAIGN = Path(os.environ["NOBBLE_CAMPAIGN"])
    else:
        try:
            from nobble.execute.campaign import latest
            _CAMPAIGN = latest("benchmark")
        except Exception:                        # noqa: BLE001
            _CAMPAIGN = None
    return _CAMPAIGN


def campaign_dir() -> Path | None:
    return _CAMPAIGN


def _read_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    rows = []
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return rows


def _cached(key: str, path: Path, loader):
    """Cache by (path, mtime) so a live campaign refreshes without a restart.

    The path really is part of the key. It said so and was not: the entry
    was stored under the bare name, so pointing the app at a different
    campaign returned the previous one's rows whenever the two files shared
    an mtime. In production _CAMPAIGN is set once and this never fires;
    it fires immediately when anything reconfigures, which is how it was
    found.
    """
    if not path.exists():
        # The empty shape each consumer expects: campaign.json is read as a
        # mapping and everything else as a list. `loader(path) if False else
        # (...)` stood here, whose first branch can never run.
        return {} if key == "campaign" else []
    stamp = path.stat().st_mtime
    cache_key = (key, str(path))
    entry = _CACHE.get(cache_key)
    if entry and entry[0] == stamp:
        return entry[1]
    value = loader(path)
    _CACHE[cache_key] = (stamp, value)
    return value


def scores() -> list[dict]:
    if _CAMPAIGN is None:
        return []
    return _cached("scores", _CAMPAIGN / "scores.jsonl", _read_jsonl)


def queue() -> list[dict]:
    if _CAMPAIGN is None:
        return []
    return _cached("queue", _CAMPAIGN / "queue.jsonl", _read_jsonl)


def results() -> list[dict]:
    if _CAMPAIGN is None:
        return []
    return _cached("results", _CAMPAIGN / "results.jsonl", _read_jsonl)


def results_tier2() -> list[dict]:
    """Refined poses, if tier 2 has run. Empty is the normal state."""
    if _CAMPAIGN is None:
        return []
    path = _CAMPAIGN / "results_tier2.jsonl"
    if not path.exists():
        return []
    return _cached("results_tier2", path, _read_jsonl)


def scores_tier2() -> list[dict]:
    """Scores of the refined poses, if tier 2 has run and been scored.

    The atlas has published this file since tier 2's output was made
    visible, and nothing read it: the pose catalogue offered the refined
    coordinates and no page showed what they measured, so there was no way
    to tell whether refinement had improved anything (F137).
    """
    if _CAMPAIGN is None:
        return []
    path = _CAMPAIGN / "scores_tier2.jsonl"
    if not path.exists():
        return []
    return _cached("scores_tier2", path, _read_jsonl)


def campaign_meta() -> dict:
    if _CAMPAIGN is None:
        return {}
    path = _CAMPAIGN / "campaign.json"
    return _cached("campaign", path, lambda p: json.loads(p.read_text()))


def site_status() -> dict:
    """Small, honest status for the header panel.

    Everything here is read from the published slice, so the figure on screen
    is the figure the pipeline produced. "Healthy" means the app can read its
    campaign, not that the science worked: a campaign with no scored pairs is
    a healthy app with nothing to show, and the panel says so rather than
    showing a green light over an empty atlas.
    """
    state = campaign_state()
    scored = scores()
    validation = precomputed("validation.json")
    layers = validation.get("layers", {})
    recovery = layers.get("pose_recovery", {})

    bridged = sum(1 for row in scored if (row.get("bridging_seeds_with_bridge") or 0) > 0)
    structures = sum(1 for row in results() if row.get("structure"))

    atlas = precomputed("ATLAS.json")
    computed = [name for name, layer in layers.items() if layer.get("computed")]

    if not state["present"]:
        health, note = "no data", "no campaign is configured on this host"
    elif not state["jobs_total"]:
        health, note = "unknown", "campaign present but its job total is not published"
    elif not scored:
        health, note = "idle", "campaign present, nothing scored yet"
    elif state["running"]:
        health, note = "running", f"{state['jobs_done']} of {state['jobs_total']} jobs complete"
    else:
        health, note = "complete", "published campaign finished"

    # "complete" describes the campaign that was published, not the project.
    # The droplet cannot see the Studio's queues, so build_atlas records what
    # was outstanding when the slice was built. Without this the header reads
    # COMPLETE while three campaigns are still to run, and a visitor
    # reasonably concludes the science is finished.
    outstanding = atlas.get("outstanding") or []
    # Split, because "finished" is a claim about this campaign and the list
    # may contain this campaign. Its tier 1 is what the slice was built from,
    # so an entry for it here is a later stage of the same campaign still to
    # run, and saying "finished" over the top of that is the thing the
    # outstanding list exists to prevent. An atlas built before the scan
    # recorded `published` has neither key, and those entries read as other
    # campaigns, which is what they were.
    own = [row for row in outstanding if row.get("published")]
    others = [row for row in outstanding if not row.get("published")]
    if health == "complete" and own:
        stage = own[0]
        note = (f"published campaign's jobs finished; its tier-"
                f"{stage.get('tier', 2)} stage was "
                f"{stage['jobs_done']} of {stage['jobs_total']} when this "
                f"slice was built")
        if others:
            note += (f", and {len(others)} other "
                     f"{'campaign was' if len(others) == 1 else 'campaigns were'}"
                     " queued")
    elif health == "complete" and others:
        note = (f"published campaign finished; {len(others)} more "
                f"queued when this slice was built")

    return {
        "health": health,
        "note": note,
        "outstanding": outstanding,
        "pairs_scored": len(scored),
        "pairs_bridged": bridged,
        "jobs_done": state["jobs_done"],
        "jobs_total": state["jobs_total"],
        "percent": state["percent"],
        "structures": structures,
        "validation_computed": len(computed),
        "validation_total": len(layers) or 3,
        "median_rmsd": (recovery.get("summary", {})
                        .get("overall_curve", {}).get("median_rmsd")),
        "campaign_id": state["campaign_id"],
        "atlas_bytes": atlas.get("bytes"),
    }


def precomputed(name: str) -> dict:
    """A document precomputed into the atlas by deploy/build_atlas.py.

    The app never imports the curation pipeline at request time: the droplet
    has no gemmi, no pandas and no BINMAN checkout, and two routes that did
    import it returned 500 there while working locally.
    """
    if _CAMPAIGN is None:
        return {}
    path = _CAMPAIGN / name
    if not path.exists():
        return {}
    return _cached(f"pre:{name}", path, lambda p: json.loads(p.read_text()))


def weight_fit() -> dict:
    """The fitted composite weights, or the refusal and its reason."""
    if _CAMPAIGN is None:
        return {}
    path = _CAMPAIGN / "weights.json"
    if not path.exists():
        return {}
    return _cached("weights", path, lambda p: json.loads(p.read_text()))


def scan_state(document: dict) -> dict:
    """Whether the design tab's scan has run, and how much of it.

    The panel was headed "Planned scan" and footed with a projection of the
    work it would take, both of them static, while the table between them
    reported measured lifts for every variant. The Lift column used to say
    "not run" in the same state and was fixed for the same reason, with a
    comment saying the page "disagreed with itself about whether the scan
    had run"; the heading and the cost line were left behind (F206).

    Keyed on the substitutions the profile has a lift for, which is the
    mapping the Lift column already builds, so the heading cannot claim a
    scan the table does not show. Counted here rather than in the template:
    the route blanks the profile when the chosen parent is not the one that
    was scanned, so the count has to follow that and not the atlas.
    """
    variants = ((document.get("preview") or {}).get("variants")) or []
    positions = ((document.get("profile") or {}).get("positions")) or []
    measured = {row.get("substitution") for row in positions
                if row.get("substitution") and row.get("lift") is not None}
    scored = sum(1 for variant in variants
                 if variant.get("substitution") in measured)
    total = len(variants)
    if not scored:
        status, heading = "planned", "Planned scan"
    elif scored < total:
        status, heading = "partial", "Scan in progress"
    else:
        status, heading = "complete", "Completed scan"
    return {"status": status, "heading": heading,
            "scored": scored, "of": total}


def throughput() -> dict:
    if not paths.THROUGHPUT.exists():
        return {}
    return json.loads(paths.THROUGHPUT.read_text())


@dataclass
class CampaignState:
    """What the app can and cannot show, so every tab can say so honestly."""

    campaign_id: str | None
    present: bool
    pairs_total: int
    pairs_scored: int
    jobs_total: int
    jobs_done: int
    running: bool

    def to_dict(self) -> dict:
        return {
            "campaign_id": self.campaign_id,
            "present": self.present,
            "pairs_total": self.pairs_total,
            "pairs_scored": self.pairs_scored,
            "jobs_total": self.jobs_total,
            "jobs_done": self.jobs_done,
            "running": self.running,
            "percent": round(100 * self.jobs_done / self.jobs_total, 1)
            if self.jobs_total else 0.0,
        }


def campaign_state() -> dict:
    meta = campaign_meta()
    queue_rows = queue()
    done = results()
    scored = scores()

    # A published atlas carries no queue, so the totals come from ATLAS.json.
    # Without this the deployed app divides by a missing denominator, reads
    # "75 of 0" and reports a running campaign as complete.
    atlas = precomputed("ATLAS.json")
    jobs_total = len(queue_rows) or int(atlas.get("jobs_total") or 0)
    pairs_total = (
        len({row.get("pair_id") for row in queue_rows})
        or int(atlas.get("pairs_total") or 0)
        or (meta.get("pairs") if isinstance(meta.get("pairs"), int) else 0)
    )

    state = CampaignState(
        campaign_id=meta.get("campaign_id") or (_CAMPAIGN.name if _CAMPAIGN else None),
        present=bool(_CAMPAIGN and _CAMPAIGN.exists()),
        pairs_total=pairs_total,
        pairs_scored=len(scored),
        jobs_total=jobs_total,
        jobs_done=len(done),
        # Unknown total means unknown state, not a finished one.
        running=bool(jobs_total) and len(done) < jobs_total,
    )
    return state.to_dict()


# Component metadata for the weights panel and the tooltips. Each entry carries
# what the number is, its units, and whether it is measured, predicted or
# model-derived, which is what spec Phase 4's tooltip requirement asks for.
# How a UI component key maps to the name the fitter uses for it.
#
# The fitter names a component after the column it reads and the UI names it
# after the signal: `lysine_reach_exposed_fraction` against `lysine_reach`.
# Four of the five names agree exactly and that one does not, so a join by
# key silently loses it, and `fitted_w.get(key, default)` turns the miss into
# a plausible default rather than an error.
#
# This lived as a literal inside campaign.html's JavaScript, which resolved
# it correctly. The Jinja that renders the slider's initial value did not, so
# the two layers disagreed about how to resolve a name and only one of them
# was right. Defined here so both read the same map, and
# `tests/test_component_names.py` holds that every fitter candidate resolves
# to exactly one UI key and back (F106).
FITTED_ALIASES = {"lysine_reach": "lysine_reach_exposed_fraction"}


def component_auc(per_component: dict | None, key: str):
    """The standalone AUC for a UI component key, through the same aliases.

    `FITTED_ALIASES` exists because the UI calls one component `lysine_reach`
    and the fit calls it `lysine_reach_exposed_fraction`. A bare
    `per_component.get(key)` misses it, which is F106 in the weight lookup
    and was F284 here: four of the five components rendered their AUC and the
    one whose note already admits it sits at chance rendered nothing.

    One function, so the template cannot resolve the name one way and the
    weight lookup another.
    """
    if not per_component:
        return None
    return per_component.get(FITTED_ALIASES.get(key, key))


def fitted_weight(fitted: dict | None, key: str, default=None):
    """The fitted weight for a UI component key, or `default`.

    One function so the template cannot resolve the name one way and the
    JavaScript another.

    A component the fit did not use starts at zero, not at its hand-set
    default, and that is the whole of F205. When a fit exists, the weight it
    gives a component it left out is zero: `components_used` names the two it
    selected and the fit's answer for the other three is that they carry no
    weight. Falling back to the default there put the ledger's composite
    column at 0.6578 for IKZF1 while the pipeline had stored 0.6189, under a
    sentence saying "Fitted on 127 labelled pairs, never by hand".

    That is F106's shape surviving for the components the fit did not pick.
    F106 made the sliders show fitted values rather than defaults, which
    fixed the ones the fit used; the ones it did not use kept their defaults
    and kept contributing to a column the page presents as the fit's.

    With no fit at all the defaults are right: they are the starting values
    the page says they are, and the panel says so in as many words.
    """
    if not fitted:
        return default
    source = FITTED_ALIASES.get(key, key)
    value = fitted.get(source)
    return 0 if value is None else value


COMPONENTS = {
    "bridge_percentile": {
        "label": "Bridge percentile",
        "units": "percentile",
        "source": "measured against 285,996 observed bridges",
        "trust": "primary",
        "default_weight": 0.35,
        "note": "Buried surface of the glue against both chains, as a percentile "
                "of the experimentally observed distribution. Compares a "
                "prediction to real interfaces rather than to the model's own "
                "confidence.",
    },
    "delta_iptm": {
        "label": "Delta-ipTM",
        "units": "ipTM difference",
        "source": "model-derived",
        "trust": "headline",
        "default_weight": 0.25,
        "note": "Ternary minus binary interface confidence on the "
                "receptor-to-peptide chain pair, minimum across seeds. A "
                "collapsed seed can dominate it: the median is shown alongside.",
    },
    "convergence_score": {
        "label": "Pose convergence",
        "units": "0 to 1, from mean pairwise RMSD",
        "source": "measured from the predictions",
        "trust": "high",
        "default_weight": 0.25,
        "note": "Pairwise peptide backbone RMSD across seeds after superposing "
                "on the receptor. Tracks reality better than confidence for "
                "peptides.",
    },
    "plip_fingerprint_match": {
        "label": "PLIP fingerprint match",
        "units": "fraction of canonical contacts",
        "source": "measured from the predictions",
        "trust": "high",
        "default_weight": 0.15,
        "note": "Fraction of the canonical degron contacts for that E3 class "
                "that the prediction reproduces.",
    },
    "lysine_reach": {
        "label": "Lysine geometry",
        "units": "not validated",
        "source": "measured, but not a validated predictor",
        "trust": "not validated",
        "default_weight": 0.0,
        "note": "BINMAN's reach window is deliberately unfitted: Cb-Cb AUC 0.42 "
                "to 0.48 on 369 assayed lysines, at or below chance and slightly "
                "inverted. Reported as a measurement only.",
    },
}


def design() -> dict:
    """The design arm's state (DESIGN_ARM.md).

    Precomputed like everything else the droplet serves: this reads the
    atlas rather than the curation stack, because importing the generator
    at request time would put the scientific stack behind a route again and
    that has already caused two 500s in production.
    """
    return precomputed("design.json")


# Keys the campaign and Delta pages embed in their page payload and never
# read. Measured on the benchmark atlas: `seed_records` is 56 per cent of a
# score row, `plip` 20, `contact_map` 10 and `convergence` 5, and neither
# page accesses any of them. They are per-seed and per-contact detail, read
# by the pose and interactions pages from `/api/pair/<pair_id>`, which still
# serves the whole row, and by `/api/pairs`, which the client never calls.
#
# This matters at campaign scale rather than at benchmark scale. Both pages
# serialise every pair into the document with `{{ pairs | tojson }}`, so the
# page grows with the campaign: measured on a 158-pair atlas, the shape the
# running campaign will produce, the landing page is 3.37 MB of HTML, of
# which 99 per cent is in keys the page never touches. Trimming is the
# difference between a landing page the droplet can serve over a slow
# connection and one it cannot.
#
# A deny-list rather than a list of keys to keep. Keeping is the safe-looking
# choice and is the more dangerous one: a scalar left out of an allow-list
# shows up as a blank cell on a page nobody is watching, while a heavy key
# left in a deny-list only costs bytes. The test enumerates this tuple
# against what each page actually accesses, so a fifth entry has to be shown
# unused before it can be added.
PAGE_PAYLOAD_OMITS = ("seed_records", "plip", "contact_map", "convergence")


def scores_for_pages() -> list[dict]:
    """`scores()` without the per-seed detail the pages embed and never read."""
    return [
        {key: value for key, value in row.items()
         if key not in PAGE_PAYLOAD_OMITS}
        for row in scores()
    ]


def crystal_control_counts(control: dict | None) -> dict:
    """Found, measurable and intended counts for the crystal control (F297).

    Computed here rather than in the template because a count belongs in
    Python, and because the three numbers are not interchangeable: a
    deposition whose glue was never modelled is not a crystal the filter
    missed, and the panel has to be able to say both without the reader
    working out the subtraction.
    """
    rows = (control or {}).get("rows") or []
    measurable = [row for row in rows if row.get("measurable")]
    return {
        "intended": len(rows),
        "measurable": len(measurable),
        "found": len([row for row in measurable if row.get("found")]),
        "unmeasurable": [row for row in rows if not row.get("measurable")],
        "status": (control or {}).get("status"),
    }
