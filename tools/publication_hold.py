"""Refuse to publish while the atlas is held, and say what is being held and why.

Called from deploy/deploy.sh's pre-flight, before any connection to the
droplet is opened, so a held atlas costs nothing and touches nothing.

Two things about the shape of this, both deliberate:

  - No cutoff is defined here or in config/thresholds.toml. "Good enough to
    publish" is not a measurement, and inventing a success radius so that a
    script could decide it would be inventing the headline. The hold is a
    recorded decision (config/publication_hold.toml) and this reads it.

  - It still prints the live pose-recovery curve next to the recorded reason,
    read out of the campaign's own validation.json rather than copied into
    the config. A hold that quotes numbers from the day it was written goes
    stale silently, and the point of re-reading it on every deploy attempt is
    that the person releasing it sees what is true now.
"""
from __future__ import annotations

import argparse
import json
import sys
import tomllib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nobble import paths  # noqa: E402

DEFAULT_CONFIG = paths.CONFIG / "publication_hold.toml"


def read_hold(config: Path) -> dict:
    """The recorded decision. A missing file is a refusal, not a release."""
    if not config.exists():
        return {
            "held": True,
            "decision": "",
            "reason": f"{config} is missing, and an absent hold file is read as "
                      "held: a publication gate that opens when its own "
                      "configuration is deleted is not a gate.",
            "released_by": "",
        }
    with config.open("rb") as handle:
        return tomllib.load(handle)


def newest_validation() -> Path | None:
    """The most recent campaign that got as far as writing validation.json."""
    found = sorted(paths.CAMPAIGNS.glob("campaign_*/validation.json"))
    return found[-1] if found else None


def recovery_now(validation: Path | None) -> dict | None:
    """The pose-recovery layer's own summary, or None if it is not computed."""
    if validation is None or not validation.exists():
        return None
    try:
        layers = json.loads(validation.read_text()).get("layers", {})
    except json.JSONDecodeError:
        return None
    layer = layers.get("pose_recovery")
    if not isinstance(layer, dict) or not layer.get("computed"):
        return None
    summary = layer.get("summary")
    return summary if isinstance(summary, dict) else None


def describe(summary: dict | None) -> list[str]:
    """The curve as lines, or one line saying there is no curve to read."""
    if summary is None:
        return ["    pose recovery: not computed in the newest campaign"]
    curve = summary.get("overall_curve", {})
    pairs = summary.get("by_pair", {})
    lines = [
        f"    pose recovery over {curve.get('n')} pose(s) in "
        f"{len(pairs)} pair(s), median {curve.get('median_rmsd')} A",
    ]
    for key, value in sorted(curve.items()):
        if key.startswith("within_"):
            radius = key.removeprefix("within_").removesuffix("A")
            lines.append(f"      within {radius} A: {value}")
    for pair_id, record in sorted(pairs.items()):
        lines.append(f"      {pair_id:28s} median {record.get('median_rmsd')} A")
    return lines


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG,
                        help="the recorded decision to read")
    parser.add_argument("--campaign", type=Path, default=None,
                        help="a specific campaign directory, instead of the newest")
    args = parser.parse_args()

    hold = read_hold(args.config)
    validation = (args.campaign / "validation.json" if args.campaign
                  else newest_validation())
    lines = describe(recovery_now(validation))

    if not hold.get("held"):
        released = str(hold.get("released_by") or "").strip()
        if not released:
            print("publication hold: the hold is marked released but names no "
                  "decision in `released_by`. Refusing: an unattributed release "
                  "is indistinguishable from an accident.", file=sys.stderr)
            return 2
        print(f"    publication released by {released}")
        for line in lines:
            print(line)
        return 0

    decision = str(hold.get("decision") or "an unrecorded decision").strip()
    reason = str(hold.get("reason") or "no reason recorded").strip()
    print(f"deploy: publication is held by {decision}.", file=sys.stderr)
    for paragraph in reason.splitlines():
        if paragraph.strip():
            print(f"        {paragraph.strip()}", file=sys.stderr)
    print("        What the newest campaign measures today:", file=sys.stderr)
    for line in lines:
        print(f"    {line.strip()}", file=sys.stderr)
    print(f"        To publish anyway, edit {args.config}: set held = false and "
          "name the authorising decision in `released_by`.", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
