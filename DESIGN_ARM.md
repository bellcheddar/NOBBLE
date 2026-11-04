# The design arm

Scope for NOBBLE's seventh tab. Not part of `BUILD_SPEC.md`, which contains no
design phase: the spec names "designed peptides" twice, both in section 3.5 as
an input class ESMFold would handle if such sequences existed. This document
is the addition, kept separate so the authoritative spec stays as written.

## What it is for

Everything NOBBLE has built so far measures whether a predicted interface
tells you anything true. The design arm is the first part that proposes
something new: variants of known degrons, scored by the same pipeline, to ask
which positions a degron actually depends on and whether any change improves
it.

## The constraint that shapes everything else

**The composite score is not validated yet.** The matched-control ROC reports
`not_computed` until the Sievers arm runs, and the weight fitter refuses for
want of labelled pairs. A design tab that ranks invented peptides by an
unvalidated score would be the exact failure this project exists to avoid:
a scoring function you cannot trust will rank designs happily and rank them
wrong, and a ranked list is read as a recommendation no matter what the
caption says.

So the arm is built to be useful *before* the score is trusted, and more
useful after:

1. Every design is anchored to a parent with an experimental label. Nothing
   is scored in the abstract.
2. The headline number is **design lift**: `delta_iptm(variant) -
   delta_iptm(parent)`. A difference of differences, which cancels anything
   constant about the parent, the receptor and the glue.
3. The tab reports the validation state of the score next to the rankings,
   and says plainly what is and is not established. An alanine scan is
   interpretable as *relative* structure even if the absolute scale is not
   yet trustworthy: "position 7 matters more than position 3" survives a
   miscalibrated score in a way "this peptide will be degraded" does not.

## Generators

Deterministic, no new dependencies, no generative model. Each produces
variants of one parent peptide.

| Generator | Produces | Why first |
|---|---|---|
| Alanine scan | one variant per position, each residue to Ala (Ala to Gly) | The canonical first experiment. Interpretable per position, and the parent is its own control |
| Saturation | all 19 substitutions at chosen positions | Follows the scan: saturate only where the scan says it matters |
| Conservative / radical | substitutions grouped by chemistry | Separates "this position needs a residue of this type" from "this exact residue" |

ESM-2 is already in the stack for diversity reduction and could propose
likelihood-ranked substitutions later. Left out of the first build: it would
introduce a second opinion about which designs are good, and the point of the
arm is to test NOBBLE's opinion.

## Cost

A design pair costs what any pair costs: 15 jobs. An alanine scan of a 15-mer
is 15 variants, 225 jobs, roughly 4.6 hours at the measured rate. That is a
deliberate choice of scale: one scan is affordable, a saturation scan of every
position (285 variants, 4,275 jobs) is not, which is why saturation follows
the scan rather than replacing it.

## What was learned building it

Three defects were found by constructing the failure rather than waiting for
it. All three produce a plausible number instead of an error, and two agree
with what a structural biologist expects, which is what makes them expensive.
Recorded in full as F11.

| Defect | Why it mattered |
|---|---|
| A scan of a zinc finger dropped the ion at its coordinating cysteines | Those are the positions the scan exists to interrogate. The lift would have been large, negative, and read as "this position is critical" |
| A substitution of a residue for itself ranked as the most sensitive position | Its two runs differ only by seed, so its lift is the noise floor, and it sorts into the ranking like any other number |
| The scan chart never drew | The script ran before Plotly loaded. Routine QC passed because with no data the script returns early, so it would have failed only after a scan had run |

Three decisions followed, beyond the scope above:

- **A variant inherits its parent's cofactor** rather than re-deriving it
  (D-NOB-038). A finger variant keeps a zinc it cannot properly hold, which is
  correct for a control: the variant differs in the residue, not in the
  chemical system around it.
- **Lift requires equal seed depth**, not merely sufficient depth. Both sides
  normally match, coming from one campaign with one seed tuple; they stop
  matching when a job fails, which is exactly when nobody is checking.
- **The scan picks its target after the main campaign** (D-NOB-040), so the
  parent is chosen from 158 scored pairs rather than the 7 that happened to
  exist when the arm was built.

## Symmetry, again

A variant and its parent must be run under identical conditions: same
receptor construct, same glue, same seeds, same sampling tier, and the same
cofactor if the parent has one. Design lift is a difference of differences,
so any asymmetry between the two shows up as signal. This is the same rule
that governs the binary and ternary arms (D-NOB-034) and the sampling tiers
(D-NOB-032), and it is checked rather than assumed.
