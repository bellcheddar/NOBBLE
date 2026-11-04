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
        return loader(path) if False else ([] if key != "campaign" else {})
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
    if health == "complete" and outstanding:
        note = (f"published campaign finished; {len(outstanding)} more "
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
