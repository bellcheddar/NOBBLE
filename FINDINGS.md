# NOBBLE findings

Interim. Written while the benchmark campaign is still running, and every number
here is from a partial run at tier-1 settings (3 recycles, 1 diffusion sample,
potentials off), which spec 1.2 defines as deliberately cheap triage. Tier 2
re-runs the top decile at 10 recycles and 25 diffusion samples. Nothing below is
a tier-2 result and nothing below is a discovery claim.

## F1. Geometry against the empirical envelope separates poses that ipTM cannot

The first benchmark pair, GSPT1 / CRBN / CC-885, is the pair spec 3.1 calls "the
highest-value single test in the panel". Across its fifteen completed tier-1
jobs, three independent signals were measured: Boltz's receptor-to-peptide ipTM,
whether the peptide is docked onto the receptor at all, and whether the glue
actually bridges receptor to peptide under BINMAN's bridging filter.

| complex | conditioning | seed | ipTM | peptide docked | glue bridges | bridge percentile |
|---|---|---|---|---|---|---|
| binary | unconstrained | 1-5 | 0.838 to 0.893 | yes, all five | n/a | n/a |
| ternary | conditioned | 1 | 0.885 | yes | **yes** | 54.1 |
| ternary | conditioned | 2 | 0.877 | yes | no | - |
| ternary | conditioned | 3 | 0.806 | yes | no | - |
| ternary | conditioned | 4 | 0.082 | **no**, 81.4 A away | no | - |
| ternary | conditioned | 5 | 0.911 | yes | no | - |
| ternary | unconstrained | 1 | 0.889 | yes | **yes** | 53.9 |
| ternary | unconstrained | 2 | 0.890 | yes | **yes** | 50.4 |
| ternary | unconstrained | 3 | 0.822 | yes | no | - |
| ternary | unconstrained | 4 | 0.916 | yes | no | - |
| ternary | unconstrained | 5 | 0.914 | yes | no | - |

Three things follow.

**ipTM does not distinguish a bridging pose from a non-bridging one.** A pose
that bridges scores 0.885; one that does not scores 0.877. The highest ipTM in
the whole ternary set, 0.916, does not bridge. This is a sharper version of the
caveat spec 4.5 already requires the app to state, and it is the direct
justification for spec 4.1's choice of the empirical bridge percentile as the
primary signal rather than the model's own confidence.

**Only 3 of 10 ternary trajectories produce the ternary architecture at all.** In
the other seven the peptide is docked on CRBN and the glue is in its pocket, but
the glue buries less than 25 square angstrom against the peptide, which is
BINMAN's floor for a half-interface and a very low bar for a 15-mer. The glue
and the degron are both present and not in contact. The three that do bridge sit
at the 50th to 54th percentile of 285,996 experimentally observed bridges, which
is a credible mid-range glue interface rather than an outlier.

**One trajectory failed to dock the peptide at all**, leaving it 81.4 angstrom
from the receptor centroid in free solvent, and Boltz's ipTM of 0.082 reported
that correctly. This is a failed run rather than a weak interface, and the
distinction changes what every downstream aggregate means (see D-NOB-023).

**Conditioning did not help.** The conditioned arm, which forces the glue into
the pocket measured from 5HXB, produced one bridge in five seeds; the
unconstrained arm produced two in five. That is consistent with spec 4.7's own
warning that forcing a binder into a site it did not choose "reliably produces
the right neighbourhood and the wrong pose", and it is why agreement between the
two arms is the signal rather than the conditioned result alone.

## F2. Pose convergence is poor at tier-1 settings, and it is informative

Pairwise peptide backbone RMSD across seeds, superposed on the receptor (436
anchor atoms, receptor RMSD after superposition 0.23 angstrom, so the frame is
sound):

| condition | mean | max |
|---|---|---|
| binary | 11.4 A | 17.1 A |
| ternary, conditioned | 43.1 A | 98.5 A |
| ternary, unconstrained | 22.1 A | 36.8 A |

Some seed pairs agree to 1.7 to 4.3 angstrom; others are tens of angstrom apart,
which for a 109-residue receptor domain means the peptide is on a different part
of the protein. Spec 4.4 predicted this would be the more honest measure for
peptides than confidence, and on this pair it is: the convergence spread
identifies the same seeds the geometry filter rejects, while ipTM does not.

Poor convergence at tier 1 is partly expected, since tier 1 runs a single
diffusion sample precisely to keep triage cheap. Whether tier 2's 25 samples
recover a converged pose is a question this campaign will answer directly, and
it is the right question to put to the Benchmark tab.

## F2b. PLIP confirms F1 independently: the glue is placed perfectly, the degron is not

The interaction fingerprint was computed for the same seeds, which is a wholly
different measurement from the dSASA bridging filter: PLIP perceives explicit
hydrophobic contacts and hydrogen bonds from a bond table, where the bridging
filter integrates buried surface area.

For the receptor side the agreement with the literature is complete. Every one of
the five canonical CRBN degron contacts is matched in every seed examined, with
none missing:

| construct position | canonical residue | role |
|---|---|---|
| TRP63 | W380 | tri-tryptophan pocket |
| TRP69 | W386 | tri-tryptophan pocket |
| TRP83 | W400 | tri-tryptophan pocket |
| HIS61 | H378 | glutarimide hydrogen bond |
| PHE85 | F402 | pocket floor |

So CC-885 is placed in the CRBN IMiD pocket correctly and reproducibly. That is
a real positive control passing: the receptor half of the ternary is right.

The degron half is not. Counting PLIP contacts between the glue and the peptide
chain: seed 1 makes **one** (SER7), seeds 2 and 3 make **none**. That is the same
verdict the bridging filter reached on the same seeds by a different route, and
the two methods agreeing makes it very unlikely to be an artefact of either.

The conclusion is specific and worth stating plainly: at tier-1 settings the
model reliably docks the glue into its pocket and does not reliably bring the
degron to it. A scoring stack that read only the receptor-side fingerprint, or
only ipTM, would call these poses correct.

## F4. The predicted degron binds the right protein in the wrong place

This is the most consequential result so far, and the one that most needed
checking before it was believed.

Peptide backbone RMSD to the deposited ternary, superposed on the receptor, at
tier-1 settings:

| Pair | Deposited | Poses | Best | Median | Worst | Within 5 A |
|---|---|---|---|---|---|---|
| GSPT1 / CRBN / CC-885 | 5HXB | 10 | 24.5 A | 29.2 A | 72.2 A | 0 per cent |
| BRD4 BD2 / VHL / MZ1 | 5T35 | 10 | 15.3 A | 19.2 A | 26.8 A | 0 per cent |

**Why this is a real result and not a broken alignment.** An RMSD of 25 angstrom
is exactly what a mis-mapped comparison produces, so the frame was measured
rather than assumed. For GSPT1 the receptor anchor matches **436 backbone atoms
and superposes at 1.75 angstrom**: the predicted CRBN CULT domain sits almost on
top of the crystal one, which is both a good receptor prediction and proof that
the frame is sound. Sixty peptide backbone atoms map correctly through the
138-residue numbering offset. After that superposition the predicted degron's
centroid is **22.2 angstrom** from the crystal degron's. Every recovery record
now carries its own anchor size and anchor RMSD for this reason, so no peptide
RMSD is ever reported without the evidence that its frame was trustworthy.

**What it means.** The model is not failing to find CRBN, and it is not failing
to dock: 14 of 15 seeds put the peptide on the receptor, the glue reaches the
tri-tryptophan pocket perfectly in every seed, and in three seeds the glue even
bridges to the peptide at the 50th to 54th percentile of real interfaces. It is
binding the correct protein, at a confident-looking interface, roughly 22
angstrom from the actual degron site.

That single observation ties together everything above it. The poor convergence
of F2 is seeds choosing different wrong sites. The missing glue-to-degron
contacts of F2b are the degron sitting too far away to be bridged. The high ipTM
of F1 is the model's confidence in an interface that exists in the prediction
and not in the crystal. A pipeline scoring only confidence would have called
this pair a success.

**The caveat, stated as loudly as the result.** These are tier-1 triage
settings: three recycles, one diffusion sample, potentials off, chosen by spec
1.2 to be deliberately cheap. Tier 2 runs the top decile at ten recycles and
twenty-five diffusion samples.

**Revised twice: read F6, then F9.** IKZF1 recovered at 5.4 angstrom and F6
attributed that to its epitope being linear rather than cut from a folded
domain. RBM39 then completed at 6.0 angstrom from a 15-mer cut out of an RRM,
which contradicts that mechanism directly. F9 has what replaced it.

## F6. The 15-mer hypothesis, which later data contradicted

**Superseded by F9. Kept because the reasoning was sound on the evidence then
available, and because what refuted it is the point.**

IKZF1 / CRBN completed and behaves completely unlike the others:

| Pair | Bridge rate | Delta-ipTM | Convergence | Pose RMSD (median) |
|---|---|---|---|---|
| GSPT1 / CRBN | 3/10 | -0.756 | 0.00 | 29.2 A |
| BRD4 BD2 / VHL | 4/10 | -0.101 | 0.00 | 19.2 A |
| BRD4 BD1 / CRBN | 4/5 | +0.002 | 0.00 | 20.4 A |
| **IKZF1 ZF2 / CRBN** | **10/10** | **+0.316** | **0.73** | **5.4 A** |

IKZF1 recovers at 4.99 to 5.40 angstrom across every one of its ten seeds, with
consistent frames (436 anchor atoms at 1.80 to 1.88 angstrom). Every seed puts
the degron in essentially the same place, and that place is the crystal's.

**Why IKZF1 and not the others.** Each benchmark peptide was checked against
the InterPro domain annotation of its own parent protein, asking a single
question: is this 15-mer window inside a folded domain?

| Pair | Window | Inside a folded domain? |
|---|---|---|
| GSPT1 | 430-444 | yes, 15 per cent of a 99-residue domain |
| BRD4 BD2 | 379-393 | yes, 13 per cent of the 112-residue bromodomain |
| BRD4 BD1 | 98-112 | yes, 14 per cent of the bromodomain |
| CSNK1A1 | 33-47 | yes, 6 per cent of the 269-residue kinase domain |
| RBM39 | 261-275 | yes, 19 per cent of the RRM |
| CDK12 | 809-823 | yes, 5 per cent of the 294-residue kinase domain |
| **IKZF1** | **144-158** | **no: a linear or loop epitope** |

The single pair that works is the single pair whose epitope is linear. The six
that fail are each a small slice cut out of a folded domain, and a 15-mer
excised from a domain has no tertiary context, cannot fold, and therefore cannot
reproduce an interface that the intact domain makes. The model docks it
somewhere plausible and confident, roughly 20 angstrom from where the real
contact is.

**So the earlier reading of F4 was too hard on the model.** It is not that
Boltz-2 cannot place a degron: given an actual linear degron it placed one, from
ten independent seeds, within about 5 angstrom.

**And this part did not survive.** The claim that the other six failed
*because* their window was cut from a fold was tested by the next pair to
complete and lost. See F9.

**What follows for the design.** Spec 3.4 builds the peptide library by tiling
15-mers, which is right for degrons, because most E3 substrate recognition is of
short linear motifs, and that is what the discovery arms of this campaign are
made of. It is wrong for the benchmark members whose recognition is
domain-mediated: BRD4's bromodomain binds its PROTAC as a folded domain, and
GSPT1's degron is explicitly described by spec 3.1 as a beta-hairpin *in domain
II*. Those members need the substrate-binding domain submitted whole, which
costs tokens but asks the right question. Recorded as D-NOB-027 and implemented
for the next campaign; the pairs in flight keep their 15-mers and are reported
with this caveat attached.

### F6a. The graded version of this claim does not hold, and that matters

As more pairs completed it became possible to ask whether *how much* of a
domain the window covers predicts *how badly* it recovers. It does not:

| Pair | Pose RMSD | Fraction of its domain | Position within it |
|---|---|---|---|
| GSPT1 | 29.2 A | 0.15 | 0.44, mid-domain |
| BRD4 BD1 | 20.4 A | 0.18 | 0.44, mid-domain |
| BRD4 BD2 | 19.2 A | 0.17 | 0.34 |
| CSNK1A1 | 12.2 A | **0.07** | 0.09, at the domain edge |
| IKZF1 | 5.4 A | linear | n/a |

CSNK1A1 covers the **smallest** fraction of its parent domain of any pair, 7
per cent of a 269-residue kinase domain, and recovers best of all the
domain-embedded substrates. A simple "smaller fragment is worse" story is
therefore wrong.

Something else is suggestive: the two worst pairs both sit dead centre in their
domain (position 0.44) and the best domain-embedded one sits at its edge
(0.09), where a window has fewer severed contacts to miss. That is a plausible
mechanism and it is **not** being claimed here. Four points cannot distinguish
it from chance, and substituting a new correlation for the one that just failed
would be fitting a story to the data twice over.

What survives is the binary distinction, which is the one F6 actually rests on:
the single pair whose epitope is linear recovers at 5.4 A, and every pair whose
epitope is embedded in a fold sits between 12 and 29 A, the best of them more
than twice the worst linear case. That gap is large and consistent. Whether
closing it needs the whole domain is exactly what the corrected campaign tests,
and this failed sub-hypothesis is a reason the test matters more, not less: the
mechanism is less well understood than F6's first write-up implied.

This is also a warning about the discovery arms, which are entirely 15-mers.
Any curated-degron hit whose window falls inside a folded domain is subject to
exactly the same objection, so the domain test above now runs over the whole
peptide library and every peptide carries an `inside_folded_domain` flag.

## F5. The time split cannot be computed on this panel, which is itself worth saying

All seven benchmark depositions predate Boltz-2's training cutoff. They are
canonical, long-published ternaries, which is precisely what makes them good
positive controls and precisely why they cannot estimate prospective
performance: a model trained on the PDB has seen them.

So the time-split layer reports `not_computed` with that reason rather than
quietly presenting the retrospective number as if it were blind. A blind number
needs post-cutoff depositions from `mgtbind_ternary` that this campaign does not
currently run, and adding them is the obvious next extension.

## F3. One of the seven scoring signals has no demonstrated discriminating power

Spec 4 lists seven signals "in descending order of trust". The second,
the lysine reach window, is not a validated predictor: BINMAN attempted the fit
and it failed, reaching AUC 0.4223, 0.4770 and 0.4595 on its three Cb-Cb
boundaries over 369 assayed lysines, with the direction slightly inverted.

The explanation is mechanistic and so unlikely to yield to refitting: the ligand
site is where a substrate is recruited, not where ubiquitin is transferred, and
the E2 that transfers it is not in the construct. NOBBLE therefore reports
lysine geometry as a measurement with an explicit `not_validated` status and
emits no `lysine_reach_fit` score. See D-NOB-024.

This matters for the composite of spec 4.8, which multiplies a weight by exactly
that quantity. The component is kept as a candidate for the weight fit, but its
fitted weight will be published next to these AUCs so nobody reads a non-zero
weight as validation.

## F4a. The contact map shows where the degron went instead

The peptide-to-receptor contact map for GSPT1 / CRBN puts F4 on one picture.
Of the 31 contacts the predicted degron makes with CRBN, almost all are with
receptor residues 26 to 36 (construct numbering), and of the three
tryptophans that form the IMiD pocket only **TRP63 is touched at all**: TRP69
and TRP83 make no contact within 4.5 angstrom and do not appear on the axis.

So the degron has not missed CRBN, and it has not landed at random. It is
packed against the face **next to** the pocket, which is why it looks like a
confident interface to every metric that only asks whether an interface
exists. The glue, meanwhile, sits correctly in the pocket and reproduces all
five canonical contacts, which is how the two can both be true at once.

This map is computed geometrically rather than taken from PLIP, which is a
protein-ligand tool and has nothing to say about where a degron meets a
receptor.

## F9. Bridge formation rate predicts pose recovery, and the construct does not

With six pairs recovered, the hypothesis in F6 can be checked against the one
thing that matters: does being cut from a folded domain actually predict
failure?

| Pair | Bridge rate | Median RMSD | Cut from a fold | Coverage of it |
|---|---|---|---|---|
| GSPT1 / CRBN | 0.30 | 29.2 A | yes | 0.15 |
| BRD4 BD2 / VHL | 0.40 | 19.2 A | yes | 0.17 |
| BRD4 BD1 / CRBN | 0.80 | 20.4 A | yes | 0.18 |
| CSNK1A1 / CRBN | 1.00 | 12.2 A | yes | 0.07 |
| **RBM39 / DCAF15** | **1.00** | **6.0 A** | **yes** | **0.21** |
| IKZF1 / CRBN | 1.00 | 5.4 A | no, linear | n/a |

**F6 is wrong.** RBM39's substrate is a 15-mer cut from an RRM, covering 21 per
cent of it, which is the *most* domain-embedded window in the panel by
coverage. It recovers at 6.0 angstrom, within 0.6 angstrom of the linear
epitope F6 held up as the one case that works. Windows cut from folds span 6.0
to 29.2 angstrom: the category does not separate anything.

**What does separate them is the bridge formation rate**, the fraction of
ternary seeds in which the glue actually buries surface against both the
receptor and the peptide:

- Pearson r = **-0.871**, p = 0.024
- Spearman rho = **-0.880**, p = 0.021
- n = 6

Every pair that bridged in all its seeds recovered within 12.3 angstrom; no
pair that bridged in fewer than half its seeds recovered better than 19.

**Why this is worth more than the hypothesis it replaces.** Pose recovery
requires a deposited crystal structure, so it can only ever be computed for
pairs whose answer is already known. Bridge formation rate requires nothing
but the prediction. If it tracks recovery, it is a usable stand-in for ground
truth on exactly the pairs that have none, which is every pair a discovery
campaign cares about. That is the thing a triage pipeline needs and the thing
spec 4.1 argued for when it made the empirical bridge envelope the primary
signal, though it argued for the percentile rather than the rate.

**What this is not.** Six points, and a correlation noticed after looking at
them rather than predicted before. It is a hypothesis with a p-value attached,
not a validated metric, and the honest next steps are the Sievers arm, which
multiplies the sample by an order of magnitude, and the corrected-construct
campaign, which is now a test of intervention rather than of F6's mechanism:
if giving GSPT1 its whole domain raises its bridge rate, the rate stays the
better predictor and the construct becomes a lever on it.

## F7. The measured throughput is worse than the smoke test implied, as warned

The first throughput figure came from a single 124-token job and read 0.343
seconds per token, which sized the campaign at 271 pairs against spec 1.2's
estimate of 200 to 250. That was published with a caveat that it was measured
on the smallest job and that pairformer cost is superlinear in length.

Measured across 75 completed jobs spanning 124 to 1,223 tokens, the median is
**0.456 seconds per token**, and the campaign sizes at **175 pairs** in the
48-hour budget. The DCAF15 members run at 0.66 to 0.69 seconds per token
individually, roughly double the small-construct rate.

So the real figure is below spec 1.2's own estimate rather than above it, and a
campaign planned on the smoke test would have been oversubscribed by about 55
per cent. This is exactly what spec 1.2 asks for when it says the manifest
generator should size itself from the measured rate rather than the estimate,
and `data/throughput.json` is rewritten on every refresh so the number tracks
the campaign rather than its first job.

## F8. Delta-ipTM is a difference of minima, and on IKZF1 that is the interesting part

Spec 4.3 defines the headline metric as `iptm_min_ternary - iptm_min_binary`:
a difference **of** minima, not the minimum **of** the differences. The two are
not the same statistic and the distinction is not pedantry, because the first
is not bounded by the per-seed values.

IKZF1 / CRBN makes it concrete. Its difference of minima is **+0.316** and its
difference of medians is **+0.136**, which looks impossible until the
components are read:

| | minimum across seeds | median across seeds |
|---|---|---|
| binary | 0.607 | 0.791 |
| ternary | 0.923 | 0.927 |

The ternary arm is almost perfectly stable, 0.923 against a median of 0.927,
while the binary arm has a seed that falls to 0.607 from a median of 0.791. So
the glue does not merely raise the interface confidence: it **removes the
variance**. Every seed agrees about the ternary and the seeds disagree about
the binary.

That is a better description of glue dependence than the headline number
alone, and it is visible only because both statistics are reported. It also
means a large Delta-ipTM can arise from a stabilised ternary as much as from a
raised one, and those are different claims about the chemistry.

The Delta tab now labels the two series as differences of minima and of
medians rather than as "minimum" and "median", which implied they were two
statistics of the same quantity.

## Pending

Remaining benchmark pairs, the Sievers matched-control ROC, lysine reach, PLIP
fingerprints, the time-split blind number and composite weight fitting. The
seed-collapse rate across the whole panel is itself a reportable number: if a
run in five commonly fails to dock, the five-seed budget of spec 1.2 is too
small for a minimum-based statistic, and that is a finding about the method.

## F10. The zinc finger arm does not need its zinc, which is the opposite of what the chemistry says

D-NOB-034 added a `ZN` ion to all 120 whole C2H2 zinc fingers in the Sievers
arm, reasoning from the chemistry: the fold is held together by a Zn(2+)
coordinated by two cysteines and two histidines, so a finger without one is a
disordered 23-mer rather than a domain. That reasoning is standard and it was
written down firmly.

It is wrong about what Boltz-2 actually predicts. Twelve peptide-only folds,
six degraded fingers and six matched controls, each with and without the ion:

| class | mean pLDDT without zinc | mean gain from adding it |
|---|---|---|
| degraded (n=6) | 95.22 | **-0.07** |
| not degraded (n=6) | 92.38 | **+1.40** |

A chain predicted at 95.22 is not disordered. Boltz-2 reproduces the
canonical fold from sequence alone, as AlphaFold2 does, having learned it
from structures that did contain the ion. **The ion is cheap insurance, not a
fix**, and the claim that the arm "would have measured noise without it" is
withdrawn.

The apparent class asymmetry (+1.40 against -0.07) is not one. Gain
correlates with the starting score at **r = -0.704**: the lower a finger
scores without zinc, the more the ion helps, and the controls simply begin
lower. As a group comparison it is +1.47 with a standard error of 0.90,
t = 1.64 at n = 12, against within-class scatter of 1.74 and 1.34. The zinc
tracks headroom, not label, so it cannot bias the ROC toward either class.

**Noted and not acted on.** The degraded fingers fold better than their
matched controls before any zinc is added, 95.22 against 92.38. That largely
cancels in a difference-of-arms statistic, but "the positives were easier to
fold" would look identical to a real result from the AUC alone. It is the
first thing to check if the ROC comes out strong.

## F11. Three ways the design arm would have produced a confident wrong answer

The design arm was built before any of it ran. Three defects were found by
constructing the failure deliberately rather than by waiting for it, and all
three share a shape: they do not crash, they produce a plausible number, and
in two cases the number agrees with what a structural biologist expects.

**1. The scan would have dropped the zinc it was measuring.**
`requires_structural_zinc` infers the cofactor from the sequence, and an
alanine scan mutates residues one at a time. Measured on ZEP2: a 25-position
scan drops the ion at **C3A and C6A**. Those are the coordinating cysteines,
the positions a scan of a finger exists to interrogate. Parent with zinc,
variant without, so the lift subtracts two differently-constituted systems
and reports the missing ion as the substitution's effect. It would have come
out large and negative, read as "this position is critical", and that is
exactly the expected answer, so it would have been believed. Variants now
inherit the parent's cofactor (D-NOB-038).

**2. A substitution of a residue for itself ranked as the most sensitive
position.** Found while building a synthetic fixture, which emitted `A9A`.
Its two runs differ only by seed, so its lift is the noise floor, and nothing
downstream distinguishes that from an effect: it sorts into the ranking like
any other number and came out on top. The real generator never emits one
because a position already alanine is scanned to glycine, but `lift.compute`
now refuses it rather than relying on every future generator remembering.

**3. The chart would not have drawn at all.** The scan profile's script sat
in the template's `content` block, which renders before the page loads
Plotly, so it threw `Plotly is not defined`. Routine QC passed throughout:
with no profile the script returns early and never reaches Plotly, so the
failure was reachable only once a scan had produced data. It was found by
rendering the tab against a synthetic profile rather than waiting 4.9 hours
for a real one.

The general lesson is the one this project keeps relearning. A failure that
stops the pipeline is cheap, because it announces itself. The expensive ones
complete, return a number in the right range, and point the way the prior
already pointed.

## F12. The 15-mers failed because a fragment cannot fold, and the proof was nearly lost to a pair id

F6 proposed that the benchmark's poor pose recovery came from submitting
each substrate as a 15-residue window cut out of a folded domain, rather
than from the model being unable to dock. The corrected campaign tests that
by giving the same substrates their whole domain, with IKZF1 held at its
15-mer as the control (D-NOB-029).

**F6 is supported, provisionally.** Five of seven pairs scored, with the
corrected campaign at 69 of 100 jobs. The conclusion now carries that
qualifier itself rather than leaving it to the table: a verdict over a
partially run campaign is a verdict about whichever pairs happened to
finish, and the conclusion is the line that gets quoted.

| pair | 15-mer | whole domain | change | verdict |
|---|---|---|---|---|
| GSPT1 / CRBN | 29.22 A | **1.17 A** | -28.05 | improved |
| BRD4 / VHL | 19.23 A | **1.71 A** | -17.52 | improved |
| CSNK1A1 / CRBN | 12.24 A | 6.19 A | -6.05 | improved |
| BRD4 / CRBN | 20.40 A | 16.52 A | -3.88 | improved |
| IKZF1 / CRBN (control) | 5.36 A | 5.36 A | **+0.00** | control held |
| CDK12 / DDB1, RBM39 / DCAF15 | | | | not yet run |

Two pairs recovered to under 2 A, which is a correct pose rather than an
improved one. Nothing got worse.

The control is the part that makes the rest usable. IKZF1 keeps its 15-mer
in both campaigns, so its delta is not merely small but exactly zero:
identical input, identical output. That is simultaneously the control
holding and a determinism check on the whole pipeline, and it says the two
campaigns differ in the construct and in nothing else.

**The result was nearly unobtainable, for a reason that had nothing to do
with the science.** `RECOVERY_TARGETS` is keyed on pair ids like
`bench01_GSPT1_CRBN`, and the corrected campaign names the same biology
`corr01_GSPT1_CRBN`. Pose recovery looked up the deposited crystal by the
literal pair id, found nothing, and reported "no predicted pose could be
aligned to a deposited chain". The comparison then returned "not concluded:
the IKZF1 control has no number in both campaigns" and would have returned
that however long the campaign ran.

Every part of that failure was honest. The layer refused rather than
inventing a number, the comparison refused rather than concluding without
its control, and both said why. None of it pointed at the pair id, because
nothing in the system knew the prefix was the problem. The target now
resolves on (gene, E3) as well as the literal id.

It was found by running the comparison early on a partially complete
campaign to see whether a signal was emerging, rather than by waiting for
the chain to run it at the end. The result would otherwise have arrived as
a refusal after 100 jobs.

## F13. A prediction for the two unfinished pairs, recorded before they finish

F12 is provisional on five of seven pairs. The two outstanding ones are the
most informative in the panel, and writing down what F6 predicts for them
now, while the jobs are still queued, makes the result a test rather than a
story told afterwards.

| pair | 15-mer median RMSD | why it is informative |
|---|---|---|
| CDK12 / DDB1 | **44.92 A** | The worst pose in the panel by a wide margin. Its substrate is a 15-mer cut from a kinase domain, so if F6 is right this is where the fragment hypothesis has the most to explain |
| RBM39 / DCAF15 | **6.08 A** | Already the second-best 15-mer pose. Little room to improve, so it tests the other side |

**Predicted, under F6.** CDK12 improves substantially: a 15-mer of a kinase
domain is the clearest case of a fragment that cannot fold, and 44.92 A is
not a near-miss pose but a chain placed somewhere else entirely. RBM39
changes little in either direction, because at 6.08 A the 15-mer was already
roughly right and there is not much for the whole domain to fix.

**What would falsify it.** CDK12 staying above about 20 A would say the
fragment was not the limitation there and something else is wrong with that
pair: the DDB1 construct, the CR8 pocket, or the 6TD3 frame. RBM39 getting
materially worse would say the whole-domain construct can harm a pair that
the 15-mer already handled, which would make the corrected campaign a
trade rather than an improvement and would weaken F12's "none got worse".

Recorded at 71 of 100 jobs, with both pairs unrun.

## F14. The zinc the arm needed to fold was also contaminating its fingerprint

Adding a structural zinc to the Sievers arm (D-NOB-034) put a second het
group into every one of its 120 structures, and PLIP perceives every het
group as a ligand. A finger's interactions CSV therefore carries two:

```
Y70:D:1   SMALLMOLECULE   4 hydrogen bonds, 5 hydrophobic
ZN:C:1    ION             4 metal complexes
```

The fingerprint counted every row. Measured on a real prediction, that gave
10 receptor contacts and an interaction set including `metal complexes: 4`.
Those four are the finger coordinating its own ion: the substrate holding
itself together, not the glue holding the substrate. Spec 4.6 wants the
glue-to-degron half of the bridge, and the arm's headline comparison is
between fingers that a glue degrades and fingers it does not, so putting
each finger's own fold into the measurement is the wrong variable on all
120 pairs.

Filtered to the glue's chain: 6 receptor contacts, hydrophobic and hydrogen
bonds only, with a note naming what was dropped. A zinc-free benchmark job
is unchanged, checked rather than assumed (7 hydrophobic, 4 hydrogen bonds,
no exclusion note).

**A second defect, not yet triggered.** When the chain map cannot be parsed
from cif2plip's output the code falls back to `A/P/L to A/B/C`. That is
correct for a three-chain job and wrong for a four-chain one: with a
cofactor the order is A, P, Z, L, so the glue is D and the fallback would
hand the ligand slot to the zinc, fingerprinting the ion and calling it the
glue. The parse has worked every time so far, including on the zinc
structure, so this has never fired. It now says it cannot be trusted rather
than quietly producing a number.

The general shape is the same as F11: adding something correct for one
reason (the fold needs its ion) changed something unrelated (what PLIP
thinks the ligand is), and the result was a plausible number rather than
an error.

**Every other consumer was then checked, on a real zinc prediction rather
than by reading the source.** Each classifies chains for itself, so
"not receptor, not peptide, not ligand" is only safe where that branch
actually exists. PLIP was the one place it did not.

| consumer | zinc handling | checked on a real structure |
|---|---|---|
| Bridge geometry (spec 4.1, primary) | chain Z skipped | dSASA 730 A2, percentile 46.4, valid two-chain bridge |
| Contact map | chain Z skipped | 23 contacts, no ZN among the residue labels |
| Docking check | chain Z skipped | docked, 56 contact atoms, 197 peptide atoms |
| PLIP fingerprint | **was counting it** | fixed above |
| Pose viewer | rendered invisibly | given spacefill |
| Token budget | 1 token, both arms | preflight reports 0 asymmetric cofactors |

The bridge metric is the one that mattered most: it is spec 4.1's primary
signal, so a zinc quietly entering it would have moved the headline number
on all 120 pairs rather than a secondary one.

## F15. The throughput model is adequate here by luck, not by design

Gate G1 is judged on `projected_hours`, which multiplies one median rate by
a representative token count. Watching the corrected campaign's large jobs
run at 0.749 s/token against a campaign median of 0.455 raised the question
of whether that single number is good enough to gate on.

Measured across all 176 timed jobs, the rate is not monotonic in size:

| tokens | n | median s/token |
|---|---|---|
| <200 | 70 | 0.477 |
| 200-400 | 60 | 0.362 |
| 400-700 | 25 | 0.364 |
| >=700 | 21 | **0.732** |

Two effects pull in opposite directions. Below 200 tokens the fixed cost of
loading the model and setting up is amortised over few tokens, so the rate
per token rises. Above 700 the pairformer's superlinear cost in sequence
length takes over. The flat middle is where neither dominates.

**For the main campaign it does not matter.** Re-projecting with a
size-aware rate gives 53.8 hours against the single-median 51.8: a 4 per
cent difference, against a Gate G1 threshold of 96. The campaign is
dominated by 120 Sievers pairs at 136 to 156 tokens, all in the first
bucket, whose rate of 0.477 sits close to the median of 0.455. The single
number is accurate here because the campaign is nearly one size class, not
because the model is right.

**Left unchanged deliberately.** A size-aware model would be more correct
and would change no decision, while adding a second thing that can be wrong
to the input of a gate. The condition under which it would matter is
recorded instead: a campaign with a wide token spread, or one dominated by
jobs above 700 tokens, would be underestimated by roughly a third. The
corrected campaign is exactly that case, and its 27 remaining jobs project
to 3.6 hours on the observed large-job rate against 2.4 on the median.

## F16. Every failed bridge in the panel fails the same way, and the reason was being discarded

`bridge_percentile` is spec 4.1's primary signal, and `bench07_CDK12_DDB1`
has none: 0 of 10 seeds produced a bridge. The campaign table showed a
blank cell and no reason, because `score_structure` records a
`reject_reason` per seed and the aggregation kept only the count.

Recovered, the reasons are uniform across the whole panel:

| pair | bridged | rejected | reason |
|---|---|---|---|
| GSPT1 / CRBN | 3/10 | 7 | `single_chain:1_qualifying_of_1` |
| BRD4 / VHL | 4/10 | 6 | `single_chain:1_qualifying_of_1` |
| BRD4 / CRBN | 4/5 | 1 | `single_chain:1_qualifying_of_1` |
| CDK12 / DDB1 | **0/10** | 10 | `single_chain:1_qualifying_of_1` |

Not one seed anywhere failed for a weak, small or unbalanced bridge. Every
failure is the same: the glue buried surface against one chain rather than
two.

That is a different claim from "the bridge was poor". A seed that fails
this way has the glue sitting on the receptor with the peptide somewhere
else entirely, so there is no interface to measure rather than a bad one.
It is consistent with CDK12's pose recovery, the worst in the panel at
44.92 A, and it says the failure mode is placement rather than
quality: the model is not building a weak ternary, it is not building a
ternary at all.

The reason now travels to the pair record and into the tooltip on an empty
percentile cell, so an absent primary signal explains itself.

## F17. The whole domain fixes the bridge, not just the RMSD

F16 found that every failed bridge in the benchmark panel failed the same
way: `single_chain`, the glue burying surface against one chain rather than
two, which means the peptide was not where the glue is. F6 says those
substrates failed because a 15-mer cut from a folded domain cannot fold.

If both are right, giving the substrate its whole domain should not merely
improve pose RMSD, it should make the bridges form. It does.

| pair | 15-mer | whole domain | rejections |
|---|---|---|---|
| GSPT1 / CRBN | 3/10 bridged | **10/10** | none |
| BRD4 / VHL | 4/10 | **10/10** | none |
| BRD4 / CRBN | 4/5 | **5/5** | none |
| IKZF1 / CRBN (control) | 10/10 | 10/10 | none |
| CSNK1A1 / CRBN | 10/10 | 10/10 | none |
| RBM39 / DCAF15 | 10/10 | 3/3 so far | none |

**Not one seed in the corrected campaign has failed to bridge.** The pairs
that were losing six and seven seeds out of ten now lose none.

This is independent of F12. Pose recovery compares a prediction to a
deposited crystal; bridge formation asks only whether the glue touches both
chains in the prediction itself, with no crystal involved. The two agree,
and they agree in the way F16 predicts: the failure was placement, and
placing the substrate correctly removes it.

The control is informative here precisely because it cannot move. IKZF1
keeps its 15-mer and was already 10/10, so it has no room to improve and
does not: the change tracks the construct rather than anything that
differs between the two runs.

**Still open.** CDK12 / DDB1 is the case that matters most and has not run:
0 of 10 in the 15-mer campaign, the worst pose in the panel at 44.92 A, and
the subject of the prediction recorded in F13. RBM39 has three of ten
seeds.

## F18. The RBM39 half of the F13 prediction is wrong

F13 recorded, before either pair ran, what F6 predicts for the two
outstanding benchmark members. For RBM39 / DCAF15 it said:

> RBM39 changes little in either direction, because at 6.08 A the 15-mer
> was already roughly right and there is not much for the whole domain to
> fix.

That is wrong. With three of ten seeds scored:

| | n | best | median | worst |
|---|---|---|---|---|
| 15-mer | 10 | 5.462 | **6.085** | 6.446 |
| whole domain | 3 | 0.659 | **0.715** | 0.817 |

The two ranges do not overlap. Every 15-mer seed lands between 5.4 and 6.4
A; every whole-domain seed so far lands below 0.82. The median moves by
-5.37 A, and the whole-domain poses are correct rather than improved.

**The reasoning behind the prediction was the error, not the arithmetic.**
I read 6.08 A as "roughly right, little room to improve". It is not
roughly right: it is a pose that is consistently about six angstrom from
the deposited one, which is a different placement rather than a slightly
imprecise one. The 15-mer's seeds agreeing with each other at 6 A made it
look converged, and convergence on the wrong answer reads like accuracy
unless the deposited structure is in the comparison.

Three seeds is not ten, so the exact median will move. The separation will
not: the distributions are disjoint by more than four angstrom.

The CDK12 half of F13 is still open and is the half the prediction was
confident about.

**Closed, and supported.** The corrected campaign finished 100 of 100 jobs,
and `tools/check_prediction.py` scores the CDK12 half as supported: the
median pose recovery moves 44.921 to 5.278 angstrom, a 39.643 angstrom
improvement, on all ten of the poses the baseline has, with bridge
formation going from 0 of 10 seeds to 6 of 10. The supporting range the
prediction was recorded against is 0 to 20 angstrom, so it lands inside by
a wide margin rather than at the edge.

The panel verdict is therefore one supported and one wrong, out of two
testable predictions. Recorded here because a prediction machinery that
only ever reports support is not a test, and the RBM39 half being wrong by
3.342 angstrom is what makes the CDK12 half worth anything.

## F19. A variant can gain confidence while losing the interface

Rendering the design scan with bridge formation marked produced a case
worth recording before any real scan runs. Among synthetic variants, two
positions came back with a **positive design lift** and **no bridge in any
seed**: Delta-ipTM rose while the glue stopped reaching both chains.

That combination is not a contradiction. Delta-ipTM is the model's
confidence in an interface between two chains; bridge formation asks
whether the glue buries surface against both. A variant whose peptide
drifts away can leave the model confident about whatever contact remains
while the ternary it was asked to build has gone.

The consequence for the arm is concrete. Ranking a scan on lift alone
would list those positions as improvements, and they are the opposite: the
substitution broke the ternary. So the two are reported separately, the
chart outlines bridge-breaking positions rather than recolouring them, and
`scan_profile` lists them under their own key.

This is the same lesson as F16 one level down. There, an absent bridge
percentile hid the difference between a weak interface and no interface.
Here, a healthy-looking lift hides it.

## F20. I read a local timestamp as UTC and killed a healthy job

Worth recording as written, because the reasoning was confident the whole
way down and every step after the first was sound.

`stat -f %Sm` prints local time. `date -u` prints UTC. This machine is on
EST. Comparing one against the other turned a job that had been running
for 13 minutes into one that had been running for 5 hours 13 minutes, and
from there everything followed: 76 seconds of CPU looked like a wedged
process rather than a normal GPU-bound one, `ps` STAT `U` looked like an
uninterruptible Metal deadlock rather than an ordinary moment blocked in a
syscall, and the five sibling jobs at 1,064 seconds each looked like proof
rather than the thing that should have stopped it. The job was 13 minutes
into a 17.7 minute job. I killed it at about 80% done.

The cost was small: one attempt, roughly 14 minutes, no data loss, the
retry picked it straight back up. The reasoning error is the finding.

Two things made it possible. The first is that the elapsed time was
computed by hand, by eye, across two commands with different timezone
conventions, when the campaign already records `started_at` as a Unix
timestamp in `state.jsonl` and could simply have been asked. The second is
that the corroborating evidence was all ambiguous: low CPU, STAT `U` and a
quiet log are equally consistent with a healthy MPS job and a dead one.
Ambiguous evidence agreeing with a hypothesis is not support for it, and
three ambiguous signals are not three pieces of evidence.

The fix is not to be more careful. It is `nobble/execute/watchdog.py`,
which answers "how long has this been running, and is that too long"
from the job's own recorded timestamp, against a bound derived from the
runner's own configuration. A number computed by the machine, in the same
frame, every time.

This is the house rule from CLAUDE.md turned back on the build itself:
BINMAN-LM never computes a number, because a number computed by reading
is a number that can be read wrongly. The rule applies to the person
reading `stat` output at one in the morning too.

### The defect found underneath it

The investigation was wrong and still turned up something real.
`subprocess.run(timeout=...)` handles its own `TimeoutExpired` by sending
SIGKILL and then calling `wait()` with no bound. That is fine for a child
that dies and fatal for one that cannot be reaped: the call never returns,
and a stalled queue is indistinguishable from a working one.

This is not hypothetical and does not need an uninterruptible process to
trigger. A child that leaves a grandchild holding the stdout pipe is
enough, because the cleanup still has to drain it. Boltz spawns worker
processes. The test for it hangs pytest past 45 seconds on the old code
and passes in 7 on the new, so the gap was real even though the stall that
sent me looking for it was not.

## F21. The deployment test stopped covering the newest page, and passed

`tests/test_deployed_app.py` exists for one reason: `/benchmark` and
`/about` once imported the curation stack at request time, passed every
local check and returned 500 in production. It blocks gemmi, pandas and
the rest, then fetches every page.

"Every page" was a tuple written by hand. The design arm added `/design`
and the tuple was not updated, so the one test whose whole job is to
catch a route that dies on the droplet silently stopped looking at the
newest and least-exercised route in the app. Four API routes were
uncovered too. The test went on passing throughout, which is the point:
a stale list produces no symptom.

`/design` turned out to be fine under droplet conditions, so this cost
nothing. It was one import away from costing a production 500 that no
local check would have found.

The list is now derived from `app.url_map`, so coverage grows with the
app, with a `MUST_INCLUDE` floor that fails if a route disappears, which
enumeration alone cannot detect. Both halves were checked by breaking
them: a route importing pandas fails the first, renaming `/design` fails
the second.

Same shape as F20 one layer up. There, a number maintained by hand was
read wrongly. Here, a list maintained by hand went quietly out of date.
Neither announced itself, because neither had anything comparing it to
the thing it described.

## F22. The licensing guard was one hand-written fragment

PROTAC-DB is licensed for internal use and must never be redistributed
(spec 2.1). The guard on that was a 15-character substring of one
compound's SMILES, written into `build_atlas.py` and the deployment test
when dBET57 was the only PROTAC in the panel.

The mechanism itself is sound and was verified end to end. dBET57's
record carries `source: protacdb`, its published `smiles` is null, and
`smiles_withheld` records why, so the redaction demonstrably ran rather
than the field happening to be empty. The live site serves the name
`dBET57` and no structure, which is the right line: the name is published
literature, the curated structure is what PROTAC-DB licenses. Every other
ligand's SMILES comes from the wwPDB Chemical Component Dictionary and
travels freely.

Two weaknesses, both of the F21 kind rather than real leaks.

The guard only knew one compound. It is now derived from the licensed
table itself, so a published string is checked against all 15,502 curated
structures. That matters because the redaction keys on provenance: a
PROTAC that *is* in the CCD, but whose SMILES BINMAN took from PROTAC-DB,
would be recorded as `encoding: ccd` and published. Byte-identity is the
right test for redistribution, since an independently canonicalised
SMILES of the same molecule is wwPDB's string and not theirs.

And a null `smiles` proved nothing on its own, because an absent field
looks identical to a redacted one. The test now requires the note the
redaction leaves behind, so the protection has to have run.

Also removed: the redaction condition read `source in REDACT_WHEN_SOURCE
or (encoding == "smiles" and source in REDACT_WHEN_SOURCE)`, whose second
clause is a subset of the first. It never decided anything while implying
the encoding mattered, which is the opposite of the rule: what makes a
record unpublishable is where the chemistry came from, not how it is
written.

## F23. The prediction scorer returned a verdict on a number still moving

`tools/check_prediction.py` exists so the F13 predictions are scored by
their own thresholds instead of being read and judged, because that
reading is where a prediction quietly becomes a description. It does that
part correctly.

What it did not do was say what the verdict rested on. Run while the
corrected campaign was still going, it printed

    RBM39   WRONG
            measured: 6.085 -> 0.731 A (-5.354), bridged 10/10 -> 3/3

on six of the ten poses the baseline has. The asymmetry was on the face
of the output, 10/10 against 3/3, and carried no weight because nothing
named it. `compare.py` already has a provisional mechanism, but it only
fires when a campaign has no recovery number at all, so a pair at 6 of 10
poses passes through as finished.

Two things were missing, and the second is the one that matters.

The pose counts, so a reader can see the verdict is not yet final. The
rule needs no configuration: both campaigns were built with the same seed
structure, so the complete baseline is the yardstick for whether the
corrected side has filled in.

And the distance to a different answer. "WRONG on 6 of 10 poses" says
little by itself. "WRONG, and the corrected median would have to climb
from 0.731 to 4.085 A to be supported, 3.354 A away" says the verdict is
safe, because four further poses cannot move a median sitting at 0.731 by
three and a half angstrom. The supporting interval is declared next to
the thresholds it comes from, so the margin is computed from F13 rather
than judged afterwards.

F18's verdict is unaffected: that margin is why. It was recorded on
partial data and happens to be robust, which is luck rather than method,
and is exactly what the scorer should have been able to state at the
time.

In the chain this runs last, after the corrected campaign has finished,
so its output there will read `final` rather than `PROVISIONAL`. The
defect only showed because the scorer can be, and was, run by hand
mid-campaign. A tool that is correct only when invoked at the right
moment is a tool that will be invoked at the wrong one.

## F24. The headline curve was safe by accident

Delta-ipTM is a difference of minima, and a minimum is not robust to how
many seeds it was taken over: a minimum of ten draws sits below a minimum
of five for reasons that have nothing to do with the interface.
`aggregate()` already hard partitions by sampling tier for exactly this
reason, and says so. Nothing extended that care to seeds lost *within* a
tier, and `matched_control_roc` never looked at seed counts at all.

Across the two sides of the curve this is bias, not noise. If the
degraded pairs finish more seeds than their matched negatives, their
minima are pulled down relative to the negatives' and the AUC moves, with
nothing in the curve to show it.

The arm is in fact clean. All 120 Sievers pairs carry 10 ternary and 5
binary jobs. The two pairs that do not are `bench03_BRD4_CRBN` and
`scr_bench03_BRD4_CRBN`, at 5 ternary jobs each because their conditioned
arm was dropped for want of a measurable pocket, and both sit outside
this curve: one is benchmark tier, the other scramble.

So the curve is protected, by a scoping rule added for a different reason
entirely. Spec 5.3 scopes it to the Sievers split because benchmark pairs
were chosen for having good co-crystals and would flatter the positive
side. That it also excludes the only two pairs with a different job shape
is luck. A 2,360-job run is expected to lose jobs, by design: the fallback
ladder records a failure and carries on. The first lost ternary job in a
Sievers pair would reintroduce the asymmetry with nothing to catch it.

The curve now reports the seed counts beside the number and names an
imbalance, rather than refusing: one lost job in 2,360 should qualify a
result, not withhold it. There is no threshold, because the comparison is
structural, and the only question is whether a pair on one side was built
like a pair on the other.

Visible in bench03 already: 5 ternary seeds against everyone else's 10,
and a Delta-ipTM of 0.0021. It is not in the curve, but it is in the
benchmark table, where it is the one number not comparable with its
neighbours.

### Two mistakes of mine inside the fix

The first version compared how many pairs held each seed count rather
than the seed counts themselves. The real arm is 24 degraded against 96
matched negatives by design, so that read as an imbalance on every curve.
An existing test caught it, which is the suite doing its job.

The second attached the imbalance caveat to score files that predate the
`seeds_ternary` field, where the counts are absent rather than uneven.
"Cannot be checked" and "checked and found uneven" are different claims,
and a caveat on the first is the sort of blanket qualifier CLAUDE.md
warns reads as a lack of confidence rather than as rigour.

## F25. The recovery numbers never said they were retrospective

Every benchmark deposition is from 2016 to 2020: 5HXB, 5T35, 6BNB, 6H0F,
5FQD, 6Q0W, 6TD3. Boltz-2's training cutoff is 2021-09-30, so all seven
could have been memorised, and none of them estimates prospective
performance.

The `time_split` layer knows this exactly, and says it well. It refuses to
compute and gives the reason: no deposition postdates the cutoff, so there
is no blind set, and the retrospective number must not be read as
prospective performance. That status is in `validation.json` and in the
published atlas.

It was not on the page carrying the numbers. `/benchmark` showed the
recovery correlation and the RMSD table with a hint saying only that
recovery needs a deposited crystal. A reader takes an RMSD on that page
as how well the method predicts, which is the one reading the data does
not support.

One generated sentence now sits beside the figure: "All 7 predate
Boltz-2's 2021-09-30 training cutoff, so this is retrospective." Eleven
words, which keeps `/benchmark` at 105 words of hint prose against the
150 budget.

Generated rather than written, which is the part worth keeping. It reads
the layer, so if a post-cutoff deposition ever joins the panel the line
stops being a caveat and becomes a result: so many of so many postdate
the cutoff, this much blind against that much retrospective. A sentence
typed into the template would have had to be remembered, and would have
gone stale in the direction that flatters.

This is the same failure as F21 and F22 in the other direction. There,
facts maintained by hand went quietly out of date. Here a fact the
pipeline had computed correctly simply never reached the page, which is
the recurring theme at the top of this file: compute whose output nothing
reads is indistinguishable from compute that never ran.

## F26. The number behind "F6 supported" was a literal in Python

CLAUDE.md is unambiguous: thresholds come from `config/thresholds.toml`,
never hard-coded in Python. The rule was kept nearly everywhere, which is
what made the exceptions hard to see. An AST walk over the package found
three.

The one that matters is in `compare.py`. "Improved" and "worse" were
decided by literal `2.0`s, so the cutoff producing the headline sentence
"F6 supported" could not be changed, or even found, without reading the
function. `CONTROL_TOLERANCE_A` sat four lines above it, correctly read
from config, which is how the inconsistency survived: the file looked
compliant.

Worse, the sentence quoted its own cutoff independently. The comparison
used a constant and the wording said "more than 2 A", so changing the
threshold would have produced a conclusion stating the old one. Both now
read the same value.

The other two: `run.py` decided the published `forced` flag on a literal
`0.2`, and `poses.py` called a superposition frame poor above a literal
`5.0`, which qualifies every peptide RMSD measured in that frame. Neither
was reachable from the config that is supposed to hold every cutoff.

Two float comparisons remain and are allowed with their reasons: a `1e-9`
epsilon for identifying which seed held the minimum, and `low > 0.5` for
an AUC, where 0.5 is the definition of chance rather than a choice.
Neither has a value anyone could sensibly tune.

The guard is an AST walk, not a regex, because a float literal inside a
formula is fine and only one being compared against is a cutoff. It also
checks the allowlist still describes code that exists, since an allowlist
outliving what it allowed is just a hole.

### A test of mine that did nothing

The first version of the wording check matched the source with a regex. The
conclusion is built from several f-string fragments, so it matched only the
first and would have passed with "2 A" hard-coded in any later one. It is
now behavioural: change the configured margin, read the sentence back, and
require it to have followed. That version fails on the mutation the first
version missed.

This is the whole theme of this file turned on the tests themselves. F21's
stale tuple, F22's hand-written sentinel and this regex all shared one
property: they passed, and that told nobody anything.

## F27. A weakened bridge read as a clean improvement

F19 recorded that a healthy-looking design lift can hide a broken
ternary: the substitution pushes the peptide away, the model stays
confident about whatever contact remains, and the lift comes out
positive. The fix then flagged outright loss, where the parent bridged in
some seed and the variant bridged in none.

It left the case in between, which is most of the interesting ones. A
parent at 10/10 against a variant at 1/10 is not an outright loss and is
barely different from one, and it carried no flag at all. `bridge_lost`
was `False`, so the scan chart, which outlines only lost bridges, drew it
as an ordinary point. With a positive lift it would be picked as
`least_sensitive`: the arm's headline claim that a position tolerates
substitution, made about a substitution that had taken the ternary apart.

The bridging string was in the table, so the number was on screen. It was
not in the chart anyone reads or in the headline pick, which is the same
shape as F25: computed correctly, carried nowhere useful.

Now reported as a rate change rather than a flag, with `bridge_weakened`
when the variant keeps under half the parent's bridging rate, and a
`bridge_weakening` list kept separate from `bridge_breaking`. Three claims
of decreasing strength rather than two: lost, weakened, held. The chart
outlines weakened points thinly against a lost bridge's heavy outline, so
the lift's own sign stays readable, and the hover says which of the three
it is with the rate change beside it.

The design arm already had the discipline this needed elsewhere. Its
`compute` refuses a lift outright when the variant and parent were scored
over different seed counts, with a comment explaining that a minimum is
not robust to sample count. That is precisely the care F24 found missing
from the headline ROC. The same file had it and the curve did not.

### My own guard had the same blind spot it was written to close

F26 added an AST guard for hard-coded cutoffs. It inspected comparisons
against float literals, and `MINIMUM_SEEDS = 3` sat four lines from the
top of `lift.py` untouched: an integer, bound to a name, never compared
against a literal. A cutoff with a name is the easiest kind to keep in
config and the easiest to forget, because it looks like configuration
already.

Extending the guard to module-level numeric constants turned up four more
genuine cutoffs: how far a numbering anchor may slide, the pLDDT window
width that decides Tier B membership, the fewest ranked pairs before tier
2 runs, and the fewest labelled pairs before a weight fit is attempted.
All four now read from `config/thresholds.toml`.

Five constants are allowed with reasons: a reproducibility seed, lysine's
reference accessible surface area, and the three runtime values governing
retries and how long to wait for a child to die. None is a threshold
applied to data, and the allowlist is itself checked for naming code that
still exists.

## F28. The third blind spot, and where the sweep stops

F26 swept comparisons against float literals. F27 swept module-level
numeric constants, after `MINIMUM_SEEDS = 3` walked through the first
sweep untouched. Neither caught an integer compared inline, which is the
most natural way to write a cutoff in Python, and five were sitting
there.

Two of them decide what the site says about its own numbers.
`len(labelled) < 25` in `weights.py` decides whether the composite is
published as indicative rather than calibrated. `positives < 5` decides
whether the fitted AUC is called a number with very wide bounds rather
than a performance claim. Both are judgements about how far to trust a
result, which is exactly the kind of number that should not be buried in
an expression.

One decides whether the headline curve exists at all: `len(positives) < 3
or len(negatives) < 3` in `matched_control_roc`, the floor below which
spec 5 forbids drawing it. One decides which jobs run: `substrate
["length"] >= 250`, the token-cap exception for a folded domain
(D-NOB-027). One decides whether collapse detection runs at all:
`len(present) < 3` in `metrics.py`.

All five now read from `config/thresholds.toml`.

### Where the sweep deliberately stops

Comparisons against 0 and 1 are not swept. They are emptiness and sign
checks, and twenty-eight of them would need allowlisting to catch
nothing. That is a stated limit of the guard rather than an oversight,
and it is written into the test so the next person does not have to
rediscover why.

Above 1, fifteen comparisons remain and are allowed with their reasons.
Each is a fact about the data rather than a choice about it: a PDB
accession is four characters, C2H2 means two cysteines and two
histidines, three points are the fewest that fix a rigid body, two the
fewest that define a direction, and a pair id is tier, gene and E3.
Writing those reasons out was worth more than the sweep itself, because
each one had been sitting in the code as a bare number that a reader
would have had to reconstruct.

The pattern across F26, F27 and F28 is one guard needing three passes
because each pass only looked where the last failure had been. A sweep
built from a single example checks for that example.

## F29. The model's query was trusted even though the model is not

CLAUDE.md: BINMAN-LM never computes, estimates or reports a number. The
design honours that precisely, and it is the better half of the module.
The model's only output is a query object. The executor runs it in Python
over the scored records. Every sentence the user reads is an f-string
built in `ask`, so the model cannot state a figure even when a figure is
what was asked for. There is a test for that now, by AST, because it is
the kind of property that holds until someone assigns `answer.explanation`
from something the model returned.

The missing half is that a query from a model is untrusted input, and
`validate` treated it as a schema problem rather than a data one. It
checked field names, operators, sort direction and the limit, and never
looked at a filter's value.

A model asked "which pairs have a high delta-ipTM" can reasonably answer
`["delta_iptm", "gt", "high"]`. Every name in that is valid. Python then
raises comparing a float to a string, nothing catches it, and `/api/ask`
returns 500. The same for `None`, a list, a dict, or `True`, and for a
number against a string field. Five shapes, all passing validation, all
reaching the browser as a stack trace rather than as an answer.

The fix is in two layers, because one would have been a claim rather than
a guarantee. `validate` now checks the value against the field's declared
type and says what was wrong in the rejection, which is useful to a model
that will be asked again. And `execute` is wrapped, so a shape nobody
anticipated comes back as a rejection with its reason instead of a 500.
The second layer exists precisely because the first is a list of cases I
thought of.

The types are declared rather than parsed. The field descriptions open
with the type in prose for the model's benefit, and a validator reading
prose would take "the number of seeds" for a number. So `FIELD_TYPES` is
explicit, published through `/api/schema` so the model is told rather than
left to infer, and an assertion at import makes a field added without a
type a failure then and there rather than a 500 on the first question that
filters on it.

Equality is deliberately left alone. `eq` and `ne` cannot raise, since a
float simply is not equal to a string, and rejecting those would turn a
harmless query into an error for no gain.

Same shape as F24: a component that was careful about its own stated
contract and silent about what arrived from outside it.

## F30. The fourth hiding place, and one number answering three questions

The cutoff sweep needed a fourth pass. A default argument is the quietest
place a threshold can sit, because a signature reads as configuration
already: `fraction: float = 0.1` in `tier2.select_top_decile` looked
settled while deciding how much of the campaign's compute the refinement
costs, at twenty-five diffusion samples a job against tier 1's one.

Five defaults were real cutoffs. The decile fraction, in two places plus
an argparse default. `negatives_per_positive = 4`, which sets the
composition of the matched-control curve. `min_atoms = 12`, the floor
below which a heteroatom is a buffer salt rather than a degrader. And
`job_timeout_seconds = 5400`, the number F20 was all about, sitting in a
signature.

The timeout needed care: `config/tuning.toml` is written by
`tools/hwprobe.py`, so a key added there by hand is a key the next
hardware probe silently drops. It went into the generator as well, and a
test checks that it is still written, because the failure mode is a
`tuning.toml` that `settings_from_config` cannot read.

### One default answering three different questions

`structures.contacts_to_ligand(..., cutoff: float = 5.0)` is the worst of
them, and not because of the literal. Three callers used it and meant
three different measurements.

`degron_gate` read `degron_scan_contact_cutoff_a` from config and passed
it. `peptides` passed a bare `5.0` to find the degron centre of a
benchmark member. `yaml_gen` passed a bare `cutoff=5.0` to decide which
receptor residues line a ligand pocket, which is a different question
again from either. So the same number existed four times: the default, two
literals, and a config key only one of the three read. Changing that key
would have moved one measurement and left two behind, which is worse than
a plain literal, because the config made it look handled.

The default is now gone rather than wired up. A shared helper with a
default cutoff gives the same answer to questions that are not the same,
and removing it makes every caller state which one it is asking. The
pocket question got its own key, since its radius and its contact list are
genuinely two numbers.

Thirteen defaults remain, allowed with reasons. Seven name a sampling
tier, which is an identity rather than a threshold. Three are procedure
parameters: a bootstrap's resampling count, its seed, and an embedding
batch size, none of which changes a result. Three are illustrative inputs
to a budget calculator that prints them rather than applying them.

### What the sweep did not find, and tier 2 anyway

Reading `tier2.py` for the fraction turned up something else. The
selection records which key it ranked on, with a good reason given: a top
decile is only interpretable if you know what it was the top decile of. It
did not record which arm each chosen pair came from, so "2 pairs selected"
could mean two negative controls.

The ranking is blind to the arm on purpose, and should stay that way: a
scramble that outranks every candidate is a result, and excluding it would
be the one reliable way to ensure nobody saw it. So the arm is reported,
not filtered, and a note fires when controls are in the decile.

My first version of that note fired when the decile spanned more than one
arm, which is ordinary, and stayed silent on a decile made entirely of
controls, which is the alarming case. Inverted, it now says how many of
the refined pairs are controls and where the budget went.

## F31. The headline metric did not say which interface it meant

Delta-ipTM is the project's headline, and spec 4.3 defines it as
`iptm_min_ternary - iptm_min_binary` with the minimum taken across seeds.
It does not say which chain pair the ipTM is, and for most of the panel
that does not matter: a single-chain receptor has one answer.

`DCAF15_DDB1_DDA1` is five chains. DCAF15 is submitted as two segments, an
N-terminal and a C-terminal domain, behind them DDB1's two beta propellers
and DDA1. The code took chain 0 against the peptide, so the headline for
RBM39 was the ipTM between the N-terminal domain of DCAF15 and the degron,
with DCAF15's other half ignored. Nothing said so. The number was correct
arithmetic over an arbitrary choice.

The real data says the choice was nearly harmless. Peptide against chain 0
is 0.7274 and against chain 1 is 0.7329 on the first binary seed: two
views of one interface split by a domain boundary. Across all 183 scored
jobs, 9 values change, all this pair, by at most 0.0103, and exactly one
Delta-ipTM moves, from +0.1872 to +0.1937.

So this is a finding about the definition rather than the numbers, and
measuring that first is what made it safe to correct rather than a
question for Marc.

Taking the minimum over the substrate receptor's own segments is not a new
rule. This module already takes a minimum across the two directions of
Boltz's asymmetric matrix, and spec 4.3 takes one across seeds, both for
the same stated reason. `score/geometry.py` had already reached the same
conclusion about the receptor, merging its segments because "for a
multi-segment receptor the relevant side is the receptor as a whole".
Geometry treated the receptor as a whole and the headline metric did not.

The scaffolding is excluded, which the data makes obvious. DDB1 sits at
0.66 and DDA1 at 0.69 against the peptide, so a minimum over all five
chains would be a measurement of how well the degron avoids the scaffold.

### The invariant nobody had written down

Either rule depends on the substrate receptor being the construct's first
segment. It is, in all six constructs, and no test said so. Identifying it
by label does not work, because the labels are domain names: `CRBN_CULT`'s
only segment is "CULT domain", carrying no gene. It is identified by
accession instead, and the invariant is now cross-checked against
`yaml_gen.RECEPTOR_CHAINS_BY_PDB`, which was read off the deposited
assemblies, so this is not one piece of code agreeing with itself.

A construct added with its scaffold first would previously have produced a
headline number about an interface that does not exist. Now it fails a
test.

## F32. PLIP failed on an entire campaign, and reported it as a score of zero

Two defects, one on top of the other, and the second is what made the
first invisible.

### The failure

`cif2plip` is invoked with `cwd` set to its own directory so its sibling
imports resolve. That is correct and the comment explains it. The
structure path was passed through as the caller gave it, and the corrected
campaign's records hold relative paths, so every conversion resolved
against cif2plip's own directory and failed:

    FileNotFoundError: unable to open() file
    .../.plip_env/cif2plip/campaigns/corrected_.../outputs/...

All six pairs. The benchmark campaign was run with an absolute campaign
path and succeeded, which is the only reason this had not been noticed:
one campaign's scoring worked and the next one's did not, for a reason
that is nowhere in the campaign.

`tools/run_chain.sh` builds the main campaign's path with
`ls -d campaigns/campaign_*`, which is relative. All 158 pairs would have
failed the same way, after the 52-hour run.

### What made it invisible

`score_campaign` computed the match as `len(canonical_matched) / expected`
without looking at the fingerprint's status. A fingerprint that never ran
has no matches, so five corrected pairs carry

    plip_fingerprint_match: 0.0

A number saying the prediction reproduced none of the canonical degron
contacts, where the truth is that nothing was measured. The module's
header is entirely about refusing rather than returning a plausible
fingerprint: the CONECT gate exists because a dropped bond table yields
"a plausible-looking fingerprint with wrong, sometimes invented,
interactions". The gate worked. The consumer turned its refusal back into
a figure.

And not an idle figure. `plip_fingerprint_match` is one of five weight-fit
candidates, so the fitter would have taken 158 zeros as observations of a
component that had simply not been computed, and the Interactions tab
would have shown zero canonical contacts for every pair in the campaign.

### Both fixed

Paths are resolved before the subprocess sees them, structure and output
directory alike, since both are read by a process running elsewhere.
Verified on the real data: `corr01_GSPT1_CRBN` now returns `ok` with 17
interactions and all five canonical CRBN residues matched, from the same
record whose stored path is relative.

A fingerprint whose status is not `ok` now yields a null with the reason,
and a `plip_fingerprint_match_status` field distinguishes the three cases
that previously all read as a number or an unexplained null: refused,
succeeded, and no canonical pattern exists for that E3.

The stored corrected scores still carry the zeros; `refresh.sh` rescores
that campaign when it finishes, which is where the chain picks it up.

This is the sharpest instance yet of the theme at the top of this file. The
compute failed, the pipeline caught it correctly, and the number that
reached the record said the opposite of what had happened.

### F32, continued: the class rather than the instance

Fixing `plip.fingerprint` closed the live failure. It did not close the
reason it was possible.

Whether a campaign's records hold relative or absolute paths followed
whichever form the caller happened to use. `run_campaign` took the
campaign path as given and derived `output_dir` and `structure` from it, so
the benchmark campaign, started with an absolute path, recorded absolute
paths, and the corrected campaign, started with
`campaigns/corrected_...`, recorded relative ones. Two campaigns in one
project disagreed about what a structure path is, and nothing in either
campaign said which kind it held.

That is the condition under which a consumer can work on one campaign and
fail on the next, which is exactly what happened. `run_campaign` now
resolves the campaign path on entry, so every recorded path is absolute
whatever the caller wrote.

A sweep for other instances found none: the only two subprocess calls in
the package that take a path are cif2plip and Boltz, and Boltz runs with
the project root as its cwd, so relative paths resolve correctly there.
Every other consumer reads the structure in-process. So this was a single
instance of a class with one other member, which is the least comfortable
kind of finding: the sweep that would have caught it had to be built from
it.

## F33. An unmeasurable seed counted as a seed that failed to bridge

A sweep built from F32: where else does a consumer turn a refusal into a
number? One place, and it is latent rather than live, which is the only
reason it reads as a near miss.

`bridge_formation_rate` is bridged over total, and the total counted every
`BridgeScore` the geometry returned. Most reject reasons belong there.
BINMAN's `single_chain:1_qualifying_of_1` means the glue buried surface
against one chain rather than two, which is a finding and the whole of
spec 4.1: CDK12 rejects that way on all ten seeds and the rate of 0.0 is
correct and informative.

Four reasons are not findings. `structure_missing`,
`no_ligand_chain_in_output`, `no_peptide_chain_in_output` and
`binary_complex_has_no_bridge` are assigned in `geometry.score_structure`
before any geometry runs, and say the input was unusable. A pair with four
usable ternaries that all bridged and four whose output carried no ligand
chain would have reported a formation rate of 0.5, when the honest answer
is 1.0 of what could be measured, with four seeds unassessable.

Latent because no campaign has produced any of the four. Every reject
reason recorded to date, 24 of them, is the single_chain verdict. The main
campaign is 1,573 ternary jobs and the fallback ladder is designed to let
individual jobs fail, so the four become reachable there, which is why
this is fixed before the run rather than after it.

The denominator now counts measured seeds only, with
`bridging_seeds_unmeasurable` and its own reason breakdown beside it, and
a pair with nothing measurable reports no rate rather than a rate of zero.
The reject-reason summary describes real negatives and no longer mixes
failures in with them.

The list of failure reasons lives in `geometry.py` next to the code that
assigns them, and a test asserts each one is still assigned there, because
a list of strings in another module drifts the moment a reason is renamed.

The rest of the sweep came back clean, which is worth recording so it is
not re-walked. `bridge_percentile` takes the median over bridged seeds
only and is null when none bridged. Exceptions from the geometry are
already excluded from both numerator and denominator. Only ternary jobs
are passed to the bridge filter at all, so `binary_complex_has_no_bridge`
cannot arise, and it is in the list defensively. `convergence_score` and
the docking counts read through `.get` and come back null rather than
zero.

### F33, continued: the honest denominator needed saying out loud

Making `bridge_formation_rate` count only measurable seeds is the right
number and the wrong display. A pair with four usable ternaries that all
bridged and four whose output carried no ligand chain now reads

    4/4 seeds bridged

which is a perfect rate with half the evidence missing. The fix made the
figure honest and the screen less so, which is the F25 shape arriving from
the opposite direction: not a computed fact that never reached the page,
but a computed fact the page now needed and did not know about.

The count travels to all four places the ratio appears, through one
helper rather than four hand-built concatenations, and is silent when it
is zero, which is every pair so far. A test executes that helper under
node against the cases that matter, rather than pattern-matching the
template, and another refuses a fifth display site that builds the ratio
by hand.

### A test of mine that passed alone and did nothing in the suite

`test_deployed_app`'s droplet fixture deletes `nobble.*` from
`sys.modules` so it can reimport the app with the scientific stack
blocked. Anything running afterwards that does `from nobble.app import
data` binds a *new* module object, while `routes` still holds the old one.
Patching the new one changes nothing the route can see.

Both new display tests passed in isolation and silently stopped asserting
anything in the full suite: the page rendered with no scores at all, so
the string they looked for was absent for a reason unrelated to the thing
under test. Patching through `routes.data` fixes it, and the two earlier
tests that had the same latent shape are now consistent.

Worth recording because it is the fourth time this session a test has
passed while checking nothing, after F21's stale tuple, F22's
hand-written sentinel and F26's regex over a multi-fragment f-string. The
failure modes differ and the symptom does not: green, and silent about it.

## F34. The suite had no test for the rule that defines the headline

Four tests this session passed while checking nothing, each by a
different mechanism, so the fifth time was worth spending on the suite
itself rather than on another feature.

The cheap checks came back clean and are worth recording so they are not
repeated. All 248 test functions carry a real assertion; none asserts a
bare literal; and the full run skips nothing, so every data-dependent
skip condition is currently false and the whole suite is genuinely
exercising.

The useful check was a mutation sweep over the eight highest-consequence
modules. Six mutations were caught: the AUC's chance line, the campaign
comparison's control check, the design arm's condition matching, tier 2's
ranking direction, the weight fit's labelled floor, and the LM's field
validation. Two were not, and one of those was my own mutation being a
no-op, which is its own small lesson about sweeps.

### The real gap

`metrics._minimum` could become `max`, or a median, and the whole suite
passed. Spec 4.3 is explicit:

    Using the minimum across the five seeds in each condition, not the mean.

That sentence defines the project's headline number, and nothing tested
it. Every test that touched Delta-ipTM either stubbed the aggregation or
used seed values where the minimum, median and mean sit close enough
together that any of the three would have passed. The rule was load
bearing and unverified.

The new tests use seeds whose minimum, median, mean and maximum are all
different: 0.10, 0.75, 0.80, 0.60, 0.95. A difference of minima gives
0.20 where a difference of medians would give 0.05, so a wrong
aggregation has nowhere to hide. They also pin that a null seed is
skipped rather than treated as zero, which would otherwise make any pair
with one failed seed look like a total collapse of the interface, and
that one bad seed setting the minimum is flagged as collapsed, which is
the whole reason the minimum is reported with diagnostics beside it.

### The second gap

`geometry.score_structure` could report `found = False` for every
structure and nothing noticed. Everything that consumes a bridge was
tested with the geometry stubbed, including the tests I added for F33, so
the one function that decides whether a bridge exists had no test
exercising its success path.

It now runs for real against a predicted ternary from a pair the campaign
scored as bridging, asserting not only `found` but that the measurements
`found` grants permission to read are actually present: a `found` with
null dSASA would be worse than a rejection. The refusal paths are covered
in the same place, including that a missing structure is refused with its
own reason rather than as an absent bridge, which is what F33 turns on.

Both gaps shared a cause. Stubbing a dependency to test its consumer is
right, and it leaves the dependency untested unless something else
exercises it. Nothing else did.

## F35. Guards nobody had reached

A second mutation sweep, over the modules the first did not cover. Two
mutations were caught: the numbering frame's bounds check, and the design
generator's refusal to emit a substitution of a residue for itself. Five
were not, and they are all the same kind of thing: guards against
conditions no finished campaign has produced, which is why nothing had
ever exercised them.

That is a weaker class of finding than F34, where the rule defining the
headline number was untested. These are defensive. But a 2,360-job run
whose fallback ladder is designed to let individual items fail is exactly
where such conditions arrive, and three of the five turn a failure into a
plausible number rather than an error.

**A ternary arm with no ligand.** `expand_pair` skips the ternary arm when
`ligand is None`. Without that, the ternary job carries no ligand chain,
so it is the binary job with a different label, and Delta-ipTM becomes
ternary minus binary over two runs that differ only by seed: a number near
zero, produced by construction and indistinguishable from a real
measurement of no glue dependence. Reachable whenever ligand resolution
fails, which is a CCD miss with no PROTAC-DB fallback.

**An RMSD over mismatched atom sets.** `_rmsd` refuses when the two atom
lists differ in length. Without that, `zip` truncates to the shorter and
the RMSD is computed over a prefix. That is the exact failure
`recovery_against_crystal`'s own docstring warns about: "getting this
wrong produces a confident RMSD against the wrong residues". Reachable
because the predicted peptide and the deposited chain are matched across
two numbering frames, and a frame that resolves only partially leaves
fewer matched atoms on one side.

**A substitution outside the peptide.** `saturate` raises on a position
past the end, which would otherwise produce a label like K99A against a
15-mer: a variant id no residue backs, ranking in the scan profile like
any other. It raises rather than recording a status, which is right here,
because positions come from the alanine scan's own output and an
out-of-range one is a bug upstream rather than a datum.

The remaining two are left untested deliberately, and saying so is the
point: an empty radii table in `score/lysine.py` and a sequence shorter
than the tile length in `curate/peptides.py` both produce an obvious
absence rather than a confident wrong figure, so a test would be
confirming that Python raises.

Two of my three first attempts at these tests were written against APIs
that do not exist, `Peptide` with the wrong fields and a
`variants.substitute` that was never there. They failed immediately and
loudly, which is the one failure mode this session has had no trouble
with.

## F36. The chain was ready, and nothing could have told me so

With the corrected campaign half an hour from finishing, the chain was
about to run seven stages unattended. A failure at stage three wastes the
night, so I checked it end to end: every script it calls exists and passes
`bash -n`; every Python entry point it names resolves, including
`compare.run` as against `compare.compare`, which are different functions
and the chain uses one while `check_prediction` uses the other; the one
inline Python block's data shape matches what it indexes, down to
`preview.parent.peptide_id`; the deploy prerequisites are all present, key,
known_hosts entry, vendored assets and atlas; and all nine routes the
deploy's final check verifies answer 200 on the live site.

No defect. Which is the finding: nothing in the repository could have told
me that, and checking it took four attempts to get right.

Three of those four failures were mine, and each was the same mistake in a
different costume. I guessed `--campaign` for `nobble.execute.tier2`, which
takes a positional, and read argparse's exit 2 as a defect in the chain. I
built a URL as `https://${PUBLIC_HOST}` when `PUBLIC_HOST` already carries
the scheme, and read nine instant HTTP 000s as a dead site. I used `${!v}`
indirect expansion under zsh and read six unset variables as a broken
`.env`. Every one of those was a confident wrong conclusion from a correct
observation of my own mistake, which is F20 again in miniature, three
times in ten minutes.

So the check is now `tests/test_chain_invocations.py`, which parses the
shell for `-m nobble.<module> <args>` and hands each set of arguments to
that module's own parser, intercepting it once accepted or rejected so
nothing runs. Sixteen invocations across eight scripts, including a guard
that fails if the chain ever stops using `-m nobble.…` and the file would
otherwise pass by finding nothing to check.

The reason this class deserves a test rather than a careful read: the
invocations live in shell strings, so no import, no linter and no type
checker sees them. `tier2.sh` passing a positional where `tier2.py` grew a
named flag would be invisible until the stage started, and the mutation
confirms it is now caught at once.

## F37. The app's cache could have served numbers the pipeline had replaced

A third mutation sweep, over the modules the first two did not reach.
Two caught, five not. Two of the five matter.

`app/data._cached` keys on (key, path, mtime) so a live campaign refreshes
without a restart. Dropping the mtime comparison, so any cached entry is
reused regardless, left the whole suite passing.

The timing is what makes it serious. `refresh.sh` rewrites
`scores.jsonl` in place after a campaign, and the chain calls it twice:
once after the main run and again at the end with tier 2 and the design
scan folded in. A cache that ignored mtime would serve the first version
for the life of the gunicorn process, so the site would show numbers the
pipeline had already replaced, with nothing anywhere saying so. Not stale
in a way anyone could see: the page would render, every figure would look
plausible, and the campaign would have moved on.

The docstring already records a previous bug in the same function, where
the entry was stored under the bare name so two campaigns sharing an mtime
returned each other's rows. That is now pinned too, alongside a test that
the cache is still a cache, because a test for freshness alone passes on a
function that never caches at all.

`degron_gate.check` prefers the glycine packing closest to the glue, both
reference degrons being glycine degrons, and falls back to the closest
contact of any kind so the test stays meaningful for another degron class.
That note is the only record the fallback was taken, and it could be
dropped with the suite still passing: the recurring shape here, a fallback
taken and not recorded.

Also removed: `return loader(path) if False else (...)`, whose first
branch can never run, in the same function.

### Two of my own mistakes, both the same one

I read "42 references to decisions that are not defined" off my own
checker and nearly wrote it up. `DECISIONS.md` lists D-NOB-001 to 042 as
table rows and the rest as `##` headings; my regex knew only the second
form. All 44 are defined, numbered 1 to 44 with no gaps. What the check did
find was that my two appended entries used `## D-NOB-043. Capitalised`
where the file's convention is `## D-NOB-008: lowercase`, now aligned.

And the mutation script restores with `git checkout --`, which discards
uncommitted work on the files it touches. I had noted that before starting
it and then edited `app/data.py` while it ran, so the dead-branch removal
was silently reverted. Caught by grepping for it afterwards rather than by
assuming the edit held.

## F38. A gate counted the wrong severity, and the data hid it

The last three uncaught mutations from the third sweep, all in the same
shape: logic whose right and wrong answers coincide on the data it
currently runs on.

Four places compute the same pair of sums over a validation run:

    "errors":   sum(1 for issue in issues if issue.severity == "error")
    "warnings": sum(1 for issue in issues if issue.severity == "warning")

`errors` is a gate. `design/assemble.py` and `execute/campaign.py` both
refuse to emit a campaign when it is non-zero, which is the right
behaviour and the reason the count matters more than it looks.

Swapping the two severities in the design manifest went unnoticed because
that manifest carries no issues at all, and the existing assertion is
`errors == 0`, which holds either way when both are zero. The same swap in
the campaign manifest is the opposite kind of wrong: that manifest carries
20 warnings and no errors, all of them "no CCD match: encoded as SMILES
and flagged", so the swap would have made `errors` read 20 and refused a
perfectly good 2,360-job campaign outright. One swap, two failure modes,
in opposite directions, depending only on which manifest it lands in.

Both are now pinned by injecting a known mix, two errors and three
warnings, and requiring each count on its own key. The gate itself is
pinned separately, because a correct count feeding a removed gate is no
better.

The design manifest's one-parent invariant is pinned too. The campaign
writer builds the parent's peptide from its library row and carries its
cofactor across, and builds each variant from the pair itself; conflating
the two would drop a zinc finger's zinc, which D-NOB-034 says invalidates
Delta-ipTM outright. The writer itself is left uncalled on purpose: it
creates `campaigns/design_<stamp>`, and the chain selects its design
campaign with `ls -d campaigns/design_*`, so a test that wrote one could
hand the chain a scan nobody asked for.

And the scramble ordering, which keeps each negative control immediately
behind its positive so a truncated queue cannot separate them. Checked
against the library manifest the pipeline actually wrote rather than by
calling `reduce_library`, which loads an ESM checkpoint: a unit test
should not need a language model to verify a sort order. My first version
did, and took ten seconds to tell me so.

## F39. Three spec requirements with nothing behind them

A fourth mutation sweep, over `execute/yaml_gen.py`, which builds the YAML
Boltz actually runs. Two mutations were caught, both by `test_zinc.py`:
the structural cofactor disappearing, and the ligand leaking into the
binary arm. Three were not, and they are the most consequential gaps any
of the four sweeps has found.

**The receptor's cached MSA.** Replacing the cached-path lookup with
`empty` for every receptor chain left the whole suite passing. Spec 1.3 is
the reason the MSAs exist: one per trimmed construct, generated offline
before the campaign, referenced in every YAML, never fetched during a run.
Dropping them would fold every receptor without an alignment. Nothing
would raise, no manifest would record it, and the only symptom would be
2,360 predictions quietly worse than the ones the spec describes. This is
the single worst thing the sweeps could have found, and it was found by
asking rather than by anything going wrong.

**The peptide's MSA.** Spec 1.3 states the opposite requirement for
peptide chains: they get none. Giving the peptide an alignment changes
every prediction in the other direction, and again silently.

So the same file held both halves of one policy and neither was tested:
the receptor must have its MSA, the peptide must not.

**The affinity cap.** Boltz-2 caps the affinity head at 128 heavy atoms,
and spec 4.7 with D-NOB-005 says affinity is recorded for the
small-molecule chain only and never for a ligand over the cap. Requesting
it regardless went unnoticed. `ligands.by_ccd` computes
`affinity_available` against the configured cap correctly; nothing
checked that `build_yaml` honours the flag it is given.

All three are now pinned, including that an uncached receptor falls back
to `empty` rather than to a path that does not resolve, since Boltz would
fail the job rather than fold without, and that the affinity property
names the ligand chain and never the peptide.

The pattern across all four sweeps is consistent enough to state plainly.
What goes untested is not the complicated code. It is the code whose
correct and incorrect behaviours produce the same observable result on the
data at hand: a count that is zero either way, a minimum that equals the
median, a guard for a condition that has not yet arisen, an MSA whose
absence makes predictions worse rather than absent.

## F40. An alignment for the wrong protein would have passed every check

F39 showed that losing the receptor's MSA degrades every prediction
silently. This is the other half, and the worse one.

The cache is content-addressed: `sequence_key` is a SHA1 of the sequence,
so a file's *name* matches its sequence by construction. Its *contents*
are written by a separate step, `tools/run_msa.sh`, and nothing anywhere
checked that the alignment inside a given file is the alignment of the
sequence it is filed under.

Preflight already checked three things, and checked them well: the
peptide carries no MSA, every receptor chain has one, and the file the
YAML names is actually on disk. All three pass for an a3m that exists, is
non-empty, is correctly named, and holds another protein's alignment. That
job does not fail. It folds, confidently, against the wrong evolutionary
signal, and every number downstream inherits it.

The live cache is correct. Seventeen files, every query line matching its
key, none empty or truncated, and all eleven sequences the constructs need
usably present. Six files are left over from construct definitions that
have since changed, which costs disk and nothing else.

Preflight now compares each receptor chain's alignment query against the
chain's own sequence, gaps and insertions stripped, cached by path because
a 2,360-job campaign references the same eleven alignments repeatedly and
some run to thirty thousand lines. It still reports `ok: true` on all
2,360 jobs, so the check was added without moving anything.

### I tested the helper and not the wiring

The first mutation I tried was removing the call from preflight's own
loop. Seven tests passed. Every one of them exercised
`_msa_query_mismatch` directly, so a correct helper that nobody calls
satisfied all of them.

That is F32's shape exactly: a value computed correctly and carried
nowhere. I had written the finding for it four hours earlier and then
reproduced it in my own tests. The fix is two tests that run `preflight`
itself over a synthetic campaign, one whose alignment is wrong and one
whose alignment is right, so the second cannot be satisfied by preflight
rejecting everything.

A same-length substitution is covered separately, because a length
comparison alone would miss a different protein of exactly the same size,
which is the one case where the error message has to say something other
than a count.

## F41. A construct boundary chosen by someone else's list order

CLAUDE.md: construct boundaries come from InterPro named entries, never
hardcoded ranges. The lookup did exactly that, and then resolved a
question the lookup cannot answer on its own.

FEM1B carries IPR036770, the ankyrin repeat superfamily, twice: residues
5 to 301, and again 424 to 610. `domain_by_accession` returned whichever
record InterPro listed first. So "the ankyrin domain of FEM1B" meant 297
residues or 187 residues depending on an ordering nobody in this project
controls, and had that ordering changed, the construct would have become a
different region of the protein with nothing failing. No error, no
warning: a ligase folded against the wrong half of itself, and a Tier B
arm built on it.

Of the twelve construct segments, FEM1B's is the only ambiguous one today.
Three other proteins carry repeated entries that no construct uses: DDB1's
three beta propellers share one CATH superfamily, KEAP1 has six Kelch
repeats and FEM1B eight ankyrin repeats under their own accessions. Any of
those becoming a construct boundary would have inherited the same
behaviour.

The resolution it happened to produce was the right one. The segment is
labelled "Ankyrin repeats, N-terminal region" and 5-301 is the N-terminal
region, so the construct was correct and correct by accident of ordering.

Now `domains()` returns records sorted by position, so an occurrence index
means something stable, and `domain_by_accession` raises `AmbiguousEntry`
naming both ranges unless the caller says which it means. FEM1B's segment
declares occurrence 0 with the reason beside it. Every construct resolves
to exactly the range it did before: nothing moved, the choice is simply
now written down.

### The reasoning was already in the file, one level down

`domains()` takes a multi-fragment location's extent with `min` and `max`
rather than first and last, and the comment says why: "Relying on that
would be relying on an undocumented property of someone else's API, and
getting it wrong moves a construct boundary without anything failing."
That is this finding, stated exactly, about fragments within a location.
It had not been applied to which location among several.

Which is the most useful thing here. The hazard was understood, written
down, and fixed at one level by someone who did not notice the same shape
one level up. A sweep built from the comment would have found it; reading
the comment and agreeing with it did not.

## F42. Two more choices taken by list order, on invariants that held

A sweep for F41's shape: a choice resolved by the order of a collection,
correct only while an invariant nobody checks continues to hold. Most
candidates were benign, `structure[0]` being gemmi's first model and
`parts[0]` a split. One looked promising and was clean, which is worth
recording: `degron_gate` takes `(glycines or contacts)[0]` and its comment
says the glycine that packs closest to the glue, and
`contacts_to_ligand` does return its hits sorted by distance, so the code
does what the comment says.

Two were real.

**`metrics.aggregate`** reads a pair's construct, peptide id, gene,
sequence, label, modality, tier, parent, substitution, position and role
off `pair_jobs[0]`, on the understanding that these describe the pair
rather than the job. They do. The telling part is that `ligand_key` is
already taken differently, from the first job that has one, because the
binary arm has none. So one field was known to vary and the other twelve
were taken on trust.

A disagreement there means the manifest emitted jobs for two different
things under one pair id, and the pair would be reported as whichever job
was read first. The worst of the twelve is `peptide_label`: a pair half
degraded and half not would land on whichever side of the matched-control
curve it happened to be read into. It is now recorded as a note and a
field rather than raised, because scoring a finished campaign is not the
place to refuse, and a pair carrying that note is one nobody should read.

**`assemble.build_manifest`** derives one pocket for a whole design scan
from `pairs[0]`'s ligand, with a comment saying every pair shares the
parent's receptor and glue by construction. True, and unchecked, so a
variant routed to a different glue would have been handed the parent's
pocket. Now a precondition at the top of `assemble`, before any work,
since there is nothing to assemble if it fails.

Both campaigns are clean: 14 pairs, no disagreement on any of the twelve
fields. As with F41, this is a correctness that was never wrong, only
unverified.

### What the exclusions are for

The check had to be told which fields vary by design. `complex_type`,
`conditioning`, `seed` and `job_id` differ across a pair's jobs by
construction, and `ligand_key` is absent from the binary arm. A check that
flagged those would fire on every pair in every campaign, which is the
failure mode of a caveat that is always on: it would have been switched
off within a day. There is a test that those five stay out of the set.

## F43. Fields I added this session were absent from most records

The schema-guarantee block in `score_campaign` carries its own history:

    A pair whose PLIP or geometry has not run yet must still carry every
    key, as null, rather than omitting it: a consumer that reaches for a
    missing key gets an error instead of a "not computed", and the app's
    Benchmark tab did exactly that on the first pair whose ternary arm had
    not finished.

It is right, it is maintained by hand, and it goes out of date exactly
when something new is added. Three of the fields this session added were
set only on the branch that computes them.

`bridging_unmeasurable_reasons`, from F33, was written only when there
were unmeasurable seeds, which is no pair in either campaign. So the key
was absent from every healthy record, and the one state it describes is
the state in which it appears.

`plip_fingerprint_match_status`, from F32, was written only when PLIP ran.
`--no-plip` is a real path and `refresh.sh` can take it, so a campaign
scored that way produced records with no status at all: a consumer asking
why the fingerprint was missing got a `KeyError` rather than an answer.
That is the same failure the block's own comment describes, reintroduced
four hours after I read it.

Both now come with a reason rather than a null. A pair scored without PLIP
says "plip was not run for this campaign", which is a different thing from
a fingerprint that failed and from one that was refused, and all three had
collapsed into an absent key.

The third was my own misreading. `iptm_receptor_chains` looked absent from
every pair, and it is a seed-record field, present in every seed record.
Checking the right level took one command and I had already written the
finding in my head.

The test derives the key set from the records rather than restating it,
and requires it to be the same whichever branches ran. A field added on
one branch now fails there instead of on the first consumer that reaches
for it. The two entries added to the hand-maintained list are a floor, not
the fix: both fields are set on every path now, so removing those entries
changes nothing today and catches the next branch that forgets.

### The test cost 112 seconds and now costs 10

The first version scored three full campaigns for real, geometry and PLIP
included, which added 112 seconds to a 28-second suite. The file is about
which keys a record carries and nothing else, so both stages are stubbed
and the campaign trimmed to three pairs. A slow test is a test that gets
skipped, which is the one way to make a schema guarantee worse than none.

## F44. CDK12 needs the pocket constraint to find its own glue site

The first finding of this session that is about the science rather than
the code, and the machinery surfaced it without being asked.

CDK12 with CR8 on DDB1, folded kinase domain, eight of ten ternary seeds
scored:

    conditioned     0.826  0.745  0.779  0.767  0.851
    unconstrained   0.252  0.281  0.653
    binary minimum  0.273

Delta-ipTM, the mandated difference of minima, is **-0.022**. The same
quantity built on medians is **+0.449**. Those are not a disagreement about
precision; they are two different answers, and both are correct readings of
the same eight numbers.

What separates them is the conditioning. Given the pocket, the model is
confident about the ternary every time, 0.745 to 0.851. Made to find the
glue site unaided, it mostly fails: two seeds at 0.25 and 0.28, one at
0.65. `conditioning_disagreement` is 0.494, so the `forced` flag is true
and true by a wide margin.

The honest reading is that the glue's placement is doing the work rather
than the prediction, and the headline number says so correctly for an
uncomfortable reason: the mandated minimum lands on a collapsed
unconstrained seed at 0.2515, which is *below* the binary minimum of
0.2732, so the ternary looks no better than the binary.

Every part of that is flagged rather than inferred.
`collapsed_seeds_ternary` is `[1, 2]`, `seed_collapse_affects_delta` is
true, and the pair carries the note "seed(s) [1, 2] collapsed well below
the median of their condition and set the mandated min". D-NOB-023 added
those diagnostics precisely so a minimum set by a collapse would not read
as a measurement of the interface, and here they earn their place on the
project's most-watched pair.

Provisional: two unconstrained seeds are still running. The minimum can
only fall, so Delta-ipTM can only become more negative and the direction
of this is settled.

What it means for F6 is not settled and is not mine to decide. The
question F6 asks is whether the whole domain recovers poses the 15-mer
could not, which is an RMSD question, and the comparison the chain runs
next answers it. This is a separate observation about the same pair, and
one the Delta-ipTM headline alone would have reported as "no glue
dependence".

### The flag said forced and not how forced

`forced` was on the campaign table with the tooltip "Pose appears only
under pocket conditioning", which is true of CDK12 at 0.494 and equally
true of a pair at 0.21. The tooltip now carries the magnitude. A tooltip
is pipeline-generated status text and outside the prose budget, which is
the right place for a number that qualifies a flag rather than a figure.

## F45. A false Gate G1, which would have stopped the build

The corrected campaign finished, the chain started, and throughput was
remeasured on it. A budget test began failing, and the number behind the
failure was `projected_hours(158) = 104.3 hours` against a Gate G1
threshold of 96. Gate G1 open means stop and ask Marc. The run that had
just started was the 2,360-job main campaign.

It was wrong. The gate is not open.

`projected_hours` multiplied the job count by a "representative job":
the median rate times the median token count of whichever campaign was
measured last. The per-token rate transfers between campaigns. The job
size does not. Throughput came from the corrected campaign, whose median
job is 397 tokens, and was applied to the main campaign, whose median job
is 124. That is a factor of three in job size and a factor of 2.4 in the
answer.

Measured properly, by summing the campaign's real tokens at the rate
observed for jobs of each size:

    0-200 tokens    2,270 jobs   0.4768 s/token
    200-500 tokens      60 jobs   0.3600 s/token
    800+ tokens         30 jobs   0.7488 s/token
                     --------
                       54.0 hours

Over the 48-hour per-run target by six hours, which is a scheduling fact
the priority ordering absorbs, and 42 hours clear of the gate. The
campaign's first jobs are now running at 0.2629 s/token, better than the
0.4768 I used, so 54 hours is an overestimate.

`projected_hours` now takes the campaign's token total and uses it when
given. Without it, it still falls back to the old method and says so in a
new `basis` field: "2370 jobs at 158.5 s for a 397-token job, which is the
median job of corrected_20261103T214331Z and not necessarily of the
campaign being sized". `status.sh` and the design report both pass real
tokens now, since both already had them to hand.

A false gate is the most expensive thing this function can do. CLAUDE.md
says stop only at a Gate; a gate that opens on a correct campaign stops
an unattended build for nothing, and it would have done so on the run the
whole project is for.

### The test that found it was coupled to a measurement

`test_gate_g1_is_judged_against_max_compute_not_the_run_target` asserted
the status of `projected_hours(167)` against whatever throughput file was
on disk. It passed for as long as that came from the benchmark campaign
and failed the moment the chain remeasured. The failure was correct and
the test was wrong to depend on it: it now injects a known measurement, so
it asserts the logic it is named for. Two further tests cover the defect
itself and the basis string.

### And my own sweep left a mutation in the tree

I stopped the fifth mutation sweep because the campaign was minutes from
finishing and I did not want source files flickering as the chain started.
Stopping it killed the script between writing a mutation and the `finally`
that restores it, leaving `curate/library.py` with its selection replaced
by every candidate.

Caught by checking `git status` immediately rather than assuming the
`finally` had run, and the library manifest was verified untouched: 158
rows, yesterday's mtime. The lesson is the obvious one in hindsight. A
tool that mutates tracked files is safe only while it completes, and
"stop it before the risky window" has a risky window of its own.

## F46. The frozen curation, and two checks of mine that checked nothing

The fifth sweep caught one of five. All four misses are curation code, and
all four decide which pairs enter a campaign: the mandatory Tier A
ligases, Tier B's pocket-druggability floor, the pLDDT profile's choice of
atoms, and whether the diversity reduction's selection is used at all.

They are unexercised for a defensible reason. The selection is frozen and
committed, so nothing reruns the code that produced it, and rerunning it
in a test would need an ESM checkpoint and BINMAN's triage table. The
consequence is that the rules behind the campaign's composition have no
test, so a future rerun could produce a different library with nothing to
say so.

So the artefacts are now checked against the rules. The worst of the four
misses is the clearest: with the reduction's selection ignored,
`library.jsonl` would hold all 25,519 candidates rather than 158, and the
campaign would be 383,000 jobs instead of 2,360. The manifest must equal
its own recorded selection, the reduction must have reduced, every
mandatory source must have survived it, and being over budget must be
recorded rather than absorbed, which it is: 158 against a budget of 156,
with a note saying the controls are not trimmed to hit a number.

### The pLDDT floor is not applied to the column named after it

My first version of the Tier B test asserted the floor against
`mean_plddt` and reported seven of fifteen frozen ligases below it. The
criterion is `best_window_mean_plddt`, where all fifteen sit between 85.8
and 98.1. `mean_plddt` is the whole-model mean, 66.8 to 90.5, and
deliberately not the criterion: a whole-model mean punishes a protein with
one tight domain and long disordered linkers, which is the shape Tier B
exists to find.

Both columns are in the table and the threshold is called
`mean_plddt_min`, which is what invited it. The distinction is now pinned
from both sides, so a selection that switched to the whole-model mean
fails rather than quietly rejecting half the tier.

### A reproducibility canary, and a test that was serving the wrong campaign

Every campaign runs the benchmark panel first, with the same constructs,
peptides, ligands and seeds. Boltz is deterministic, so a job id in two
campaigns must carry the same numbers in both: the main campaign's first
nine shared jobs reproduced the benchmark campaign's to every recorded
decimal. That overlap is now a test, and it is a canary for the whole
input path. A moved construct boundary (F41), a lost cached MSA (F39), a
dropped structural zinc, a pocket constraint on an unconstrained arm:
none of those raise, and every one changes the prediction for a job whose
id did not change.

Checking the app against today's scoring schema turned up something
smaller and more embarrassing. `create_app` calls `data.configure(campaign)`
itself, so a `configure()` before it is silently undone and the app falls
back to `NOBBLE_CAMPAIGN`. Two tests I wrote earlier today did exactly
that, and were working through the environment variable while appearing to
work through the configure call. Both now pass the campaign to
`create_app`, and I proved it by pointing the environment variable at a
nonexistent path: they still pass, where before they would have served
whatever that resolved to.

All fourteen routes render today's schema against today's records, which
was the thing worth knowing: the chain rebuilds the atlas from this
scoring code in about thirty-seven hours.

## F47. Every BRD4/VHL job was submitted with a hydroxyproline it does not have

The reproducibility canary added an hour earlier found this on its first
real use, which is the best argument for it.

`bench02_BRD4_VHL__binary__unconstrained__seed1` scored 0.8855 in the
benchmark campaign and 0.8807 in the main one. Same job id, same seed,
same model. Diffing the two YAMLs gave one difference, three lines:

    modifications:
    - position: 1
      ccd: HYP

Position 1 is BRD4 Pro379. HYP is hydroxyproline.

Spec 2.3 keys its table on the degron class, and says so: "Any peptide
whose **degron class** requires a modification and which is submitted
without one is a manifest error." The class in the table is "VHL /
HIF-1alpha". `annotate_required_modifications` keyed on the E3 instead,
matching any peptide whose `e3_hint` contained VHL, BTRC or FBXW7.

That is a different rule and a wrong one. VHL reads HIF-1alpha through a
prolyl hydroxyl installed by the PHD enzymes, and a PROTAC supplies that
hydroxyproline from its own ligand: bench02's degrader is MZ1, whose VHL
end is VH032, which carries a (2S,4R)-4-hydroxyproline that occupies the
pocket. The substrate contributes none. BRD4 Pro379 is not a hydroxylation
site, and nothing in an MZ1 ternary would read it if it were.

So every BRD4/VHL job in the main campaign went to Boltz with a residue
that does not exist in biology. And the rule has never once fired on the
class it was written for: the library contains no HIF-like, DSGxxS or CPD
degron at all, so its only effect in this project has been the
misapplication.

### Fixing the rule was not enough

`yaml_gen` reads `required_modification` off the peptide record, and the
record comes from the frozen library manifest. The rule writes the
manifest and the manifest writes the YAML, so a corrected rule with a
stale manifest regenerates the same wrong YAML. The field was re-derived
with the fixed rule: one peptide changed, from HYP to none, with the
reason recorded on the row. 158 rows, selection untouched, since
`required_modification` does not enter the diversity reduction.

### Why the campaign was left alone

Four of the pair's fifteen jobs had already run when this was found, and
eleven had not. Correcting the YAMLs in place would have given the eleven
the corrected input and left the four with the old result, so one pair
would hold two different inputs and its two arms would be measured against
different molecules. Uniformly wrong is recoverable; half-and-half is not.

So `tools/rerun_pair.py` corrects and clears a pair as a separate step, to
run when the GPU is free and before the final atlas rebuild. It takes the
corrected YAML from a campaign that already holds a known-good copy of the
same job rather than re-deriving, because re-deriving means calling
`assemble_campaign`, which writes a new `campaigns/campaign_<stamp>`
directory, and both the chain and `status.sh` pick their campaign with
`ls -d campaigns/campaign_* | tail -1`. A scratch assembly would silently
become the campaign the rest of the chain targets. It requires exactly one
known-good source, because two that disagree cannot both be the reference
and taking the first is how F41 and F42 happened.

All fifteen resolve to the benchmark campaign's copies, and the diff is
the three lines above and nothing else.

### The canary now carries a named expected failure

A permanently red suite trains you to ignore it, which is F42's lesson
about always-on caveats. The fifteen job ids are listed with the reason
and the command that clears them, so the canary still catches new drift,
and a second test fails once they agree again: an allowlist that outlives
what it allows is a hole, and that test is the only reminder that the
rerun is done.

## F48. The forced flag was computed, published, displayed, and ignored

F47 was found by reading one line of the spec against the code that
implements it, so I read the rest. Spec 4.7:

    A pose that only appears under conditioning is flagged `forced: true`.
    Forcing a binder into a site it did not choose reliably produces the
    right neighbourhood and the wrong pose, so forced hits are shown
    separately and never in the headline ranking.

The flag is computed correctly, carried into every scored record and shown
on the campaign table. Nothing acted on either half of the instruction.

**Never in the headline ranking.** `tier2.select_top_decile` ranks on the
composite, or the bridge percentile, or the median Delta-ipTM, and takes
the top tenth for refinement at twenty-five diffusion samples a job. A
forced pair could take a place there, so the most expensive thing the
pipeline does could be spent refining a pose the spec says is wrong.

CDK12 is the live case and the reason this is not hypothetical. Its
conditioned seeds sit at 0.745 to 0.851 and its unconstrained at 0.252 to
0.653: a disagreement of 0.494, forced by a wide margin (F44).

Forced pairs are now ranked separately rather than dropped, and the
selection records which of them would have entered the decile. A forced
pair that outranks every candidate is a finding, and the rule is the same
one the arm reporting follows: report it, do not let it vote. If every
scorable pair is forced the decile is empty and says so, rather than
refining a forced pose because it was the only candidate left.

**Shown separately.** The headline scatter drew forced pairs exactly like
found ones. They are now hollow: the position still carries the
measurement, and the marker says not to read it as a pose the model chose.
The hover names it with the magnitude rather than a bare flag, because
"forced" is true of CDK12 at 0.494 and equally true of a pair at 0.21.

Three rules of the spec read against the code, and this is the one that
had drifted. The other two had not. Spec 3.1's prohibition on applying a
disorder prefilter to linear degron mimetics is satisfied vacuously: no
such prefilter exists, ESMFold is not used for it, and no peptide is
rejected on pLDDT anywhere, the `mean_plddt_min` floor being a Tier B
receptor threshold. Spec 4.7's affinity rule, a column and never a ranking
key, was already held by D-NOB-005 and by a test.

## F49. Reading the rest of the spec against the code

F47 and F48 both came from comparing one line of the specification with
the code that implements it, so I read section 4 through. Four rules, one
small gap, and two readings of mine that were wrong before they were
right.

**4.1, the bridge percentile against 285,996 observed bridges.** Clean,
and already pinned by a test against the live store count.

**4.2, the lysine reach window.** The spec says to apply BINMAN's
reach-window fit, "already calibrated against 976 observed diGly sites",
and report `lysine_reach_fit`. The field is deliberately absent, and
D-NOB-024 explains why at length: BINMAN's reach window carries
`fitted = false`, and its own measurements on 369 assayed lysines give
AUCs of 0.42 to 0.48, at or below chance and inverted. The spec's premise
is factually wrong, so the project reports the geometry and derives no
score. The other two things 4.2 asks for, the count inside the window and
the relative SASA, are both there per lysine and in aggregate. A deviation
from the spec, argued and logged, which is what CLAUDE.md asks for.

**4.4, pose convergence, "report mean and spread".** Clean: `mean_rmsd`
0.789 and `spread` 0.801 on the first pair, with `max_rmsd` and the full
pairwise matrix beside them.

**4.5, the ipTM calibration caveat.** The one gap, and a small one. The
About page carried the conclusion, "separates cognate from non-cognate
antigens poorly", without the measurement behind it. The spec gives a
number, ROC-AUC 0.5 to 0.60, and names ipTM-min as the strongest of the
confidence metrics. A reader asking how weak got an adjective. Both now
sit in the same two short sentences, five words longer.

### Two wrong readings, and a shell mistake

I grepped the About page for "Thera-SAbDab" and "0.60", found neither,
and concluded the caveat was missing altogether. It was there in
different words, naming 519 antibodies and stating the conclusion. That
is F20's mistake in a smaller place: a test for the wrong string read as
absence of the thing.

I then asserted the caveat was two sentences by counting full stops, and
got four, because "0.5" and "0.60" each contain one. Counting dots
followed by whitespace is correct and obvious afterwards. That is the
third naive string check of mine to be wrong today, after the regex over
a multi-fragment f-string in F26 and the pLDDT column name in F46.

And a stray `cat >` with no heredoc swallowed the rest of my own script as
its standard input, so the test file was never written, an empty `.go`
file appeared in a Python project, and a blocked shell sat in the
background looking like a slow test run. Diagnosed by reading what the
background process was actually doing rather than waiting longer for it.

## F50. String checks of mine fail; executed ones have not

Three naive string checks of mine were wrong today, in three different
places, and each looked right until it ran:

  * F26: a regex over the source matched only the first fragment of a
    multi-part f-string, so the check would have passed with the hard-coded
    value it existed to forbid sitting in any later fragment.
  * F46: the Tier B pLDDT floor asserted against `mean_plddt`, the
    whole-model mean, rather than `best_window_mean_plddt`, the criterion.
    Seven of fifteen frozen ligases came back "below the floor" and none
    was.
  * F49: the About page grepped for "Thera-SAbDab" and "0.60", neither
    present, the caveat present in other words. Then two sentences asserted
    by counting full stops, which came to four because "0.5" and "0.60"
    each contain one.

Nothing executed was wrong. The `bridgedOf` helper run under node, the
monkeypatched scorers, the synthetic campaigns through `preflight` and
`score_campaign`, the AST walks: all of those either passed for the right
reason or failed for one.

The difference is not carefulness. A string check asserts that some text
looks a particular way, and the thing it is standing in for is a
behaviour, so every one of them carries an unstated assumption about how
that behaviour is spelled. Three of mine had the spelling wrong.

So the newest of them is converted. `test_forced_exclusion` matched a
regex over `delta.html` to check that the headline view draws a forced
pair differently. The two decisions are now named helpers, `forcedStyle`
and `forcedLabel`, lifted out by name and run under node against real
inputs: a forced pair must come back more transparent, more heavily
outlined and differently coloured than a found one; a record from before
the flag existed must render as found; and two different disagreements
must not read the same. Mutation-checked by drawing forced pairs solid and
by dropping the magnitude from the hover, both caught.

Naming them is the part that made it possible. Written inline in a Plotly
trace, the logic could only be grepped for; given a name, it can be
called. That is the same reason the other executable helper exists, and it
is worth preferring on its own.

The source checks that remain are the ones whose subject really is the
text: the AST sweeps for hard-coded cutoffs, the shell parse that feeds
each chain invocation to its own argparse, and the documents-against-code
tests. Those assert about source because source is what they are about.

## F51. The manifest flagged it and the table could not show it

Continuing the spec reading into section 2. Two rules, one clean and one
half-done.

**Clean.** Spec 2.2 on the affinity cap: "Where a ligand is over the cap,
run the structure prediction normally and record `affinity_unavailable`
rather than failing the job." `ligands.py` records exactly that string,
with the heavy-atom count and the cap, in three places, and no job fails
for being over it.

**Half-done.** The same section: "Fall back to `smiles:` only when no CCD
match exists, and flag those jobs in the manifest **so the difference is
visible in the results table**."

The manifest flags it properly. Every affected queue row carries
`ligand_encoding: smiles` and `flags: ['smiles_fallback']`, and the
campaign summary records twenty warnings reading "no CCD match: encoded as
SMILES and flagged". The instruction's purpose is the second clause, and
none of it reached the table: `aggregate` builds pair-level metrics without
carrying the encoding across, so the scored record's `ligand_encoding` was
null and the table had nothing to show. One join away from unknowable.

Which matters because the two are not interchangeable. A CCD-resolved
ligand's chemistry is the wwPDB component dictionary's and travels freely.
A SMILES fallback's is PROTAC-DB's, is withheld from every published record
(F22), and is the less canonical of the two. A reader comparing
`bench03_BRD4_CRBN` against its six neighbours had no way to know its
ligand rests on a fallback.

The encoding and the merged flags now reach the pair record, taken from the
arm that has them exactly as `ligand_key` already was, since a binary job
carries neither. The table marks the exception rather than adding a column:
six of seven benchmark pairs resolve to a CCD, and a column of blanks is
worse than a mark on the one that does not. The mark says what the fallback
costs rather than carrying a bare label.

Both the helper and its test follow F50: `ligandCell` is named so the test
can run it under node rather than grep the template, and it is run against
a CCD pair, a SMILES pair, and a pair with no ligand at all.

## F52. The headline validation layer satisfied half its specification

Spec section 5 read against the code. Two of three layers clean, and the
third missing a test nobody had recorded as missing.

**5.1, pose recovery.** Clean, including the clause easiest to let slip:
"the seven benchmark pairs are reported individually, by name, on the
About page". All of them are, with their own recovery numbers, and the
success-rate curve uses the 1, 2, 3 and 5 angstrom breakpoints the spec
names, read from `thresholds.toml`.

**5.2, the time split.** Clean, and already the subject of F25: it
computes correctly, refuses when there is no blind set, and now says so on
the page carrying the numbers.

**5.3, the matched-control ROC.** The spec asks for two tests:
"Delta-ipTM on the Sievers degraded versus non-degraded split, with the
Slabicki graded labels as a secondary continuous test". The binary split
is computed, carefully, with a bootstrap interval and a scope that keeps
the benchmark panel out of it. The graded test is absent, and nothing
anywhere said it had been asked for.

It is absent because the data does not exist. BINMAN's validation store
holds seventeen parsed datasets and the raw downloads behind them, and
none is Slabicki's. The name appears three times in `references.json`, as
bibliography, one of those being the Sievers paper he co-authored. NOBBLE
consumes BINMAN's stores rather than acquiring its own, so there is no
continuous label to correlate against.

That is the same situation as Degronopedia and ProtCID, which D-NOB-010
records plainly and which makes the furniture veto report `not_computed`
rather than `false`. The difference was the record. The ROC reported the
half it could compute and looked complete.

So the layer now names the missing test with its reason, and D-NOB-046
records the decision and what it costs: a continuous label would separate
a weak degrader from a strong one, and degraded against not-degraded
cannot, so the headline curve is coarser than the specification intended
and now says so.

The test for it checks the premise rather than restating it: if the
Slabicki data is ever acquired into BINMAN, the test fails, which is the
reminder to implement the secondary curve rather than leave the note
standing. That is the same guard as the F47 drift allowlist and the F26
cutoff allowances, and it is the third time today that an "it cannot be
done" note needed a test to stop it outliving the reason.

## F53. The ledger was faceted on two of five things

Spec Phase 4 on the Campaign tab: "Faceted on modality (glue / PROTAC),
tier (benchmark / A / B), and flags (furniture, forced,
affinity_unavailable)."

Modality and tier were there, with three useful extras the spec does not
ask for: bridging seeds only, pinned only, complete scores only. None of
the three flags was.

**forced** is the one that matters, and it is the second half of F48's
finding arriving from a different direction. Spec 4.7 says forced hits are
"shown separately", which I read as a marker and an exclusion from the
ranking; Phase 4 says the ledger is faceted on it, which is the other
mechanism and the one that lets a reader ask the question. CDK12 is the
live case at 0.494.

**affinity_unavailable** could not be faceted on at all, for exactly F51's
reason: `affinity_available` was on the queue row and dropped when scoring
aggregated jobs into pairs, so there was nothing for a filter to read. The
same one-join fix, the third time today. It needed care in a way F51's did
not: the JSONL row carries the string `"False"`, which is truthy, so the
value is parsed rather than passed through, and the mutation that treats
it as a boolean is caught.

**furniture** is deliberately not offered. ProtCID was never acquired, so
the field is null on every pair and its status is permanently
"not_computed: protcid_unavailable" (D-NOB-010). A control that can never
match anything is worse than no control: it invites a reader to conclude
that nothing was furniture, when the truth is that nothing was tested. The
reason sits in the template where the control would have gone, so its
absence is distinguishable from forgetting it.

One distinction worth the care it took. The affinity facet matches
`affinity_available === false` and not `!p.affinity_available`, so a pair
whose availability was never recorded is left out rather than filtered in.
`None` is not `False`: one says the ligand exceeds the cap, the other says
nobody looked, and a filter that conflates them makes a claim out of a
gap. That is the same distinction as F32's refused-versus-never-attempted
fingerprint and F43's absent-versus-null key.

The filter predicate is lifted from the template and run under node, per
F50, against a plain pair, a forced one, one over the cap, one with
nothing recorded, and one that is both.

## F54. A divergence I created while removing hard-coded cutoffs

Phase 4's Delta tab asks for four things beyond the scatter: marginal
distributions on both axes, lasso selection pushing to the Campaign tab, a
ROC panel, and a draggable threshold that live-updates precision and
recall. All four are there and working.

Reading the ROC panel turned up something else, and it is mine.

Its comment states the requirement plainly: "This filter and the Python one
have to agree, because the figure here and the number in the validation
report are supposed to be the same curve." Both refuse to draw below three
scored pairs a side, which is spec 5's rule that a matched-control curve
without its matched negatives must not be reported at all.

They agreed by both being written as a literal 3. Then F28 moved the Python
side into `thresholds.toml` as `roc_minimum_per_side` and left the
template's literal where it stood. Nothing broke, because the two numbers
are still equal. But the config became the source of truth for one of them
and not the other, so a single edit would have made the chart draw a curve
the validation report refused, or refuse one the report drew, with nothing
failing either way.

That is a worse state than before the change. Two literals are visibly
two literals; one literal and one configured value looks handled.

The floor is now passed into the template from the same config the layer
reads. The test that matters is not the one asserting they are equal,
because two literals were equal too: it changes the configured value and
requires both sides to follow.

Worth recording as its own finding rather than folding into F28, because
the lesson is specific. Moving a constant into configuration is only half
a fix if something else was reading the constant. F28 swept Python for
cutoffs and the template is not Python, so the sweep could not have seen
it, and I did not think to look. Three sweeps found cutoffs in
comparisons, in module constants and in default arguments; the fourth place
was another language.

## F55. Two more template cutoffs, one of which nothing could have caught

F54's lesson was that a sweep for hard-coded cutoffs had looked in three
places in Python and the fourth place was another language. The sweep that
should have followed is now a test, and it found two more in the templates.

The first is `benchmark.html`'s recovery band, a literal 5 beside a
configured `rmsd_breakpoints = [1, 2, 3, 5]`, with the chart's own comment
claiming it was "banded on the success-rate breakpoints the curve already
uses". The same shape as F54 and caught by the same reasoning.

The second is different in kind and is the reason this is a separate
finding. The page styles its Pearson correlation on whether `p < 0.05`,
and no Python anywhere applies a significance level. So there was nothing
for it to diverge from: a grep for a value held in two places would never
have found it, because it was held in one. It is a project-wide
statistical threshold that happened to live in markup.

A cutoff with a twin is a divergence risk. A cutoff with no twin is not
safer, it is less visible: the twin is what makes the first kind
findable. The alpha is now `scoring.significance_alpha`, and the test that
holds it checks both ends, because a page that ignored the configured
value entirely would pass a one-ended test by luck.

## F56. The right answer with a false reason: IKZF1 is a zinc finger

`requires_structural_zinc` decides whether a peptide is co-folded with the
Zn(2+) its domain needs. Its docstring ends "The test is the complete
motif, not the source", and the code tested the source: a curated class
outside `zinc_finger` returned the reason "not a zinc-finger domain"
without the motif being counted at all.

For the one peptide this fired on, that reason is false. The design scan's
parent is IKZF1's degron window, and IKZF1 is a zinc finger; the window is
a fragment of finger 2 whose histidines fall outside it. The campaign's
own `campaign.json` recorded "not a zinc-finger domain" against
`PFQCNQCGASFTQKG`, which carries a CxxC pair, so the record contradicts
both the protein and the sequence beside it.

No number is wrong. The peptide gets no zinc either way, and that is the
correct decision, reached through the absent histidines rather than
through its provenance. What was wrong was the explanation, which is what
a reader of the campaign metadata gets, and which would have been the
starting point for anyone later asking why the design arm's parent folds
without an ion.

The gate also meant the motif test never ran for a peptide outside the
domain classes. A complete coordination site submitted as a tile would
have fallen through in silence, and the recorded reason would have denied
it was a zinc finger at all. No such peptide exists in the library, which
the fix checks over all 5670 rather than assumes, and the reorder is
decision-neutral on exactly that premise.

The motif is tested first now and the third case is reported rather than
dropped. The family resemblance to F47 is close: both keyed a decision on
the wrong attribute and produced a plausible output, and in both the
plausibility is what kept them hidden.

## F57. Three directories that looked like campaigns that found nothing

`campaigns/` held `design_20261104T075843Z`, `design_20261104T081815Z` and
`design_20261104T081927Z`. Each contained an empty `yaml/`, an empty
`outputs/` and nothing else: three failed attempts at assembling the design
scan, 20 minutes apart, from a run that raised after creating its directory.

Every assembler creates those two subdirectories and then does work that
can raise, so the skeleton outlives the failure under a campaign name. A
skeleton is not distinguishable from a campaign that ran and produced no
results, which is the project's recurring shape: a state that reads as an
answer.

`latest()` sorts by name and returns the newest match, so the newest
skeleton was "the latest design campaign". Nothing calls `latest("design")`
today, which is the only reason this had not yet produced a wrong answer.
Four of that function's seven callers use what it returns without checking
anything further.

Both reuse guards had the same defect in miniature. They tested
`queue.jsonl` and then read `campaign.json` unconditionally, so the one
state they were written to detect, an assembly that died part way through,
would have raised `FileNotFoundError` rather than been handled.

Two fixes, because there are two failures. An assembly that raises now
removes its own directory, which covers the failure that actually happened.
A process killed between the mkdir and the manifest cannot clean up after
itself, so `latest()` also requires the completion marker, which every
assembler writes last. The first is the cause, the second is the one that
cannot be caught at the source.

Collapsing the four assemblers onto one helper removed something I had not
gone looking for: three independent copies of the timestamp format, one per
assembler, all matched against a single regex in `latest()`. A copy drifting
from that regex would not have failed anything. The campaign would simply
have stopped being found, which is the same silence the skeletons produced,
arrived at from the other direction.

## F58. Removing the litter would have removed the evidence with it

F57's fix deletes a campaign directory whose assembly failed. Reproducing
the design assembly afterwards succeeded, so the three skeletons were
transient, almost certainly my own edits to the tree while calling into it
during the mutation sweeps. Almost certainly is as far as it goes: nothing
recorded a traceback, so the cause cannot be confirmed.

That is the state the fix would have made permanent. Litter with no
explanation at least says that something failed three times, 20 minutes
apart. A directory silently removed says nothing at all, and is the quieter
of the two failures rather than the smaller one.

The reason is now appended to `data/manifests/failed_assemblies.jsonl`
before the directory goes: the error, the message, the traceback and what
the directory held. Appended rather than rewritten, because three identical
failures in sequence said more together than any one of them did.

Two things fell out of testing it. The fixture for F57's tests redirected
`CAMPAIGNS` and not the new manifest, so four test failures were appended
to the real one before I looked: a fixture that redirects some of a
function's outputs stops covering the rest of them without saying so. And
the recorder's `except OSError` was too narrow. A `FAILED_ASSEMBLIES` path
that pathlib rejects raises `ValueError` before any I/O, so the diagnostic
would have replaced the error it exists to describe. Its own comment says
that must not happen, which is how the test came to look for it.

## F59. Two descriptions of every job, and nothing compared them

A campaign holds the queue row, which says what a job is and which
everything downstream reads, and the YAML, which is what Boltz is actually
given. One assembly writes both, so they normally agree.

They disagree in the main campaign. F47 fixed a modification rule that had
put a hydroxyproline on BRD4 Pro379, and the queue was reassembled: the
fifteen `bench02_BRD4_VHL` rows correctly record that no modification is
required. The fifteen YAML files were already on disk and were not
regenerated, so they still carry `ccd: HYP`. All fifteen have now run.

Nothing compared the two, and a disagreement between them is invisible from
either side. Boltz reads the YAML and cannot know what the queue says; the
scorer reads the queue row and the results, which look exactly like results
for the job the queue describes. The number would have been published as
BRD4 against VHL, and it is a measurement of a hydroxyproline BRD4 does not
have.

The comparison is now a module, and the atlas build refuses on it before
writing or removing anything, so a refusal leaves the previously published
atlas in place: stale rather than wrong. It asks whether the two agree
rather than looking for a hydroxyproline, so it covers the reverse case too,
which is the one a reassembly actually causes. Across all four campaigns it
reports exactly those fifteen jobs and nothing else.

The chain now runs the correction itself, between the main campaign and the
publish, where the GPU is free and nothing has been published. It also had
`ls -d campaigns/design_* | tail -1` in four places, which is F57's
skeleton-shadowing bug in the other language: both now require the
completion marker. That is twice in one session that a rule fixed in Python
was still wrong in a different file type, after F54 and F55 made the same
point about the templates.

**And a mistake of mine in testing it.** The wiring test runs the real
`build_atlas.py`, which is safe while the build refuses. Mutating the
refusal away, to confirm the test catches its removal, let the build run and
rebuild the published atlas from a campaign with 54 of 2360 jobs scored.
Recoverable, because the atlas is tracked, and `git checkout` restored it.
But a check should not be able to do that: the output directory is now
overridable and the test writes to a temporary one, which was verified by
removing the refusal again and confirming the published atlas was untouched.
Mutation testing deliberately disables safeties, so a test that invokes a
real destructive path is only as safe as the guard it is testing.

## F60. The GPU guard waited on a name for the thing, not the thing

There is one MPS device, so two campaigns sharing it halve each other's
throughput and risk an out-of-memory on the larger jobs.
`nobble_wait_for_gpu` enforced that by checking whether any of six tmux
sessions existed.

A session name is a proxy. Kill a chain and its `run_queue` child keeps
running, outside every session the list knows, and the guard returns
immediately. I nearly did exactly that: `run_chain.sh` needed editing while
it was running, and killing it while leaving its queue alive was the first
plan. The relaunched chain would have started a second campaign on a device
already in use, and the guard would have said the device was free.

Worse, `run_queue.sh` did not wait at all, though `wait_for_gpu.sh` opens by
saying it is "sourced by every script that starts inference". It is the
script that starts inference: the chain, tier 2 and the design scan all
reach the device through it or beside it. A sweep for an *invocation* of the
runner, rather than a mention of it, found `run_corrected.sh` in the same
state and correctly left `status.sh` alone, which imports `disk_gate` and
starts nothing.

The guard now asks for the runner process itself. `--throughput` runs are
excluded, because `refresh.sh` runs one after every campaign to rewrite a
JSON from results already on disk and it never opens the device.

**Three of my own tests were worth less than they looked.** Mutation
testing caught all three, which is the only reason this entry can be
specific about them.

Removing the wait while keeping the detection passed everything: seven
tests asserted that the guard could *tell* whether the device was busy and
none that it then *waited*. The interval is now overridable so a test can
sit through it, and the two halves are separate functions, because with a
campaign in a tmux session on this machine the session half never returns
and the process half could not otherwise be reached.

Removing the ancestry exclusion also passed, and that one is not a missing
test but a claim I could not make. macOS `pgrep -f` already omits its own
ancestry, parent and grandparent alike, while reporting siblings, so the
exclusion changes nothing observable here. It is kept, because it is what
makes the guard correct rather than accidentally correct, and the test now
checks the ancestry chain is computed rather than pretending to demonstrate
an effect this platform hides.

And the existing self-exclusion test broke in a way worth recording: a
pattern named in a command line is matched by `pgrep` against the tmux
process carrying it, which is a sibling and so not excluded, and quoting it
inside `bash -c '...'` closes the outer quote. The script is written to a
file now, which has neither problem.

## F61. Seconds per token is not one number, and the projection said it was

F45 replaced a "representative job" with a measured seconds-per-token rate,
on the reasoning that the per-token rate transfers between campaigns and a
job size does not. `projected_hours`'s docstring then claimed the resulting
figure was reached by "summing the real tokens at the rate measured for jobs
of each size".

It was not. The code multiplied every token by one median rate. The
docstring described a method that was never written, which is the same shape
as F56: a right-looking number with an explanation that does not describe how
it was produced.

And the method actually used is biased, because the rate is not a property of
the model. On the main campaign it runs from 0.211 s/token for 200-400 token
jobs to 0.663 for 800-1600 token jobs. Attention cost does not grow linearly
with sequence length, so a single median understates any campaign whose large
jobs are a minority of the jobs and a majority of the cost. That is the usual
shape and it is this campaign's: 2,215 of 2,289 remaining jobs are under 200
tokens, while the 29 jobs over 800 tokens carry a tenth of the tokens left.

A linear fit gave `seconds = -23.1 + 0.504 * tokens`, and a negative
intercept is the fit saying the relationship is not linear rather than that a
zero-token job finishes before it starts. With one job above 800 tokens there
is no curve to fit, so the projection bands rather than models: each job is
priced at the median rate measured for jobs of its size, and a band with no
measurement is priced at the slowest rate observed and counted in
`unmeasured_jobs`. Guessing cheap is the one error that opens a gate too late.

On this campaign's remaining queue the flat rate gives 48.6 hours and the
banded rate 51.4. Both are inside Gate G1's 96, so nothing was reported
wrongly: this was a measurement error and not a false gate, which F45 shows
is the expensive failure. I had also written 46.8 hours into PROGRESS.md an
hour earlier from my own flat-rate arithmetic, which is corrected there.

The band edges are configured, and the binning is one function imported by
both the writer and the projection. Two copies of a binning rule is how a
rate measured in one set of bands comes to be applied in another, which is
this finding arriving again by duplication.

## F62. A campaign has two queues and the check read one

Three stages had never executed: tier 2, the design scan and the prediction
scorer. A stage that has never run is the largest remaining risk in an
unattended build, so each was dry-run against the real campaign with the
inference step left out, to find a crash now rather than in fifty hours.

**Correction.** "Each was dry-run" overstated it when written. Scoring and
tier 2 selection had run; the prediction scorer had not, and the design
arm's lift path still had not, because it needs design results that do not
exist. The prediction scorer has since been run and works, and the design
lift is covered in F63. The claim was wider than the evidence by exactly
the stages this finding exists to be careful about.

They work. Scoring the partial campaign succeeded and the composite
correctly refused to fit on six positives and no negatives. Tier 2 selected
a decile, explained why it had ranked on bridge percentile rather than the
unfitted composite, and built a queue.

The queue it built was for `bench02_BRD4_VHL`, and it pointed at the
tier-1 YAML files, which still carry F47's hydroxyproline. Two things
follow.

The first is good and worth recording because the correction path depends
on it: tier 2 reuses the tier-1 YAML verbatim, since only the sampling
settings differ between tiers and those are command-line arguments. So
regenerating a pair's tier-1 YAML corrects its refinement too, and the
chain correcting before it refines is the right order. That property had no
test, and `build_tier2_queue`'s docstring asserting it is not the same as
something checking it.

The second is a gap in F59. `stale_inputs` read `queue.jsonl`, and a
campaign has `queue_tier2.jsonl` beside it. On this campaign it happened to
catch the same files through the tier-1 queue, so the atlas still refused,
but a campaign whose tier-1 inputs had been corrected while its refinement
queue still named an old YAML would have passed. The check I wrote one
context window ago covered the queue that was in front of me rather than
the queues that exist. It now discovers them, and each report names the
queue it came from, because which queue it is tells you whether correcting
and rerunning tier 1 is enough.

The dry run left a decile selected from six of 158 scored pairs in the live
campaign. `build_tier2_queue` opens its target with `w`, so the chain
rewrites it from the full scores and nothing was at risk, but it was removed
rather than left: a top decile chosen from six pairs is exactly the state
that reads as an answer. The property it demonstrated is now a unit test
that does not depend on the artefact existing.

Also checked and found sound, so recorded as verified rather than fixed:
CLAUDE.md's rule against hard-coding cores, memory or device holds. The one
device literal in the codebase compares the configured device against `mps`
to choose boltz's `--accelerator`, which is a translation rather than a
hard-coding. And the four run scripts export inconsistent subsets of
`tuning.toml`'s `[env]`, which looked like drift until `boltz_environment()`
turned out to apply all of it to the inference subprocess, and the runner
parent turned out not to import torch at all. Tier 2 is therefore not at
risk of running without the MPS fallback, which was the concern worth
chasing.

## F63. The design arm's entry point had thirty tests around it and none on it

`lift.from_scores` is what the Design tab and `tools/run_design.sh` both
call. `test_design.py` has thirty tests covering the pieces it composes,
`lift.compute` and `scan_profile`, and one that mentions `from_scores` in
its docstring. Nothing called it.

The composition is where the selection happens: which row is the parent,
which rows are its variants, and what is reported when either is missing.
That is the part that can be wrong while every piece is right. It filters
on `tier == "design"` and on `parent_peptide_id`, and either filter failing
open composes a difference of differences between unrelated pairs. The
number would be a real subtraction of two real measurements and would be
about two different peptides.

Four mutations confirm it now fails: dropping either filter, dropping
refused lifts from the reported list, and taking the first scored row as
the parent instead of matching on the identifier. The last one is the
quietest, because a campaign whose first row happens to be the parent would
pass every other test in the file.

Found by asking which code paths had still never executed, rather than by a
sweep. Scoring, tier 2 selection and the prediction scorer had all run by
then; this was the one left, and the reason it was left is that it cannot
run until the design campaign produces results, which is queued behind
fifty hours of main campaign. A path that cannot be exercised for two days
is exactly the one worth covering with fixtures.

## F64. Verified rather than fixed: the template edits and the new config key

Four templates were edited across F55 and the two findings before it, and
the local app had been serving them from a process started before those
edits. With `debug=False` Jinja does not reload, so the running instance was
compiled from the old files: a QC pass against it would have reported on
templates that no longer exist. Restarted first, then checked.

`node qc/qc.mjs`: 14 pages captured, 0 non-200, 0 console errors, 0 serious
axe violations. The edits are clean end to end, which the template tests
could not establish on their own: they run the inline helpers under node and
the routes through Flask's test client, and neither sees a console error or
an accessibility regression.

F55 also introduced a deployment hazard worth checking rather than assuming.
`routes.py` now reads `scoring.significance_alpha`, so a droplet without the
updated `config/thresholds.toml` would raise `KeyError` on `/benchmark`. The
app-code rsync excludes `campaigns/`, `logs/`, `qc/`, the MSA and cache
directories and the atlas, and does not exclude `config/`, so the key
travels. Deployed to confirm it in the environment that matters: the droplet
has neither gemmi nor pandas nor BINMAN, which is why spec Phase 4 requires
a precomputed atlas and why two routes once returned 500 there while working
locally.

All nine routes answer 200 on the droplet, and the live page carries
`const RECOVERED_A = 5.0` from the configured breakpoints and renders its
Pearson stat from the configured alpha. HTTPS answers 200 and port 80 still
returns 301.

Deployed now rather than at the end of the chain deliberately. The chain
deploys last, so an environment-specific break in a change made today would
have surfaced after fifty hours of campaign rather than within the hour.
The published atlas is unchanged and still the benchmark panel's, because
the main campaign's atlas refuses while F47's correction is pending, so this
shipped the code fixes and nothing else.

One thing this did not find, recorded because the error was mine and the
near-miss is instructive: a grep over the served page for `RECOVERED_A`
came back empty and briefly looked like the template had stopped injecting
it. The pattern was an alternation with `stat--good`, and `head -4` consumed
four class matches before reaching the constant. The template was correct
and the check was wrong, which is the same shape as the string checks F50
retired, arriving this time in a shell pipeline.

## F65. What a truncated run actually keeps, as a number

`projected_hours` says that overrunning the 48-hour target is "a scheduling
fact the priority ordering absorbs: the run yields the benchmark panel, then
the Sievers split, and loses discovery off the tail". Gate G1's whole
argument rests on that sentence, and it had never been checked.

The tier ordering holds: benchmark jobs 0 to 99, Sievers 100 to 1899,
scrambles 1900 to 2359. So a run cut short loses scrambles first, which is
what the sentence claims.

The tier ordering is not sufficient, though, and that is the part worth
recording. The matched-control ROC needs degraded and not_degraded pairs
together. A Sievers block that ran all 24 degraded pairs first and all 96
not_degraded after would satisfy the tier ordering exactly and still leave
a truncated run holding one side of a comparison and no curve at all.

It interleaves. The block runs at a constant four not_degraded to one
degraded, in every quarter. So, against the configured floor of three pairs
a side:

| complete pairs per side | job | share of campaign | projected hours |
|---|---|---|---|
| 3 (the floor) | 400 | 16.9% | 11.2 |
| 5 | 610 | 25.8% | 15.3 |
| 10 | 1015 | 43.0% | 23.3 |
| 20 | 1645 | 69.7% | 35.8 |
| 24 (every degraded pair) | 1855 | 78.6% | 39.9 |

**Corrected.** The table above originally read 145, 190, 400, 1255 and 1495,
and was optimistic by roughly a factor of two. The arithmetic was right and
the scoping was wrong: it counted every pair carrying one of the two labels,
and `matched_control_roc` computes the curve over the Sievers arm alone. The
layer excludes the benchmark panel for reasons it states, other ligases,
PROTACs as well as glues, no matched negative from the same screen, and a
panel selected for having good co-crystals that would raise the positive
side and the AUC with it. Those seven pairs are also at the head of the
queue and so complete first, which is exactly what made the curve look
available at job 145.

Found by reading the layer while looking at something else, not by the test
written to protect this. That test used the same unscoped count, so it
enshrined the error: it would have gone on passing while reporting the wrong
figure (F73).

The falsifiable test is therefore computable about eleven hours in and fully
populated on the positive side at 40 of the 51 hours remaining. The last 21%
of the campaign deepens the negative side and runs the scramble control,
which is what "discovery off the tail" means in jobs.

Computable is not powered, and the two must not be conflated: three pairs a
side is a curve that the About page's own 0.5 to 0.60 caveat exists for.
Both rows are in the table for that reason.

**A lapse of mine in checking this.** The first version of the interleaving
test was mutation-checked by rewriting the live campaign's `queue.jsonl`,
clustering the labels, running the test, and restoring the file. It came
back byte-identical, the results file held 72 unique jobs with no
duplicates, every result was still a queue job and the completed set was
still the queue's leading prefix, so the campaign was unharmed. That is
luck, not method: the runner reads that file.

It is the second time a mutation check of mine has reached live state, after
the published atlas earlier today, and the shape is the same both times.
Mutation testing deliberately removes a safety, so the thing being mutated
has to be something a test is allowed to break. The check is now a pure
function over a list of jobs, with two negative controls that feed it a
clustered copy and a one-sided copy in memory. Nothing on disk is involved,
and the controls also close a gap the file mutation never covered: that the
real queue passes says nothing about whether a clustered one would be
caught.

## F66. The safe path was harder to use than the unsafe one

Two mutation checks of mine reached live state today. One removed the atlas
build's stale-input refusal, to confirm the test caught its removal, and the
test then ran the real build and rebuilt the published atlas from a campaign
with 54 of 2360 jobs scored. The other rewrote a live campaign's
`queue.jsonl` while the runner was reading it. Neither did lasting harm: the
atlas is tracked and `git checkout` restored it, and the queue came back
byte-identical with the results file still holding 72 unique jobs whose
completed set was the queue's leading prefix. Both were luck rather than
method.

`tools/mutate.py` exists precisely to prevent this and was not used either
time. The reason is worth being plain about: it only ran a fixed list of
mutations, so a one-off check was faster to write as a shell loop with a
`trap` than to add as an entry and run. The unsafe path was the convenient
one, and that is a property of the tool rather than of the day. So the first
fix is `--file/--find/--replace/--tests`, which runs an ad-hoc mutation
under the same rails: the dirty-tree refusal, the signal handlers, the
restore, and the clean-tree verification on exit.

The second fix is the lesson the two share, and it is not "do not mutate
live files". The atlas lapse mutated `deploy/build_atlas.py`, which is
source and entirely legitimate to mutate. What was written was the atlas,
by a test that was only safe while the code it tested was correct. Which
file is edited does not predict what gets written, because a mutation
removes a safety deliberately and the tests then run without it.

So the harness fingerprints live state, 32 files on this checkout, before
and after every run and reports any change with a non-zero exit. Campaign
results, every queue, the state log, scores, the published atlas and the
measured throughput. Size and mtime rather than a hash, because hashing
hundreds of megabytes between every mutation would cost more than the
failure mode is worth, and a rewrite preserving both is not a real one.

It refuses to mutate live state at all, before touching anything, and
refuses anything outside `nobble/`, `tools/`, `deploy/` and `qc/`. Not
because editing a document is dangerous but because a mutation there is not
testing code, and the sweep would report "not caught" for a change no test
could have been expected to notice, which is a false negative dressed as a
finding.

Both guards are checked by mutating the harness with the harness, which
refused on the first attempt because `mutate.py` had uncommitted changes:
the entry guard doing its job on its own author.

## F67. The house style was enforced by nothing, and my sweep for it leaked

CLAUDE.md and BUILD_SPEC.md 1.4 both state the house style: British
English, no em dashes, and a forbidden-word list. Nothing checked it for the
whole build, and thousands of words of FINDINGS.md, DECISIONS.md and UI copy
were written against it on trust.

The trust was mostly warranted. No forbidden word appears outside the two
files that state the rule. No American spelling appears anywhere, and the
British forms are in active use: colour, behaviour, tumour and labelled all
occur, which is what makes the absence of their counterparts evidence rather
than a broken pattern.

Writing the check settled one question that had never been decided. The app
templates hold 32 em dashes and every one is an empty-value placeholder in a
table cell or a stat. The rule's own remedy, "use colons, semicolons or
parentheses", cannot be applied to a glyph standing for "no value", so the
rule is about punctuation in prose and the placeholder is allowed. The 11
em dashes used as punctuation are all in BUILD_SPEC.md, which is the
authoritative input rather than this project's output, and which is where
the rule is stated. Recorded as a decision because an unrecorded
interpretation is indistinguishable from an unnoticed violation.

**The sweep then leaked twice, and the harness from F66 found both.** This
is the first use of that harness on something I had just written, and it
earned its place immediately.

The forbidden-word check matched `\b<word>\b`, so it caught "delve" and
missed "delved", "delves", "delving" and "seamlessly". Those are most of
the real uses, because the inflected form is how a word of that kind
actually turns up in a sentence. Worse, the test meant to cover the
boundary used
"shelve" as its negative case, and "shelve" does not contain "delve" at
all. So the test passed, the check looked boundary-safe, and every
inflection went through. It matches `\b<word>\w*` now, which keeps the
leading boundary, and the negative cases are words that genuinely contain a
banned stem: "bedevilled", "seamed".

And the control asserting the British forms are in use passed when its loop
was emptied, because the loop target was a literal in the test body. A
control that passes vacuously is not a control. The forms are a named
constant now and the test refuses an empty one.

Both are the same shape as the thing this sweep exists to catch: a check
whose correct and incorrect behaviours produce the same result on the data
at hand.

## F68. The installed app would have painted its chrome in the house blue

CLAUDE.md reserves the marcdeller.com palette for the README and the blog
mark, and `depot.css` repeats it at the top of the file, naming the colour:
"header and #1e73be palette do NOT apply here". `site.webmanifest` set
`theme_color` to #1e73be, the exact colour that line excludes, and
`background_color` to white where Depot's background is concrete.

Nothing contradicted it. `base.html` carries its own
`<meta name="theme-color">` with the right Depot values for light and dark,
and that is what a browser tab uses, so every surface anyone had looked at
was correct. The manifest only takes effect once the app is installed, so
the installed app would have shown house-brand chrome and a white splash,
and the splash is the one surface a reader sees before any stylesheet loads.

Both now read Depot's `--bg`. Three places hold that colour, the CSS
variable, the meta tag and the manifest, and the tests check they agree
rather than that each is a particular string, which is the reasoning that
fixed F54 and F55.

**Three bugs in the tests themselves, all mine and all found by running
them.** The icon path check dropped the `static/` segment, so it looked for
files one directory above where they are. And the dark-mode lookup matched
`depot.css`'s header comment twice over: first on a bare
`prefers-color-scheme: dark` anchor, then on the full `@media` query, which
the comment also quotes in full. Both times it sliced from the comment and
found the light `--bg` twenty lines below, then compared it against the dark
meta tag. Anchored on the opening brace now, which is what distinguishes the
rule from the prose about it.

Then the house-style sweep from F67 failed on F67's own entry, which is the
sweep working. The entry names the inflections the old pattern had been
missing, and naming them is using them by a literal reading. A rule that
cannot be written about is a rule whose violations cannot be explained, so a
forbidden word in straight double quotes is now a citation rather than a
use: exactly the quoted token, on the same reasoning as the em-dash
placeholder. A quoted phrase is still a use, and an unquoted use beside a
legitimate citation is still caught, both of which are tested, because those
are the two ways the allowance could become a loophole.

Two passages were reworded rather than exempted. Exempting FINDINGS.md and
BUILD_LOG.md would have excused the two files most likely to drift, since
they are where almost all of this project's prose is written.

## F69. The natural-language component had no way to reach it

Spec 1.2 lists BINMAN-LM as a component: Head A translates a campaign
question into a query object, Head C abstains when the campaign has not run
the pair in question. Both are implemented in `nobble/app/lm.py`, both are
tested, and `/api/ask` serves them.

Nothing called it. The app's only fetch targets were `/api/pair/` and
`/api/status`, so no reader could ask a question. PROGRESS.md described the
query head as part of a complete Phase 4, which was true of the backend and
of nothing a user could reach: the recurring shape, a component whose output
nothing reads.

The Campaign tab now carries an ask panel, beside the ledger the questions
are about. It renders the count and the matched pair identifiers, both
computed by the executor in Python, and the translated query labelled as
the model's reading of the question and placed after the figures rather
than among them. That separation is the no-arithmetic contract at its edge:
a threshold in a query was chosen by the model, and a reader must be able
to see what was filtered without the number reading as a measurement.

Where no model is configured the panel says so in one sentence and adds
that the figures do not depend on it, because a panel that reads as broken
would make a reader doubt the numbers beside it.

That is the droplet's state and it is deliberate, so the claim here needs
stating precisely rather than generously. QC passes (14 pages, 0 non-200, 0
console errors, 0 serious axe) and the panel is deployed and live, where it
reads "No model is configured". A visitor to nobble.mdeller.com still
cannot ask a question, because spec Phase 4 requires the droplet to serve a
precomputed atlas with no compute at request time, and a model call is
compute at request time. The component is reachable on a host with
`BINMAN_LM_URL` set, which is the Studio. What changed is that it is
reachable at all: before this there was no interface on any host.

## F70. Asking whether a model exists imported one, and broke two tests

Adding the panel made `/campaign` ask whether BINMAN-LM is configured, and
that question was answered by importing it.

`from app import lm` binds a real `lm` attribute on the `app` package, and
`from app import lm` thereafter prefers that attribute over anything in
`sys.modules`. The LM tests substitute a fake model with
`monkeypatch.setitem(sys.modules, "app.lm", fake)`, which works only while
no real `app.lm` has been imported. So one unconfigured render anywhere in a
test session permanently defeated every later substitution, and two tests
that passed alone failed in the suite.

The symptom was misleading in a way worth recording. Both tests had patched
`lm.available` to return True, so the obvious reading was that the patch had
not taken. The locals showed `fake = <module 'app.lm'>` and an error of
"BINMAN_LM_URL is not set", which is BINMAN's own message: the fake was
being bypassed rather than ignored.

Two bisections went wrong before that. The first matched the candidate
files' own unrelated failures rather than the LM ones, and the second
excluded `test_lm_contract.py` by a pattern meant to exclude only
`test_lm.py`. Reading the failure's locals took one command and should have
been the first step rather than the fourth.

`available()` now checks the configuration before the import rather than
after. Without `BINMAN_LM_URL` the answer is False either way, so this is
the same verdict reached without the side effect, and it saves the droplet
importing a package it does not have. The variable name is checked against
BINMAN's own source, because NOBBLE now knows it in a second place.

## F71. D-NOB-007 was stated and checked by nothing

    Shared code is widened in place in BINMAN or BoltzMaker, never forked
    (D-NOB-007).

A rule about the thing most likely to go wrong quietly, and nothing
enforced it. A local edit to a shared file produces a working project and a
divergence nobody sees until the two copies are compared, which until now
nothing did.

Enumerating every file NOBBLE holds at the same relative path as BINMAN or
BoltzMaker gives four: `elementor-widget-markdown.css` and
`tools/readme_forge.py` are byte-identical to their peers, and `wsgi.py` and
`tools/hwprobe.py` differ.

Neither difference is a fork, and both are now recorded as decisions rather
than left as unexplained divergence. `wsgi.py` is each project's own entry
point and the shared name is a convention. `tools/hwprobe.py` is 388 diff
lines from BINMAN's, which is too many to be a fork: they are independent
implementations. NOBBLE's writes the campaign tuning this project needs,
token caps and recycle counts and diffusion samples, which BINMAN has no
concept of, so widening BINMAN's would move NOBBLE's vocabulary into it.
The hardware half, cores and memory and device, is genuinely duplicated and
is recorded here as duplication rather than repaired, because replacing a
working Phase 0 probe mid-build to deduplicate a dozen lines is the wrong
trade.

The same sweep covers the generated README. `README.polished.md` is produced
from `README.md` by the forge and the two are byte-identical today, because
`polish()` checks `already_branded` and leaves a branded document alone. But
identical is not in step: the next edit to `README.md` would make the
generated copy stale and nothing would say so. The check regenerates in
memory and compares, and a second test holds the idempotency that makes
that comparison the right one, because if `polish()` were not idempotent the
two files would differ by design.

Three copies of a timestamp format, two theme colours, two binning rules and
two queue files, all found in the last two days by looking for the same
shape. This is the sweep for it at the level of whole files.

## F72. The published atlas reported that it had withheld nothing

Spec 2.1 is unambiguous: PROTAC-DB stays internal-use-only and is never
redistributed. `deploy/build_atlas.py` enforces it by nulling the `smiles`
field of any ligand record whose `source` is `protacdb`, replacing it with a
note, and `ATLAS.json` reports how many it withheld.

It reported 0. The key was initialised to zero at the top of `main()` and
incremented nowhere, so it was a literal dressed as a count, published on
every build since the first. The atlas it described contained a
`smiles_withheld` field: one record had been withheld while the summary said
none had.

Zero is the worst value it could have held. On a licensing guarantee it does
not read as "this number is not computed", it reads as "no PROTAC-DB
chemistry was present in this campaign", which is a stronger and different
claim than the truth. The real figure is 1, and the record is dBET57, the
one benchmark ligand with no CCD entry.

A count alone would still not be enough, so the ligands are named beside it.
A zero cannot distinguish "nothing needed withholding" from "the detection
stopped firing", and those need opposite responses: the first is fine and
the second is a licence breach waiting for the next campaign.

**Found by sweeping for a defect class rather than by reading the code.**
Two vacuous tests of mine in one day, F65's clustering control and F67's
emptied loop, made "a test whose every assertion sits inside a loop that may
be empty" worth checking mechanically. 515 test functions, none without an
assertion and none asserting only literals, but 17 with every assertion
inside a loop. Most are guarded inside a helper the sweep cannot see. The
one worth opening was `test_published_atlas_withholds_protacdb_chemistry`,
because an empty bundle would have satisfied it by examining nothing, and it
is the test standing behind a licensing constraint. Reading it is what
turned up the counter beside it.

It now counts the files it read and refuses zero, and two controls hold the
check itself: an empty bundle must report nothing examined, and a bundle
with the chemistry planted in it must be reported. Weakening the guard to
`>= 0` passed before those existed, because the real atlas has files either
way.

The published atlas has been rebuilt and now says `redactions: 1,
redacted_ligands: ["dBET57"]`. The rebuild went to a scratch directory first
and the real one was rewritten deliberately rather than by a test, which is
D-NOB-051 being applied rather than restated.

**The rest of the audit, and why it is not a permanent test.** All 17
flagged tests were read. Two were genuine: the PROTAC-DB leak check above,
and `test_no_cached_alignment_is_empty`, which examined every cached
alignment and would have passed on an empty cache. That one now asserts it
read something, because an empty MSA cache is not harmless: F39 showed a
missing receptor alignment degrades every prediction rather than failing
them. Both are fixed.

The other fifteen are false positives of the static check, in three shapes.
Some guard the collection inside a helper, as `_library()` does with its own
assertion. Some count what they examined and skip on zero, as
`test_the_real_campaigns_have_no_pair_level_disagreement` does. Some iterate
a non-empty literal bound to a name one line earlier, as the construct
boundary table does.

So the sweep is recorded here as a method rather than kept as a test.
Keeping it would mean fifteen allowlist entries carrying no information,
and an allowlist that large is the thing F67 and F71 both had to guard
against: it outlives what it allows, and the next genuine case arrives
looking exactly like the fifteen nobody reads.

## F73. The figure I published for when the headline test arrives was wrong

F65 recorded when the matched-control ROC becomes computable, as a table of
jobs, campaign share and projected hours, and put it in both FINDINGS.md and
PROGRESS.md. Gate G1's reasoning about truncation rests on it.

The floor was reported as reached at job 145, 6.1% of the campaign, 6.2
hours in. The real answer is job 400, 16.9%, 11.2 hours. Every row was
optimistic by roughly a factor of two.

The arithmetic was right. The scoping was wrong. `matched_control_roc`
computes the curve over `tier == "sievers_zf"` alone, and I counted every
pair carrying one of the two labels. The benchmark panel carries "degraded"
too, and the layer excludes it for reasons written beside the exclusion:
other E3 ligases, PROTACs as well as glues, no matched negative from the
same screen, and a panel chosen for having good co-crystals, so including it
would raise the positive side and the AUC with it. Those seven pairs are
also at the head of the queue and complete first, which is precisely what
made the curve look available so early.

Two things about how this was found are worth more than the correction.

It came from reading `matched_control_roc` while looking at something else
entirely. Nothing flagged it, and nothing would have: the number was
plausible, the method was described accurately in the finding, and the
description did not mention the one filter that mattered.

And the test written to protect this made the same mistake.
`_completion_index` counted labels without the tier filter, so it agreed
with the wrong figure and would have gone on agreeing. A test derived from
the same misunderstanding as the claim it checks is worth nothing, and this
is the second time today a check of mine shared its subject's error, after
the boundary test that used "shelve" to stand for "delve".

The arm and the labels are now named once, in the layer, and imported by the
test. The scoping check is executable rather than textual, because the first
version grepped its own source for the literal it forbids and matched the
assertion doing the grepping.

## F74. A NaN in the headline curve would have biased it, not broken it

Reviewing `matched_control_roc` for correctness rather than for a symptom.
The estimator itself is right: Mann-Whitney U, which credits a tie with half
a win, and a bootstrap interval with a fixed seed so the published figure is
reproducible. The seed-balance reasoning beside it is the kind of care this
number deserves.

The selection was not. Both groups were chosen with
`isinstance(row.get(statistic), (int, float))`, and NaN is a float.

What a NaN does there is the interesting part. It does not raise and it does
not propagate: NaN is neither greater than nor equal to anything, so the
estimator scores it as having lost every comparison. It is counted as a
unanimous loss rather than as missing data. One NaN among three positives
takes the AUC from 1.0 to 0.667, and at the configured floor of three pairs
a side that is the difference between a result and nothing.

The route in is real rather than theoretical. Python's `json` writes NaN as
a bare `NaN` literal and reads it back, so a non-finite value round-trips
through `scores.jsonl` with nothing in the chain objecting. A boolean would
have passed the same check too, since `isinstance(True, int)` is true, and
been compared as 1 against real deltas.

No scored record carries a non-finite delta today, which is how F25, F32
and F43 all looked before they fired. The project's own standard is that a
guard for a condition that has not yet arisen is still worth having when the
failure is silent, and this one is silent in the direction that matters: it
moves the headline AUC down, towards the null result, which is the direction
a sceptical reader would not question.

Three changes. `_finite` is the filter, and it rejects NaN, both infinities
and booleans. `_auc` refuses non-finite input rather than returning a
number, as the floor under the filter. And the layer reports
`non_finite_dropped`, because excluding a scored pair changes the
denominator and a reader comparing the positive count against the campaign
has to be able to see why; `None` is counted separately, since a pair that
was never scored is a different thing from one whose score came back as NaN.

One of my four tests had the wrong expected value, worked out by hand:
0.2 beats both negatives, 0.0 ties one and loses to the other, so the AUC is
2.5 of 4 rather than 3 of 4. The test caught my arithmetic rather than the
code's.

## F75. Conditioning does not cost anything, which is worth writing down

While confirming the campaign was healthy rather than hung, the last six
jobs showed a conditioned job at 0.7375 s/token beside five unconstrained
ones at 0.6630. An 11% premium on a third of the queue would mean F61's
banding, which prices jobs by token count alone, understates the campaign by
about four hours.

It is a size confound. The conditioned job was 1223 tokens and the
unconstrained ones 1199. Controlling for token count across 276 timed jobs
in three campaigns, the two conditionings agree to the fourth decimal at
every size where both exist: 0.5075 against 0.5049 at 143 tokens, 0.3655
against 0.3639 at 454, 0.7313 against 0.7324 at 1223. Binary jobs look
cheaper per token for the same reason, being smaller rather than
structurally faster.

So the model is right and nothing changes. Recorded anyway, in
`projected_hours`'s own docstring where someone would go to add the factor,
because the measurement that makes the current model correct is more useful
there than the conclusion is here. A negative result that is not written
down gets rediscovered as a hypothesis.

Deliberately not a test. Asserting a tolerance between two medians of live
measurements fails for reasons unrelated to what it protects, and this
project has enough of those. The projection's own banding will absorb a real
change if conditioning ever does start to cost something, because the bands
are measured per campaign rather than fixed.

Also checked in passing, since the review began as a health check: the last
seven jobs' recorded durations match the wall-clock gaps between their
outputs to within six seconds, and the job running now is at 864s against
the previous conditioned job's 902s. On schedule rather than hung, which is
the question F20 answered wrongly by comparing a local timestamp against a
UTC one and killing a healthy job at 80% completion.

## F76. F74 fixed one of fourteen copies of the same rule

F74 found that `isinstance(value, (int, float))` admits NaN, and that a NaN
reaching a comparison is scored as a unanimous loss rather than as missing
data. It fixed the site it was found at, in `matched_control_roc`.

The idiom appeared in fourteen places. Fixing one copy of a rule is the
shape this project keeps finding: three copies of a timestamp format, two
theme colours, two binning rules, two queue files, and now this. The rule
lives in `nobble/numeric.py` and the call sites import it, with a sweep that
fails on a fifteenth.

Two sites would have mattered more than the one that was found.

`tier2.choose_ranking_key` decides which pairs tier 2 spends ten recycles
and twenty-five diffusion samples on. A NaN bridge percentile counted as
rankable, and then sorted, would have sent the refinement budget to the
wrong pairs.

And `score.run`'s bridge percentile median was taken by index from a sorted
list, which is worse than it looks. A NaN does not merely get misplaced:
every comparison against it is false, so `sorted` leaves the other elements
unsorted too, and any index into the result is arbitrary. Measured:

| seed values | median by index | correct |
|---|---|---|
| `[1.0, nan, 2.0]` | `nan` | 2.0 |
| `[3.0, nan, 1.0, 2.0]` | 1.0 | 2.0 |
| `[90.0, nan, 10.0, 50.0, 70.0]` | 10.0 | 70.0 |

A bridge percentile median of 10 where the answer is 70, on what spec 4.1
calls the primary signal.

It does not always corrupt the answer, and that is recorded too, because the
finding would otherwise overclaim: `[nan, 1.0, 2.0, 3.0]` still gives 2.0.
Unspecified rather than reliably wrong is what makes it hard to notice.

`percentile_of` is the route in that exists today. It returns NaN when the
reference distribution is empty, which happens on a host without BINMAN's
atlas, so such a host would have produced a NaN percentile for every pair
and a median that was anybody's guess, rather than refusing.

The refactor cannot move a published figure, which was checked rather than
asserted. `median_of` keeps the lower median its call sites computed, and on
data with no non-finite value the two are the same estimator: 0
disagreements across 3,023 lists, 23 of them taken from the real scored
records and 3,000 generated. And no record in any campaign carries a
non-finite value, from 22,500 float values examined.

Also reviewed and found sound, so recorded rather than changed:
`percentile_of` uses `bisect_left`, which reports the proportion strictly
below a value. Ties are immaterial at this scale, the heaviest being
`buried_fraction = 1.0` at 802 of 285,996 rows, so the choice understates
that one extreme by 0.28 points and every typical value by under 0.01. The
distribution is cached once rather than queried per call.

## F77. An unmeasurable component scored as the best possible one

Spec 4.8's composite puts every component on 0 to 1 so that a weight means
the same thing across them. The scaling ends in a clamp,
`max(0.0, min(1.0, value))`.

`min(1.0, nan)` returns 1.0. Python's `min` keeps what it holds when the
comparison is false, and `nan < 1.0` is false. So a NaN component neither
propagated nor raised: the clamp converted it into the maximum possible
score. A pair whose bridge percentile could not be measured would have
ranked as having the best bridge in the panel. `+inf` did the same, and
`-inf` became 0.0.

That is the worst of the three outcomes available. Propagating would have
shown a NaN on the page; raising would have stopped the scorer; promoting it
to 1.0 reads as a measurement, and reads as the best one.

The route in is `percentile_of`, which returns NaN when the reference
distribution is empty, and the distribution is empty on any host without
BINMAN's atlas. A non-finite component is now absent rather than clamped, so
the weighted mean renormalises over what was measurable, which is what both
`fit` and `apply` already did with a missing value. Two pairs alike except
that one's bridge is unmeasurable now score the same, where before the
unmeasurable one scored 0.75 against 0.5.

An out-of-range value is still clamped, because that is a different thing: a
bridge percentile of 120 is a bug upstream and 1.0 is the right answer for
it.

**And `weights.py` carried its own Mann-Whitney estimator.** Identical in its
tie handling to the one in `layers.py`, and never hardened when F74 hardened
that one. It is the function the grid search maximises to choose the weights,
so a non-finite feature would have biased the weighting itself rather than
one reported number.

The two contracts differ for good reasons and that is kept: the validation
layer reports an absent curve as NaN and refuses to publish, the fitter
returns None and declines that point on its grid. The arithmetic is shared
in `nobble/numeric.py`, with a sweep that fails on a third copy. Sharing the
estimator and splitting the contract is the distinction that was missing:
sharing neither is how one copy came to be hardened and the other did not.

This is the third finding in a row from the same question, which is worth
naming. F74 asked what happens to a NaN in the headline curve. F76 asked how
many other places made the same assumption, and found fourteen. F77 asked
what the surviving numeric code does with one when it is not compared but
scaled, and the answer was worse than either.

## F78. The recovery statistics were computed over values that need not be numbers

`_rmsd` sums squared coordinate differences and takes a square root.
`gemmi.Position` accepts a NaN coordinate, and one NaN anywhere in the sum
makes the result NaN. There was no guard, and every consumer filtered on
`is not None`, which a NaN passes.

What it reaches is wider than a median, and that is the part worth stating.
`pose_recovery` sorts a pair's values and reports `ordered[0]`, the middle
element and `ordered[-1]` as best, median and worst recovery. Every
comparison against NaN is false, so `sorted` leaves the other elements
unsorted too: `[5.0, nan, 1.0, 9.0]` comes back with 5.0 at the front, so
the "best" recovery is not the best of anything. All three are published on
the Benchmark tab, and the median is what `tools/check_prediction.py` scored
F13's predictions against.

`success_rate_curve` had a second shape of the same problem. It filtered on
`is not None` and then counted values at or below each breakpoint. `NaN <=
1.0` is false, so a NaN counted as a failure at every breakpoint while
remaining in the denominator: a pair with one unmeasurable seed would have
reported a lower success rate than it earned, which is a quieter error than
a visible NaN.

**What is demonstrated and what is not.** A NaN coordinate yields a NaN
RMSD, and that NaN reaches the published median: both measured. That a
Boltz-written CIF can carry a NaN coordinate is not demonstrated. An attempt
to read one through gemmi's CIF parser failed on a malformed test file
rather than on the NaN, so the external route is unproven and is recorded
here as unproven. The fix is three lines and the consequence is a published
figure, so it is guarded either way.

The refactor moves nothing. 221 rmsd fields in the published atlas were
compared before and after, and none changed; 112 rmsd values across the
campaigns and the atlas are finite. An unmeasurable RMSD is now None, which
puts it on the same footing as a superposition with too few anchor atoms,
and a pair with nothing measurable is absent from `by_pair` rather than
present with three meaningless numbers.

This is the fourth finding from one question and the last of them: F74 in
the headline curve, F76 across fourteen type checks, F77 in the composite's
clamp, F78 in the geometry that feeds all three. The pattern each time was
not that a NaN appeared, because none ever has, but that the code treated
"not a number" as a number and the failure was silent in a direction that
flattered the result.

## F79. F45 added a parameter and nobody ever passed it

F45's finding was that sizing a campaign from a "representative job" taken
from whichever campaign was measured last is wrong: the per-token rate
transfers between campaigns and the job size does not. It opened Gate G1
falsely at 104.3 hours against a real 54, which is the most expensive thing
that function can do.

The fix added `tokens_per_pair` to `cost_of` and `total_tokens` to
`projected_hours`, and F61 later added `job_tokens` for per-band pricing.
The design arm is the only caller of `cost_of`, in two places, and passed
none of them. So the one surviving caller kept taking the fallback that the
finding was about, with the basis string beside it saying so in full: "a
144-token job, which is the median job of campaign_20261104T004632Z and not
necessarily of the campaign being sized".

It gave the right answer by coincidence. Throughput is currently measured on
the main campaign, whose median job is 144 tokens, and the design scan's
jobs are 144 and 124. Remeasure on the corrected campaign, whose median job
is 397, and the same unchanged scan is projected at 11.5 hours against a
real 4.4. The chain remeasures throughput after every campaign, so that was
one `refresh.sh` away.

The preview now prices the exact job list the assembler would emit, taken
from `build_manifest` rather than recomputed: 240 jobs, 32,960 tokens, 4.4
hours, which is the figure the assembled campaign gives because it is the
same list. Recomputing the token formula in the report would have been a
second copy of `construct.residue_count() + peptide.length + cofactor +
ligand_atoms`, which is the shape this project keeps having to undo.

Found by running the chain's stages against real data after a day of
refactoring, to check nothing had regressed. Nothing had. What showed up was
a basis string describing a weakness nobody had read, which is a reminder
that this project's habit of writing the reason beside the number only
works if someone looks.

A correction to my own diagnosis on the way: the first reading of the design
cost showed `None`, and I took it for a regression from the refactor. The
cost lives under `preview.cost` and my probe read a top-level key that has
never existed. The code was right and the probe was wrong, for the second
time today after the `RECOVERED_A` grep in F64.

## F80. A factor that decides when a refinement is abandoned, written in code

F79 generalises: a parameter added by a fix that no caller passes. Sweeping
for the shape, every optional parameter in `nobble/` against every call
anywhere, positionally or by name, gives twenty-two never supplied. Most are
ordinary configurable defaults and were left alone. Three stated a reason
that nothing exercised.

`settings_from_config`'s timeout carries the comment "Still overridable,
because a test needs to", and no test overrode it. The claim was the
justification for the parameter's existence, which makes it worth either
removing or making true. It is true now.

`cost_of`'s `tokens_per_pair` became dead when F79 wired `job_tokens`
through. It is the one-size form of the same idea and worth keeping, so the
branch that expands it is tested: for a uniform scan the two must agree, or
the simpler form is a trap for the next caller.

`matched_control_roc`'s `statistic` names the curve's whole subject and had
only ever been computed on one field. A test now asks for a curve over
`bridge_percentile` with the deltas deliberately reversed, so the two
statistics cannot agree by accident.

**And the real find, from following the timeout.** Tier 2's timeout was
`job_timeout_seconds * 4`, an inline factor deciding when a refinement is
killed. The existing cutoff sweep looks in comparisons, module constants and
default arguments; F54 added templates as a fourth place; this is a fifth,
arithmetic.

The factor is now `tier2_timeout_multiple` in tuning. What it should be is
not known, and the comment beside it says so. Tier 2 runs 10 recycles
against 3 and 25 diffusion samples against 1. If cost were the product of
those, the slowest tier-1 job observed, 902 seconds, becomes 20.9 hours
against a six-hour bound. If recycles drive the trunk and samples the
structure module, which is closer to how Boltz is built, the two are nearer
additive and four may be generous. I do not know which applies, and tier 2
has never run, so the number is a guess either way.

What makes the guess tolerable is that it fails loudly. A timed-out job is
retried once and then recorded as `timeout after 21600s`, naming the value
to change, so the first tier-2 campaign measures the factor rather than
quietly losing refinements. That property is now a test, because it is the
only reason leaving a guess in place is defensible.

The watchdog's `hard_bound_seconds` derives from the runner rather than
being configured separately, so it follows the multiple: 12.2 hours for tier
2 against 3.2 for tier 1. A bound that did not follow would call a healthy
refinement stalled, which is F20's mistake with a longer fuse.

## F81. The code said "treat this as unverified" and then reported it as ok

`plip.fingerprint` parses the chain map out of cif2plip's stdout rather
than assuming it, because assuming it would attribute every peptide contact
to the receptor. That care is right and the parse works: all twenty real
fingerprints across three campaigns parsed it successfully.

When the parse failed it fell back to the documented A/P/L to A/B/C
ordering and appended two notes, the second reading "Treat this fingerprint
as unverified". Then, at the end of the function, `result.status = "ok"`
unconditionally.

`run.py` branches on `finger.status != "ok"` and knows nothing about
`notes`. So the warning went to a field nothing downstream reads, the
status said the opposite, and the reader of the two was the one that could
not see the warning. The match was recorded as a measurement, fed to the
weight fitter as an observation and shown on the Interactions tab, which is
the state F32 already fixed once for a different cause.

The fallback is correct for three chains. A peptide carrying a structural
zinc gives four, A, P, Z and L, so the ligand is D and the map hands the
ligand slot to the ion: every "glue to degron" contact would have been the
zinc's coordination to the receptor. The Sievers arm is whole zinc fingers,
120 of the campaign's 158 pairs and the arm the headline ROC is computed
on, and those jobs begin at queue position 100. The campaign is at 78.

So this is latent in the sense that it has never fired, and twenty-two jobs
away from the first four-chain input.

There is no fallback now. An unparsed chain map is a refusal, which costs
one component on one pair rather than the component's meaning across the
arm that matters most. The guess was the wrong trade in a way that is worth
stating plainly: a fingerprint that refuses is visibly absent, and a
fingerprint built on the wrong chain is a number that looks like every
other number.

Three probe errors of mine today, this being the third. Looking for the
chain-map notes I read `row["plip_notes"]`, which has never existed, and
concluded the notes were discarded. They are under `row["plip"]["notes"]`.
After the `RECOVERED_A` grep in F64 and the `preview.cost` key in F79, the
pattern is mine rather than the code's: I guess at a field name instead of
printing the keys first, and the guess reads as a finding.

## F82. The four-chain case, and a claim of mine that was too wide

**Corrected below.** The first version of this entry said the four-chain
path "had not been exercised" and tested it against a structure I built by
inserting a zinc into a three-chain benchmark ternary. Both were wrong.
`campaigns/smoke_sievers` holds a real prediction of `sv_neg_ZN346_d5063d`
with chains A, P, Z, L, and `test_plip_ions.py` has been running the
fingerprint and every geometry consumer against it all along. I looked in
`zinc_probe`, found peptide-only predictions, and stopped looking.

What remains true, and is the narrower thing this finding is worth: those
existing tests assert the *consequence*, that the ion stays out of the
fingerprint and out of the bridge metric. Neither fails if the map is right
for the wrong reason. The mapping itself is now pinned, Z to C and L to D,
which is the fact F81's removal of the fallback depends on. The test uses
the real prediction, so the synthetic structure is gone.

## F82 (original text). The four-chain case, verified before the first real one

F81 removed a chain-map fallback that assumed three chains, leaving an
unparsed map as a refusal. That left a question worth answering before the
Sievers arm starts rather than after: does the parse work on a four-chain
job at all? If it did not, the refusal would be correct and the PLIP
component would be absent for 120 of the campaign's 158 pairs.

It works. A real benchmark ternary with a zinc inserted as chain Z between
the peptide and the glue, which is where the assembler puts it, parses as
`{'A': 'A', 'P': 'B', 'Z': 'C', 'L': 'D'}`. The glue is identified as chain
D, the ion's single row is excluded with a note naming D as the glue, and
seven receptor contacts and one peptide contact survive the filter.

So F81's refusal is a floor rather than a change of behaviour, and F14's ion
exclusion is confirmed on a four-chain input for the first time.

The assembler's chain order was read from a real Sievers YAML,
`sv_neg_BCL6B_c2c0a3`, rather than from the comment that asserts it:
protein A, protein P, ligand Z, ligand L, with the ion as a ligand entry
before the glue. That part stands.

The rest of this paragraph was wrong and is kept for the record. It said
the `zinc_probe` campaign did not help, its structures being peptide-only,
and that the test therefore had to construct a four-chain structure. The
first clause is true and the conclusion does not follow: `smoke_sievers`
holds the real thing. Checking one campaign and generalising to all of them
is how a fixture gets built for a case that already had one.

## F83. The ion is a zero target, not a zero source

Delta-ipTM is the receptor-to-peptide ipTM, minimised across the substrate
receptor's segments. Which chain index the peptide occupies is derived from
the construct: receptor segments take 0 upward, then the peptide, then the
structural ion, then the glue.

A three-chain job cannot get that wrong in an interesting way. A four-chain
one can, and the Sievers arm is 2,160 zinc-bearing jobs beginning at queue
position 100.

Checked against the real thing rather than reasoned about.
`campaigns/smoke_sievers` holds both arms of `sv_neg_ZN346_d5063d`, and the
aggregated pair gives `iptm_min_ternary` 0.952 and `iptm_min_binary` 0.856:
the receptor-to-peptide values, not the ion's. The arithmetic is right.

The matrix is asymmetric and that is the part worth recording.
`pair_chains_iptm[i]["2"]` is 0.0 for every row, the ion being a target no
chain has an interface with, while row "2" carries ordinary values, 0.995 to
the receptor and 0.953 to the peptide. So reading the ion where a receptor
segment belongs gives a plausible 0.99 and reading it where the peptide
belongs gives 0.0. The catastrophic direction is the peptide index, not the
receptor set, which is the opposite of where I would have put the guard.

My first version of the test asserted the ion's row was zero as well. It is
not, and the test failed rather than passing on a wrong premise, which is
the one time today that getting it wrong cost nothing.

The arithmetic holds because every zinc-bearing job uses a one-segment
construct, so the peptide is chain 1 and the ion chain 2. That is a property
of this queue and not of the code: all 2,160 are CRBN_CULT, and no
multi-segment construct carries an ion. Asserted, so a Sievers pair on VHL
or DCAF15 fails the test rather than silently moving both indices.

## F84. The mutation harness reported a false all-clear

Found by accident, while mutating something else. An identical find and
replace pair printed "1 of 1 caught".

A mutation whose anchor does not appear exactly once is skipped: the file is
never changed and the suite never runs. That `continue` fell through to a
summary computed as `len(chosen) - missed`, and `missed` was incremented
only for a mutation that actually ran. So a sweep whose anchors had all gone
stale printed "5 of 5 caught" and exited zero.

This is the tool from F66, built because two hand-rolled mutation checks
reached live state, and used for every verification in this project since.
It is also the exact defect it exists to find: correct and incorrect
behaviour producing the same observable result. A sweep that tests nothing
is indistinguishable from a sweep that catches everything.

Skips are counted separately now, named in the summary, and exit non-zero,
because a stale anchor is an unverified mutation rather than a passing one.
The five fixed anchors were checked and none is stale, so no earlier result
in this project rests on it. That is luck: the anchors are string literals
in a file that has been edited all day.

Worth noting what did not catch this. The harness has fifteen tests,
including ones that assert it refuses live state, cleans up on failure and
records a traceback. None asserted anything about its arithmetic, because
the summary line looked like reporting rather than logic.

## F85. Counts inside report strings, and two tests of mine that were wrong

F84's defect was arithmetic in a summary line, untested because the line
read as output rather than as logic. Sweeping for the shape, arithmetic on a
`len()` inside an f-string, gives four sites.

Two are correct and are now pinned rather than re-derived. `runner.py`'s
"N job(s) unrun" uses `enumerate(pending, start=1)` and breaks before
running the job, so at index 1 of 10 it reports 10 unrun, which is right.
`inputs.py`'s "and N more" is guarded by the comparison that keeps it
positive, and a list of exactly the example count now has to say nothing
rather than "and 0 more".

One was wrong and it was mine. `pose_recovery` notes how many benchmark
pairs have no recovery number and explains that their ternary jobs have not
completed. F78 gave that sentence a second cause, by dropping any pair whose
every RMSD was non-finite, and left the explanation asserting only the
first. So a pair whose geometry could not be measured would have been
reported as one that had not run, sending a reader to the queue instead of
to the structure. The two are counted apart now, and a test against the live
campaign checks the counts in the notes account for exactly the pairs
missing.

**Two of my own tests were wrong in the same batch**, both in ways this
project has already named.

The first grepped `layers.py` for the new sentence, which is split across
two lines of an f-string and so never appears contiguously. That is the
string-check failure F50 retired, written again by me in the test for a
finding about untested report logic.

The second was worse, because it failed for everyone rather than passing
wrongly. F84's test drives the harness's success path, and the harness
refuses to start on a file with uncommitted changes, which is correct: it
reads that file as its baseline. So the test passed when I wrote it with a
clean tree and failed in the next full suite run with work in progress. It
skips on that refusal now, naming the file, because the refusal is the
harness working rather than the test's subject failing.

A test that depends on the working tree being clean is a test that fails for
reasons unrelated to what it protects, which is the argument F75 used to
decline writing one at all. I should have applied it here.

## F86. The caveat that has never rendered, driven before it has to

Spec 4.8's composite includes `lysine_reach_exposed_fraction`, and
`weights.py` marks it `NOT_VALIDATED`: BINMAN measured its reach window at
Cb-Cb AUC 0.42 to 0.48 on 369 assayed lysines, at or below chance and
slightly inverted (D-NOB-024).

Reviewing spec 4.2's component for correctness found nothing to fix. The
module is one of the more careful ones: the status defaults to
`not_validated` and carries the AUC figures and the reason, `LYSINE_MAX_ASA`
cites Tien 2013, the exposure threshold is configured, and a single
`lysine_reach_fit` score is marked "deliberately absent" with a pointer to
the decision that removed it.

The fitter's handling is also right, and worth recording because the
alternative looks tidier. It does not exclude the component. It lets the
grid decide and appends a caveat if the component ends up carrying weight,
on the reasoning that excluding a component by hand is a stronger claim
than thirty labelled pairs support, and so is weighting it silently.

That only works if the caveat is read, which is where F81 went wrong for a
different field. This one is read: `about.html` iterates
`weight_fit.caveats`. But the composite has never fitted, so the caveat has
never rendered, and the path from the fitter to the page was established by
inspection rather than by exercise.

It renders. Driven with a synthetic fitted result carrying 0.25 on the
unvalidated component, the About page shows "no validated discriminating
power" and the decision reference. A clean fit shows no caveat block, which
matters as much: a caveat on every fit reads as a disclaimer rather than a
finding, and the UI budget in CLAUDE.md says so.

Worth doing now rather than later because the condition is close. The
composite refuses below eight labelled pairs and has seven positives with no
negatives; the Sievers arm supplies the negatives and starts in 21 jobs.
This is the second thing today checked just before the campaign reaches it,
after the four-chain chain map, and in both cases the cost of being wrong
afterwards is a published number rather than a failed test.

## F87. One real finding, one I claimed wrongly, and the harness told me which

Reviewing spec 4.4's convergence component. Two candidate findings; one
holds and one does not.

**The scale, which holds.** `convergence_score` was
`max(0.0, 1.0 - (result.mean_rmsd / 10.0))`. That 10 decides a published
component of the composite, and it was written inside the expression. The
cutoff sweep looks in comparisons, module constants, default arguments and
templates, so this is the same fifth place as F80's timeout multiple:
arithmetic. It is `scoring.convergence_scale_a` now, and the test that
matters changes the configured value and requires the score to follow, since
a scale that is read and ignored looks identical to one that is used.

The clamp has F77's shape too. `max(0.0, 1.0 - nan/scale)` returns 0.0,
because `nan > 0.0` is false, so a non-finite mean would have become the
worst possible convergence rather than no convergence. That route is closed
upstream by F78 and the filter is now `finite` rather than `is not None`, so
the guarantee is local instead of a property of another function.

**The ipTM minimum, which I claimed wrongly.** `_receptor_peptide_iptm`
filters with `is not None` and takes a minimum, and `min` with a NaN present
is order-dependent: `min([0.9, nan])` is 0.9, `min([nan, 0.9])` is nan. So
the order of a construct's receptor segments would decide whether a NaN
survived into Delta-ipTM. I wrote that up as a gap in the headline path.

It is not a gap. `_pair_iptm` already requires `finite` on each cell, which
was one of F76's fourteen sites, so a non-finite value becomes None one
level up and the minimum never sees it.

What found that was the mutation harness. Reverting the filter to
`is not None` failed no test, which means my test was passing for a reason
other than the one it claimed: the NaN was filtered before reaching the code
under test. Without the mutation I would have published a finding about a
hazard that F76 had already closed, with a test that appeared to prove it.

The change stays, as defence in depth, with the comment saying it is
redundant and why. The write-up says which half the harness confirmed.

And F84 paid for itself inside the hour. The first attempt at this mutation
was skipped, because F76 had made the anchor appear twice, and the harness
said so instead of reporting "1 of 1 caught". Before that fix I would have
read the skip as a pass and kept the wrong finding.

## F88. A day of scoring changes, diffed against the published atlas

F74 through F87 changed the ipTM selection, the Mann-Whitney estimator, the
composite's clamp, the RMSD guard, four median sites, the convergence scale
and fourteen numeric type checks. Each was argued to be behaviour-preserving
on finite data and several were checked individually. This checks all of
them at once, against the thing that matters: what the published atlas says.

Rebuilt from the same campaign into a scratch directory and compared leaf by
leaf. 10,969 values. Two moved, both deliberate:

    design.json.preview.cost.projected_hours   4.2 -> 4.7
    design.json.preview.cost.basis             representative job -> banded

That is F79, the design preview no longer taking the fallback F45 exists to
replace. Everything else is identical, including every RMSD, every ipTM,
every bridge percentile and the whole comparison report.

Three fields are in the published atlas and absent from the rebuild, all
build-time: byte counts and the outstanding-campaign list, which moves as
the queue advances.

**One false alarm, recorded because the reasoning was the useful part.** The
new figure totals 34,720 tokens where I had measured the assembled design
campaign at 32,960, and two token counts for one scan would be the F59 shape
exactly. They are different parents. The atlas's preview is for GSPT1,
chosen from the benchmark campaign's own scores, and the assembled scan is
IKZF1, chosen later from the main campaign. Both are 15-mers and both emit
240 jobs, so the numbers looked comparable and are not: GSPT1 gives 34,720
tokens and 4.7 hours, IKZF1 32,960 and 4.4.

Checking that took one command and the alternative was a finding about a
discrepancy that does not exist. Four of those today, after the
`RECOVERED_A` grep, the `preview.cost` key and `plip_notes`, and the pattern
is the same each time: I compare two numbers without first checking they are
answers to the same question.

## F89. The published scan target was chosen by the method that was rejected

`_default_parent` picks which degron the design arm scans first. It ranks
the candidates by measured Delta-ipTM, "because the degron worth scanning
first is the one with the largest signal to move", and falls back to the
shortest glue parent when nothing is scored so the tab has something before
a campaign runs. Its docstring says plainly why length is the wrong rule:
it "was an arbitrary tiebreak that happened to land on BRD4/VHL: a PROTAC
pair, when the arm is about glue dependence".

`build_atlas.py` never configured a campaign before building the design
report. `data._CAMPAIGN` starts as None, `data.scores()` returns an empty
list when it is None, so the ranking saw nothing scored and the fallback
fired on every atlas this project has ever published. The fix that replaced
length with measurement was inert in the published output.

The chain does configure, so the two disagreed about the arm's headline
choice. The site said the scan target was GSPT1, picked by length. The scan
the chain assembles and will run is IKZF1, picked by a measured Delta-ipTM
of +0.316. One answer on the page and a different one in the queue.

Both now read the same ranking. The published parent is IKZF1 and says
"largest measured delta-ipTM of the scored parents (+0.316): the degron with
the most glue dependence", which is a sentence that can be checked against
the scores it cites. Rebuilt and deployed.

Found by following my own mistake. F88 compared a design cost of 4.7 hours
against a measured 4.4 and I put it down to different parents, which was
true, and stopped there. The question I had not asked was why the atlas was
previewing a different parent from the one the chain assembles, and the
answer was that it had never been asking the measurement at all.

So the cost now names its parent, in the basis string and as a field. Two
15-mers emit the same number of jobs and different token totals, and a
figure without its subject invites exactly the comparison I made.

The wiring test skipped on its first run, because it asked for the latest
scored campaign and that is the main one, whose atlas build correctly
refuses while F47's correction is pending. A wiring test that skips is what
F40 is about, so it drives the benchmark panel instead.

## F90. The fix sat where it was needed, not where it belonged

F89 added a `configure` call to `build_atlas.py` immediately above the
design report, which is the section that was wrong. That leaves every
section built earlier, the benchmark panel and the About page, depending on
not needing the data layer.

Whether that is true was a question worth removing rather than answering.
The call is at the top of `main()` now, where the campaign is resolved, so
nothing is built before it.

It is behaviour-preserving: 11,002 leaf values compared against the
published atlas and none moved, with `benchmark.json` and `about.json`
byte-identical. So those two sections genuinely did not need it, which is
the answer I would have guessed, and guessing was the thing to avoid.

The test checks position rather than presence. A `configure` call somewhere
in the file is exactly what was true while the design report was still
taking its fallback, because the call was below it. So the assertion is
that every write into the bundle happens after the call, and that there is
only one call, since two would make the order matter again.

This is the third time today a fix has been placed at the symptom rather
than at the rule: F74 guarded one of fourteen numeric type checks, F78
guarded one of nine median sites, and F89 configured one of five sections.
Each time the sweep that followed was worth more than the original fix.

## F91. The configured seed count was read by nothing

A sixth place the cutoff sweep does not look. It tests for an `ast.Constant`
holding a number, in comparisons, module constants and default arguments;
F54 added templates and F80 and F87 added arithmetic. A module-level
collection of numbers is none of those, because a tuple of constants is not
a constant.

Four exist. `weights.GRID` and `numbering.ANCHOR_LENGTHS` are search
ladders with their reasoning written beside them, and are left alone. The
other two are the same list: `SEEDS = (1, 2, 3, 4, 5)` in
`curate/manifest.py` and again in `execute/corrected.py`.

`config/tuning.toml` declares `campaign.seeds = 5`, and nothing read it.
Editing it changed nothing, which is the shape this project treats as a
defect wherever it appears: a value computed or configured and then ignored
is indistinguishable from one that was never there.

The count is not an incidental number. Delta-ipTM is a difference of minima
over seeds, and a minimum is not robust to how many draws it was taken
over, which is the reasoning behind the hard partition by sampling tier and
behind the seed-balance report beside the headline curve. It also sets the
campaign's size: 158 pairs times 5 seeds times 3 arms is 2,360 jobs.

Two copies made it worse than one. A corrected campaign emitted with a
different seed count from the benchmark it is compared against would break
that comparison's premise, which is that exactly one variable changed.
`corrected.py` imports the manifest's list now.

Behaviour-preserving: the configured value is 5 and the derived tuple is
identical, so `jobs_per_pair` is still 15 and the live campaign's seeds
still match, which is asserted against the queue rather than assumed.

**Fifth false alarm of the day, and the clearest.** Verifying the change, I
compared the fresh manifest against the assembled queue and found ten extra
jobs, `bench03_BRD4_CRBN` and its scramble gaining a conditioned ternary
arm. I had compared two different stages: the manifest emits both
conditionings for every ternary and the assembler drops conditioned jobs
with no pocket, which bench03 has none of because its ligand has no CCD
entry. The campaign's own metadata records
`conditioned_jobs_dropped_no_pocket = 10`, so the answer was written down at
assembly time in a file I could have read before counting.

## F92. Five false alarms, one command

Five times today I compared a figure against another that looked comparable
and was not.

- A `RECOVERED_A` grep over a served page, where the alternation matched
  class names and `head -4` consumed them before reaching the constant.
- `preview.cost` read as a top-level key, which has never existed, so a
  working projection read as `None` and looked like a regression.
- `row["plip_notes"]`, also never existing, so notes that are kept read as
  discarded.
- A design cost of 4.7 hours against a measured 4.4, which is two parents.
- A fresh manifest's 2,370 jobs against the queue's 2,360, which is the
  manifest before the assembler's pocket filter and the queue after it.

Every answer was already recorded in the project. `campaign.json` carries
`conditioned_jobs_dropped_no_pocket = 10`. `design.json` carries its
parent. The notes are under `plip.notes`. The failure each time was not
reading, and the remedy for that is fewer greps rather than more care.

So `tools/status.sh` has a provenance section now, printing the three facts
that each of those questions turned on: what the assembler emitted and what
it dropped and why, whether any input is stale and therefore whether the
atlas build will refuse, and which degron the design ranking chooses against
which one the site publishes.

The third is the one worth having. Those two disagreed for the whole
project's life and F89 found it by accident; the line marks the
disagreement, and a test feeds it a published file naming a different parent
to check the marker fires, because a line that cannot show a problem is not
worth printing.

The fourth false alarm is also the one that produced a real finding. Asking
why the atlas previewed a different parent from the one the chain assembles
was the question I had not asked, and the answer was F89. The other four
cost time and produced nothing, which is the honest accounting: the same
habit that found one defect manufactured four non-defects.

## F93. One substrate domain moved, and the campaign had not recorded which it used

The corrected campaign exists to test one claim: that a folded domain
recovers the pose better than a 15-mer fragment. Its substrate boundaries
come from an InterPro lookup, and a fix to how an ambiguous entry is
resolved moves them. `campaign.json` recorded `campaign_id`,
`compare_against`, `created_at`, `jobs_emitted`, `pairs` and `purpose`, and
not which domain any job used.

One has moved. `corr05_CSNK1A1_CRBN` submitted a 269-residue domain; the
plan now specifies 219, P48729 17-235, with the shorter sequence a strict
substring of the longer. Five of the seven pairs match the plan exactly and
IKZF1 is a 15-mer control by design, so this is isolated rather than
systematic.

It reaches the headline. CSNK1A1 is one of the six pairs in the published
`improved` list, 12.24 angstrom to 6.189, and the published substrate plan
beside it is recomputed at atlas-build time and so describes the 219-residue
domain. A reader matching the plan against the result would have been
matching a plan to a measurement of a different construct.

`stale_inputs` could not see it. That check compares a YAML against the
queue row beside it, and both were written by one assembly, so they agree
about a boundary that has since moved. The comparison that matters is
against the plan, which is what `superseded_substrates` does.

The caveat is on the conclusion, not only in the per-pair table, for the
same reason the incomplete one is: the sentence is the line that gets
quoted. It says the measurement stands and describes a different construct
from the plan beside it, because the number is not wrong and saying so
would be a different and false claim. Which of the two domains is right is
a question about the kinase rather than about the code, and this finding
does not answer it.

Two mistakes of mine on the way, both caught.

The first was comparing the longest sequence in each YAML against the plan,
which reads the receptor for most pairs: five of seven appeared to match no
current domain. Found by the result being implausible rather than by a test,
and the fix is to read the chain whose id is P.

The second the cutoff sweep caught on its next run. My own guard used
`len(submitted) < 30` to tell a 15-mer from a domain, which is a number in
an expression deciding what counts as a domain. The distinction is in the
data: the fragment arm submits the curated 15-mer, so it is identified by
matching those sequences. A degron is a slice of the domain it sits in, so
without that every fragment would have been reported as superseded.

## F94. The preventive half, and what the recorded plan showed

F93 found that one substrate domain had moved and that the campaign had not
recorded which domain it used. That is two problems and F93 only fixed the
detection: `superseded_substrates` compares a campaign's YAMLs against the
plan, so the next move is caught, but a campaign still recorded nothing to
be checked against.

`corrected.assemble()` records the plan now: gene, E3, mode, accession, the
InterPro or PFAM entry the boundary came from, and the range. The entry is
the part that matters, because without it a reader cannot tell whether a
boundary changed or a different entry was chosen for the same gene.

Writing it down showed something the comparison had not. Five of the six
folded domains resolve from an InterPro entry, IPR054696, IPR001487 twice,
IPR000504 and IPR000719. CSNK1A1 resolves from PF00069, a PFAM accession,
and CSNK1A1 is the one whose boundary moved.

That is a signal and not a cause, and it is recorded as a signal. It does
not establish that the sourcing is why the boundary moved, and it is where
someone deciding which of the 269 and 219 residue domains is right should
start. The test pins the set of PFAM-sourced domains at exactly CSNK1A1, so
if another gene joins it the question arises again rather than quietly.

The plan is published as the plan rather than as the campaign's record, and
that is left alone deliberately. `build_atlas` recomputes it, which is
correct for a document that describes what the plan says; the comparison
beside it now carries the caveat naming the pair whose construct differs.
Together those are honest. Replacing the published plan with a campaign's
recorded copy would describe a past run as though it were the current
intent.

My own habit again, and the one F92 was about. The first version of the
recorded plan read `pair_id` and `substrate.gene`, neither of which exists:
the gene and the E3 are top level and the substrate carries the accession,
entry, range, length, mode and reason. Printing the keys took one command
and I wrote the guess first, which is the seventh time today.

## F95. A sweep that found nothing, and why it is kept

Seven times today I read a field that does not exist: `preview.cost` as a
top-level key, `row["plip_notes"]`, `pair_id` and `substrate.gene` on a
plan entry, and others. Each returned None and None read as a finding until
I checked. The habit is mine, but the same mistake in production code is
decidable, so I swept for it.

The general form is not decidable. 94 string keys are read in `nobble/` and
never written there, and almost all are legitimate: TOML section names,
BINMAN store columns, an environment variable. A sweep reporting those is a
list to ignore, which is worse than no sweep.

The configured subset is decidable, because the file exists and can be
opened. Every `paths.thresholds()` and `paths.tuning()` chain in the
project, 89 of them, resolves to a key the TOML actually holds.

So this found nothing and is kept, which needs a reason rather than an
instinct. Read with `["key"]` a missing key raises on the first call, which
is loud and gets fixed in a minute. Read with `.get("key")` it returns None
silently, and None then flows into whatever the value was for: a threshold
that is None compares false against everything, a scale that is None raises
somewhere unrelated, a device that is None is handed to Boltz as a string.
Both forms are swept, because the point is that the key is real rather than
which form reads it.

It is also the other direction of F91. That found `tuning.campaign.seeds`,
a key the file held and nothing read. This checks for a key Python reads
and the file might not hold. The two together are the pair of questions
worth asking of a configuration, and only one of them had an answer.

Mutation-checked both ways: a typo'd key read by index and the same typo
read through `.get` are each caught.

## F96. The caveat existed and had not reached the page

F93 put the superseded-substrate caveat on the comparison's conclusion,
because that sentence is the line that gets quoted and CSNK1A1 is one of
the six pairs in the improved list. The caveat was written, tested, and
committed.

It was not on the page. `comparison.json` is built by the atlas and the
atlas had not been rebuilt since, so the published conclusion still ended
at "Bridge formation agrees and is independent of the crystal". Both the
live site and the local bundle: the caveat existed in `compare.run()`'s
output and in nothing a reader could see.

That is the same shape as the thing it was written to fix. F81 found a
warning in `notes` that nothing downstream read; this is a warning in a
function's return value that nothing downstream had rebuilt. A caveat that
has not been published is not a caveat, and the test that proved it renders
was passing against a freshly computed report rather than the deployed one.

Rebuilt and deployed. The live conclusion now carries it.

Found by re-running the chain's six stages end to end, which was the point
of doing that rather than trusting the unit tests: scoring, validation,
tier 2, the comparison, the design report and the atlas all still run after
a day of changes to eight modules, and the one thing wrong was something no
test could have caught, because it was a fact about the deployed artefact
rather than about the code.

The gap this leaves is worth naming. Nothing checks that the published
atlas was built from the current code. F88 did it by hand, diffing 11,002
leaf values after the scoring changes, and found two deliberate moves. That
check is not automated, and a caveat added to a report is exactly what it
would catch.

## F97. The gap F96 named, closed

F96 ended by naming what it could not fix: nothing checks that the
published atlas was built from the current code. F88 had made that check by
hand, diffing 11,002 leaf values after a day of scoring changes, and F96
was the case it would have caught, a caveat present in the code's output
and absent from the page.

`tools/atlas_drift.py` is that comparison as a command. It reads the
campaign the published atlas names, rebuilds into a temporary directory,
and compares leaf by leaf: 11,008 values, four seconds, 25 MB of scratch.

`deploy.sh` runs it before the rsync and refuses on drift. Refusing rather
than rebuilding, and the reason is worth stating: a deploy that silently
rebuilds publishes something nobody looked at, and the rebuild is one
command whose output an operator should see. The message names that command.
`tools/status.sh` reports it too, because a drift found at deploy time is a
refused deploy and a drift found in status is a rebuild.

The exclusion list is where this check could go wrong in either direction.
`built_at`, byte counts, `jobs_done` and the outstanding-campaign list move
on every build by design, so counting them would make the check fire always,
which is the same as never firing. Excusing too much is the opposite
failure, so a second test asserts that `redactions`, `redacted_ligands`,
`conclusion`, `median_rmsd` and `auc` are not covered by any exclusion:
F72's redaction count was misreported and must never be waved through as a
build-time fact.

The control is the F96 case itself. The test strips the caveat from the
published conclusion, confirms the check reports drift and names
`comparison.json.conclusion`, restores the file, and then confirms the
check reports "in step" again, so a control that failed to restore would
fail loudly rather than leaving the atlas edited.

Both mutations caught: a volatile list that swallows everything, and a
comparison that never reports a difference. The second took long enough to
run in the background, because each mutation rebuilds the atlas.

## F98. A decision already made, and its premise checked instead

The Sievers fingers carry `msa: empty`. D-NOB-029 gives folded-domain
substrates an MSA and a C2H2 finger is a folding unit, so the question of
whether the arm should get one looked open. It is not: D-NOB-035 decided it,
and the recorded reason is stronger than the concern I was forming.

The reason is the ROC rather than the cost. Alignment depth would not be
distributed evenly across the two classes the headline curve separates. The
matching that built the arm matched on length and amino-acid composition, not
on how well studied the parent protein is, so if the degraded set came
systematically from better-characterised genes then MSA depth would correlate
with the label and the curve would partly measure homology. D-NOB-034 covers
the folding half: what a C2H2 finger needs to fold is its zinc, and it has
one.

What was missing is that nobody had checked the arm against that description.
The argument rests on three facts, and all three hold in the assembled queue:

| | pairs | distinct genes | length median | length range |
|---|---|---|---|---|
| degraded | 24 | 24 | 23 | 23-26 |
| not_degraded | 96 | 86 | 23 | 23-26 |

Composition is matched to within two percentage points on every class:
cysteine and histidine 0.191 against 0.195, basic 0.188 against 0.179, acidic
0.048 against 0.054, hydrophobic 0.294 against 0.273. The gene asymmetry the
argument turns on is real and is the sharpest part of it: every degraded
finger is its own gene, while the 96 controls come from 86, so "better
studied" has room to track the label in exactly one direction.

No change made. `tests/test_sievers_matching.py` pins the four numbers, the
`msa: empty` on the peptide chain, and the presence of the decision with its
reason, because a decision is only as good as its premise and an arm whose
classes stopped being matched would need the question reopened. Recorded
rather than fixed, on F75's precedent: the next reader to notice a folding
unit without an alignment will otherwise rediscover this as a hypothesis.

## F99. The confidence and the structure came from different poses

Tier 2 has never run. It is ten jobs at the end of a fifty-hour campaign, at
ten recycles and twenty-five diffusion samples with potentials on, and the
cheap thing to check was whether its Boltz invocation is even valid. It is:
`--recycling_steps`, `--diffusion_samples` and `--use_potentials` are all
real options in the installed Boltz. The defect was one layer down.

Boltz writes one structure and one confidence JSON per diffusion sample,
ranked rather than indexed: `argsort(confidence_score, descending)` puts the
best model at `_model_0`. At one sample there is one of each. At twenty-five
there are fifty files, and `_read_outputs` asked for the two by different
rules. The structure came from `*_model_0.cif`, sorted. The confidence came
from the first hit of `rglob("confidence_*.json")`, which is directory order
and nothing else.

Replaying the old function against a freshly written twenty-five sample
directory: structure rank 0, confidence rank 14. Not creation order, not
alphabetical, just what APFS handed back. Every one of the ten tier-2 jobs
would have recorded one pose's ipTM beside another pose's bridge
percentile, PLIP fingerprint and RMSD, and the pairing would differ between
machines. Delta-ipTM is the tier-2 headline and is a difference of two
ipTMs, so both would have described a structure nobody scored.

The fix is not to sort the confidence glob. The confidence is now derived
from the chosen structure's own filename, `confidence_<structure stem>.json`,
which makes the mismatch unrepresentable rather than merely unlikely. When
that file is absent the function returns no confidence and a reason saying
which of the two failures happened, and the caller puts the reason in the
retry detail instead of the old fixed string: "no confidence JSON written"
and "a structure whose confidence JSON is missing" are different problems
and the manifest should record whichever is true. Several confidence JSONs
with no structure is a refusal, on F81's precedent.

The replay also exposed a second flaw, in code I had just written as well as
in the old version. The ranks are not zero-padded, so a sorted `*.cif`
fallback puts `_model_10` ahead of `_model_3`: with ranks 0 to 2 missing it
scored rank 10 while ranks 3 to 9 sat in the same directory. Structure
choice is now by numeric rank, preferring this job's own files, mmCIF over
PDB, a ranked model over an unranked one, with the name as the tie-break so
the choice does not depend on directory order either.

Tier 1 is unaffected, which is worth stating precisely rather than
reassuringly: at one diffusion sample each pattern matches exactly one file,
so old and new pick the same pair, and two tests hold that, one on a
synthetic single-sample directory and one on a directory Boltz actually
wrote during this campaign. The long-lived tier-1 runner is still holding
the old module in memory and does not need restarting for that reason.
`tools/tier2.sh` spawns a fresh `nobble.execute.runner --tier 2`, so the fix
reaches tier 2 without touching the campaign in flight.

`tests/test_sample_pairing.py` builds the twenty-five sample layout the
pipeline has not yet seen rather than waiting fifty hours to meet it, and
asserts the property rather than the ordering: for every rank, the
confidence returned is the one named after the structure returned, and the
structure is the best rank still present.

## F100. The one number sized for the smallest job and applied to the largest

Tier 2 runs after the campaign and has never run. Its time limit was
`job_timeout_seconds * tier2_timeout_multiple`, the multiple was 4, and the
config comment said so plainly: "4 is a guess rather than a measurement, and
it is the quantity most likely to abandon a refinement that was working. The
first tier-2 campaign measures it." The first tier-2 campaign is the one that
would be lost, so I tried to measure it without running it.

BoltzMaker has 146,761 recorded runs with `recycling_steps`,
`sampling_steps` and `duration_seconds` fields, which looked like exactly
the data needed. Every one of them is null: BoltzMaker ran at defaults
throughout, and the 146,749 rows in its web registry are upload records with
no timings at all. There is no measurement of the scaling anywhere, which is
worth writing down so the next person does not search for it twice.

It can be bounded instead. Boltz runs the trunk once per recycle and the
structure module once per diffusion sample, so tier 2 against tier 1 is 10/3
on one part and 25/1 on the other. Applying both ratios to the whole tier-1
time and adding them double-counts on purpose: the result is above the true
weighted sum for any split between the two, which a test checks at five
splits from all-trunk to all-diffusion. An allowance covers potentials,
which are off at tier 1 and on at tier 2 and so appear in neither ratio.

Against the live campaign the guess turned out adequate, and only because of
which pair the decile happened to pick:

| pair | tokens | worst tier 1 | bound | headroom |
|---|---|---|---|---|
| bench06_RBM39_DCAF15 | 1223 | 918s | 7.2h | 0.83x |
| bench02_BRD4_VHL | 454 | 166s | 1.3h | 4.58x |
| bench07_CDK12_DDB1 | 357 | 130s | 1.0h | 5.88x |
| bench03_BRD4_CRBN | 173 | 81s | 0.6h | 9.42x |
| bench01_GSPT1_CRBN | 155 | 76s | 0.6h | 10.00x |
| bench05_CSNK1A1_CRBN | 143 | 74s | 0.6h | 10.28x |
| bench04_IKZF1_CRBN | 144 | 74s | 0.6h | 10.35x |

Six pairs have between 4.6 and 10 times the headroom they need. The seventh
has 0.83, and it is not an outlier to be tuned away: DCAF15 is a declared
exception to the token cap, 1,223 tokens by construction because the receptor
has to be the DCAF15, DDB1 and DDA1 assembly, and it is in the benchmark by
design. The selection currently holds `bench02_BRD4_VHL`, chosen from six
scored pairs. It is reselected on the full campaign, and `bench06` is
currently running its tier-1 jobs.

Each refinement now carries a budget in the queue, sized from its own pair's
measured tier-1 cost with the configured cap as a floor, and the runner reads
it. `bench02` keeps the 6.0 hour floor because its bound is below it;
`bench06` gets 10.8 hours instead of being killed at 6.0 while on course.
A pair with no measured tier-1 cost gets the floor.

The second half is the retry. A timeout was retried, so a job whose budget
was too small spent it twice: at the old setting, twelve hours per job across
ten jobs, for an outcome the first attempt had already decided. The budget is
now per job rather than per attempt, which makes a crash retry with the
remainder and leaves a timeout nothing to retry with. That is a trade-off
rather than a pure win and is recorded as D-NOB-060 with the recovery it
gives up.

Two things are worth separating here. The budget is a correction. The retry
is a judgement, and my first version of it was more confident than the
evidence: I inferred "the budget is spent" from elapsed wall clock, which is
true in practice and leaves the reason to be read off the clock. A test I
wrote caught it, because a stubbed runner returns instantly and the retry
fired. The timeout branch now breaks and says why.

## F101. The exclusion list handled the source and not its consumers

F97 added the atlas drift check and argued, in its own write-up, that the
exclusion list is where it could go wrong in either direction: "counting
them would make the check fire always, which is the same as never firing."
The list excludes `throughput`. It does not exclude the values computed from
throughput, which is one line away in the same tuple.

Thirteen jobs later the check reported 63 drifted values. Every one was a
design preview's `cost.basis` or `cost.projected_hours`, moved because the
campaign had remeasured its token bands: the 800 to 1600 token band went
from 0.663 to 0.7375 seconds per token as the DCAF15 jobs completed, and the
representative job from 144 tokens at 66.8s to 155 at 72.2s. Nothing was
wrong. The atlas was in step on everything that is not a function of
timings, and the check said "DRIFTED from the code: 63 value(s)".

The consequence is the one F97 named. `deploy.sh` refuses before the rsync on
drift and `status.sh` reports it, so both would have fired continuously for
the length of every campaign. Worse for the signal: the report prints six
rows and then "and 57 more", so a real difference would have arrived
somewhere in the 57. The drift F96 was, a caveat missing from the published
conclusion, is exactly that shape.

This is the third instance of the same habit in this project and the first
in my own code from an hour earlier. F74 guarded one of fourteen numeric
type checks, F78 one of nine median sites, F89 configured one of five atlas
sections. Here the source is excluded and its consumers are not.

The fix is not a wider exclusion. A cost that moved for a reason other than
new timings is worth seeing, and F97's own test asserts that `redactions`,
`redacted_ligands`, `conclusion`, `median_rmsd` and `auc` are not excused.
So drift now comes back in two categories: `moved`, which needs explaining
and fails the check, and `recomputed`, which is counted and reported and
does not. The check reads "in step, 11008 leaf values compared, 63
recomputed from new timings".

The category is matched on the whole leaf name, `.cost.basis` and
`.cost.projected_hours`, rather than on a substring, because "cost" would
swallow anything with cost in its path. A test holds that each pattern is a
full leaf name and that the science fields cannot be filed under new
timings, which is the same guard F97 wrote against the first category,
applied to the second.

The control is the one that matters: with sixty-odd costs legitimately
moving, strip the caveat from the published conclusion and the check must
still report `comparison.json.conclusion`, fail on it, and print it in the
first six rows rather than the 58th. It does, and the file is restored with
a check that the restore worked.

## F102. Boltz calls the structural zinc the ligand too

F81 dealt with PLIP perceiving every het group as a ligand. Boltz does the
same thing one level up, in a confidence field, and that one had not been
looked at.

The main campaign reached the Sievers arm at job 100. The first completed
result,
`sv_neg_ZN346_d5063d__binary__unconstrained__seed1`, reports `ligand_iptm`
0.9946. That is exactly `pair_chains_iptm["2"]["0"]`, the structural zinc's
row, and the job is the binary arm: there is no glue in it at all. Across
the 120-pair Sievers arm the field would describe the finger holding itself
together, on both arms, which is the measurement D-NOB-034 added the zinc to
make possible rather than anything about the glue.

Nothing reads it, which is why nothing is wrong. It is recorded in
`scores.jsonl` and is not in the published atlas, the app, or any template.
So this is a note, not a fix: the field stays as a record of what Boltz
reported, with a comment at the field saying what it means on a job carrying
a cofactor, and a test that fails if any module in `nobble`, `deploy`,
`tools` or `qc` starts reading it. Wiring it to a glue panel would otherwise
ship a plausible number, and 0.99 is exactly the sort of plausible.

Two things were verified rather than assumed while looking at this, on real
output rather than on fixtures.

The zinc is present in the binary arm. The completed structure has chains A
at 109 residues, which is the CULT domain's 318-426, P at 26, and Z holding
one ZN. D-NOB-034's requirement is that a cofactor appears in both arms or
neither, and preflight checks the YAMLs; this is the prediction.

`pair_chains_iptm` is not symmetric, and more so than the smoke test
suggested. A to P reads 0.8561 and P to A reads 0.9274, against the 0.876
and 0.840 recorded in `_pair_iptm`'s docstring. The zinc's column is 0.0 in
all three rows and its row is 0.9946 and 0.9019, so a consumer reading one
direction would get either a near-perfect score or a zero for the same pair
of chains. `_pair_iptm` already symmetrises on the minimum, for the reason
spec 4.3 gives for seed aggregation, and `iptm_receptor_peptide` for this
job is 0.8561: the conservative direction, over receptor chains only, with
the zinc's zero column and high row both outside it.

## F103. The RMSD nobody had checked was comparing the right residues

The live site reports a median pose RMSD of 17.14 angstrom and 0 of 65 poses
within 3 angstrom. That is a positive control failing, so it is either Gate
G6 or a measurement bug, and the second had to be ruled out first.

Three hypotheses, taken in order of how much damage each would do.

**The frame is broken.** It is not. The detail rows carry
`receptor_anchor_atoms` and `receptor_rmsd`, and the first pair reads 436
atoms at 1.751 angstrom. The receptor superposes.

**The reference chains are different copies in the asymmetric unit.** A
peptide from one copy compared against a receptor from another would be tens
of angstrom away and consistent across seeds, which is exactly the observed
pattern: bench07's ten seeds span 44.28 to 45.23, agreeing with each other
to within an angstrom while sitting 45 angstrom from the reference. Ten
independent diffusion runs do not agree to an angstrom on a wrong pose. They
agree because the error is in the reference, not the prediction.

Measured, in all seven depositions, as the minimum interatomic distance
between the named receptor and substrate chains: 2.51, 2.80, 2.68, 1.84,
2.71, 2.74 and 1.90 angstrom. Every pair is a genuine interface. The
hypothesis is wrong.

**The window is mapped onto the wrong stretch.** The correspondence crosses
two independently resolved frames, and the function's own docstring says
"getting this wrong produces a confident RMSD against the wrong residues".
Checked by comparing residue identity for every matched position across all
seven: `CLVDKKSGEKSKTRP` against `CLVDKKSGEKSKTRP` for GSPT1, whose frame is
138 residues from canonical, and the same for the other six. The
correspondence is right.

So the measurement is sound and 17.14 angstrom is a real number about a real
thing. It is also a number the project had already explained and the site had
already labelled: F6 diagnosed it as the cost of cutting a 15-mer out of a
folded domain, the corrected campaign re-ran six pairs as whole domains, and
the published benchmark page puts the two side by side with IKZF1 named as
the control that keeps its 15-mer in both. No gate. The question had been
asked and answered, which is the second time in this session that checking
beat escalating.

**The gap was that none of it was asserted.** The docstring warned about the
failure, three layers of frame resolution guarded against it, and no code
compared a single residue. A frame that resolved wrongly later, against a new
deposition or a changed accession, would produce a confident number on the
layer that decides whether the positive controls work.

So the residues are now compared, and the RMSD is withheld when too few
agree. The control shifts the substrate frame by fifty residues and confirms
the RMSD is refused; the receptor anchor is untouched in that test and still
superposes under 5 angstrom, which is the whole reason the peptide identity
had to be the thing that caught it.

**My first version of the check was wrong, and real data caught it.** It
required exact equality. Run against the corrected campaign, CDK12 refused:
294 residues matched, receptor anchored at 0.956 angstrom, and 293 of 294
identical. The one difference is a K where 6TD3's construct carries an R,
sequence variation between the crystallised protein and UniProt Q9NYV4.
Exact equality would have discarded a correct measurement of the pair whose
recovery F13 made a recorded prediction about. The floor now lives in
`thresholds.toml` at 0.9, which separates variation from misalignment by a
wide margin: a misaligned window agrees at chance, around 5 per cent, and
the seven real ones agree at 1.0, 1.0, 1.0, 1.0, 1.0, 1.0 and 0.9966. A
difference above the floor is reported in a note naming the positions and
the RMSD stands.

Measured while there, the corrected campaign's first-seed recoveries:
GSPT1 1.118, BRD4/VHL 1.46, BRD4/CRBN 16.152, IKZF1 5.357, CSNK1A1 6.122,
RBM39 0.659, CDK12 2.367. Three pairs under 1.5 angstrom against a 15-mer
panel where nothing came within 5.

## F104. Two labels that described the wrong data, and a measured bound

Two small things in published fields, found by reading what the pipeline says
about itself while the campaign ran.

**The throughput note named an arm it was no longer measuring.** It read
"Measured on the benchmark panel", unconditionally, as a literal. That was
true for the first hundred jobs of the main campaign and false from job 100,
where the Sievers arm begins. At 120 timed jobs the measurement spanned two
arms whose per-job cost differs by a factor of twenty six, a Sievers binary
being 136 tokens in 35 seconds against a DCAF15 ternary at 1,223 tokens in
915, and the note still named one of them.

It matters because which jobs a rate came from is the whole of F45: a rate
measured on one job-size mix and applied to another projected a 37-hour
campaign at 104 hours and opened Gate G1 on a run that was inside budget.
The note is published in the atlas, where `throughput` is excluded from the
drift check, so nothing would have caught the label going stale. It now
counts the arms it measured: "Measured on 100 benchmark job(s), 21
sievers_zf job(s)", with a `measured_on` field carrying the counts, and a
job with no arm counted as unlabelled rather than folded into one.

**The weight fit was silent about a comparability it inherits.**
`delta_iptm` is `iptm_min_ternary - iptm_min_binary`, and D-NOB-023 states
the principle exactly: a minimum is not robust to sample count, and drawing
more can push it down and never up. That decision applied it to diffusion
samples and partitioned tier 1 from tier 2 to stop the two mixing.

The same argument applies within tier 1, and there it had not been looked at.
Every regular pair submits 5 binary unconstrained jobs and 10 ternary ones,
5 conditioned and 5 unconstrained, so `iptm_min_ternary` is a minimum over
ten draws and `iptm_min_binary` over five, for every pair in the campaign.

Two separate questions, and they have different answers.

Does it bias the headline ROC? No, and for two reasons. The shape is
identical across all 120 Sievers pairs, so any order-statistic offset is a
constant applied to both classes, and an AUC is rank-based and invariant to
that. Beyond which, `matched_control_roc` already refuses on uneven seed
counts, in both directions: "uneven within a group: some pairs contributed
fewer seeds than others, so their minima are not comparable", and "uneven
between groups". The check I was converging on was already built.

How large is the effect anyway? Measurable now, on the first Sievers pair to
complete all fifteen jobs. Its conditioned ternary minimum is 0.9425 and its
unconstrained one 0.9411, so folding both into a single minimum moves the
ternary term by 0.0014, against a `delta_iptm` of 0.179. The two
conditionings agree closely, which is the condition spec 4.7 already checks
for its own reasons, and that agreement is what makes the count asymmetry
negligible rather than merely constant.

What was missing is that the weight fit, which spec 4.8 deliberately does not
scope to the Sievers arm, inherits the panel's irregular pairs and said
nothing about them. Two of 158 have 5 ternary rather than 10, one benchmark
and one scramble, because their conditioned arm was dropped for having no
pocket: the same ten jobs `campaign.json` records as
`conditioned_jobs_dropped_no_pocket`. The fit now reports its seed-shape
composition and caveats a non-modal shape, computed before the
minimum-labelled floor can return early so it is readable while a campaign
is still filling. Reported rather than refused, because two pairs out of 158
do not move a weight searched on a five-point grid, and narrowing the fit
would use less data than the spec asks for.

Verified on real output while there, now that the arm is running: the
four-chain path produces what it should. The first completed Sievers ternary
carries chain A at 109 residues, P at 26, Z holding one ZN and L holding one
Y70, with a four by four pair matrix. The path was checked ahead of itself in
F82, F83 and F86; this is it running.

## F105. Three layers all asserted the same thing and none of them read it

The design page ranks variants, and a ranked list reads as a recommendation
whatever the caption says, so the caveat beside it carries weight. It said the
composite score is not validated. That is true today. It was asserted in three
places and derived in none, so it would have gone on being said after it
stopped being true.

**The field.** `score_validation` exists to carry the matched-control ROC's
real status, and read `data/atlas/validation.json`. That path has never
existed: `data/atlas` is an empty directory, and the layer statuses live in
the campaign, which is where `build_atlas` reads them for everything else,
including the correlation twenty lines further down. Guarded by
`if validation_path.exists()`, so it fell through silently on every build
since it was written, and `{}` is what the failure and an honest "nothing to
report" both look like.

**The string.** The caveat was a Python literal: "the matched-control ROC
reports not_computed until the Sievers arm runs". It is published, and it
becomes false the moment the Sievers arm finishes, which is the moment the
project's headline result arrives. The design page would have gone on saying
the score is not validated while the curve that validates it sat one file
away.

**The template.** `design.html` checked `design.caveat` and then rendered a
sentence of its own: "The composite is not validated yet, so read the
ordering of positions, not the absolute lift." So the derived sentence, had
there been one, would have been computed, published and never shown. This is
the layer that actually reaches the reader, and it was the one furthest from
the data.

F96 was a caveat that never reached the page. This is a caveat that reaches
the page and could not change, three times over, in the one panel whose job
is to stop a scan being read as a prediction.

Now: the status is read from the campaign, with the published atlas as a
fallback and an unreadable status falling back to "not validated" rather than
to silence, because that is the safe direction for a page that ranks things.
The sentence is derived from it and names the AUC and its confidence interval
when there is one. The template renders that sentence. The layer's own reason
can run to three lines, so it stays in `score_validation` where a reader of
the JSON finds it, and the panel keeps to 20 words against a budget of 40.

**Two mistakes of my own, both caught by reading output rather than by a
test.**

`build` already had a local named `campaign` holding the campaigns directory,
assigned before the validation lookup. The argument I added was shadowed, so
a campaign passed in was silently replaced by `campaigns/` and could never
have been read. Visible only because the diagnostic I had just added printed
the paths it searched, and the first one was `campaigns/validation.json`.

Then the diagnostic recorded resolved paths, which published
`/Users/<name>/Documents/...` into `design.json` and made the value depend on
how the build was invoked: the chain passes a relative campaign path and the
drift check passes an absolute one, so the same campaign produced two
different bundles and the drift check could never settle. Both now relative
to the project root.

That second one is worth a check of its own, and did not have one.
`build_atlas` verifies that no PROTAC-DB chemistry reaches the bundle,
because spec 2.1 requires it. Nothing verified that the bundle carries no
local filesystem paths, which is the other thing a build leaks by accident
and which puts a home directory on a public page.
`tests/test_no_local_paths_published.py` checks every published JSON for
`/Users`, `/home`, `/private/tmp`, `/var/folders` and the project root
itself, and holds that a relative and an absolute campaign argument produce
the same bundle.

The atlas was rebuilt from the campaign it names, `benchmark_20261103T192126Z`,
and the drift check reports in step across 11,014 leaf values.

## F106. Two name spaces for five components, and only one layer knew

The composite has five components, and they have two sets of names. The
fitter names each after the column it reads; the UI names each after the
signal its slider is labelled for. Four agree exactly:
`bridge_percentile`, `delta_iptm`, `convergence_score`,
`plip_fingerprint_match`. The fifth does not. `weights.CANDIDATES` carries
`lysine_reach_exposed_fraction`, because the value is a fraction derived from
the score row's `lysine_reach` object, and `data.COMPONENTS` is keyed
`lysine_reach`.

So a join by key loses exactly one component of five, and the join was
`fitted_w.get(key, meta.default_weight)`, which turns the miss into a
plausible number: the lysine slider would have shown 0.0 as though the fit
had chosen it, on the one component the project separately flags as having no
validated discriminating power.

This was already found and already fixed, in one of the two places that do
the join. `campaign.html`'s JavaScript builds a `FITTED_ALIASES` map and
resolves through it, with a comment saying "without the alias the fitted
weight lands on no slider". The Jinja that renders the same slider's initial
`value=` three hundred lines above did not. So the two layers disagreed about
how to resolve a name, only one of them was right, and the right one was the
one that ran second and overwrote the other. The user-visible symptom was
already gone; what remained was a correct answer that depended on JavaScript
running after a wrong one.

It had not bitten and could not yet: the fit needs the Sievers matched set
and reports `not_fitted` with no weights at all, so the far side of the alias
has never held a value. It would have bitten when the fit lands, which is the
end of the campaign.

The map now lives in `data.py` with a `fitted_weight()` function beside it,
the route passes both, the Jinja calls the function and the JavaScript is
served the map rather than carrying its own copy. One definition, two
consumers, which is the arrangement that makes the two unable to disagree.

Three of the tests are the invariant rather than the instance: every UI key
resolves to a fitter candidate, every candidate is reachable from some UI
key, and the mapping is one to one, so a component added on either side with
a name the other does not use fails here rather than rendering a default.
A fourth holds that an alias mapping a key to itself is rejected, since that
is noise that hides a real one. One checks that a fitted zero survives,
because zero is a decision and `or` would have replaced it with the default.
And the last renders `/campaign` with a fitted lysine weight injected, which
is the state that has never existed, and asserts 0.25 reaches the slider's
server-rendered value.

Found by sweeping the templates for sentences that assert a state rather than
deriving it, after F105 found one. That sweep's own result is worth recording:
`about.html` branches on the real layer status in all three places it reports
one and renders `{{ roc.get('status') }}`, `{{ split.get('status') }}` and
`{{ recovery.get('status') }}`; `campaign.html` branches on `meta.trust`; and
the one remaining literal, ProtCID's veto being not computed, is a permanent
fact rather than a state. So F105 was a single instance and not a class, and
this is what the sweep turned up instead.

## F107. The open question was a bug, and the evidence was in the crystal

PROGRESS listed one question as explicitly unanswered: which CSNK1A1 domain
is scientifically correct, the 269 residues the corrected campaign submitted
or the 219 the plan specifies. F93 recorded it as a boundary that moved and
said so plainly: "which of the two domains is right is a question about the
kinase rather than about the code, and this finding does not answer it." It
put a caveat on the published conclusion and left it there.

It is a question about the code.

`domain_context()` returns every annotation enclosing a degron, and
`benchmark_substrate_constructs` submits `domains[0]` as the substrate when
the 15-mer cannot fold alone. That list arrived in InterPro's response order
and was never sorted. So the submitted construct depended on how the API had
ordered its records, and the proof is in the repository: the library manifest
records CSNK1A1's note naming **IPR000719**, and the same call today returns
**PF00069** first. The boundary did not move because anyone changed a lookup.
It moved because an unordered list was read by index.

**The kinase question has an answer, and three independent lines agree.**

PF00069 gives 17-235 and IPR000719 gives 17-285 for a domain both of them
call "Protein kinase domain". PFAM is one member signature of the InterPro
entry that integrates it, and its boundaries are where the HMM alignment ends.

Every other signature on P48729 agrees with the longer extent: CDD's
catalytic domain at 16-281, SMART at 17-283, the PROSITE profile at 17-285.
PF00069's 17-235 is the lone outlier.

And 5FQD chain C, the deposited CSNK1A1 in the lenalidomide ternary, resolves
residues **10 to 303 continuously, 294 residues with no unmodelled gaps**.
The 50 residues PF00069 drops are ordered structure, not a disordered tail. A
protein kinase is bilobal and 17-235 ends inside the C-lobe.

So IPR000719 is right, the campaign submitted the correct construct, and the
plan was what was wrong.

**The fix is an ordering, recorded as D-NOB-061.** Longest domain-level entry
first, InterPro preferred over a PFAM signature on a tie, accession last so
the order is total. Seven substrates submit a domain and exactly one moves:
CSNK1A1 to IPR000719 17-285. BRD4, GSPT1, RBM39, CDK12 and ZN346 keep what
they had, and CDK12 was already on IPR000719.

Four things close together. The construct is deterministic. CSNK1A1 agrees
with the campaign again, so the superseded-substrate discrepancy is gone and
the caveat comes off the published conclusion rather than being reworded. No
substrate resolves from a PFAM accession, which is the convention
`constructs.py` has always followed for receptors, and which
`test_superseded_substrates` had pinned as a standing anomaly: "the set of
PFAM-sourced domains has changed... The one superseded boundary was the only
member, which is why this is pinned". It was pinning the bug.

The running main campaign submits 15-mers for its benchmark pairs, so it is
unaffected and needs no restart.

**A second defect in the same function.** `max_coverage` is the maximum of
`window / length` over all enclosing domains, which is the *smallest* of
them, and the note and the plan's reason both quoted it beside
`domains[0]`'s accession. On 7 of 121 substrates those are different
domains, so the sentence paired one domain's name with another's percentage:
BRD4 read "inside IPR001487 and covers only 17%" where IPR001487's own
coverage is 13%. Both now quote the domain they name. `max_coverage` keeps
its job unchanged, because deciding whether a window can fold alone is
answered most conservatively by the domain it fills most of, and a 23-residue
zinc finger covering all of a 23-residue annotation is self-sufficient
however many larger domains contain it. Two questions were sharing one
ordering, which is what made the first defect possible.

**Three near-misses of my own.**

The first sweep reported 94 substrates changing and I almost wrote that down.
88 of them are zinc fingers where `inside_folded_domain` is false, so
`domains[0]` never becomes a construct: I had measured "the annotation
changes" and called it "the construct changes". Restricted to the 7 that
actually submit a domain, the answer is one.

The rule I first tried was "prefer InterPro, then highest coverage", which
reads naturally and is wrong: highest coverage is the shortest domain, so it
would have kept CSNK1A1 on PF00069 and moved BRD4 from the 111-residue
bromodomain to a 102-residue repeat-specific sub-entry. Shortest is right for
asking whether a degron fills its domain and wrong for asking what to fold.
A test now holds that length outranks the database preference.

And two of the tests I wrote for this were vacuous: they looped over the
plans reading `plan["peptide_start"]` and `plan["peptide_length"]`, neither of
which exists, so every iteration hit `continue` and the assertions never ran.
Found by printing the plan's keys rather than by the tests failing, which is
the eighth field-name guess of this build. Both take the degron window from
the peptide library now and assert they checked all six.

## F108. The same defect on the receptor side, in the function that fixed it

F107 was an unsorted list read by index on the substrate side. The receptor
side has its own lookup, and it has the same defect, in the function whose
docstring describes having fixed it.

`domain_by_accession(accession, entry, occurrence)` returns a named InterPro
entry. An entry can be annotated several times on one protein, and F41 found
exactly that: FEM1B carries IPR036770, the ankyrin repeat superfamily, at
5-301 and again at 424-610. Its docstring says so, and says why it mattered:

> This used to return whichever InterPro listed first, which is both the
> wrong 187 or 297 residues depending on an ordering nobody controls, and a
> boundary that could move without anything failing (F41).

The fix was to refuse an ambiguous entry unless the caller names which
occurrence it means, "counted from the N-terminus". The code then did
`matches[occurrence]`, where `matches` is filtered out of
`domains(accession)` in response order. So it replaced "whichever InterPro
listed first" with "whichever InterPro listed Nth" and kept the failure mode
intact: a receptor construct boundary that moves when the API reorders its
records, with nothing raising.

Latent today, and less consequential than I first wrote. Response order and
N-terminal order agree for Q9UK73: [0] is 5-301 and [1] is 424-610, so
`FEM1B_ANK` with `interpro_occurrence=0` gets the 297-residue N-terminal
region it declares, which is what spec 1.1 means. The day they stopped
agreeing, FEM1B's receptor would silently become the 187-residue C-terminal
region.

**Correction.** This first said "and FEM1B is a benchmark E3". It is not. The
benchmark E3s are CRBN, DCAF15, DDB1 and VHL, and the main campaign submits
four constructs: CRBN_CULT on 2,270 jobs, then VHL_VCB, DCAF15_DDB1_DDA1 and
DDB1_BPC on 30 each. `FEM1B_ANK` and `KEAP1_KELCH` are declared in
`constructs.py`, token-budgeted and tested, and submitted by no job in any
campaign. So `interpro_occurrence` is used by exactly one construct and that
construct is unused: the broken contract is real and its blast radius today
is nothing. Found by comparing `E3_TO_CONSTRUCT`'s values against the
constructs any queue actually names, which is the same kind of key-set
comparison that found F106.

That day is not hypothetical. It is what happened on the substrate side:
the library manifest records IPR000719 as CSNK1A1's first enclosing entry
and the same call today returns PF00069 first.

One line: the matches are sorted by start before being indexed, which makes
"counted from the N-terminus" true rather than coincidental. The contract
was already written down; now the code keeps it.

Testing it needs a deliberate disagreement, since the real data agrees. The
test hands back the two FEM1B annotations in reverse and asserts occurrence 0
is still 5-301, which fails against the old code and passes against the new.
Two more hold that a single annotation is unaffected and that an ambiguous
entry with no occurrence still refuses, because sorting makes the index
meaningful and does not make guessing acceptable.

The sweep for other consumers of the raw list found two, and both are now
ordered: this one and `domain_context`.

## F109. The correction step rewrote a live campaign's memory in place

`tools/rerun_pair.py bench02_BRD4_VHL --apply` is F47's fix, still pending.
The pair's fifteen jobs were emitted with a hydroxyproline on BRD4 Pro379,
the rule is fixed, the YAMLs on disk are not, and the step regenerates them
and drops the pair's rows so the queue runs them again.

It runs once, by hand, when the GPU is free, against a campaign holding days
of compute. Nothing in the suite exercised it. The only mentions of it were
comments in other tests saying it was pending, which is a different thing
from a test.

Its matching rule turns out to be careful. It takes a row when `pair_id`
matches exactly or when `job_id` starts with the pair id plus the `__`
separator, so a pair whose id is a prefix of another is not swept up. It
keeps an unparseable line rather than dropping it, which is right: a torn
final line from a kill mid-append is a job this tool cannot read, not a job
that did not happen. And it takes a `.bak` first.

The write was not atomic. `path.write_text(...)` truncates before it writes,
and `state.jsonl` is how a 2,360-job campaign knows which jobs are done. A
kill inside that window leaves a partial record, and the project's own rule
is to assume the process can be killed at any moment. The `.bak` makes that
recoverable by hand; the campaign resuming on its own would read the
truncated file and re-run whatever had been lost. At 170 jobs that is hours,
and the step is meant to run at the end when it would be far more.

Now written to a sibling and renamed, which is atomic within a directory, so
a reader sees the old file or the new one. The test for it raises inside
`os.replace` and asserts the original survives, which fails against the old
code because there was no replace to raise in.

One smaller thing: a second run overwrote the first `.bak`, losing the
original. The backup is only taken when one does not already exist, because
the first is the one that predates any of this.

Nine other tests cover the matching rule, the prefix case, a row matched by
`job_id` alone because `state.jsonl` carries a "running" row before the
result and those have no `pair_id`, the torn line, the no-match case taking
no backup, and the dry run changing nothing.

## F110. Three caches that a kill would have corrupted permanently

F109 made one rewrite atomic. The sweep that followed it, for everything
that writes a file a later run reads back, found three more, and they are the
caches.

`Path.write_text` truncates and then writes, so a kill inside that window
leaves whatever had been flushed. For a stage output that is recoverable: the
stage is idempotent and a re-run overwrites it. For a cache it is not, and the
three differ in how loudly they would fail.

**The InterPro cache** is JSON, so damage fails to parse. That sounds like
the safe case and is the subtle one. `_fetch` returns the file because it
`exists()` and never re-fetches it, so the corruption is permanent, and
`domain_context` catches `Exception` and reports `interpro_unavailable`,
which makes `inside_folded_domain` falsy and drops the substrate from its
folded domain to the 15-mer. Fragment against domain is the independent
variable of the F6 experiment. It would have been changed silently, by a
kill, for one protein, permanently.

**The UniProt sequence cache** is plain text, which is worse. A truncated
protein sequence is still a valid-looking protein. There is no parse step to
fail at, nothing raises, and every domain slice taken from it is quietly
short: the receptor construct, the substrate window, the frame that pose
recovery anchors in. F107 and F108 were both about a domain boundary arriving
wrong; this is the same boundary arriving wrong by a third route, and the only
one of the three with no detection at all.

**The MSA index and the a3m writer** are the third. Spec 1.3's point is that
no campaign contacts an MSA server, so the cache is load-bearing, and
preflight already checks that a receptor chain's a3m query matches the chain
it is attached to, which would catch a damaged alignment.

All four writes now go through `paths.write_atomic`, which writes a sibling
and renames. `os.replace` is atomic within a directory, so a reader sees the
old contents or the new ones. The temporary is deliberately beside the
target, because the guarantee does not cross filesystems, and a test asserts
that rather than trusting it.

The sequence cache also gets a check on read, because plain text has no parse
step: empty is refused, and anything outside the residue alphabet is refused,
with the path named so the fix is to delete that file. A clean truncation is
still valid residues and this cannot catch it. That is why the write is
atomic rather than merely validated, and it is worth saying plainly instead
of implying the check is complete.

Measured rather than assumed: the live caches are intact, 1,201 InterPro
responses all parsing and 16 sequences all plausible between 102 and 1,490
residues. The fix removes the cause, not damage already on disk, and a test
checks both, along with one that fails on a leftover `.writing` file, since
an interrupted write would otherwise leave no trace anyone looks at.

A fourth test holds the rule rather than the three instances: no bare
`write_text` in any of those modules. A cache added later is the same defect
again, and that is the form this has taken four times now.

## F111. Seven readers that a kill mid-append would have stopped

The runner appends to `results.jsonl` one row at a time and may be killed at
any moment, which the project states as a rule rather than a hope. Its own
reader of `state.jsonl` has always known what that means:

> A torn final line from a kill mid-write: ignore it and re-run that job.

Seven other readers of the same append-only files built their rows in a list
comprehension with no guard. A kill at the wrong moment leaves a fragment on
the last line, and the next stage raises `JSONDecodeError` instead of
processing the complete records before it. The seven are `metrics.aggregate`,
`score/run`, `write_throughput`, the pose-recovery and ROC layers,
`design/lift` and the tier-2 selection: scoring, validation, the weight fit,
the refinement selection and the cost projection, which between them are
every stage that runs after the compute.

With 180 jobs done that is an hour lost to a restart. The stages it blocks
run at the end, against 2,360.

`scores.jsonl` is in the same position by a different route: it is written in
one pass rather than appended to, so a kill truncates it, and the last line
can be a fragment just the same. Four of the seven read it.

One shared reader now, `paths.read_jsonl`, with the behaviour named at each
call site rather than chosen globally. `tolerate_torn=True` for the
append-only and single-pass files.

The other six sites stay strict, and that is the more interesting half.
`queue.jsonl` and the library manifest are written once, before anything
runs, and nothing appends to them. A line that will not parse there is a
damaged input rather than a torn tail, and tolerating it would run 2,359 of
2,360 jobs without saying so. A test holds that those readers do not acquire
the flag, because the tempting fix is to apply it everywhere and be done.

`paths.torn_lines` counts them, so a stage that tolerates a tear can report
how many it skipped rather than skipping in silence, which is the failure
F99 and F103 were both instances of.

The six strict readers were converted too, to `read_jsonl(path)` with no
flag, and the reason is a test of mine that was vacuous. It inspected lines
containing `read_jsonl(` and asserted none of them carried `tolerate_torn`
on a queue, and at that point the queue readers were still bare
comprehensions, so nothing matched and the loop body never ran. Found by
asking what a mutation would have to hit rather than by the test failing.
It now counts what it inspected and requires at least five, and a second
test drops a torn line into a real queue and confirms `run_campaign` raises.
That is the second vacuous test I wrote today, after the two in F107.

The end-to-end test builds its fixture from real rows rather than inventing
one. My first attempt invented a results row and died on `e3_gene`, which is
the ninth field name I have guessed wrong in this build, and the fixture now
takes a real pair's rows and cuts the last line.

## F112. The stall detector ran once, after the stall could no longer matter

F20 cost most of a night to one ambiguity: a campaign that has stopped looks
exactly like a campaign that is working. Both show a `running` record and a
live process, and every check that asked "is the process alive" answered yes
while the queue sat still for 3h45m.

`nobble/execute/watchdog.py` exists because of that, and it is careful. It
separates an informational `overdue`, which compares a job against the
slowest comparable one the same campaign has finished, from a `stalled` that
needs no tuning: the runner cannot legitimately spend more than its timeout
times its retries plus the grace it allows a kill, so a job past that bound
means the runner has lost control of it. It returns 0, 1 or 2, so a caller
need not read its prose.

It was reachable from one place: `tools/status.sh`. And the chain calls
`status.sh` on its last line, after the deploy. So across the forty-seven
hours in which a stall is possible, nothing consulted it, and it spoke once,
when the answer could no longer change anything. A detector that runs after
the event is not a detector, and this one was built in response to the event
it was not watching for.

Armed in `run_chain.sh` now, for the length of the chain: a loop that polls
every `NOBBLE_WATCHDOG_SECONDS` (600 by default) and prints only when the
exit code is non-zero, with a trap that takes it down however the chain ends
so a killed run does not leave a loop polling a campaign nobody is running.
Keyed on the exit code rather than on the printed verdict, because grepping
for "   ok  " would couple the chain to the spacing of a status line, which
is what F54 was.

Checked before relying on it: the watchdog only reads. The only occurrences
of "kill" in it are in its own prose, it runs no subprocess and writes no
file, so arming it unattended for days beside a live campaign cannot act on
one. It is the runner's own timeout that stops a job; this only says so. A
test strips the comments and docstrings and asserts that, because "it only
reads" is the kind of claim that stops being true quietly.

Replaced by rename rather than edited in place. The chain is running, and
bash reads a script by byte offset as it goes, so editing the file under a
live run corrupts what it executes next. That is F57's lesson and it applies
to its own fix.

The running chain therefore does not have this: it is executing the old
inode. A separate watch is armed alongside it for the remainder of this
campaign, polling the same read-only check every ten minutes and reporting
only a stall, so silence means healthy. The chain that follows this one picks
up the fix itself.

## F113. I gave two decisions numbers that were already taken, twice

Writing up F100 and F107 I needed two new decision ids. I grepped
`^## D-NOB-03[0-9]`, saw 039 as the highest, and wrote D-NOB-040 and
D-NOB-041.

Both existed. D-NOB-040 is "the design scan picks its target after the main
campaign, not before", cited in DESIGN_ARM.md. D-NOB-041 is "the site is not
republished while a campaign is running", cited by name in `run_chain.sh`'s
comment about why the atlas is rebuilt at the end. So for a few commits the
record had two entries under each number, and a reader following either
citation would have landed on whichever came first in the file.

Renumbering to 050 and 051 collided again, because those exist too: "the
atlas build refuses on an input the code would not emit" and "the atlas
output directory is overridable".

The cause is the same both times, and it is the cause of F107 and F108 as
well: I inferred a fact about a collection from a pattern that did not cover
it. `^## D-NOB-03[0-9]` cannot see 040, and after it has shown you 039 the
answer looks obvious.

Measured instead: 53 headings, 51 distinct numbers, highest 59. Mine are
D-NOB-060 and D-NOB-061, above the highest rather than into a gap, because a
gap exists where something was withdrawn or renumbered and reusing one makes
an old citation point at a new decision.

`tests/test_decision_ids.py` checks it now: no number used twice, and every
number cited anywhere in the code or the logs resolves to a decision, since
a citation pointing at nothing reads as a reason that was written down.

**And the test made the same mistake in miniature.** It matched only
`^## D-NOB-NNN` and so reported 1 to 7 as unused. They are not: D-NOB-001 to
007 came from the spec and sit in a table at the top of DECISIONS.md, which
is also where CLAUDE.md's citation of D-NOB-007 resolves. The test now reads
both forms and asserts it can see each, with one case pinned at either end:
D-NOB-007's "widened in place" from the table and D-NOB-061 from the
headings. With both read, there is exactly one real gap, 45.

Caught because the first version of the dangling-citation test failed,
naming D-NOB-001, 005 and 007. A test written to catch an incomplete pattern
failed on its own incomplete pattern, which is at least the right way round.
