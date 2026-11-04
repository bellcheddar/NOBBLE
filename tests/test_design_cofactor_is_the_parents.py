"""Every variant in a scan inherits the parent's cofactor decision (F151).

`lift` is `delta_iptm(variant) - delta_iptm(parent)`, and its own docstring
says a difference is interpretable only when its two terms differ in one
thing. `MATCHED_CONDITIONS` enumerates those things: construct, e3_gene,
ligand_key, modality. The structural cofactor is not among them, and a score
row carries no cofactor field at all, so `lift.compute` could not compare
them if it wanted to.

That is sound, because the mismatch cannot arise: `assemble` computes
`requires_structural_zinc` once from the parent and gives the result to every
variant. Inferring it per variant would be actively wrong, because an alanine
scan mutates the coordinating cysteines and would drop the ion at exactly the
positions the scan exists to measure.

So the guarantee is structural rather than checked, and it was resting on a
comment. `run_design.sh` credited preflight with it, and preflight checks a
different thing: that a pair's binary and ternary arms agree, not that a
variant agrees with its parent.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_the_assembler_takes_one_decision_and_reuses_it():
    source = (ROOT / "nobble" / "design" / "assemble.py").read_text()
    # `build_manifest` is where the decision is taken; `assemble` writes
    # what it produced. Sliced to the manifest builder because that is the
    # function whose single call is the guarantee. Slicing from `assemble`
    # instead counted zero calls and failed, which is the right way round:
    # a test that cannot find the thing it is about should say so.
    body = source[source.index("def build_manifest"):source.index("def assemble")]
    calls = body.count("requires_structural_zinc(")
    assert calls == 1, (
        f"requires_structural_zinc is called {calls} times while building "
        "the manifest; once is what makes every variant share the parent's "
        "decision"
    )
    assert "parent_cofactor" in body
    # And the whole module calls it once, so no other path can infer it.
    assert source.count("requires_structural_zinc(") == 1, (
        "something else in the module infers the cofactor as well"
    )


def test_no_assembled_scan_mixes_cofactors():
    """Checked on whatever design campaigns exist, through the YAMLs.

    The YAML is what Boltz reads, so it is the thing that decides whether
    the ion was there, whatever the queue row says.
    """
    for campaign in sorted((ROOT / "campaigns").glob("design_*")):
        yamls = sorted((campaign / "yaml").glob("*.yaml"))
        if not yamls:
            continue
        with_zinc = {("ZN" in path.read_text()) for path in yamls}
        assert len(with_zinc) == 1, (
            f"{campaign.name} mixes cofactors across its pairs, so a lift "
            "taken in it would report the ion as the substitution's effect"
        )


def test_the_decision_is_recorded_with_its_reason():
    """A campaign has to say which way it went and why.

    Without it, a scan that ran without zinc and a scan that ran with it are
    indistinguishable after the fact, and the lift's interpretation differs
    between them.
    """
    for campaign in sorted((ROOT / "campaigns").glob("design_*")):
        meta_path = campaign / "campaign.json"
        if not meta_path.exists():
            continue
        cofactor = json.loads(meta_path.read_text()).get("cofactor")
        assert isinstance(cofactor, dict), f"{campaign.name}: {cofactor!r}"
        assert "required" in cofactor and cofactor.get("reason"), cofactor


def test_run_design_does_not_credit_preflight_with_the_wrong_half():
    script = (ROOT / "tools" / "run_design.sh").read_text()
    header = script[:script.index("set -uo pipefail")]
    assert "assembler" in header, (
        "the header still attributes the variant-against-parent guarantee to "
        "preflight, which checks binary against ternary within a pair"
    )


def test_preflight_checks_the_half_it_does_check():
    source = (ROOT / "tools" / "preflight.py").read_text()
    assert "cofactor_by_pair" in source
    assert "asymmetric" in source, (
        "preflight no longer compares a pair's arms, which is the half it is "
        "responsible for"
    )
