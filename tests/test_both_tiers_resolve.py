"""Fourteen call sites indexed the six-entry Tier A registry.

Marc named eleven Tier B receptor constructs, `tier_b_constructs.report()`
said `ready`, and nothing could use them. Every consumer of a construct did
`C.CONSTRUCTS[name]`, which holds spec 1.1's six Tier A receptors, so a Tier
B name would have raised `KeyError`: at manifest build, at campaign
assembly, in YAML generation, and in four scoring modules. The arm was
selected, frozen, gate-passed, answered, and unrunnable at every stage.

I fixed the instance in `campaign.py` first and nearly stopped there, which
would have moved the KeyError one step later. The category is what mattered:
fourteen sites across nine modules, found by grepping for the subscript
rather than by reasoning about which stage runs first.

`constructs.by_name` resolves either registry, with `by_name_or_none` for
the one caller that treats an unknown construct as a status. This test
forbids the direct subscript outside the module that owns the registries, so
the fifteenth call site fails here rather than at assembly time.

Two more of the same shape were in the same sweep and are checked below.
`msa.required_sequences` iterated the Tier A registry, so `precompute()` had
nothing to fetch for Tier B and every Tier B job would have been submitted
with `msa: empty`: single-sequence predictions compared against a panel
predicted with MSAs, which is not a comparison. And `E3_TO_CONSTRUCT` routed
six genes, so a Tier B pair had no receptor to look up at all.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.curate import constructs as C  # noqa: E402
from nobble.curate import manifest as M  # noqa: E402
from nobble.curate import tier_b_constructs as T  # noqa: E402
from nobble.execute import msa  # noqa: E402

# The module that owns both registries is where direct access belongs.
OWNER = "nobble/curate/constructs.py"
# Subscripts and iterations both. The first version of this forbade only
# `CONSTRUCTS[` and `CONSTRUCTS.get(`, and two call sites reached the Tier A
# registry by iterating it instead: `manifest.validate` and
# `tools/preflight.py` each built the declared-exception set from
# `CONSTRUCTS.items()`, in identical comprehensions, so marking a Tier B
# construct `exception = true` changed nothing in either and the manifest
# went on reporting ten token_cap_exceeded errors. A guard that enumerates
# one spelling of an access pattern is the same mistake as fixing one call
# site of fourteen (F211).
SUBSCRIPT = re.compile(
    r"CONSTRUCTS\s*\[|CONSTRUCTS\s*\.\s*(get|items|values|keys)\s*\(|"
    r"\bin\s+(C\.)?CONSTRUCTS\b"
)


def _sources() -> list[Path]:
    return [path for directory in ("nobble", "tools", "deploy")
            for path in sorted((ROOT / directory).rglob("*.py"))
            if "static/vendor" not in path.as_posix()]


def test_nothing_outside_constructs_indexes_a_registry_directly():
    offenders = {}
    for path in _sources():
        relative = path.relative_to(ROOT).as_posix()
        if relative == OWNER:
            continue
        hits = [n for n, line in enumerate(path.read_text().splitlines(), 1)
                if SUBSCRIPT.search(line) and not line.strip().startswith("#")]
        if hits:
            offenders[relative] = hits
    assert not offenders, (
        "direct registry lookup(s), which raise KeyError for a Tier B "
        f"construct. Use constructs.by_name: {offenders}"
    )


def test_the_owner_still_has_one():
    """Otherwise the sweep above passes because the registry is gone."""
    source = (ROOT / OWNER).read_text()
    assert SUBSCRIPT.search(source), "by_name no longer reads CONSTRUCTS"


def test_by_name_reaches_both_registries():
    for name in sorted(C.CONSTRUCTS):
        assert C.by_name(name).e3_gene
    tier_b = T.load()
    assert tier_b, "no Tier B constructs defined, so this checks one tier"
    for name in sorted(tier_b):
        assert C.by_name(name).e3_gene


def test_by_name_or_none_is_none_rather_than_raising():
    assert C.by_name_or_none("NO_SUCH_CONSTRUCT") is None
    assert C.by_name_or_none(None) is None
    assert C.by_name_or_none("") is None
    assert C.by_name_or_none(next(iter(C.CONSTRUCTS))) is not None


def test_every_tier_b_gene_with_a_construct_can_be_routed():
    for gene, construct in T.load().items():
        assert M.E3_TO_CONSTRUCT.get(construct.e3_gene) == gene, (
            f"{construct.e3_gene} does not route to {gene}, so a Tier B pair "
            "has no receptor to look up"
        )


def test_the_route_map_is_derived_rather_than_transcribed():
    source = (ROOT / "nobble" / "curate" / "manifest.py").read_text()
    for gene in sorted(T.load().values(), key=lambda c: c.e3_gene):
        assert f'"{gene.e3_gene}": ' not in source, (
            f"{gene.e3_gene} is written into E3_TO_CONSTRUCT as well as the "
            "form, so the two can disagree"
        )


def test_msa_precompute_asks_for_both_tiers():
    wanted = {record.get("sequence") for record in msa.required_sequences()
              if record.get("sequence")}
    for name, construct in sorted(T.load().items()):
        for segment in construct.segments:
            assert segment.sequence() in wanted, (
                f"{name} is not in the MSA requirement, so its jobs would go "
                "to Boltz with msa: empty"
            )


def test_an_excluded_gene_is_not_routed():
    """The four exclusions have no construct, so nothing should route them."""
    for gene in T.exclusions():
        assert gene not in M.E3_TO_CONSTRUCT, (
            f"{gene} was excluded but still routes to a construct"
        )
