"""Delta-ipTM has to name the chain pair it is about.

Spec 4.3 defines the headline as a difference of ipTM minima and does not
say which chain pair the ipTM is. For a single-chain receptor the question
does not arise. For a receptor submitted as several chains it does, and it
was being answered silently: chain 0 against the peptide.

For DCAF15_DDB1_DDA1 that is the N-terminal domain of DCAF15 alone, while
its C-terminal domain, which the substrate also binds, was ignored. The
minimum across the substrate receptor's own segments is the rule this
module already applies twice over, across the two directions of Boltz's
asymmetric matrix and across seeds.

Whichever rule is used, it rests on an invariant nobody had written down:
the substrate receptor is the construct's first segment. These tests hold
that, so a construct added with the scaffold first fails here rather than
producing a headline number about the wrong interface.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from nobble.curate import constructs as C  # noqa: E402
from nobble.score import metrics  # noqa: E402


def test_the_substrate_receptor_is_always_the_first_segment():
    """The invariant the chain choice depends on.

    Cross-checked against yaml_gen's own gene-to-accession map, which was
    read off the deposited assemblies, so this is not one piece of code
    agreeing with itself.
    """
    from nobble.execute.yaml_gen import RECEPTOR_CHAINS_BY_PDB

    accession_of_gene: dict[str, str] = {}
    for mapping in RECEPTOR_CHAINS_BY_PDB.values():
        for gene, (_chain, accession) in mapping.items():
            accession_of_gene[gene] = accession

    checked = 0
    for name, construct in C.CONSTRUCTS.items():
        expected = accession_of_gene.get(construct.e3_gene)
        if expected is None:
            continue                     # no deposited assembly to check against
        assert construct.segments[0].accession == expected, (
            f"{name}: first segment is {construct.segments[0].accession}, but "
            f"{construct.e3_gene} is {expected}. The receptor-peptide ipTM "
            "would be measured against the wrong protein"
        )
        checked += 1
    assert checked >= 4, f"only {checked} construct(s) cross-checked"


def test_substrate_receptor_chains_groups_the_segments_of_one_protein():
    chains = {name: construct.substrate_receptor_chains()
              for name, construct in C.CONSTRUCTS.items()}
    # DCAF15 is submitted as two domains; the substrate binds both.
    assert chains["DCAF15_DDB1_DDA1"] == (0, 1)
    # VHL's partners are different proteins, so only VHL itself.
    assert chains["VHL_VCB"] == (0,)
    # And every construct starts at chain 0, by the invariant above.
    for name, indices in chains.items():
        assert indices and indices[0] == 0, f"{name}: {indices}"


def test_the_scaffolding_chains_are_excluded():
    """A minimum over all five chains would be dominated by DDB1, which the
    peptide is not supposed to touch, so the statistic would measure how
    well the degron fails to engage the scaffold."""
    construct = C.CONSTRUCTS["DCAF15_DDB1_DDA1"]
    chains = construct.substrate_receptor_chains()
    assert len(chains) < len(construct.segments)
    excluded = [construct.segments[i].accession
                for i in range(len(construct.segments)) if i not in chains]
    assert "Q16531" in excluded, "DDB1 is still in the ipTM pair"
    assert "Q9BW61" in excluded, "DDA1 is still in the ipTM pair"


def test_the_value_is_the_minimum_across_the_receptors_own_segments():
    matrix = {
        "0": {"5": 0.80}, "1": {"5": 0.60}, "2": {"5": 0.10},
        "3": {"5": 0.05}, "4": {"5": 0.20},
        "5": {"0": 0.80, "1": 0.60, "2": 0.10, "3": 0.05, "4": 0.20},
    }
    value, chains, first_only = metrics._receptor_peptide_iptm(
        {"pair_chains_iptm": matrix}, "DCAF15_DDB1_DDA1"
    )
    assert chains == [0, 1]
    assert value == 0.60, "did not take the minimum over DCAF15's two segments"
    assert first_only == 0.80, "the previous definition is no longer recoverable"
    # Emphatically not the minimum over everything, which would be DDB1's 0.05.
    assert value != 0.05


def test_a_single_chain_receptor_is_unchanged_by_the_rule():
    matrix = {"0": {"1": 0.42}, "1": {"0": 0.42}}
    value, chains, first_only = metrics._receptor_peptide_iptm(
        {"pair_chains_iptm": matrix}, "CRBN_CULT"
    )
    assert chains == [0]
    assert value == first_only == 0.42


def test_the_asymmetric_matrix_is_still_symmetrised_conservatively():
    """Boltz's matrix is not symmetric; the lower direction is taken. That
    rule predates this change and must survive it."""
    matrix = {"0": {"1": 0.876}, "1": {"0": 0.840}}
    value, _chains, _first = metrics._receptor_peptide_iptm(
        {"pair_chains_iptm": matrix}, "CRBN_CULT"
    )
    assert value == 0.840
