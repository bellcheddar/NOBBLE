"""The Sievers arm must be co-folded with the drug that actually degraded it.

The screen tests five IMiDs and reports which were significant per zinc
finger, and the answer differs between them: pomalidomide is significant for
23 of the 32 degraded zinc fingers, lenalidomide for 8. Running the whole arm
under one drug would place zinc fingers on the positive side of the ROC while
co-folding them with a drug the same screen says does not degrade them, which
inverts the label the ROC is built on.

Eight of the 32 are significant only for CC-122 or CC-220, which have no CCD
code in BINMAN's ligand table. Spec 4.18 scopes its falsifiable prediction to
"lenalidomide or pomalidomide", so those fall outside the arm rather than
being run under a drug that does not degrade them.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from nobble.curate.peptides import IMID_CCD, IMID_PREFERENCE, Peptide, sievers_drug_for


def _zf(significant: list[str]) -> Peptide:
    return Peptide(
        peptide_id="zf", sequence="ACDEFGHIKLMNPQ", source="sievers_zf",
        label="degraded", accession="P00000", gene="ZNFX",
        start_res=1, end_res=14,
        screen_drugs={"tested": ["CC122", "CC220", "LEN", "POM", "THAL"],
                      "significant": significant},
    )


def test_pomalidomide_is_preferred_when_both_are_significant():
    """Not arbitrary: pomalidomide covers 23 of 32 degraded zinc fingers
    against lenalidomide's 8, so preferring it keeps the arm on one drug
    wherever the screen allows."""
    assert sievers_drug_for(_zf(["LEN", "POM"]))["ccd"] == IMID_CCD["POM"]


def test_lenalidomide_is_used_when_it_is_the_only_one_significant():
    assert sievers_drug_for(_zf(["LEN"]))["ccd"] == IMID_CCD["LEN"]


def test_a_zinc_finger_with_no_ccd_drug_is_refused_not_substituted():
    """The whole point. Substituting pomalidomide here would put a zinc
    finger the screen calls undegraded by pomalidomide on the positive side
    of the ROC."""
    routing = sievers_drug_for(_zf(["CC220"]))
    assert routing["ccd"] is None
    assert routing["drug"] is None
    assert "unroutable" in routing["status"]


def test_thalidomide_is_not_in_the_preference_list():
    """It has a CCD (EF2) and is deliberately excluded: every
    thalidomide-significant row in the screen is also pomalidomide-significant,
    so including it changes no assignment while widening the claim past the
    spec's prediction."""
    assert "THAL" not in IMID_PREFERENCE
    assert "THAL" in IMID_CCD, "the CCD is known; the exclusion is a scope choice"
    assert sievers_drug_for(_zf(["THAL", "POM"]))["drug"] == "POM"


def test_a_control_inherits_its_positives_drug():
    """A control co-folded with a different IMiD than its positive would
    differ from it in two things at once, and the pair would measure neither."""
    from nobble.curate.peptides import sievers_matched_set

    matched = sievers_matched_set()
    by_id = {p.peptide_id: p for p in matched["peptides"]}
    controls = [p for p in matched["peptides"] if p.parent_peptide_id]
    assert controls, "no matched controls were produced"

    for control in controls:
        parent = by_id[control.parent_peptide_id]
        assert control.screen_drugs["assigned_ccd"] == parent.screen_drugs["assigned_ccd"]
        assert control.screen_drugs["inherited_from"] == parent.peptide_id


def test_dropped_positives_do_not_consume_controls():
    """Dropping has to happen before matching. A dropped positive that had
    already taken four controls would starve a kept one."""
    from nobble.curate.peptides import sievers_matched_set

    matched = sievers_matched_set(negatives_per_positive=4)
    assert matched["positives"] == 24
    assert matched["controls"] == 96, "a kept positive lost controls to a dropped one"
    assert len(matched["dropped_positives"]) == 8
