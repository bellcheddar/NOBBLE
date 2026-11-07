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
campaign's size: 158 pairs times 5 seeds times 3 arms is 2,370, and the queue holds 2,360 because two pairs carry two arms rather than three.

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

## F114. The README's headline numbers were not pinned to anything

F103 changed `recovery_against_crystal`, adding the residue-identity check
that withholds an RMSD when the compared window is not the window the plan
describes. Every one of the seven benchmark pairs passes it, so no number
moved. I established that by rerunning the seven and reading the values.

Then it occurred to me what those values are. The README leads with three of
them:

> submitting the whole domain instead of a 15-residue window moves GSPT1 /
> CRBN from 29.22 A median pose RMSD to **1.17 A** and BRD4 / VHL from
> 19.23 A to **1.71 A** [...] The IKZF1 control keeps its 15-mer in both runs
> and moves by **exactly 0.00 A**, so the change tracks the construct and
> nothing else.

Recomputed from both campaigns' own results, over all ten seeds each:
GSPT1 29.221 to 1.171, BRD4 / VHL 19.235 to 1.711, IKZF1 5.357 in both
campaigns and therefore 0.000 between them. Every figure holds.

So nothing was wrong. What was wrong is that nothing would have said so. The
most-quoted numbers in the project came out of a function I had edited an
hour earlier, and the only thing standing between a published claim and a
silent change to it was my noticing.

`tests/test_readme_figures.py` recomputes all three from the campaigns rather
than asserting a stored value, so it checks the pipeline rather than a
fixture. The control is its own test, because that is the claim the other two
rest on: two pairs improving could be two pairs improving for any reason, and
a control that does not move is what makes the improvement attributable to
the construct.

One of the five is about the document rather than the data: it asserts the
README still quotes those figures. A pinned number guarding a sentence that
has been reworded is worse than no pin, because it keeps passing.

## F115. Why the primary signal cannot report a confident zero, and where that lives

`percentile_of` bisects the atlas distribution and returns
`100 * position / len(reference)`. Every comparison against a NaN is false,
so `bisect_left` walks left the whole way and returns 0. A non-finite dSASA
would therefore be reported as bridge percentile **0.0**: not a refusal, the
lowest real value, indistinguishable from a tiny interface. Bridge percentile
is spec 4.1's primary signal and the key tier-2 selection ranks on, so such a
pair would be pushed to the bottom of the ranking by an unmeasurable number
wearing a plausible one's clothes. `max(bridges, key=...dsasa_total)` one line
above has the same exposure, since a NaN in a `max` returns an arbitrary
element.

Neither is reachable, and that is the finding rather than a defect.

BINMAN's `find_bridges` admits a half-interface only when
`self.dsasa >= min_dsasa and self.contacts >= min_contacts`, and `NaN >= x`
is false, so a non-finite half never qualifies. `dsasa_total` is the sum of
two halves that did qualify, so it is finite by construction. Checked rather
than argued: 0.0 is what bisection gives for NaN and for -inf, the criterion
rejects both, and every bridge percentile in every scored campaign is finite
and inside 0 to 100.

Two things make this worth writing down rather than filing as "no action".

The protection is structural but it is not NOBBLE's. It is one line in
another repository, and the obvious equivalent rewrite, `not (dsasa <
min_dsasa)`, reads identically and accepts NaN. D-NOB-007 says shared code is
widened in BINMAN rather than forked, which is right, and it means NOBBLE
depends on behaviour it does not own. So the dependency is pinned here, where
it is depended on, with a control that the floor is applied at all: without
it the NaN rejection would pass for the wrong reason on a criterion that
rejected everything.

And `percentile_of` does guard its one other failure, an empty reference
distribution, and guards it the right way round: no distribution to compare
against returns NaN rather than 0.0. The same function treats a missing
reference as unmeasurable and would treat a missing value as the worst
possible. That asymmetry is only safe because of a line in another
repository, which is exactly the kind of thing that is true until someone
tidies it.

This is the sixth concern this build that turned out to be unreachable. The
check cost ten minutes; a write-up claiming the primary signal could report
NaN as zero would have cost more.

## F116. The headline chart drew an absent bridge as percentile zero

Spec section 4 read against the code, which is the audit F52 did for section
5 and nobody had done for section 4. Most of it holds. 4.5's calibration note
is on the About page in the form the spec asks for, ipTM-min and all. 4.2's
substitution of lysine geometry for an uncalibrated fit is D-NOB-024, decided
and recorded. 4.8's sliders exist. 4.1's percentile is against the 285,996
and says so on the axis.

One clause does not, and it is in the view the spec calls the headline.

The Delta scatter plots Delta-ipTM against bridge percentile. It did it like
this:

    y: rows.map(p => p.bridge_percentile === null ? 0 : p.bridge_percentile)

So a pair with no measurable bridge was drawn on the axis, among pairs with a
genuine weak bridge, and the hover read `bridge percentile %{y:.1f}`, which
turns the plotted position into a stated number: "bridge percentile 0.0" for
a measurement that does not exist.

CDK12 is that pair. All ten of its seeds reject as `single_chain`, which says
the glue touched one chain rather than two. Not a weak bridge, no bridge.

The campaign table already knew. It blanks the cell and puts the reject
reasons in the tooltip, with a comment saying why: "without this the cell is
blank and the distinction is invisible". So one surface distinguished absent
from worst and the other did not, and the one that did not is the headline.

F115 established that the computation cannot report a confident zero, because
BINMAN's bridging criterion rejects a non-finite dSASA before it can reach
the percentile. This is the same hazard arriving by presentation rather than
by arithmetic, which is why finding the first made the second visible.

Those points now sit in their own band below the axis, at -1 inside a range
widened to -4, so the position cannot be read as a percentile. The axis
labels it "none". The hover takes the text from customdata rather than from
the plotted position, so it says "no bridge in any seed". They stay in the
chart rather than being dropped, because a pair that vanishes from the
headline view is worse than one drawn wrongly.

A test counts the customdata entries by splitting on top-level commas and
asserts the hovertemplate reaches exactly that far, because a hovertemplate
indexes positionally and a field inserted in the wrong place silently
relabels every one after it. The first version of that test counted lines and
found seven entries where there are nine, the first line holding three.

## F117. The licensing check ran in one direction only

Spec 2.1 and CLAUDE.md set three restrictions on what may be redistributed:
PROTAC-DB is internal-use-only, UbiBrowser ships as derived counts, BioLiP2
annotations do not ship. The bundle is rsynced to a public host, so a breach
is published rather than merely committed.

`build_atlas` checks one direction. It redacts any ligand record whose
chemistry came from PROTAC-DB, prints "verified: no PROTAC-DB chemistry in
the published bundle", and F72 fixed its count reporting zero while a
withheld field sat in the file.

Nothing checked the other direction: that every SMILES which *is* published
has a source permitted to be. The absence of a forbidden source and the
presence of a permitted one are different claims, and only the first was
being made.

Read record by record off the live bundle: seven ligand records. Six are
`deposited_ternary`, chemistry taken from the PDB entries themselves, and
published. One, dBET57, is `protacdb` and is withheld. UbiBrowser and BioLiP2
appear only in `about.json` as availability booleans, which says which
sources were reachable rather than shipping any of their rows.

So the constraint holds, and now in both directions, with four tests: every
published SMILES has a permitted source, a PROTAC-DB record carries no value
and says why, the restricted names appear only against a boolean or a count,
and no restricted name carries structured content, which is the shape a leak
would take.

My first assertion was wrong and the data corrected it. I asserted that a
withheld record has no `smiles` key at all. It has one, set to null, beside
`smiles_withheld`. That is the better shape: a reader learns the record has
chemistry and that it was withheld, rather than that the field does not
exist. The test asserts there is no value rather than no key.

## F118. Spec sections 2 and 3 read against the code, and what the empty cache meant

F52 audited spec section 5 and F116 did section 4. These are the two in
between, recorded because an audit that found nothing is worth exactly as
much as the search nobody repeats.

**2.2, ligand chain encoding.** Both clauses hold. CCD preferred over SMILES
with the fallback flagged in the manifest and marked in the results table,
which is F51. A ligand over Boltz's 128-atom affinity cap records
`affinity_unavailable` as a warning and the structure prediction runs, rather
than the job failing.

**2.3, post-translational modifications.** The spec asks for a manifest error,
not a low score, when a degron class needs a modification and the peptide is
submitted without one. Two checks cover it from different sides.
`manifest.validate` raises `ptm_residue_absent` as an error when the sequence
carries no residue of the required type, which is the precondition.
`stale_inputs` compares the modifications the YAML asks for against the
modifications the queue row requires, and I checked it is symmetric rather
than assuming: required and present is clean, required and absent is
reported, present and not required is reported, which is the F47 case, and
neither is clean. It blocks the atlas build, so a missing modification cannot
be published.

**3.4, peptide library construction.** The clause easiest to let slip is the
last one: "record the reduction ratio and the clustering parameters in the
manifest". Both are there, in the library manifest rather than the campaign
one: 25,519 candidates to 158 selected, `reduction_ratio` 0.0062, and the
parameters including the ESM-2 model, the pooling, the seed and the budget.

That answered something that had looked like a gap. `data/cache/esm2` is
empty, which reads as "the embedding was never run". It was not, and
correctly: `diverse: 0`, because the mandatory sources contribute 127 of a
measured budget of 156 and the full mandatory set is 158, so the selection is
`over_budget: mandatory members alone exceed the measured budget` by 2 pairs.
`embed()` is called only on the optional candidates and there were none. An
empty cache is the consequence of a budget, not a stage that did not run.

The over-budget state is reported rather than failed, because the mandatory
members are deliberately not trimmed and Gate G1 is judged on
`max_compute_hours` rather than the 48-hour per-run target. Two pairs over a
target is a scheduling fact; 96 hours is the gate.

**3.5, where ESMFold is used.** Already audited, in the entry at F28's "three
rules of the spec read against the code": ESMFold is not used at all, because
none of its three permitted cases has arisen, and the clause the spec
emphasises, that the disorder prefilter must not be applied to linear degron
mimetics, holds because no such prefilter exists.

Sections 1 and 2's remaining clauses are covered by tests that already exist:
house style, the MSA policy through preflight, the token cap through the
construct budget, and the campaign budget through `projected_hours` and Gate
G1's exit code at curation time.

## F119. The significance level was in config and in four other places

`config/thresholds.toml` says `significance_alpha = 0.05` is "the only
significance level this project applies". D-NOB-047 put it there, having
found it as a literal `p < 0.05` in `benchmark.html`, and gave the reason: "a
reader changing what the project counts as significant should not have to
know it is written in markup."

It was also written in arithmetic, in prose, in a second template and in a
caveat I wrote this morning.

The matched-control ROC's bootstrap returned
`(values[int(0.025 * rounds)], values[int(0.975 * rounds)])`. Its layer
reported "not distinguishable from chance at 95 per cent confidence".
`about.html` printed "95% CI". And F105's design caveat printed "95 per cent
CI". Four copies of a 95 that is `1 - alpha`, agreeing with the configured
value by coincidence rather than by derivation.

So turning alpha down to 0.01 restyled one chart on the benchmark page and
left the headline result's interval at 95 per cent, with three surfaces
saying so. The one number the project calls its only significance level
governed the least important thing it touches.

All four derive from it now. The bounds are the alpha/2 and
1 - alpha/2 order statistics, `confidence_level()` computes the percentage,
and the layer reports it in a `confidence_level` field beside `ci95` so no
surface has to know what alpha was when the atlas was built. The `rounds`
default argument became `scoring.bootstrap_rounds`.

This widens what alpha governs, so it is recorded as D-NOB-062 rather than
treated as a tidy-up: it now changes the interval's width and therefore
whether `interpretation` reads "above chance", which branches on the lower
bound against 0.5.

**How it was missed is the interesting part.** The cutoff sweep examined this
exact function. Its allowlist carried `_bootstrap_interval.rounds` with a
written reason, "a precision and compute trade-off rather than a cutoff on
data", which is right. So someone read the signature, considered the default,
and waved it through. The two percentile literals are one line below, inside
the return statement, and F80 had already recorded that the sweep reads
comparisons, module constants and default arguments and not arithmetic.

An allowlist entry is evidence that a line was looked at. It is not evidence
that the lines around it were. That allowance is now retired, with the note
kept in its place, because the absence of an entry would read as the function
never having been examined.

Two of my own tests needed fixing on the way, both the same shape. One
scanned for a hard-coded 95 and failed on its own docstring explaining the
old literals; prefix-skipping cannot see a continuation line inside a
docstring, so the docstrings are blanked before the scan. The degenerate
bootstrap test pins the indexing rather than the sampling, because a
perfectly separated set gives AUC 1.0 on every resample and a perfectly tied
one gives 0.5, so the bounds are known without reasoning about randomness.

## F120. The headline verdict had two branches for three outcomes

Reading `_bootstrap_interval` for F119 meant reading what consumes it. The
matched-control ROC turned its interval into a sentence like this:

    "above chance" if low > 0.5
    else "not distinguishable from chance at N per cent confidence"

That reads as exhaustive. It is not. An interval entirely below 0.5 is a
third case, and it is the opposite of indistinguishable: the statistic
separates the two classes, in the direction opposite to the prediction. An
AUC of 0.15 with an interval of 0.08 to 0.24 would have been reported as not
distinguishable from chance, which is false twice over.

For Δ-ipTM it would mean the matched negatives gaining more interface
confidence from the glue than the degraded fingers do. That is a finding, and
spec 4.3 asks for it by name: "If it does not [hold], that is a real result
about co-folding models and ternary cooperativity, and the app should report
it as such rather than hiding it." Spec 5 adds that a poor ROC is not a gate
failure while failing to report one is. Reporting a mislabelled one is worse
than either.

The project already knows how to say it. D-NOB-024 reports BINMAN's lysine
reach window as "at or below chance and slightly inverted" on an AUC of 0.42
to 0.48, and declines to weight it. The headline curve had no way to reach
the same conclusion about itself.

Three branches now, in a named function rather than a conditional
expression, because the shape is the cause: `A if cond else B` invites
reading B as everything-else, and a function with three returns does not.
Both boundaries are strict, so an interval touching 0.5 from either side
claims nothing.

The estimator underneath is correct and was checked rather than assumed:
perfect separation gives 1.0, perfect inversion 0.0, all ties 0.5, and a
single tie among four comparisons 0.875, which is the Mann-Whitney statistic
normalised by the product of the group sizes.

The cutoff sweep caught the new comparison immediately, which is the sweep
working. `low > 0.5` was already allowed with the reason that 0.5 is the
definition of chance for an area under a curve rather than a tunable
threshold. `high < 0.5` is the same constant on the other side and is listed
separately rather than folded into the first entry, on F119's lesson: an
allowlist entry is evidence that one line was looked at, not that its
neighbours were.

## F121. The prediction scorer counted two of its three verdicts

The same shape as F120, found by looking for it. `tools/check_prediction.py`
scores the F13 predictions mechanically, and its docstring is explicit about
why: "a scorer that cannot return 'wrong' is not scoring anything."

It can return four things. "not yet testable" for a pair whose data has not
arrived, then `"WRONG" if falsified else ("supported" if passed else
"unclear")`. Four verdicts, and the branching is complete.

The summary counted two of the three testable ones. `tested`, `wrong` and
`supported`, with no `unclear`, and the printed sentence read "N testable
(... ), N supported, N wrong". So `tested` could exceed supported + wrong
with nothing saying which prediction was unaccounted for, and a reader would
have to notice the arithmetic rather than the sentence.

It adds up today: one supported, one wrong, of two testable. It would not
the first time a prediction landed between its falsification and its
supported interval, which is precisely the case "unclear" exists to name.
The per-pair lines print every verdict, so the information was there; the
sentence that gets quoted was the thing that could not say it.

Counted and printed now, with an assertion in `main` that the three add up to
the number the sentence opens with. A test holds the same invariant against
the real campaigns, and a second builds the three-verdict case
synthetically, because the invariant on today's data is satisfied by there
being nothing to miss.

Three findings in a row from one question: what does this code do with the
case it does not mention. The bootstrap's percentile literals (F119), the
ROC's missing third branch (F120), and this.

## F122. Two sibling endpoints disagreed about whether a pair exists

The app is public, so I probed it with input it does not expect: unknown
ids, percent-encoded `../`, a four-thousand-character parameter, a GET on a
POST route. Nothing raised, nothing returned 5xx, and both
`/structure/<job>.cif` and `/crystal/<pdb>.cif` refuse a traversal by
matching the identifier against the campaign's own records rather than by
sanitising a path.

One thing disagreed with itself. `/api/pair/<id>` returned 404 for a pair the
campaign has no record of. `/api/pair/<id>/structures` returned 200 with
`{"pair_id": "nope", "crystal": null, "structures": []}`, which asserts that
the pair exists and produced nothing.

Those are two different states, and this project separates them everywhere
else: F116 on an absent bridge against a percentile of zero, F85 on an
unmeasurable RMSD against a pending one, F99 on a missing confidence against
a reason. A pair whose jobs all failed is a real outcome with a real empty
list, and the Pose viewer would have rendered one of those for a pair that
does not exist.

**And my first fix was wrong, which the existing tests caught within a
minute.** I used the sibling's check, `_pair_or_404`, which looks in
`data.scores()`. Scoring runs after the campaign, so for the whole length of
a run every completed pair is in `results.jsonl` and none are in
`scores.jsonl`. That fix 404s every pair while a campaign is running, which
is precisely when the viewer is used. `test_tier2_catalogue` writes an empty
`scores.jsonl` beside a populated `results.jsonl` for exactly this reason and
failed three times over.

Existence is judged on the campaign's results now, tier 1 or tier 2, which is
what the endpoint reads anyway.

Then my test for the fix was wrong twice. It asserted the endpoint uses
`_pair_or_404`, which is the thing that was wrong; and its replacement called
`data.configure()` on a bare temporary directory, which does not pin it, so
the app fell back to the newest real campaign and 404ed a pair the fixture
had just written. It runs `create_app(<dir>)` in a subprocess now, the way
`test_tier2_catalogue` already did.

Three wrong attempts at one twelve-line change, each caught immediately,
which is the argument for small changes against a suite that runs in two
minutes.

## F123. The browser marked an incomplete composite and the stored record did not

Spec 4.8's composite is computed twice. `weights.apply` computes it for the
pipeline and `run.py` stores it as `nobble_score`; `nobble.js` recomputes it
in the browser on every slider move, which is what lets the ranking
re-derive without a round trip.

I checked they agree, and they do. Running both rather than reading both:
`qc/composite_harness.mjs` loads `nobble.js` under node with the smallest
browser stubs that let it initialise and calls its real `composite` on the
same rows and weights as Python's `apply`. They match to 5e-5 across the
benchmark panel, which is exactly Python's `round(..., 4)`. The aggregation
is the same weighted mean renormalised over the components that had values,
and the two normalisations that matter, `bridge_percentile / 100` and
`clamp((delta_iptm + 1) / 2)`, are the same. Python additionally clamps the
other three components, which are already bounded by construction, so the
difference is defensive rather than real.

What they do not share is coverage, and the JavaScript explains why in a
comment I could not have written better:

> a pair part-way through its jobs has null convergence and null PLIP, and
> renormalising over the weights that did have values gives it a score built
> from two components sitting in the same ranked column as one built from
> four. RBM39 ranked second that way on a composite that never saw its pose
> convergence. A score is only comparable to another score over the same
> components.

So the page returns `components`, `requested` and `complete` beside every
score and shows them. `weights.apply` returned a bare float, and `run.py`
stored it with the fit's provenance and no coverage at all. A reader of
`scores.jsonl`, of `/api/pairs`, or BINMAN-LM sorting on `nobble_score`,
would have compared a three-component score against a four-component one as
the same quantity.

Not hypothetical: two of the seven benchmark pairs score on fewer components
than the weights ask for. RBM39 has three of four and CDK12 has two, which is
the pair with no bridge at all.

`weights.coverage` reports it now, from the same traversal the score comes
from, and `run.py` stores it as `nobble_score_coverage`. It is None today
because the fit needs the Sievers matched set, so this takes effect when the
fit lands, which is the end of the campaign.

The agreement itself is now a test rather than a thing I checked once. Two
implementations of one formula agree until they do not, and the page is where
the ranking is read.

## F124. The largest shared file sat outside the check that protects shared code

CLAUDE.md states D-NOB-007 as a rule: shared code is widened in place in
BINMAN or BoltzMaker, never forked. F71 built
`tests/test_shared_code.py` to enforce it, and its own docstring says why:
"Stated in CLAUDE.md and checked by nothing."

It enumerates every file NOBBLE holds **at the same relative path** as a
peer and requires byte-identity. Three files qualify. Its `SKIP_PARTS` also
skips `app`, on the stated grounds that those directories are "each
project's own by definition".

NOBBLE's app is not entirely its own.

Compared by content rather than by path, twelve files are byte-identical to a
peer's copy at a different path. Nine are vendored libraries, molstar,
plotly, d3, tabulator and the fonts, which neither project owns and the rule
does not reach. Three are project code:

| NOBBLE | peer | size |
|---|---|---|
| `app/static/vendor/molstar-bridge.js` | `BINMAN/app/static/js/molstar-bridge.js` | 39 KB |
| `app/static/css/depot.css` | `BINMAN/app/static/css/binman.css` | 34 KB |
| `elementor-widget-markdown.css` | `BoltzMaker/wordpress/...` | 3.7 KB |

All three are identical today, so nothing is forked. What is missing is
anything holding them to it, and the two largest are the easiest to edit by
accident for opposite reasons.

`molstar-bridge.js` is 991 lines of BINMAN's viewer filed under NOBBLE's
`vendor/`. The directory name says third-party, so a reader skips it and so
does every sweep: my own greps all excluded `vendor`, the project's house
style and cutoff checks never look there, and `SKIP_PARTS` would have
skipped it anyway. It is the single largest piece of shared code in the
project and it was outside the check twice over, once by path and once by
convention. Nothing in the test suite referenced it by path before today.

`depot.css` is BINMAN's stylesheet under a different name, which is what
"the Depot design system is inherited from BINMAN" means in bytes. A rename
defeats a same-path comparison completely.

`SHARED_AT_A_DIFFERENT_PATH` names the three now, each with the reason and
with what to do instead: widen BINMAN's copy and re-vendor. Three further
tests hold the map honest, that every entry names a file NOBBLE still has,
that no vendored library is listed, since that would turn a rule about shared
code into a rule about pinned dependencies, and that the bridge really is
project code, which it demonstrates by naming the spec section it implements
in its first line.

Verified by divergence rather than by reading: appending one comment line to
`depot.css` fails the check, and the restore is confirmed by the two md5s
matching again.

The content of the bridge, read while there, is sound. Its numeric literals
are the standard AlphaFold four-band pLDDT scale, documented as such, and a
block of ligand presentation tuning gathered in one place with a comment
saying that is why. The finding is where the file lives, not what it says.

## F125. The cutoff sweep walked one directory of four

F124 was a check that could not see a file. This is the same question asked
of the check that has found the most: every scan in
`test_no_hardcoded_cutoffs.py` walks `ROOT / "nobble"`.

`tools/`, `deploy/` and `qc/` hold pipeline logic too. Preflight refuses a
52-hour run. `build_atlas` decides what is published and what is withheld.
`check_prediction` scores the recorded predictions. `rerun_pair` clears a
campaign's memory. A cutoff added to any of them was invisible to the rule
the project states in CLAUDE.md and enforces here.

Measured before being written up, because the interesting answer was that it
had not yet cost anything. The only float cutoffs in those three directories
are four in `check_prediction.py`, and they are the one case where a literal
is not merely acceptable but required:

> So the thresholds live here, taken verbatim from F13, and the verdict is
> [...] the point: a scorer that cannot return "wrong" is not scoring
> anything.

A prediction's thresholds are part of the prediction. Moving 20.0 and 2.0
into `thresholds.toml` would make the verdict tunable after the result is
known, which is the opposite of what the scorer exists for. That is the
strongest reason a literal can have and it is already written down.

So the sweep now covers all four directories with that one file allowlisted
and the reason recorded. Three tests: nothing else hides a cutoff, the
allowlist is not stale, since an entry for a file with no cutoff left reads
as evidence that one was considered which is F119's lesson, and the scan
finds something to judge, so neither of the first two passes by scanning
nothing.

Verified by adding a plausible accidental cutoff to `tools/preflight.py` and
confirming the scan names it by file and line, then restoring and confirming
the suite is green again.

## F126. The house-style check excluded its own JavaScript by suffix

Third in a row from the same question. `test_house_style.py` scans
`.md .py .html .mjs .sh .toml`. `.js` is not in the list, and the reason is
obvious once stated: the vendored libraries are `.js`, and scanning five
megabytes of minified molstar would produce nothing but noise.

That is a suffix doing a path's job. It also excluded
`nobble/app/static/js/nobble.js`, 343 lines of this project's own
JavaScript whose comments carry as much prose as any module in the package:
the explanation of why the composite reports its coverage, which F123 quoted
at length, lives there.

Measured before changing anything, because the useful answer was whether it
had cost anything. It had not: no American spellings, no banned words, no em
dashes. The file was already written to the house style, by hand, with
nothing checking.

`.js` is in the list now and `static/vendor/` is excluded by path, which
brings in exactly one file. The exclusion covers the libraries and one more
thing: `molstar-bridge.js` is `.js`, is project code, and stays excluded
because it is **BINMAN's** project code, byte-identical to its copy there
(F124). Holding it to NOBBLE's house style would demand an edit D-NOB-007
forbids, so the two rules would contradict each other. A test asserts it is
excluded by path rather than by luck, so if it ever moves out of
`static/vendor/` the decision gets made again instead of inherited.

Two of the three new tests exist to stop the suffix being dropped again.
Without them `.js` could come back out of `SUFFIXES` and every style test
would still pass, having found nothing because it was looking at nothing.

One slip of my own, caught by reading rather than by the suite: the new
exclusion test used `pytest.skip` on a branch that cannot be reached here,
and this file imports no pytest. It would have raised `NameError` on a
checkout without the bridge, in a test whose whole purpose is to behave
correctly where a file is absent. It returns instead.

Three findings from one question, asked of three checks: `test_shared_code`
could not see a renamed file or an `app` directory (F124), the cutoff sweep
walked one directory of four (F125), and this one drew its boundary with a
suffix (F126). None had cost anything yet. All three were drawn with a tool
one notch too blunt for the job.

## F127. Python writes JSON that a browser rejects, and nothing checked

The scope audit that produced F124, F125 and F126 turned up one more, and
this one is about a consequence rather than a coverage count.

`test_numeric_rule.py` enforces F76 and F77's rule about what counts as a
number. It scans `ROOT / "nobble"`. `deploy/build_atlas.py` is outside it,
and `build_atlas` runs `scipy.stats.pearsonr` and `spearmanr` over the
recovery-against-bridge points and publishes `round(float(r), 3)` with no
finiteness guard of its own.

What makes that worth more than another scope entry is what a non-finite
result would do. Python's `json.dumps` writes `NaN`, `Infinity` and
`-Infinity` by default. None of the three is valid JSON and `JSON.parse`
rejects all three. So one non-finite number anywhere in the atlas does not
put a wrong figure on a page. It puts no page there, because the document
fails to parse, and the benchmark chart reads that file.

Measured: all nine published files parse under a strict parser, and so do
every API response. A NaN cannot reach the correlation today either, because
`median_rmsd` arrives through `finite_values` and `bridge_rate` divides by a
total already checked non-zero.

Both guards are upstream of the place the risk lands, and neither is stated
where the correlation is taken. So the check is now at the boundary that
matters: the bytes a browser loads. `tests/test_published_json_is_valid.py`
parses every published file and every API response with
`parse_constant` set to raise, which is what the browser does, and separately
asserts no file contains the tokens at all, because a parse error reports a
byte offset and a reader needs a field name.

The first test in the file is the control: it dumps a NaN with Python's own
encoder, asserts the token appears, and asserts the strict parser rejects it.
Without that, the five tests below could pass against a parser that accepts
everything.

Verified by writing a NaN into the published correlation and confirming three
of the six fail, then restoring and confirming all six pass.

Four findings from one question asked of four checks. None had cost anything
yet, and all four boundaries were drawn with a tool one notch too blunt: a
same-path comparison that a rename defeats, a walk of one directory in four,
a suffix standing in for a path, and a numeric rule that stopped at the
package while the published bytes are written outside it.

## F128. The published bundle carried the build machine's paths, and my own test could not see them

Checking the repository for anything that should not be public before
considering a push, which found no credentials: the deploy takes
`DROPLET_SSH`, `SSH_KEY`, `REMOTE_DIR` and `SERVICE` from the environment
with `${VAR:?}` so it fails rather than defaults, no key or `.env` is
tracked, and no PEM block, credential-shaped assignment or address appears
in any tracked file.

What it did find is `/Users/dellboy` in three tracked files. One is
`config/hardware.toml`, the hwprobe output, which is local by nature. The
other two are `deploy/atlas/results.jsonl` and `deploy/atlas/scores.jsonl`:
the published bundle, rsynced to a public host.

307 occurrences, in four fields. `results.jsonl` carried `yaml` and
`output_dir`; `scores.jsonl` carried the nested
`seed_records[].structure` and `plip.conect.pdb_path`.

The build knew about exactly one of them. Its comment says so: "results.jsonl
carries absolute structure paths from the build machine, which are
meaningless on the droplet, so they are rewritten to the flattened names
published beside them." It rewrites `row["structure"]`, the top-level field,
and passes the other four through. The top-level `scores.jsonl` structure is
`None` and its nested copy, one level down in `seed_records`, was absolute.

Nothing functional was broken, and that is why it survived. The seed overlay
builds its URLs from `job_id`, so nothing on the droplet reads those four
fields; the live structure endpoint serves its 84 KB either way, verified
before and after. The cost was a home directory on a public page, 307 times.

**F105 added a test for precisely this and it could not see it.** It globs
`PUBLISHED.glob("*.json")`. The bundle also holds `.jsonl`, which is where
most of the paths were. `build_atlas`'s own PROTAC-DB leak check, forty lines
below the rewrite, scans `(".json", ".jsonl")` because it had to. Mine
scanned one extension, so the test written to catch a published home
directory was blind to the two files holding nearly all of them.

That is the fifth boundary this session drawn one notch too blunt, and the
only one of the five that had already cost something.

Every absolute project path in a published record is now rewritten at any
depth, and made project-relative rather than dropped: which YAML produced a
record and where Boltz wrote it is provenance a reader of the bundle can
use, and the name of the directory it was built in is not. The published
`structure` is preserved as the copy beside it, which a test asserts
separately, since relativising that one would have broken the viewer.

The leak test now walks every published text file by suffix set, and names
`results.jsonl` and `scores.jsonl` explicitly, because the glob that missed
them looked perfectly reasonable.

## F129. The same glob, in two more tests I wrote the same day

F128 found `*.json` where the bundle also holds `.jsonl`. The obvious next
question is whether I did it more than once, and I did: three of the tests
added today enumerate the published bundle, each with its own glob, and two
still had the narrow one. The licensing check and the strict-JSON check both
skipped `results.jsonl` and `scores.jsonl`.

Those are the two files that hold the records, which is why it is worth more
than a third correction. `results.jsonl` carries ten `smiles` tokens, so the
check on what chemistry may be published was not looking at the file with
chemistry-shaped fields in it; and a hundred rows per file is where a
non-finite component would surface.

Both are clean. The ten tokens are `"ligand_encoding": "smiles"` and the
`smiles_fallback` flag, label names rather than chemistry, because
`build_atlas` applies `redact()` to the JSONL rows as well: dBET57's SMILES
string appears nowhere in the bundle, which I checked directly rather than
inferring from the top-level records. Both files parse strictly, line by
line.

**The fix is one definition, not three corrected globs.** `tests/conftest.py`
now says what the published bundle is, by suffix set, and all three tests
read it from there. That is F106 one layer down: the composite had two
implementations that agreed until they would not, and this was three
enumerations of the same directory that had already stopped agreeing.

Widening the glob turned out not to be a glob change. A `.json` file is one
document and a `.jsonl` file is one per line, so the licensing tests failed
with a decode error the moment their glob was corrected. `published_documents`
yields `(path, line, document)` from either layout, and the assertions name
the line, because "results.jsonl failed" is not a useful thing to be told
about a file with a hundred rows.

And the shared-code check caught the new `conftest.py` on the next run,
because BINMAN and BoltzMaker each have one at that path and mine differs.
It is not shared code: BINMAN's opens a sqlite connection, BoltzMaker's fixes
`sys.path`, and the shared name is pytest's convention, which is the same
reason `wsgi.py` is already listed as allowed to differ. Recorded there with
that reason. It is also F124's widening working within the hour: the check
that could not see a renamed file now sees a new one the moment it lands.

## F130. A NaN is truthy, which the numeric sweep does not look for

F74 found that `isinstance(value, (int, float))` admits a NaN. F76 moved the
rule into `nobble/numeric.py` and swept the fourteen places that had retyped
it. That sweep looks for the type check.

It does not look for a truthy guard asking the same question, and two
modules used one on a measured duration.

`write_throughput` filtered `if item.get("seconds") and item.get("tokens")`,
then built `rates = sorted(seconds / tokens ...)` and took
`rates[len(rates) // 2]`. A NaN is truthy, so it passes that filter, and one
NaN in a list leaves `sorted()` with the whole list unsorted: the index then
returns the NaN or an arbitrary neighbour rather than the median. That median
sizes the campaign and feeds the projection Gate G1 is judged on.

The watchdog's comparable-job filter did the same thing and takes its typical
rate by the same index, which is the baseline its `overdue` signal is
measured against.

Neither is reachable from the runner. `seconds` is a difference of two
`time.monotonic()` readings and `tokens` is an integer from the queue, so a
NaN cannot arise. Both use `finite` now anyway, because ten lines from the
throughput filter sits the `tier1_worst_seconds` added for F100, which
already did: two rules for one question in adjacent code is precisely what
F76 was about, and I wrote the second one myself this morning without
noticing the first.

The truthy form also rejected a zero, and that is kept deliberately: a job
recorded at zero seconds or zero tokens is not a measurement either, so the
guard is `finite(...) and value > 0` rather than `finite(...)` alone. A test
holds both halves, because replacing a truthy check with a finiteness check
silently admits zero if nobody looks.

Verified behaviour-preserving on the real data: 100 benchmark jobs timed at
a median of 0.4551 seconds per token, which is the figure the README quotes.

**No sweep added, and that is a decision.** A general "truthiness standing in
for finiteness" detector cannot tell `if rows:` from `if row.get("seconds"):`
without knowing which fields are numeric, and F95 established the precedent:
a sweep whose false positives outnumber its findings fifteen to two is not
kept. The two instances are fixed, tested by name, and a test asserts that
the numeric sweep still covers the type check and not this, so the note goes
stale loudly if that changes.

## F131. Two of my tests rewrote state the app reads

`tools/mutate.py` fingerprints a list of files before and after every
mutation, `PROTECTED_GLOBS`, and `data/throughput.json` is on it. Running a
mutation for F130 printed it as changed, which is that list doing its job.

The suite was writing it. `write_throughput` writes `paths.THROUGHPUT`,
`data.throughput()` reads it, and the Campaign page shows it, so two tests
that called `write_throughput` without redirecting the path were rewriting
live state on every run.

One was benign and one was not. `test_throughput_label`'s live-campaign test
remeasured the same campaign, which only wastes the work. F130's
`test_the_live_measurement_is_unchanged` measured the **benchmark** campaign
into the shared file, so after any suite run the app reported 100 jobs at
0.4551 seconds per token instead of the 317 the running campaign had done.
Correctly labelled, because F104 made the file name its own campaign, and
describing the wrong one.

Both redirect to `tmp_path` now, and the file was restored by remeasuring the
campaign it is supposed to describe.

Checked the general case rather than those two: fingerprinting all thirty
protected files across a full suite run leaves three changed, and two of them
are the running campaign's `results.jsonl` and `state.jsonl`, which the runner
appends to every thirty-five seconds while a 148-second suite runs. That is
the runner, not the suite. After the fix the third stops changing.

Three mistakes of mine inside one small test, each caught by the next thing I
ran.

The first assertion was `calls <= redirects + 1`, which permits exactly one
unredirected call: the defect it exists to catch. The second counted its own
regex literal, finding five calls against four redirects in the file holding
the pattern as data, which `test_house_style.py` already solves with a
`THIS_FILE` skip. And the test that started it wrote the live file while
asserting that nothing should.

That last one is worth saying plainly. I wrote a test that corrupted the
state the application serves, in the same commit as a finding about a NaN
reaching a measurement, and what caught it was not the suite but a list
someone else had written down of files that must not change.

## F132. The live site compresses the HTML and not the 10 MB of JavaScript

Measured against nobble.mdeller.com rather than reasoned about. Page loads
are fast, 0.09 to 0.24 s for 24 to 164 KB of HTML, so there was no symptom
to chase. The assets are a different matter:

| Asset | Served |
|---|---|
| `static/vendor/molstar/molstar.js` | 5105.3 KB |
| `static/vendor/plotly/plotly.min.js` | 4451.9 KB |
| `static/vendor/tabulator/tabulator.min.js` | 432.4 KB |
| `static/vendor/d3/d3.min.js` | 273.2 KB |
| `static/vendor/molstar/molstar.css` | 71.1 KB |
| `static/css/depot.css` | 33.7 KB |
| Total to a first visitor | 10367.5 KB |

None of those shrink under `Accept-Encoding: gzip`. The HTML does: the
campaign page goes from 163.7 KB to 36.4 KB, a factor of 4.5.

That split is not arbitrary and it is not a half-configured vhost. nginx's
http-level default is `gzip_types text/html`, so the one content type that is
compressed is the one Flask serves through the proxy, and the assets, which
nginx serves itself by `alias`, are the ones it was never told to compress.
The vhost in `deploy/provision.sh` has no `gzip` directives at all, which
explains the observation exactly.

Worth stating what this is not. It is not a measured page-load problem: the
site is fast, and a vendored, pinned asset is fetched once per cache lifetime
and then served from the browser. It is a first visit on a slow connection,
and the honest size of that first visit is 10.1 MB where about 2.5 MB would
do.

The fix is six directives. Getting them onto the live box is the part that
needed care. `provision.sh` writes the vhost from scratch and certbot then
edits that same file in place to add the TLS lines, so regenerating it to
pick up a gzip block would take HTTPS off the site. So the block went into
`provision.sh` for the next clean provision, and `deploy/enable_gzip.sh`
exists to put it into the file that is already there: back the vhost up,
splice the block in after `client_max_body_size` with `sed`'s `r` command,
run `nginx -t`, and reload only if nginx says the result is valid, restoring
the backup if it does not. Running it twice is a no-op, and the worst case is
the configuration it started with.

`gzip_comp_level 5` rather than 9. The last levels cost noticeably more CPU
for a percent or two of size, and the droplet has 3.8 GB of RAM and also runs
gunicorn.

I could not apply it myself: a direct `ssh` to read the live vhost was
declined, which is the right default for a production box. The script is
written to be read before it is run.

## F133. The Tier B glue recall set contained no glues

`glue_recall_set` is the ligand side of spec 3.3's discovery arm, which asks
whether any known glue chemotype shows a Delta-ipTM signal against an
unexploited ligase. It selected BINMAN's `ccd_class = 'glue_candidate'`. The
rule behind that class, in BINMAN's own `ccd_class_rule` column, is
`size_and_no_furniture_signal`: large enough not to be furniture, and nothing
says it is furniture. A negative definition, and 7,676 CCDs satisfy it.

The ordering made it worse. `order by heavy_atoms asc`, so a limit took the
smallest end of that bucket. `glue_recall_set(15)` returned fifteen compounds
of ten heavy atoms each: 3-nitrotoluene, adipic acid, 3-hydroxybenzoic acid,
2-amino-6-fluorobenzonitrile. Lenalidomide has nineteen and is the smallest
thing this campaign calls a glue.

Replaced with the evidence the rest of the project runs on. A compound is in
the recall set if it was observed bridging a triaged E3 ligase in a deposited
structure, if a bridge of that compound is classed `molecular_glue` or
`protac` by BINMAN rather than `native_cofactor` or
`crystallisation_artefact`, and if it is not flagged as furniture. 130 CCDs
across CRBN, VHL, KBTBD4, DCAF16 and RNF113A, reduced to 121 Murcko
chemotypes because the spec's question is about chemotypes. Median 59 heavy
atoms.

Which of the three conditions actually does the work, measured rather than
asserted, because I asserted it wrongly first. The claim here was that all
three are load-bearing and that dropping the furniture flag admits citrate
and tetraethylene glycol. A mutation sweep did not catch dropping it, which
is how I came to measure:

| Conditions | CCDs | Admitted |
|---|---|---|
| all three | 130 | |
| without the furniture flag | 130 | nothing |
| without the evidence class | 133 | CLR, IHP, OH0 |
| without either | 137 | and CIT, PG4, XYZ, A1JQT |
| without the ligase join | 1,248 | 1,118 more, among them RAP, FK5, FSC, MFX, EVP |

The ligase join does most of the work and the evidence class does the rest.
Citrate and tetraethylene glycol are excluded by the evidence class, not by
the furniture flag, and the furniture flag changes nothing on today's data.
It is kept as the second of two filters on the same risk, because the
evidence class is someone else's annotation and a bridge classed
`molecular_glue` for a compound BINMAN already flags as furniture is the case
it covers. Kept, documented as redundant, and not claimed to be
load-bearing: an untestable condition is not a defect, but calling it
essential when it is not makes the next reader trust the wrong one.

The join is the interesting one. Without it the set is ten times larger and
it is not junk: it is rapamycin, FK506, fusicoccin, the fluoroquinolones,
etoposide. Those are the textbook molecular glues, and every one of them is a
glue of something that is not an E3 ligase. The mutation sweep caught none of
my tests on it, for the reason that makes the condition worth a test of its
own: what arrives when the join goes is a thousand real glues of the wrong
proteins, so the curated controls are still present, the fragments still
absent, the chemotypes still distinct and the median still glue-sized. Both
halves are now pinned, the seven named compounds being absent from the set
and present in the same query without the join, because asserting that seven
codes are missing proves nothing unless they would otherwise be there.

Worth stating as a property of the set rather than a defect: it deliberately
excludes rapamycin and FK506. Spec 3.3's question is about unexploited
ligases, and neither compound has been observed on a ligase.

The test is on the content of the set rather than on the query: all five of
the campaign's curated glues are in it, and none of the fragments the old
bucket returned first. A definition of "known glue chemotype" that excludes
pomalidomide or includes 3-nitrotoluene is wrong whatever SQL it is spelled
with.

My first attempt dropped lenalidomide. It shares a Murcko scaffold with
A1IWG, both at one deposition, and A1IWG sorts first alphabetically, so the
deduplication picked the unknown compound to represent the chemotype whose
known member is the point. The deduplication was right and the tie-break was
arbitrary, so the scaffold representative is now chosen by a stated
preference, curated glue first, and that preference is tested on the real
LVY/A1IWG pair rather than on a fixture.

Nothing caught any of this because nothing calls the function. See F134.

## F134. Tier B is selected, frozen, gate-passed and never run

Spec 3.3 is unusually direct: "**Tier B is in the first campaign** (decision
D-NOB-002). Do not defer it." The selection half is done properly. The
funnel is auditable, 15 ligases are frozen to
`data/tier_b_selection.parquet`, DCAF8L1, CCNF and ASB8 come out at ranks 1
to 3 exactly as the spec predicts, and PROGRESS.md records the phase-1 gate
as passing.

No Tier B pair exists in any campaign. The five campaigns on disk hold
`benchmark`, `sievers_zf`, `scramble`, `corrected` and `design` jobs.
`assemble_campaign`'s own docstring says what it emits: "benchmark panel,
Sievers arm and scrambles".

The gate is why this went unnoticed, and the gate is not wrong. Spec 4.6
words it as "Manifest contains the Tier B set, non-empty, with at least 10
ligases", and the manifest does. Selection and execution are separate halves
and only the first has a check. The LM's example query in spec 5 is "show me
Tier B pairs where the glue dependence beats the matched negatives", and the
open question in spec 6.3 is whether the Tier B arm publishes as a ranked
list: both presume results that do not exist.

What it would cost, measured rather than guessed. Receptor windows are 200
residues each, a glue is 59 heavy atoms at the recall set's median, a peptide
is 15, so a Tier B job is 274 tokens. At the campaign's measured 0.4825
s/token and 15 jobs per pair that is 0.55 hours per pair:

| Design | Pairs | Hours |
|---|---|---|
| 15 ligases, 1 chemotype, 1 peptide | 15 | 8.2 |
| 15 ligases, 5 chemotypes, 1 peptide | 75 | 41.1 |
| 15 ligases, 10 chemotypes, 1 peptide | 150 | 82.3 |
| 15 ligases, 121 chemotypes, 1 peptide | 1815 | 995.6 |
| 15 ligases, 5 chemotypes, 3 peptides | 225 | 123.4 |

Automatic scope reduction gets some of the way. The arms can go from three to
two by dropping the unconstrained ternary control, which is the
pocket-conditioning check and is already validated on tier A, and the seeds
from five to the three that `config/thresholds.toml` sets as the floor below
which a Delta-ipTM is not interpretable. That is 6 jobs per pair rather than
15, so the five-chemotype design falls to 16.5 hours.

Against the budget: 22.9 hours are spent, the running campaign has roughly 57
hours of tier 1 left, and `max_compute_hours` is 96. There is no room for
16.5 hours, and one chemotype against fifteen ligases cannot answer a
question whose subject is "any known glue chemotype".

So this is Gate G1 as CLAUDE.md defines it: the minimum viable set exceeds
`max_compute_hours` after automatic scope reduction. Recorded rather than
decided, because the three ways out are Marc's: accept that Tier B publishes
as a separate campaign, raise the budget, or supply a GPU. What is not
acceptable is the state it was in, where the spec says do not defer, the
project reports the phase complete, and the arm does not exist.

**Revised by F163:** the gate is not only about compute: Tier B cannot be assembled at all, because none of the fifteen has a receptor construct and neither mechanical route to one is allowed.
## F135. Refinement was never priced against the gate it can blow

Gate G1 is judged against `max_compute_hours`, and the projection it is
judged on prices tier 1 only. `curate.diversity.projected_hours` sizes a
selection of pairs at the measured tier-1 rate, which is the right question
when choosing how large a library to select. Nothing asked it about
refinement.

Refinement is not a rounding error on tier 1. It re-runs the top decile's
ternary jobs at 25 diffusion samples and 10 recycles against tier 1's 1 and
3. `tier2.py` contains no reference to `max_compute_hours`, to
`projected_hours`, or to any total: what it gives each job is a timeout, and
a timeout bounds one job. The main campaign's decile is 150 jobs, and 150
jobs at the six-hour timeout is 900 hours of permitted wall clock against a
96-hour gate.

Nothing had gone wrong, because tier 2 has never run. The chain runs it as
soon as tier 1 finishes.

The projection is a range, for the reason `scaling_bound` already gives:
Boltz runs the trunk once per recycle and the structure module once per
diffusion sample, and the split between them is unknown without instrumenting
a run. So the cost is `trunk * (r2/r1) + structure * (d2/d1)` with
`trunk + structure` equal to the tier-1 time, which is smallest when all of
tier 1 is trunk and largest when all of it is the structure module. On this
campaign's decile those extremes are 31 hours and 235 hours against 73 hours
remaining. One of them fits and one is three times over.

The gate is judged on the high end. A budget judged on its optimistic end is
how a budget is overrun, and I had it the other way round first: judging on
the low end so that a refusal would not depend on an unmeasured split. That
reasoning is right for a refusal and wrong for permission to start.

Being pessimistic is also temporary, which is the part worth keeping. The
range exists only because tier 2 has never run, so the first completed
refinement collapses it to a measured factor, paired by job id because a
tier-2 job id is its tier-1 job id plus a suffix. The refusal says so rather
than just refusing. Automatic scope reduction then drops pairs from the
bottom of the ranking, never seeds from a pair, and on the current campaign
five of the decile's sixteen pairs are affordable under the bound, with more
likely once the first one has been measured. Gate G1 opens only if nothing is
affordable.

Two mistakes of my own in the tests for this. `gate_g1` first read
`paths.CAMPAIGNS` for hours spent, so two of its tests passed only because
the live campaign had consumed 22.9 hours: the gate answered a different
question every time the runner finished a job, which is F131 again in a
different file. Accounting over the directory the campaign being priced lives
in fixes it for both the real case and the fixture. And with that fixed, the
two fixtures turned out not to exceed the budget at all, so the assertions
had been passing on live state rather than on the thing they name.

**Revised by F161:** the projection charged an unmeasured campaign nothing, so the gate reported a fit at 0.0 hours.
## F136. The progress report's library figures were from an earlier build

PROGRESS.md's phase table said "25,567-peptide library reduced to 220". The
manifest says 25,519 candidates reduced to 158. Both of the stated numbers
were real once: the candidate pool before a deduplication, and a budget from
before the hardware probe measured the real one.

Nobody would act on a wrong reduction ratio, which is why it sat there
through every rewrite of that table. It is now recomputed from
`library.summary.json` by a test, along with the one sentence in that cell a
reader would actually challenge.

That sentence is the part worth having found. The manifest records
`"diverse": 0` and says why: the mandatory benchmark and Sievers members plus
their composition-matched scrambles cost 158 against a budget of 156, so the
diversity selection had no headroom and selected nothing. Spec 3.4 names five
peptide sources and the campaign's library holds three. Curated UbiBrowser
degrons, Koren C-degrons and ProtCID packing-only epitopes are built as
candidates and then squeezed out entirely.

That is not a defect. The manifest states it in two notes, the mandatory
members are deliberately not trimmed because the Sievers split is the
headline ROC's control set, and the queue is priority-ordered so a run cut
short loses discovery from the tail rather than a control from the middle.
What was missing is that the progress report said "library reduced to 220"
and nothing on the way to it said "and this campaign is calibration only".
The cell now says so, and a test fails if `diverse` stops being zero, which
is the right moment to rewrite the sentence rather than leave a stale one
standing.

Also corrected: a finding that computed the campaign's size as "158 pairs
times 5 seeds times 3 arms is 2,360 jobs". That product is 2,370. The queue
holds 2,360 because two pairs carry two arms rather than three, which is the
fact the sentence was reaching for and had rounded into the arithmetic.

## F137. Refinement's numbers were written, published and read by nothing

Tier 2 writes `scores_tier2.jsonl`. `deploy/build_atlas.py` publishes it, and
nothing read it: not the app, not validation, not the LM. The pose catalogue
offered the refined coordinates with no number beside them, so there was no
way to tell whether refinement had improved anything. The log entry that made
tier 2 visible says "the atlas now publishes the tier-2 slice, the app
exposes it". The app exposed the structures.

Showing the scores is easy and showing the wrong ones is the risk, which is
the part worth writing down. `iptm_min` is a minimum over seeds, and the
minimum of a larger sample of the same distribution is smaller in
expectation, so tier 2 at 25 diffusion samples sits below tier 1 at 1 before
anything physical has changed. `delta_iptm` is their difference and moves with
it. A before-and-after of either reads as the refinement working.

So `nobble/sampling.py` states the rule rather than leaving it to whoever
writes the next panel: a mean, a median or a proportion survives a change of
sample count, a minimum does not. `bridge_formation_rate` is a proportion
over jobs, `bridge_percentile` a median of percentiles,
`convergence_score` is built from a mean pairwise RMSD, and each answers the
same question at either sampling regime. The comparison is a whitelist, so a
quantity added to `scores.jsonl` later is withheld until someone has thought
about its shape. A blacklist fails the other way, and its failure is a biased
number presented as an improvement, which would look exactly like a result.

The module imports `nobble.numeric` and nothing else. The droplet serves a
precomputed atlas with no scoring stack and no gemmi behind it, and this is
read from both sides.

It imported nothing at all on the first attempt, and that was the mistake.
Writing the change as `round(after - before, 4) if isinstance(before, (int,
float)) and isinstance(after, (int, float))` kept the module dependency-free
and admitted a NaN, which `tests/test_numeric_rule.py` rejected on its next
run with the reason already written into its docstring: a new
`isinstance(x, (int, float))` is a fifteenth copy of a rule with one home and
it admits NaN by construction. A NaN change would have reached the page as
the literal `NaN`, which `JSON.parse` refuses, so the panel would not have
rendered at all rather than rendering a wrong number (F130). `numeric` is
pure stdlib precisely so that importing it costs the droplet nothing, and the
import test now checks that transitively rather than checking for no imports
at all.

Verified by running tier-2 scoring for the first time, on a copy of the
benchmark campaign with a synthesised refinement queue. It works, and
`delta_iptm` comes out None with `seeds_binary` 0, which is right: tier 2
refines ternary jobs only, so there is no binary arm to difference against.

## F138. QC reported a clean site against a server from hours earlier

Browser QC drives a live server and reports pages captured, non-200
responses, console errors and axe violations. It had no idea which build was
answering.

I ran it after adding F137's panel and it said 14 pages, 0 non-200, 0 console
errors, 0 serious axe violations. The panel was not in any of those pages. A
Flask process from earlier in the build still held port 5055, my own server
had failed to bind and died with "Address already in use" in a log nobody was
reading, and the report was a true description of the old build.

What caught it was looking for the new element in the DOM and being told
there was no such element. That is a thing I happened to do and not a thing
the harness does, which is the whole finding: the verification step could
pass against the wrong subject and say nothing.

So `/healthz` now reports a fingerprint over the app's own source and
`qc/qc.mjs` refuses to report on a server whose fingerprint is not the
working tree. The expected value comes from `tools/app_fingerprint.py`
rather than being recomputed in JavaScript, because two implementations of
one hash drift and the symptom of that drift is QC rejecting a server that is
in fact current.

Which files count took one correction. Vendored libraries are excluded, since
hashing 10 MB of Mol* and Plotly makes the fingerprint a statement about
Mol*. But the loose file beside them, `molstar-bridge.js`, is BINMAN's own
shared code, and it changes: the first thing I did after adding the check was
widen that bridge, which fixed a serious axe violation and moved no
fingerprint at all. Loose files in `vendor/` are now included and the pinned
subdirectories are not, with `VENDOR.json` standing in for the libraries so a
version change still moves the digest.

Two things fell out of pointing the tools at a named host.

`qc/axe_detail.mjs` was hardcoded to `https://nobble.mdeller.com` while
`qc.mjs` ran against localhost. The two reported different violations and
neither said which host it had audited, so for a while I was reading
production's accessibility report as though it were the working tree's. It
takes `NOBBLE_BASE` now and prints the host it looked at.

And the violation it found on the live site is real and already fixed here:
four serious colour-contrast failures on `/pose`, the backronym's italics
fading from #7b7e79 to #b9bbb6 against #f7f7f4, the last at 1.8:1 against a
required 4.5:1. The working tree renders all of them at #61655f, which
passes. They will clear on the next deploy. The live site's `/healthz`
reports no fingerprint at all, which is the honest statement that it predates
this check.

The violation in the working tree was `.msp-logo`: Mol*'s own logo, rendered
as a link with no text, in the tab order with no accessible name. Reachable
only once the plugin has initialised, which is why a QC run whose viewer
loads nothing never sees it. Fixed by widening `mountViewer` in BINMAN in
place rather than forking it (D-NOB-007), and re-vendoring the identical
file. Named rather than hidden: the logo is Mol*'s attribution and removing
it is not ours to decide, and a name satisfies the rule while leaving the
link where its authors put it. Retried on a short bounded timer because the
logo appears asynchronously after the mount, so a single query right after
construction finds nothing.

**Revised by F159 and F162:** the guard reported an unreachable server as a stale build, and a file vanishing between the listing and the read aborted the check with a traceback.
## F139. The copy budget was a rule nothing could measure

CLAUDE.md sets it: "Budget: under 40 words per panel, under 150 per page,
excluding tables, labels and pipeline-generated status text." Nothing
measured it for the whole build.

Measuring it took three attempts and the first two were wrong in ways worth
recording, because both produced a confident number that would have justified
cutting copy that should stay.

A static count over the templates said every page but one was over, the worst
panel at 126 words. It sums paragraphs that are mutually exclusive in the
rendered page: an empty-state hint and the text that replaces it never appear
together. So I measured the rendered pages instead, which said five of seven
were over.

That was still wrong, and in the more interesting direction. The composite
panel read 124 words, which looked like clear bloat until I read it: six
paragraphs, one per component, each a single line saying what that number
means. That is exactly what the rule asks for, and those lines are
`weight__note`, the slider's own `aria-describedby`, which makes them labels,
which the rule excludes. The markup already separated all three excluded
categories and my selector ignored it: `weight__note` for a control's label,
`mono` for machine output, `.empty` for a transient state. With the rule's
own exclusions applied, the composite panel reads 23 words and `/benchmark`,
`/interactions`, `/design` and `/` all pass.

What was left was one real violation and one judgement. The violation was
`/pose` at 96 words, of which 49 were presentation provenance: the AlphaFold
four-band scale, the translucent gaussian surface, the emissive shell. That is
reasoning, it is the category the rule names and sends to DECISIONS.md, and it
was already in `molstar-bridge.js`'s own comments. It is now a Jinja comment,
so a reader of the template still finds it and a reader of the page does not.
The affinity disclaimer went from two sentences to the one the rule allows.
`/pose` reads 37 words.

`/delta` read 50 while the Sievers arm is still running and 39 once the ROC
computes, the difference being the empty state. Excluded as transient: the
budget is about the copy a finished page carries, not about a message saying
what has not run yet.

`/about` is 526 words over ten panels and is exempt by D-NOB-067 rather than
by oversight. The rule's stated purpose is to keep reasoning off the data
panels, and the page that exists to explain the project is what makes that
possible rather than what defeats it.

The measurement now runs inside browser QC and exits 4 when a data page is
over, which is the part that matters: the two previous attempts at this
number were mine, and the reason the budget drifted for a whole build is that
checking it was a thing somebody had to decide to do.

**Revised by F159 and F160:** the budget held only while the headline panels were empty, and one of the filter's classes existed on nothing.
## F140. The deploy checked that the site worked, not that it was this site

`deploy/deploy.sh` ends by fetching every page and requiring 200, and the
comment above it records why that replaced a /healthz check: /healthz has
answered `{"ok": true}` while every real page returned 500. That check is
right and it is not sufficient. An rsync that excluded a file, a gunicorn
that restarted on a stale import, a worker that outlived the restart: each of
those answers 200 on every page with the previous build, and the deploy
reports "deployed and verified".

Which is F138 one layer down. Browser QC could pass against a server from
hours earlier; the deploy could pass against a droplet that had not taken the
code. The same digest closes both, so the deploy now records the fingerprint
of the tree before the rsync and compares it against what `/healthz` reports
after the restart.

An absent fingerprint is a failure, not an abstention. A server from before
this check reports none, and after a successful deploy the new code is
running and reports one, so "cannot tell, carry on" would pass exactly the
deploy that did not take effect.

Two things my own tests caught while writing it. The fingerprint was being
taken after the code rsync, which describes the Mac rather than the bundle:
the same thing unless the tree changes during a deploy, which is when the
check matters. And the test that the hashed files are all rsynced exists
because an excluded path would be hashed on the Mac, absent on the droplet,
and every deploy would then refuse for a reason that looks like a failed
deploy.

Verified against real servers rather than by reading the shell: the
extraction returns the digest from the current build and the empty string
from the stale process still holding port 5055, which is the branch that
refuses.

## F141. Head C's abstention named what the campaign has, under "missing"

Spec 5 gives Head C one job beyond refusing: "Head C abstains when the
campaign has not run the pair in question and states what is missing."

`Answer.missing` was set from `_named_pairs`, whose signature said it
returned the question's gene and ligand names "split into present and
absent". It returned `present, []`. The absent half was empty on every path,
and the reasoning for the half that was never written sat in a comment
directly above the return: "Only treat a word as a named entity if it looks
like one: present in the campaign, or a gene-shaped token the campaign
plainly lacks."

The caller then assigned the present half to `missing`. So a question about
BRD4 and VHL, against a campaign holding both, abstained with
`missing: ["BRD4", "VHL"]`. The field is serialised to the browser by
`/api/ask` through `asdict`, so that is what the endpoint published.

Two reasons it survived. No template renders `missing`, so the only reader
was a client nobody had written. And the model is unconfigured, so `ask` has
never run against a real question on the live site.

The rule it used to decide what a gene name looks like was "three characters
or more", which makes "the" and "and" candidates for being gene names. That
is the part that convinced me not to fix the heuristic. What is missing is
derivable from the query Head A produced, which names its own fields and
values, so no rule for the shape of a gene name is needed. Each filter is
applied on its own: one that matches nothing names something the campaign
does not hold. If every filter matches alone and the conjunction still does
not, every part has been run and the combination has not, which is a
different and more useful thing to be told, and it is precisely the case the
old code got backwards.

The cutoff sweep then failed, which is the detail worth keeping. That length
rule was in `ALLOWED_INT_COMPARISONS` with the justification "shortest token
worth matching on", so the project had granted it an explicit exemption, and
`test_the_integer_allowances_are_all_still_real` noticed the allowance no
longer describes anything in the tree. An allowlist that is only ever added
to stops being a list of the cutoffs that exist, so the sweep checks both
directions. Removing the heuristic removed the need for the exemption.

## F142. The mutation harness could not tell the runner's appends from a rewrite

The full suite failed on
`test_mutation_harness.py::test_a_real_mutation_still_reports_and_exits_cleanly`,
and the same test passed on its own. It drives `tools/mutate.py` through a
real mutation, and `mutate.py` exits 4 when a protected live-state file
changed while the sweep ran, on the stated grounds that "a mutation removes a
safety, so a test run under it can reach things no test should touch".

That is right about the hazard and wrong about how it detects it. The sweep
compared size and modification time, so any write at all exited 4, and the
campaign runner appends a line to `results.jsonl` and `state.jsonl` every
thirty-five seconds or so. With a campaign running, whether this test passes
depends on whether the runner happened to finish a job during the second or
two the sweep's inner pytest took. F131 had already recorded the fact and
read it the other way round: it noted that two of the three changed files
were the runner's and fixed the third.

An append and a rewrite are distinguishable, exactly rather than
heuristically. The runner only adds bytes to the end, so the bytes that were
there are still there; a test that corrupts live state rewrites the file,
which is what happened when one of mine replaced a running campaign's
throughput measurement with a benchmark's. So the previous `before_size`
bytes are re-read and hashed, and a prefix that still matches is the runner
doing its job. Reading only `before_size` bytes costs the same whether the
file is a kilobyte or a gigabyte, which was the original objection to hashing
at all.

I then wrote the same class of defect into the fix. The prefix digests were a
module-level dict that `_fingerprint` filled as a side effect, and
`_live_state_changes` calls `_fingerprint` to get the "after" state, so the
baseline was overwritten with the new content's digests before any comparison
happened and every append still read as a rewrite. The four-case check caught
it immediately: append, rewrite, truncation, no change. A function that looks
like a measurement and quietly replaces the baseline is the shape this
project keeps finding, and I put one inside the fix for another. The digests
are now taken explicitly by the caller and passed in.

**Revised by F154:** an identical rewrite has the same size and prefix, so it was reported as the runner appending.
## F143. The status page showed half of Gate G1

`tools/status.sh` has a gates section, and it reported G1 from
`projected_hours`, which prices tier 1. So a reader saw "G1 compute closed,
52.6 h projected, max 96" while refinement of the decile cost 29 to 219 hours
against 71 remaining.

`nobble.execute.budget` has computed that since F135. It was not surfaced
anywhere a reader looks, and for a status page whose stated job is to say
"which gates are open" that is most of the way to not having computed it.

Three things the line had to get right, and I got each wrong first, which is
worth recording because every one of them produced a plausible-looking number.

Scope. `gate_g1(campaign)` with no pair list prices every ternary job in the
campaign, so the first version read "OPEN, 159 to 1,190 h for 1,570 jobs".
Refinement only ever runs on the top decile. Pricing the whole campaign
answers a question nobody asks and reads as a gate about to stop the build.

Source. The second version read the decile out of `tier2.json`. That file
answers "what did the last selection cost", and a status page is asked "what
will refinement cost". The two agree only until scoring advances: the
selection on disk was taken against the six pairs scored at the time and
names one pair, where the finished campaign's decile is sixteen. So the
decile is sized from the campaign's own pair count, and labelled as a size
rather than as the ranking, because which pairs are in it needs the scores.

Outcome. The third version said "OPEN" and stopped there, which reads as a
halt. It is not one: `tier2.run` drops pairs from the bottom of the ranking
until the rest fits, and only an empty result opens the gate for real. The
line now says both, and on the running campaign that is "OPEN on the full
decile of 15 pairs, 5 of 15 fit after reduction, gate closed".

Also corrected: `run_chain.sh` described the deploy check as "refuses to
report success unless all nine routes answer 200", which was the whole of it
until F140 added the build comparison. A comment a reader relies on to know
what the chain guarantees.

## F144. A correction tool whose scope argument did not scope its writes

`tools/rerun_pair.py --campaign <dir>` reads that campaign's queue and
rewrites the YAMLs it names. The paths in a queue row are absolute by
construction, since F32 made them so, and the tool writes to
`Path(row["yaml"])` with nothing comparing it to the campaign on the command
line.

So pointing it at a copy of a campaign rewrites the original's files and
leaves the copy untouched. That is how anyone would test a destructive tool,
and it is what I was about to do: a fixture assembled with
`cp campaigns/<live>/*.jsonl` carries the live campaign's paths, and
`--apply` against it would have edited the running campaign's inputs.

No harm has been done, because the chain passes the campaign it means. The
hazard is in the shape of the interface: an argument that looks like a scope
and only selects a source.

Every target is now required to be inside the campaign named on the command
line, and the whole run refuses rather than correcting part of one campaign
and part of another. The structure route in the app has had the same check
since it was written, which is what made its absence here recognisable.

## F145. It found no reference, on every invocation the chain has made

`_known_good` returns the same job's YAML from another campaign, "if exactly
one has it", excluding the campaign being corrected:

    if candidate.parent.parent != exclude

`ROOT.glob` yields absolute paths, so the left side is absolute.
`newest_complete` prints `campaigns/campaign_<stamp>` and the chain passes
that, so the right side is relative. An absolute path never equals a relative
one. The campaign being corrected was therefore not excluded from its own
search, every YAML name was found twice, "exactly one" was never true, and
the function returned None for every job.

This is the comparison between two spellings of one path that F32 is about,
and F32 is cited in this file, at the call site, eighty lines below.

Measured rather than reasoned: with the chain's own spelling the function
returns None; with both sides resolved it returns the benchmark campaign's
copy, and all three spellings of the same directory now agree. The
"exactly one" rule is unchanged and still refuses two candidates, which is
the part of it that was right.

## F146. And then it cleared the results anyway

The two halves of the tool are "regenerate the YAMLs" and "clear the results
so they re-run", and the second only means anything if the first worked. With
no known-good copy the input is whatever it already was, so clearing the
results re-runs the same jobs on the same bad YAML.

Under F145 that was every job, every time. The chain's correction step would
have printed "no known-good copy" fifteen times, dropped thirty state rows
and fifteen results rows, re-run fifteen jobs on the hydroxyproline YAML they
were meant to replace, and left `stale_inputs` refusing the publish exactly
as before. The GPU time is the smaller loss; the larger one is that the
publish blocker would have looked addressed.

It now refuses, with a non-zero exit, for any job whose input it could not
verify. A job skipped because its YAML already matched the reference is a
different case and is not counted: that input is verified and re-running it
is a legitimate request.

One of my own tests for F144 then passed for the wrong reason. It put the
queue's target inside `campaigns/`, which gave `_known_good` two candidates,
so this refusal fired first and the containment check could be disabled
without the test noticing. The mutation sweep said so. The target now sits
outside `campaigns/` altogether, which is what a relocated campaign looks
like, so exactly one reference exists and containment is the only thing that
can stop the write.

## F147. The scan profile belonged to the ranked parent, not the scanned one

The design arm's one durable claim is the ordering of positions in an
alanine scan: `scan_profile`'s own docstring says so, because an ordering
survives a monotone miscalibration of the scale in a way "this peptide will
be degraded" does not.

`report.build()` chooses a parent from the current scores and then asked the
newest design campaign about that parent's variants:

    lifts = lift_module.from_scores(scored[-1], chosen["peptide_id"])

A design campaign is assembled for whichever parent led when it was
assembled. The chain keeps the two in step at that moment, because stage 4
re-assembles the scan from this report's own preview, and nothing makes them
stay in step afterwards.

They are already apart. The assembled design campaign records
`benchmark_888fd2c63e`; `report.build()` now ranks `benchmark_83c557c3dc`
first, because the main campaign has scored more pairs since the scan was
assembled. So this was not a hypothetical: the scan would have run its 240
jobs, scored them, and shown no profile at all. `from_scores` matches
variants by `parent_peptide_id`, finds none for a parent the campaign is not
about, and returns "parent not scored", which on the page is indistinguish-
able from the scan not having run.

The failure is graceful, which is why it would have been hard to notice. No
number is misattributed; the panel is simply empty after seven hours of GPU.

`campaign.json` records `parent` and `parent_sequence`, written by the
assembler, so the profile now comes from the campaign's own record of what it
scanned. Where that disagrees with the ranking, the report says so rather
than leaving a reader to wonder why the profile is of a different peptide
from the one at the top of the list. Reading the artefact's own record rather
than re-deriving it is F137's lesson in a second place.

The fallback matters too. A design campaign with no recorded parent falls
back to the ranked one, because older campaigns predate the field, and that
is exactly what the old code did unconditionally: the fallback is pinned by a
test so it cannot quietly become the normal path again.

Also noted while reading: `run_design.sh` writes `scan_profile.json` beside
the campaign and nothing reads it. The published profile is the one
`report.build()` recomputes into `design.json`. Two computations of one
value is the shape this project keeps finding, and after this fix both take
the parent and the sequence from the same `campaign.json`, so they agree by
construction rather than by coincidence. The file is kept and labelled rather
than deleted, since it is the only per-campaign copy.

**Revised by F160:** the profile was attached to the right peptide and the panel above it still named the other one.
## F148. Verifying the publish path for refined poses, and the one thing holding it together

The atlas rebuild with tier 2 and the design scan included is the last stage
of the chain that has never run. F137 made the app read the tier-2 slice, and
that was checked against a local campaign; whether it works through the
published bundle was still an assumption.

Run rather than assumed. `build_atlas.py` takes `NOBBLE_ATLAS_OUT`, so the
build can go to a scratch directory instead of over the published one, which
is what F131 wishes had been true of the test that rebuilt the live atlas
from a campaign with 54 of 2,360 jobs scored.

Built from a campaign carrying tier-2 results and scores: 110 structures
where tier 1 alone is 100, 28.5 MB, the PROTAC-DB redaction verified, and
both tier-2 files present with all ten of their structures published under
flattened names. Serving that bundle through `create_app`, the pose
catalogue offers 25 structures of which 10 are refined, every one of the ten
URLs returns 200, and the refinement comparison renders. So the path works
and there is no defect to fix.

What the exercise did surface is how little holds it together. A structure
reaches the browser through three independent constructions of one filename:
the builder copies it to `f"{row['job_id']}.cif"` and rewrites the row to
`structures/<that>`; the API offers `f"/structure/{row['job_id']}.cif"`; the
route serves `/structure/<path:job_id>.cif` by looking the job up again.
Nothing tied the three together.

They agree today. If the published name ever gained a prefix, a tier suffix
or a different extension on one side only, every pose URL would 404 while the
atlas, the API and the page each looked correct in isolation: the catalogue
would list structures and the viewer would show its empty state. That is the
same shape as F135's `TIER2_SUFFIX`, where a job id is built in one module
and parsed in another.

Pinned without rebuilding an atlas: the three spellings, the `path`
converter that makes a job id's punctuation a non-question, and a check over
the published bundle that every structure on disk is named by a row and
every row's structure is on disk. Both directions, because a file nothing
points at is dead weight on the droplet and a row pointing at nothing is a
404 in the viewer. The current atlas holds 100 of each and they match
exactly.

## F149. Three scientific paths verified before they run, and nothing to fix

The campaign has roughly forty hours left, after which scoring, the ROC, the
composite fit and the publish all run for the first time on real data.
Finding out then that one of them refuses is forty hours too late, so each
was run on a fixture with the campaign's own shape.

The matched-control ROC. Its arm scoping and its labels agree exactly with
what the pipeline writes: `tier == "sievers_zf"` with `degraded` and
`not_degraded`, which the queue carries for 24 and 96 pairs. On a fixture of
that shape it computes: AUC 0.8043, a bootstrap interval excluding 0.5, the
seven benchmark pairs correctly excluded from the curve, and the seed balance
reported as balanced. The secondary graded test still names itself as
unavailable, which is right.

The composite fitter. 158 labelled pairs, 31 positives and 127 negatives,
exactly the campaign's own composition, fitting at objective 0.923 across
five components. Both caveats fire: that the AUC is in-sample because the
grid maximised it on the same pairs, and that the lysine term carries weight
without validated discriminating power.

Spec 1.3's MSA policy, which is upstream of every prediction and which I had
not read. It is implemented exactly. Across all 2,360 YAMLs the receptor
chains reference cached `.a3m` files, seven distinct ones from the seventeen
on disk; the peptide chain carries `msa: empty`, which is Boltz's way of
saying no MSA and is what the spec requires; ligand chains carry no `msa`
key at all. One MSA per construct, not one per peptide.

The design lift path scores 15 of 15 positions with nothing refused. The
publish path serves refined poses from a scratch-built atlas, all ten URLs
at 200.

One thing worth recording rather than fixing. `weights._features` reads
`lysine_reach` as a mapping, and my first fixture gave it a float, which
crashed the whole fit with an `AttributeError`. Every one of the twenty
scored rows on disk carries a mapping, and the scorer is the only writer, so
a float cannot arrive without a code change: the crash is unreachable and
the fixture was wrong, not the code. Recorded because the next person to
write a fixture for this will make the same mistake, and because
`lysine_reach` having had two shapes before is what F106 was about.

## F150. What the primary signal is a percentile of

`reference_distribution` builds the population `bridge_percentile` is
measured against, and its docstring said "only `status = 'ok'` rows, and only
genuine two-chain bridges, so the percentile compares like with like". The
query filters on `status` and a non-null value. There is no exclusion of
symmetry-mediated contacts, of the `crystallisation_artefact` evidence class,
or of furniture ligands, and there never was.

So the reference population includes 1,890 bridges BINMAN classes as
crystallisation artefacts and 38,748 symmetry-mediated ones: PEG and citrate
wedged between lattice neighbours, counted alongside pomalidomide in CRBN.
For the project's primary signal, that is worth being sure about.

It is correct, and the spec settles it rather than my judgement. Spec 4.1
names the population by its size, "a percentile against the distribution of
285,996 experimentally observed bridges already in the BINMAN atlas", and
285,996 is the unfiltered count. Filtering would produce a different number
from the one the spec specifies.

Whether it matters is a separate question from whether it is correct, and
that one is measurable. Against four populations, all bridges, symmetry
excluded, artefacts excluded, and the glue and protac classes alone, the
median dSASA runs from 767.9 to 805.0 square angstroms and a given
prediction's percentile moves by one to six points:

| dSASA | all | no symmetry | no artefacts | glue and protac only |
|---|---|---|---|---|
| 300 | 5.87 | 4.17 | 5.88 | 5.94 |
| 500 | 23.51 | 18.99 | 23.43 | 18.37 |
| 800 | 52.88 | 49.47 | 52.71 | 53.13 |
| 1200 | 86.34 | 85.06 | 86.28 | 92.65 |
| 1800 | 99.01 | 98.88 | 99.00 | 99.36 |

The glue-class population is 11,467 bridges and its median is 769.8 against
the full population's 767.9. Molecular glue interfaces are, by this measure,
indistinguishable in size from bridges in general, which is why the choice
of reference barely moves the answer. A concern retired with numbers rather
than argument.

The docstring is corrected, because it mattered in one respect the
measurement does not settle: a high percentile means "a larger interface
than most bridges the atlas has observed", incidental ones included, and not
"larger than most molecular glue interfaces". Here those are nearly the same
claim. They are not the same claim, and the stronger one is the one a reader
would assume from the word "genuine".

## F151. The design arm's cofactor guarantee was resting on a comment

`lift` is `delta_iptm(variant) - delta_iptm(parent)`, and its docstring is
explicit that a difference is interpretable only when its two terms differ in
one thing. `MATCHED_CONDITIONS` enumerates those things: construct, e3_gene,
ligand_key, modality. The structural cofactor is not among them, and a score
row carries no cofactor field at all, so `lift.compute` could not compare
them if it tried.

D-NOB-038 is about exactly this hazard, and `run_design.sh`'s header
attributed the protection to preflight: "the failure worth catching is the
silent one: a variant whose cofactor differs from its parent's completes
perfectly well and reports the missing ion as the substitution's effect".

Preflight does not check that. It builds `cofactor_by_pair[pair][arm]` and
requires a pair's binary and ternary arms to agree, which is D-NOB-034 and a
different claim: it stops Delta-ipTM being a difference across the ion, not
the lift.

The guarantee is real and it lives somewhere else. `build_manifest` calls
`requires_structural_zinc` once, on the parent, and every variant inherits
the result, with a comment saying why inferring per variant would be actively
wrong: an alanine scan mutates the coordinating cysteines, so a
per-variant inference would drop the ion at exactly the positions the scan
exists to measure. Verified on the assembled campaign: 16 pairs, none with
zinc, nothing mixed within a pair, and `campaign.json` recording the decision
once with its reason, "incomplete coordination site (2 Cys, 0 His): no zinc
added rather than a zinc with nothing to hold it".

So there is no defect in the behaviour, and two things worth fixing about its
standing. The guarantee was structural and unpinned, resting on one comment
in one function; it is now a test that the call happens once in the manifest
builder and once in the module, that no assembled scan mixes cofactors across
its pairs, and that the decision is recorded with a reason. And the comment
that sent a reader to preflight for it now says which half preflight owns
and where the other half comes from.

A guarantee by construction is better than a guarantee by check. It is worse
than either when the documentation points at the wrong one, because the next
person to change the assembler reads that documentation.

## F152. Which assertions never ran

The failure that recurs most in this project is a test that cannot fail.
F107 had two tests looping on a key the plan does not carry, so every
iteration hit `continue`. F111's strict-side test filtered on a line that
never matched. F122's asserted the wrong check. F131's permitted the defect
it existed to catch. One of mine this session asserted the right outcome for
the wrong reason. Every one passed, and passing is what made them invisible.

A static sweep finds the shape and drowns in it: 68 tests have every
assertion inside a loop, and nearly all of those loop over something that
cannot be empty, such as every template or every construct. A list of 68
tests to read is not a sweep anyone runs twice.

The decisive measurement is whether each assertion *executed*. One that never
runs cannot fail, whatever it says, and that holds whether it sits behind an
empty loop, an early return, a skip, an untaken branch or a filter that
matches nothing. `coverage` is not in the environment and this needs one
number rather than a report, so `tools/vacuous_tests.py` runs the suite under
a twenty-line tracer.

2,063 assertions, 2,049 executed, 14 never reached. That is a list worth
reading, and reading it gave three outcomes.

Eleven are honest. Four are behind `pytest.skip` for a state this checkout
does not have: no recomputed atlas values, a campaign occupying the GPU, tier
2 not selected. Seven are the untaken branch of a conditional whose other
branch asserts, which is how a test should handle live data it cannot control:
`test_gates.py` checks for "Provisional" when pairs are incomplete and for
its absence when they are not, and only one of those can run.

Two were mine, from F147, and both were worse than they looked. One returned
early when the ranked parent happened to equal the scanned one, so it
asserted nothing; the other returned early when the live campaign and the
live report happened to agree. Standalone they disagree, so the assertion
should have run, and under the full suite it did not. The reason is the
finding inside the finding: `data.configure()` sets a module global that
`monkeypatch` cannot undo, nine test files call it, and
`design.report.build()` reads `app_data.scores()` to rank its candidate
parents. So whether my test asserted anything depended on which tests had run
before it. `tests/conftest.py` now restores `_CAMPAIGN` and the cache around
every test, and both tests assert on both branches.

One was genuinely vacuous. `test_the_bridge_reference_count_is_the_one_quoted`
searched `thresholds.toml` for a key containing "bridge" with an integer value
over 100,000, and there is no such key: the count is a property of BINMAN's
atlas, not a configured cutoff. `quoted` was always None and the comparison
behind `if quoted is not None` never ran, so the README's 285,996 was checked
against nothing at all. It now counts the atlas and requires the spec to state
the same figure, so three places agree rather than two of them agreeing with
each other.

What the sweep cannot do is tell whether an assertion that did run is *about*
anything: F122's ran and asserted the wrong thing. It narrows where to look.

## F153. The project's own mutation sweep covered almost nothing

`tools/mutate.py` carries a default list of mutations, and the list held
five, all in `curate/`. Its docstring says five sweeps with it found eleven
real gaps, which is true and is about sweeps someone wrote anchors for by
hand. With no arguments it said nothing at all about scoring, validation,
the design arm or the budget: every check of those modules this build has
been an ad-hoc run, and that method covers what someone remembered to type.

Eight added, each reversing a decision the project argued for in a docstring
or a decision record, so "not caught" would mean the argument is unguarded
rather than that the mutation is exotic:

- the receptor-to-peptide ipTM taking the best segment instead of the worst,
  and the asymmetric pair-ipTM matrix read optimistically, which are the two
  halves of the conservative-minimum choice spec 4.3 rests on
- convergence no longer falling with RMSD
- scrambles and non-degraded peptides no longer counting as negatives in the
  composite fit
- the ROC drawing a curve with too few pairs on a side
- lift no longer subtracting the parent
- the refinement gate judged on the optimistic end
- the glue recall set no longer requiring a ligase on one side

Twelve of thirteen caught, and all eight of the new ones. The suite is
genuinely holding those decisions.

The one not caught is a pre-existing entry: in `curate/plddt.py`, CA atoms
stop being preferred for the pLDDT profile. Recorded rather than fixed here,
because the profile's values move and nothing currently asserts which atom
they came from; the honest statement is that the preference is a documented
choice with no test behind it.

**Revised by F155:** one of the mutations it added cannot be caught, because the behaviour it reverses is unobservable.
## F154. A sweep that excused the thing it exists to flag

Running F153's sweep printed four lines saying a protected file "grew by
appending while the sweep ran: the campaign runner, not the mutation". Two
were the campaign's `results.jsonl` and `state.jsonl`, which is what F142
added that message for. The other two were `deploy/atlas/comparison.json`
and `deploy/atlas/design.json`, which the campaign runner does not write.

Three defects behind it, each a consequence of the last.

Mine first. F142's `_grew_by_appending` accepted `st_size >= before_size`
with a matching prefix. A file rewritten with identical content has the same
size and the same prefix, so it was reported as an append when nothing had
been appended and something had rewritten a published file. Requiring
strictly more bytes fixes it, and the four cases are pinned: append
tolerated, identical rewrite flagged, same-size rewrite flagged, truncation
flagged. Nothing was lost by that particular rewrite; the report was a false
statement about which process had touched a protected file, which is the one
thing the check exists to say.

Then what the rewrite was. Two negative controls perturb a published file,
run a check against it, and restore it in a `finally`:
`test_atlas_drift.py` truncates `comparison.json`'s conclusion to prove the
drift check sees it, and `test_provenance_report.py` renames the published
design parent to prove the provenance line marks a disagreement. Both are
right to need a perturbation and both restore it, which is why the content is
identical and `git diff` is empty. The window is real: a run killed between
the write and the restore leaves the live bundle holding a truncated
conclusion or naming a parent that is not the ranked one. Two things already
contain that, the file being tracked and the deploy's own drift check
refusing to publish while it disagrees with the code, and neither is a
reason to keep writing a published file from a test.

Both now work on a copy. `atlas_drift.PUBLISHED` takes
`NOBBLE_ATLAS_PUBLISHED`, for the same reason `build_atlas.py` takes
`NOBBLE_ATLAS_OUT`: a reporting tool should be pointable at a bundle other
than the live one.

And the third, which the first attempt at that fix exposed. The drift line
honoured the override and the design-target line did not, because
`provenance.py` held a second, hardcoded spelling of the published path,
`Path("deploy/atlas/design.json")`, a few lines from the drift check that
reads the same bundle through its own constant. So a test pointed at a copy
still read the live site, and said so by reporting the real parent. One
thing spelled twice, which is this project's most common defect and the
reason the first version of the fix looked like it worked.

The suite now leaves both published files untouched.

## F155. The untested choice could not be tested, and the one beside it could

F153's sweep left one mutation uncaught: in `curate/plddt.py`, CA atoms stop
being preferred for the per-residue pLDDT profile. I went looking for the
missing test and found there is nothing to test.

AlphaFold writes one per-residue confidence into every atom's B-factor.
Across 200 cached models and 106,983 residues: no residue has atoms that
disagree about `b_iso`, every residue has a CA, and not one has the CA first.
So `[atom for atom in residue if atom.name == "CA"] or list(residue)` and
`list(residue)` select different atoms and the same number, the fallback
never fires, and removing the preference has no observable effect. The sweep
was right and the entry was a false positive.

The preference stays. It states which atom the number is meant to come from,
and a model storing genuine per-atom confidence would make the difference
real. What changed is that it is no longer claimed as load-bearing, and the
invariant it rests on is a test: if AFDB ever ships per-atom values, that
test fails, which is the moment the preference starts deciding the profile.

The entry is replaced rather than left in. A mutation with no observable
effect is a false positive, and keeping one trains the reader to shrug at a
miss, which is the opposite of what a sweep is for.

In its place, the thing the same function's docstring is actually about: the
explicit `CoorFormat.Mmcif`. BINMAN's fetcher stores every cached body under
a `.bin` suffix, gemmi infers format from the extension, and without the
argument it raises "Unknown format" on a perfectly good mmCIF. That was
caught silently once and turned 20,279 usable models into a uniform "no
model" answer.

That one was not caught either, which is the part worth recording. The
invariant test I had just written reads models with gemmi directly and
passes the format itself, so it cannot see the bug: a test can sit next to a
defect, exercise the same data, and be blind to it because it takes a
different route in. The new test goes through `plddt_profile`, and through
`summary()`, which swallows the exception into the status that was reported
20,279 times. Both mutations are now accounted for: one removed as
unobservable, one caught.

## F156. The constraints the project answers to outside itself

F153 widened `mutate.py`'s default list from five mutations to thirteen and
F155 corrected one of them. What all nineteen now cover is a decision the
code makes. What none of them covered is a promise the project has made to
somebody else.

Six added for those, and they are the ones whose failure would not be a wrong
number but a broken undertaking:

- **PROTAC-DB chemistry stops being withheld from the published bundle.**
  Spec 2.1 is unconditional: PROTAC-DB stays internal-use-only and is never
  redistributed. Publishing to a public site is redistribution, so the
  redaction is the whole of how that promise is kept.
- **A finished job stops counting as finished.** The resume guarantee:
  `TERMINAL_STATUSES` is what makes a restart skip work already done, and
  emptying it turns a kill into a repeat of up to 2,360 jobs.
- **The YAML and the queue row stop being compared.** F47's refusal, which is
  what stops a result computed on an input the current code would not emit
  from reaching the published atlas.
- **Tier-2 records can reach a tier-1 number.** D-NOB-032: a minimum over 25
  diffusion samples pooled with one over 1 biases Delta-ipTM downwards for
  exactly the pairs that were refined.
- **The pose viewer asserts a pair exists when the campaign has no record of
  it.** F122: a pair whose jobs all failed and a pair that does not exist are
  different states, and 200 for both says they are the same.
- **Head C stops naming the filter the campaign cannot satisfy.** Spec 5
  requires the abstention to state what is missing, which F141 had to fix
  once already.

All six caught. Nineteen of nineteen now, after F155's correction, and the
part worth recording is not the score. It is that the list had grown to cover
what the code decides and still said nothing about what the code promises,
and those are different questions. A sweep that only tests decisions will
pass on the day a licensing constraint is deleted.

## F157. The README called a finished result provisional

The README's early results ended: "These are interim, triage-tier numbers, and
the corrected-construct comparison is provisional while CDK12 is still
running."

CDK12 finished. `comparison.json` records `pairs_compared: 7`,
`pairs_incomplete: 0` and `provisional: false`, and
`tools/check_prediction.py` has been scoring CDK12 as a supported prediction
for some time, with its numbers: 44.92 A to 5.28 A, 0 of 10 seeds bridging to
6 of 10.

Two things made it invisible. A caveat that understates a result is the kind
of staleness nobody chases, because the direction feels safe. And the
assertion that would have caught it was in the seven that F152's sweep found
never executing: `test_gates.py` checks for "Provisional" in the conclusion
when pairs are incomplete and for its absence when they are not, and only one
branch can run. That test is correct and it is about the pipeline's own
conclusion string, not about the README.

Corrected to what the data says, in digits so it can be tied to the file: 7
pairs compared, none incomplete, 6 improved by more than 2 A, the control
held, none worse, 4 bridging in more seeds and none in fewer. The prediction
sentence now states both outcomes, one supported and one wrong, rather than
only the wrong one.

Pinned in the direction that actually drifts. The new test compares the
README against `comparison.json` and fails either way: a provisional
comparison described as complete, or a complete one still carrying the
caveat. The second is what happened, and the first is what would happen if
someone fixed this by deleting the sentence.

The suite then caught me editing one copy of two.
`test_the_polished_readme_is_in_step_with_the_readme` compares
`README.polished.md` against what `tools/readme_forge.py` would produce from
`README.md`, and the polished file is what the marcdeller.com house header
and palette are applied to. So a correction to the README that stops at the
README leaves the published version saying the old thing. Regenerated, and
worth noting as the shape rather than the slip: a document with two
representations has the same problem as a value with two spellings, and this
project's answer in both cases is to derive one from the other and check it.

## F158. The progress report answered its own question two ways

PROGRESS.md is the document that says whether the build needs a decision.
F134 opened Gate G1 on Tier B and recorded it in a section of its own, under
a heading saying so. The "Gates open" section, further down, still read "No
gate is currently open. All six are closed."

Both sentences were written deliberately, neither was wrong when written, and
nothing compared them. So the file answered the one question it exists to
answer in two different ways, and which answer a reader got depended on where
they stopped reading. The one that says no decision is needed is the one a
reader is hoping for, which is the wrong half to leave standing.

The handover was stale in a second way, and this one would have cost the
user work. "Next action, once the chain exits" credits
`tools/rerun_pair.py` as "tested for the first time", which was true of its
atomic write and not of its correction: F145 found that the correction
returned nothing on every invocation the chain has ever made, and F146 that
it cleared the state rows regardless, so the fifteen jobs would have re-run
on the same hydroxyproline YAML and the atlas would have gone on refusing.
Someone following those instructions would have rerun the chain, watched the
correction report fifteen jobs "left alone", and had no reason to think the
publish was still blocked for the same reason as before.

Both corrected, and the list now carries what the rerun actually gains from
this session: a correction that corrects, tier 2 priced against the gate
before it runs, refined poses that are readable, a design profile attached to
the parent that was scanned, and a deploy that refuses a droplet serving
something other than what was shipped.

The consistency check is a test, because the next gate to open will be
recorded the same way: in a new section, by someone who does not scroll. It
blanks quoted spans first, since the cell that used to carry the wrong
sentence now records that it did, and the first version of the test fired on
that record. That is the third time in this session a check has forbidden its
own explanation, after F150's docstring and F152's conftest comment, so it is
the rule and not the exception.

Verified by restoring the contradiction and watching the test fail, then
restoring the file and checking it byte for byte.

## F159. Browser QC had never seen a computed ROC

Every QC run in this build has been against the benchmark campaign, where
the matched-control ROC is `not_computed` and the Delta tab shows an empty
state. So the page that carries the project's headline result had never been
rendered with that result present. Fixed by building a campaign whose ROC
computes, from the benchmark campaign plus a synthesised Sievers arm of 24
degraded and 96 matched negatives, and pointing QC at it.

Four things fell out, and the first was mine from F138.

**An unreachable server was reported as a stale build.** The fingerprint
guard fetched `/healthz` once and treated a failed fetch the same as a
missing field, so it said "does not report a source fingerprint" about a
server that was still binding its port. It now retries three times over two
seconds and distinguishes the two, because one is an operator's timing and
the other is a stale build, and blaming the build sends someone to restart a
server that is running.

**Then it reported a healthy server as unreachable, and was right.** Node
and Chromium refuse a list of unsafe ports, 5060 and 5061 among them as SIP,
and the failure is `bad port`: curl reaches the server, `fetch` cannot. Told
only that nothing answered, an operator restarts a server that was never
down. The message names that case now. The port PROGRESS.md documents, 5055,
is not on the list, so this only bites someone who picked one.

**The copy budget held only while the headline panel was empty.** With the
ROC computed, `/delta`'s chart panel read 71 words against a budget of 40.
The excess was a caption the chart writes from the data, "Showing the 12
pairs whose difference of minima is furthest from their difference of
medians, 115 further pair(s) agree more closely and are not plotted", plus
eighteen words explaining why only some are plotted. The counts are
pipeline-generated status text, which the budget excludes; the explanation is
reasoning about a presentation choice, which the budget sends to
DECISIONS.md. The caption is marked and the explanation is a comment, and the
panel reads 24.

The marking exposed something worse in my own F139 filter: it excluded
`chart__caption`, and no template carried that class. A filter entry naming
nothing is a filter entry that looks like coverage, and the caption it was
meant to exclude was marked `panel__hint` and counted as prose the whole
time. Both ends now meet, and a test fails if either moves.

**And the verdict was not beside its curve.** The Delta tab computes an AUC
in JavaScript for the chart title. The bootstrap interval and the
interpretation are computed in Python, land in `validation.json`, and were
rendered on the About tab. A reader looking at the curve saw one number and
had to infer what it meant.

That matters most in the case spec 4.3 asks to be reported rather than
hidden: an interval entirely below 0.5, where the statistic separates the two
classes in the opposite direction to the prediction. F120 wrote that sentence
specifically so an inverted result would say so, and nothing put it next to
the figure. It is there now, as `AUC, 95 per cent CI, interpretation`, absent
rather than empty when the ROC has not computed, and marked as the machine
output it is.

## F160. The design tab named one peptide and plotted another

The remaining state the UI had never been rendered in: a design tab with a
scan profile. The design campaign has never run, so every QC pass has seen an
empty panel. Rendered with a scored scan, two things were wrong and both were
mine from earlier today.

**The copy budget again held only while the panel was empty.** With a profile
present `/design` read 44 words against a budget of 40, from two sentences
the scan generates: the positions where the bridge weakened and the position
where it was lost, each a hand-written frame around a
`<span class="mono">` of substitutions computed from the data.

That is a third shape the budget tool had not handled. F139 excluded a
paragraph whose own class marks it as machine output; this is a paragraph
whose class is prose and part of whose text is not. The rule excludes
pipeline-generated status text, and the markup already distinguishes it at
span level, so the measurement now counts a paragraph's own words and
subtracts its `mono` descendants. The panel reads 36, and both sentences
stay: each is the one-sentence disclaimer the budget explicitly permits,
because a positive lift at a position whose bridge weakened is exactly a
figure that would be read the wrong way without it.

**And the page named the wrong peptide.** F147 attached the profile to the
parent the campaign scanned rather than the one the report ranks first, and
computed a note for when those differ. Nothing rendered the note, and the
panel above the chart still names the ranked parent. So the page showed
"Parent GSPT1" above the per-position profile of a different peptide, with
every substitution label belonging to the second and the heading to the
first.

That is worse than what F147 replaced. Before it, the profile did not appear
at all: unhelpful, and not misleading. Half a fix moved the failure from
silence to a confident mislabel, which is the direction that costs a reader
something. The two campaigns are already apart on this checkout, so the
mislabel is what the design tab would have shown the first time the scan
landed.

The scan panel now states which peptide the profile is of and which campaign
it came from, and shows the mismatch note when the ranking disagrees, both
marked as the pipeline output they are. Pinned, including that the note
element is absent rather than empty when the two agree.

## F161. The gate I added priced an unmeasured campaign at zero

A review pass over this session's own code, prompted by its own record:
F142's fix needed F154, F138's needed F159, F147's needed F160, and F139's
needed both. Fixes written quickly have a defect rate, and the honest
response is to read them again rather than look for new ground.

`budget.tier2_projection`, which decides Gate G1 for refinement, charges an
unpriced job the mean of the priced ones, because a projection that gets
cheaper the less of the campaign has run would pass the gate at the start of
every campaign. That is the right rule and it has a hole: with *no* completed
ternary job there is nothing to take a mean of, the guard does not fire, the
sum is zero, and the projection came back 0.0 hours with `fits: True`.

`test_an_unpriced_job_is_not_a_free_job` exists for exactly this and
exercised only the partial case, three of four unpriced. It passed while the
all-unpriced case charged nothing, which is F152's lesson arriving from the
other direction: that sweep finds assertions that never run, and this is an
assertion that runs and does not reach the case it names.

Reachable, and not only in theory. `status.sh` prices whatever campaign is
newest, including one that started a minute ago, and the line read "G1
refine closed, 0.0 h" which is the most reassuring thing a status page could
say about a cost nobody knows.

Nothing priced is not nothing to pay, and it is not a gate either. A gate is
a cost that exceeds the budget; this is a cost nobody knows. So the
projection carries `priceable`, `gate_g1` returns `fits: False` with
`judged_on: "nothing measured"` and a verdict that calls itself a refusal to
guess, `tier2.run` refuses with its own status rather than declaring G1, and
the status page reads "not priced" rather than "closed".

Keeping those apart matters because of what G1 does. In unattended mode an
open gate stops the build and asks for a decision, and the first version of
this fix did open G1 on a campaign that had simply not finished a job: a
decision nobody could make from the evidence, about a number that did not
exist yet.

Two more mistakes inside the fix, both found by running it rather than
reading it. `affordable_pairs` took `priceable` from the last affordable
prefix, and the first of those is the empty prefix, which has no jobs and so
is trivially priceable: the flag came back False for a campaign that cannot
be priced at all. It asks the requested set now. And the test above is split
in two, so the refusal cannot quietly become permanent: one case asserts
that nothing measured refuses, the other that a single measurement is enough
to price the rest.

## F162. The deploy's own check could fail with a traceback instead of a verdict

Continuing the review of this session's code after F161. `app/fingerprint.py`
gates two things: browser QC refuses a server whose digest is not the working
tree, and `deploy.sh` refuses a droplet that is not serving what was shipped.

The property both rest on had never been tested: that the digest is a
function of relative paths and content and nothing else. If it were not, the
droplet could never agree with this machine and every deploy would refuse,
blaming the droplet. Verified against a real rsync into a temporary root
using the deploy's own exclude list, which produced the same digest,
`9364eabf5091a859` on both sides. Pinned as the cheap version of that, which
copies only the twenty-one hashed files to a different root.

The defect is smaller and real. `files()` globs and `detail()` then reads, so
the set can go stale between the two: an editor, or a mutation sweep
restoring a file, is enough. A file listed and then gone raised
`FileNotFoundError`. `deploy.sh` captures the digest with
`SHIPPING=$(... app_fingerprint.py)` under `set -e`, so a deploy would abort
on a Python traceback rather than on a verdict, which is the least useful way
to stop one. QC would report that it could not compute the expected
fingerprint and refuse for a reason that sounds like a configuration problem.

A missing file is now recorded as `<missing>` rather than raised. Recorded
rather than skipped, deliberately: a tree with a file missing *is* a
different tree and should produce a different digest, where skipping would
make it produce the same digest as a tree that never had the file, and
`--detail` would not say which one went.

Worth noting what this review has and has not found. Two passes over this
session's own code have turned up one defect that mattered, F161's gate
pricing an unmeasured campaign at zero, and one that would have wasted an
afternoon, this one. Neither was in the logic the findings were about; both
were in what happens when the inputs are not there yet.

## F163. Tier B is not blocked on compute, it is blocked on fifteen constructs

F134 recorded Gate G1 open on Tier B and measured the cost: 16.5 hours after
automatic scope reduction, against a budget with no room. That framed the
decision as a budget decision, and it is not only one. I went looking for
what it would take to assemble a Tier B campaign, because with the decision
pending the useful thing is to have the work ready either way.

It cannot be assembled. Spec 1.1 defines six receptor constructs, all for
named Tier A ligases, and none of the fifteen Tier B genes has one. So every
Tier B pair needs a receptor construct that does not exist, and the two
mechanical ways to produce one are both ruled out by decisions this project
has already taken:

- Take the longest annotated domain. `interpro.domain_by_accession`'s own
  docstring rejects this: "Named entries rather than the longest domain
  because which domain binds the substrate is science knowledge, and only
  the lookup belongs in the code." That is F41.
- Take the frozen selection's `best_window`. That is the highest-mean-pLDDT
  200-residue window from the pLDDT scan, which is a statement about which
  part of the model is confident, not about which part binds substrate.

What the decision involves, quantified rather than asserted. Across the
fifteen accessions InterPro annotates 220 domains of 60 residues or more,
from 5 for ASB8 and RNF175 to 28 for FBXO11. The top-ranked one by
N-terminal position is this:

| gene | candidates | top-ranked domain |
|---|---|---|
| DCAF8L1 | 6 | DDB1- and CUL4-associated factor, 154-587 |
| CCNF | 22 | F-box-like domain superfamily, 32-114 |
| ASB8 | 5 | Ankyrin repeat and SOCS box, 1-272 |
| KCNC1 | 16 | Potassium Channel Kv1.1, 5-122 |
| NEURL2 | 10 | Neuralized, 20-243 |
| TRIM55 | 8 | Zinc/RING finger, C3HC4, 4-119 |
| KCND2 | 17 | Potassium Channel Kv1.1, 1-144 |
| KCTD4 | 11 | Potassium Channel Kv1.1, 27-135 |
| FBXO11 | 28 | unnamed, 143-244 |
| FBXW4 | 8 | SCF Complex F-box/WD repeat, 11-411 |
| TRIP12 | 24 | E3 ubiquitin-protein ligase HECT, 285-2067 |
| SMURF2 | 22 | C2 domain, 1-119 |
| RNF175 | 5 | RING finger protein RNF121/RNF175, 15-328 |
| TRIM17 | 19 | Zinc/RING finger, C3HC4, 1-83 |
| RAG1 | 19 | V(D)J recombination-activating, 1-1043 |

Two things in that table are worth a reader's attention, and I am stating
what the annotations say rather than what the biology is, because which
domain binds substrate is the science knowledge this project keeps out of
the code.

The top-ranked domain is frequently not a substrate-binding one. An F-box
binds SKP1 and a RING binds E2; for CCNF, TRIM55, TRIM17 and FBXO11 the
first-listed domain is part of the ligase machinery rather than the
substrate interface. A C2 domain is a membrane-targeting module, which is
SMURF2's. So "take the first" would submit the wrong half of several
proteins.

And four of the fifteen have a top-ranked domain that already exceeds the
tier-1 token cap of 400 before a peptide or a glue is added: DCAF8L1 at 434
residues, FBXW4 at 401, RAG1 at 1,043 and TRIP12 at 1,783. Those need either
a sub-domain choice or a declared exception, which spec 1.1 provides for and
which is again a per-protein decision.

Spec 3.3's selection function asks for pocket druggability, structural
coverage, tumour enrichment and the triage composite. It does not ask which
domain binds substrate, and nothing downstream supplies it. That is the
actual distance between "Tier B is selected, frozen and gate-passed" and
"Tier B can run", and it is fifteen decisions rather than a day's coding.

So the G1 note is corrected. F134 offered three ways out: a separate
campaign, a larger budget, or a GPU. Any of those still leaves Tier B
unrunnable until someone names a substrate-binding domain for fifteen
proteins. Recorded here with the candidate counts and the token overruns so
that naming them is a sitting down with a table, not a research project.

The mechanism for closing F163 is D-NOB-068: `config/tier_b_constructs.toml`
ships empty with the candidates listed, and
`nobble/curate/tier_b_constructs.py` loads and validates what is filled in.
Deliberately the mechanism and not the judgement, and tested against a
*filled* table synthesised in the tests, because a module that only ever runs
against an empty form is the shape this project keeps finding defects in:
F134, F137, F141, F145 and F147 were all paths nothing had executed.

One defect in my own loader, found by that filled-table test rather than by
reading it: `report()` built its `form` field with `relative_to(ROOT)`, which
raises for a form outside the project root. A report that raises while
describing a blocked state is worse than the blocked state.

Two more things worth recording about how that went in.

The cutoff sweep caught the module on its next run. I had written
`PEPTIDE_RESIDUES = 15` and `GLUE_HEAVY_ATOMS = 59` as module constants, and
both decide whether a filled-in construct is accepted, which makes them
thresholds and puts them in `config/thresholds.toml` by CLAUDE.md's rule.
The sweep was right and the numbers have moved.

And it caught them after I had already committed, because the command was
`pytest ... | tail -3 && git commit`, and a pipeline's exit status is the
last command's: `tail` succeeded, so the `&&` did not gate anything. I have
been running the suite that way all session and it has only now mattered,
which is the definition of a latent fault in one's own method rather than in
the code.

## F164. Nine findings were superseded and not one said so

FINDINGS.md is the document of record, read from the top by anyone tracing
why something is the way it is. In one session nine findings were revised by
later ones in the same session, and not one pointed forward.

So a reader of F134 concludes Tier B costs 16.5 hours of compute and stops,
where F163 says it cannot be assembled at all because none of the fifteen has
a receptor construct. A reader of F142 concludes the runner's appends are
told apart from a rewrite, where F154 says an identical rewrite was reported
as an append. A reader of F138 concludes the fingerprint guard is sound,
where F159 says it blamed the build for an operator's timing and F162 that a
vanished file aborted it with a traceback.

This is F158's defect moved from one document to another: statements written
deliberately, each true when written, nothing comparing them, and the one a
reader reaches first being the stale one. It is also a measurement of this
session rather than a complaint about it. Seven of the nine revisions are of
my own work from the same day, which is the honest rate for fixes written
quickly: F135 needed F161, F138 needed F159 and F162, F139 needed F159 and
F160, F142 needed F154, F147 needed F160, F153 needed F155.

The convention is a `**Revised by FNNN:**` line at the end of the earlier
finding, saying in one clause what changed. At the end rather than the top,
because a reader who has read the finding is at the bottom of it, and the
point is to catch them before they act on it.

The relation is maintained in the test rather than inferred from the prose.
"This finding revises that one" is a judgement, and a regex guessing at it
would either miss revisions or invent them; what the test guarantees is that
a recorded relation stays symmetric, points at findings that exist, and
never points backwards.

## F165. The gates section contradicted itself again, past my own check

F158 found PROGRESS.md saying "No gate is currently open. All six are
closed" while a section above recorded Gate G1 open on Tier B, and added a
test. The section still contradicted itself, four bullets lower down, and the
test did not notice.

Two bullets, both headed G1. The first, written for F134, says it is open on
Tier B. The second, written much earlier for F45, says "G1 compute: closed,
and was briefly reported open in error" and describes a false open that was
corrected the same day. That second one is worth keeping: a Gate reported
open stops an unattended build, so a false one is as costly as a missed one
and the record matters. What it is not is a statement about now, and it sat
in the same list in the same form as the bullets that are.

F158's test compared a blanket claim against gates named as open. It never
compared two bullets about one gate, so the narrower contradiction passed
straight through a check written for exactly this defect. A check narrower
than the thing it is named for is the shape this project keeps turning up,
and finding one in my own fix from two hours earlier is the clearest
instance of it yet.

The historical bullet now says so in its heading, and the check counts
present-tense claims per gate and requires at most one, treating a bullet
headed "history", "formerly", "was briefly" or "used to" as a record rather
than a claim. Verified by restoring the contradiction, watching it fail, and
restoring the file byte for byte.

Writing that test turned up a second, smaller thing: my first version
captured only each bullet's bold heading, and G3 and G5 put their state
after the closing asterisks, so it reported them as stating nothing at all.
It captures the whole first line now.

The current bullet also points at what would close the gate, which it did not
before: `config/tier_b_constructs.toml` and D-NOB-068, so a reader learns
that G1 closes on fifteen lines of config rather than on code.

## F166. The sweep for unreached assertions could not see 33 of them

F165's lesson, applied to the tool F152 built: a check narrower than the
thing it is named for. `tools/vacuous_tests.py` reports "the assertions no
run reached", and it walked only functions called `test_*`.

Thirty-three assertions live elsewhere in `tests/`: in module-level helpers
like `_published_names`, `_run_panel`, `_page` and `check`. Those are often
where a test's real check sits, which is the point of a helper, and a helper
that is never called because every caller skips has assertions that never
run. That is precisely what the sweep exists to find, and it could not see
them.

So F152's figure was wrong in the reassuring direction. It reported 2,063
assertions with 14 unreached; the count was never the whole set, and the
unreached ones among those 33 were invisible rather than absent. The sweep
now attributes every assertion to its enclosing function whatever that
function is called, and anything outside a function to the module, since an
assertion at import time runs or the file does not load.

Worth being plain about the pattern rather than only the fix. Four of this
session's tools and checks have turned out narrower than their names: F139's
copy budget missed a class its own filter named, F158's consistency check
compared a blanket claim and not two bullets, F161's unpriced-job test
covered the partial case and not the empty one, and now this. In each case
the check passed, which is what made the narrowness invisible, and in each
case the thing that found it was running the check against a state nobody
had put it in before.

**What the widened sweep then found: nothing.** 2,183 assertions, 2,170
executed, 13 unreached, and not one of the 33 helper assertions among them.
They all run. The 13 are the same honest set as before, skips for state this
checkout lacks and untaken branches of conditionals whose other branch
asserts, plus two from a test added since.

So the fix changed no verdict, and that is worth recording rather than
quietly dropping. The tool was blind to 33 assertions and all 33 were fine;
had I stopped at the first result I would have been right by luck, and I
would not have known it.

## F167. The handover's figures were typed, so they were already wrong

PROGRESS.md's "Waiting on Marc" table said "G4 Publish: 160 commits
unpushed". It is 202. The number was right when written and this session
commits often, so it was stale within the hour and will be stale again by
the time anyone reads it.

The same row says `origin/main` still carries 100 of the absolute project
paths F128 removed, which is the reason a push does not fix that on its own.
That one is 107.

Neither figure is worth a reader's trust unless something checks it, and
both are one git command away: `rev-list --count origin/main..HEAD` and
`git grep -c` against the published atlas on the branch. Both are measured
now and compared against what the table says, so the table is either right
or the suite fails.

This is the same defect as F136, where the progress report quoted a library
reduction from an earlier build, and F157, where the README called a
finished comparison provisional. Three instances is enough to state the
rule: a number in a document that is also available from a command should be
checked against the command, and the ones that are not will be wrong in
whichever direction flatters the state of the work.

The third row, `bash deploy/enable_gzip.sh`, carries no figure and is
unchanged. The script still passes a syntax check and references nothing
altered since it was written, which I checked rather than assumed, because
twenty-odd findings have landed between writing it and now.

## F168. The figures I pinned were figures nobody can state

F167 found two stale numbers in the handover, replaced them with measured
ones, and pinned them with a test. The commit that did it incremented the
unpushed commit count, so the test failed on its own commit: 202 written,
203 by the time anything could read it.

I then replaced the stale suite size the same way, tying "1,048 passing, 4
skipped" to the 1,052 tests pytest collects. Adding that one test moved the
collected count to 1,053. Twice in two attempts, the fix broke its own
check, for the same reason each time.

The distinction that settles it, and which F167 missed:

A figure that is a property of the **data** can be written down and checked.
It changes only when the data does, and a reader wants the number itself:
25,519 library candidates, 2,360 jobs, 285,996 bridges, 7 pairs compared.
Those are pinned and should stay pinned.

A figure that is a property of the **work** changes as a consequence of doing
the work. Writing one down is a race against oneself, and pinning it with a
test makes the race a failure rather than a staleness. Commits, tests and
findings are all of that kind. The handover gives the command now:
`git rev-list --count origin/main..HEAD`, `git grep -c /Users/dellboy
origin/main -- deploy/atlas`, `pytest tests/ -q --collect-only | tail -1`.

F167 stated the rule as "a number also available from a command should be
checked against the command". That is half right and the half it misses is
the expensive half: some numbers should not be in the document at all, and
the test's job is to check that the command is there instead.

A third thing in the same test, smaller: the collect-only subprocess ran
`"python"` with a PATH of `/usr/bin:/bin`, and the interpreter this project
uses is in neither, so it failed with `FileNotFoundError` rather than a
verdict. `sys.executable` now. That is the second time today I have had a
check fail with an exception instead of an answer, after F162.

**And then a third instance, inside the commit that named the pattern.**
PROGRESS.md also said "This session, F132 to F167. Thirty-six findings".
Writing this finding made both wrong, and the test pinning them failed on
that commit. I had applied the rule to the commit count and the suite size
and not to the finding range, in the same sitting, which says something about
how partial a fix can be while feeling complete. The start of the range is a
fact about when the session began and stays put; the end is a command.

Worth recording plainly: I committed that on a failing test. The command was
`pytest ... > /dev/null; echo exit=$?; git add -A && git commit`, and the
`&&` binds to the `echo`, which always succeeds. This is the second time
today the same shell habit has let a commit through on red, after the
cutoffs in D-NOB-068, and on both occasions I had just written down that the
habit was the problem. Noting it again is not the fix; the fix is to run the
suite and read its status before the commit, as a separate step.

## F169. The correction's precondition, checked on the real layout

F145 restored `_known_good`'s rule that a reference counts only when exactly
one other campaign holds the same job's YAML, and F146 made a missing
reference a refusal rather than a silent no-op. Neither checked whether the
rule is satisfiable on the layout the chain will actually meet, which is the
question that decides whether the F47 correction works when it runs.

It is. For all fifteen of `bench02_BRD4_VHL`'s YAMLs exactly one other
campaign holds the name, and the reason is worth writing down because it is
not obvious: the corrected campaign has 100 YAML files for the same seven
pairs and none of them collide, because it prefixes its jobs `corr01_`
rather than `bench01_`. Across all four campaigns with a `yaml/` directory,
2,700 distinct names and not one held by more than two campaigns. The two
scratch directories, `smoke_sievers` and `zinc_probe`, hold no `yaml/` at
all.

So the rule holds for a reason that could change. A future campaign reusing
the `bench` prefix, a second benchmark run for instance, would give three
copies of every name and the correction would find no reference for any of
them. That is now a hard refusal with a message naming the holders, so the
failure is visible rather than a quiet fifteen jobs re-run on the same input,
and this test says so before the chain gets there.

## F170. An opt-out that protected the atlas and not the measurement

`tools/refresh.sh` scores a campaign, validates it, measures throughput and
publishes the atlas. It takes `--no-publish`, and the comment explaining why
is specific: "Publishing is opt-out, because scoring a secondary campaign to
look at it should not change what the public site serves. Running
`refresh.sh campaigns/corrected_...` to inspect a half-finished run
republished the atlas from it, which is a side effect nobody asks for when
they say score this."

The flag gated the atlas build. It did not gate the throughput step, and
`write_throughput` writes `data/throughput.json` unconditionally.

That file is shared state with four readers. `app/data.py` serves it,
`curate.diversity.projected_hours` sizes a campaign from it and decides Gate
G1 on the result, `tools/wait_for_gpu.sh` consults it, and `mutate.py` lists
it as protected precisely because a test must not change it. So
`refresh.sh campaigns/benchmark_... --no-publish`, which reads as "score this
and change nothing shared", replaced the running campaign's measurement with
the benchmark's.

This is F131's incident arriving through a tool rather than a test. There, a
test of mine wrote the live throughput and put the benchmark's measurement
where the running campaign's belonged; the protected-file list caught it. The
same write through `refresh.sh` is nobody's mistake and nothing catches it,
because the tool is entitled to write the file when it is doing the thing the
file is for.

The opt-out is decided once now and gates both, with the skip saying what it
is protecting. Verified by running `refresh.sh` against the benchmark
campaign with the flag and confirming `data/throughput.json` came out
byte-identical, still describing the running campaign's 317 timed jobs.

The shape is one this project keeps producing: a boundary drawn one notch too
narrow. F128's walk of one directory in four, F144's argument that scoped a
read and not the writes, F139's filter naming a class nothing carried, and
now a flag that covers one of two side effects. In each case the narrower
thing was the one someone had in mind at the time, and the wider one was
equally obvious afterwards.

## F171. The drift check compared stale against stale

`tools/atlas_drift.py` is what stops a deploy publishing an atlas that is not
what the current code builds. F96 is the finding it exists for: a caveat was
written, tested and committed and was not on the page, because
`comparison.json` is built by the atlas and the atlas had not been rebuilt.
`deploy.sh` refuses while it reports drift.

It reported "in step" while the published atlas was missing four fields the
code had been producing for some time: `non_finite_dropped` from F74,
`secondary_graded_test` from F52, `seed_balance` and `seed_counts`, and
`peptide_identity`, `peptide_predicted_sequence` and
`peptide_deposited_sequence` on all 65 pose-recovery rows from F103.

The mechanism. `build_atlas.py` **copies** `validation.json` from the
campaign rather than recomputing it, which is reasonable: the atlas
publishes what the pipeline produced. The drift check rebuilds the atlas
from that same campaign and compares. So a rebuild that copies a stale file
produces a stale file, which matches the stale published one, and the check
passes. It cannot see staleness shared by the published atlas and the
campaign artefact it was copied from, and that is the only kind of staleness
that arises here, because both come from the same place.

How it surfaced is worth recording, because I was not looking for it. F170
needed proof that `refresh.sh --no-publish` leaves shared state alone, so I
ran it against the benchmark campaign. `--no-publish` did protect the atlas
file and `data/throughput.json`, and the run also rescored the campaign,
which is what scoring a campaign means. That rewrote the campaign's
`validation.json` with the current code's output, and the next suite run went
red on two atlas-drift tests. My verification did not create the drift; it
removed the thing that was hiding it.

Two changes. The check now recomputes the documents the atlas copies before
rebuilding, so it answers the question it is named for rather than comparing
two copies of one stale file. And the atlas is rebuilt, so the published
bundle carries those fields: the ROC summary goes from 5 keys to 9 and all 65
recovery rows gain the identity fields F103 added.

The deploy was blocked while this stood, which is the check working. What was
not working is that it had been passing for as long as the staleness was
symmetric, and a check that cannot fail while both sides are wrong together
is the most expensive kind to trust.

## F172. My fix for F171 was narrower than the thing it named

F171 found the drift check comparing a stale published atlas against a
rebuild that copied the same stale file, and fixed it by recomputing
`validation.json` before the comparison. `build_atlas.py` copies three flat
documents, not one.

The evidence was in F171's own output. Beside
`ATLAS.json.files.validation.json: 29099 -> 39654` sat
`ATLAS.json.files.weights.json: 475 -> 893`. The weights document was
equally stale, equally copied, and visible in the same four lines I read to
write the finding. It is also free to recompute: the fit reads
`scores.jsonl` and returns in milliseconds.

So the check now recomputes both, and the two copied documents it does not
recompute are named in the source with the reason. `scores.jsonl` would take
minutes, because scoring runs PLIP and the geometry filter over every
structure, and a check the deploy waits on cannot afford that; what keeps it
current is `refresh.sh`, which scores before it publishes. `campaign.json`
records what an assembler built and there is nothing to recompute it from.
The test requires every copied document to be either recomputed or mentioned
as a deliberate exclusion, so the next one added has to be one or the other.

This is the fifth time today a check has turned out narrower than its name,
after F139, F158, F161 and F166, and the first where the wider case was
sitting in the output of the finding I was writing. The pattern is not that
these are hard to see. It is that having found one instance, I stopped
looking, and the remedy is mechanical: when a fix names a category, make the
test enumerate the category rather than assert the instance.

## F173. My own `git add -A` published a file nothing references

The full suite went red on F148's check that every published structure has a
row naming it: 101 structures on disk, 100 named. The orphan was
`bench01_GSPT1_CRBN__binary__unconstrained__seed5 2.cif`, byte-identical to
the real `seed5.cif`, mode `-rw-------` against the real file's `-rw-r--r--`,
and timestamped 12:57 where the rebuild wrote at 18:14.

That is an iCloud sync-conflict copy, not something the build produced. The
project root is iCloud-backed. `build_atlas.py` clears `deploy/atlas` before
it writes, so the builder cannot leave a stale structure behind; iCloud can,
by restoring a copy of the file the rebuild replaced, with its own earlier
timestamp and its own permissions. It then sat in the bundle until `git add
-A` in F171's commit tracked it, which is what published it.

Two things worked. F148 caught it, and it caught it as the thing it is: a
file on the droplet that no row names, which is exactly the failure that
check exists for. And the owner-only mode would have been the next problem,
because `deploy.sh` rsyncs modes verbatim and the service user cannot read a
`-rw-------` file, so a requested structure would have come back 500. Nothing
requests this one, so it would have sat there unread.

The file is removed. The new check names the class rather than the instance:
no tracked file and no file under `deploy/atlas` may carry a sync-conflict
name, so the next one is read off a test name instead of diagnosed from a
byte compare and a `git log` walk. Its third test pins the pattern against
six names the project actually uses, because " 2.cif" is a suffix an
ordinary name could plausibly carry and a check that fires on `_v2.html` or
`icon_300.png` would be worse than none.

What I will not do is stop using `git add -A`, which is the thing that
actually went wrong. The build commits whole phases and an explicit file list
would miss new outputs, which is a worse failure than publishing a duplicate
that a test catches within one suite run. The lesson is narrower than my
instinct: a sync-backed working tree puts files in the build's output
directory, and the defence belongs in the checks rather than in the commit.

## F174. The landing page grew with the campaign, and 99 per cent of it was unread

The app has only ever served a 100-job atlas. The running campaign is 2,360
jobs over 158 pairs, so I built an atlas of that shape and served it.

The landing page was 3,289 KB of HTML. So was Delta. Both embed every scored
pair with `{{ pairs | tojson }}`, which is the right shape for a read-only
atlas, with nothing to fetch and no spinner, but it means the document grows
with the campaign.

Of those bytes, 99 per cent sat in keys neither page accesses. Measured by
intersecting the keys a score row carries against every property access in
each page's own template, the base it extends and the scripts it loads:
`seed_records` is 56 per cent of a row, `plip` 20, `contact_map` 10 and
`convergence` 5. They are per-seed and per-contact detail that the pose and
interactions pages read from `/api/pair/<pair_id>`, which still serves the
whole row, and that `/api/pairs` still publishes in full. The client never
calls `/api/pairs`, so nothing lost a source.

Leaving the four out took the page from 3,289 KB to 514 KB, and gzipped from
427 KB to 18 KB. Render time went from 34 ms to 6 ms. Resident memory is
unchanged at 84 MB for the whole atlas, which is what it should be: the rows
are still loaded, they are just not all serialised into the document.

Verified rather than assumed. Every scalar the pages sort and render on is
identical before and after, pair by pair, and in a real browser the campaign
table renders 7 rows across 12 columns with no empty cell and no console
error, with Delta, pose, interactions, benchmark, design and about all
drawing their marks.

A deny-list, not a list of keys to keep, and that is the deliberate part.
Keeping is the safe-looking choice and the more dangerous one: a scalar left
out of an allow-list renders as a blank cell on a page nobody is watching,
while a heavy key left in a deny-list only costs bytes. Two tests hold the
list to what the pages access, in both directions.

Neither of those would have caught how this happened. The page did not grow
because someone added a key to a list; it grew because fields were added to
a score row and nobody asked whether the page reads them, and no list of
names covers a field nobody has thought about. So there is also a budget, in
`config/thresholds.toml` because it decides an acceptance: bytes of payload
per pair, 3,125 measured against 6,000 allowed. Its reach is measured and
stated rather than implied, because this is the sixth time today a check has
been narrower than its name: `seed_records` returning adds 11,069 bytes per
pair and `plip` 3,869, both of which breach it, while `contact_map` adds
2,048 and `convergence` 917, neither of which does alone. The budget is the
half of the problem a list of names cannot reach, not a replacement for it.

One consequence for the pending work. `deploy/enable_gzip.sh` has been
waiting on a shell on the droplet and reads as a refinement.

That paragraph originally said the landing page is "a 514 KB download rather
than 18 KB" without the script, which is wrong, and the live site disproved
it the moment this build was deployed: nginx compresses `text/html`
whatever `gzip_types` says, so the page has always been served gzipped. This
file's own `enable_gzip.sh` says as much in a comment, and I wrote the claim
anyway from the local measurement, where there is no nginx. The measured
truth is 52,632 bytes plain and 14,064 gzipped, served, today, without the
script having been run (F189).

What the script is actually for is the types nginx does not compress by
default, and the trim in this finding stands on its own: 3.3 MB of HTML
would have been 427 KB gzipped, which is still a bad landing page.

## F175. The deploy never asked whether the bundle would fit

F174 put a number on the published bundle: 265 MB of structures for the
running campaign, against 25 MB for the benchmark atlas every deploy so far
has shipped. That made a gap in `deploy.sh` worth closing. It rsyncs
`deploy/atlas` with `--delete` and has never asked how much room is on the
far side.

The failure is not a refused deploy, which would be fine. It is rsync
running out of space part way through, which leaves a half-written atlas
behind a live site: pages that resolve, structures that 404, and a catalogue
listing poses the viewer cannot open. The site would look healthy to
`/healthz` and to the page-by-page check at the end of the deploy, because
both ask whether the app answers, not whether its data is complete.

So the deploy now reads `df` once over the connection it has already opened,
before it writes anything, and refuses if the bundle would not leave the
configured margin free. Two details are deliberate. It compares the whole
incoming bundle against free space rather than the growth from what is
already there, because `--delete` removes the old copy after the transfer
rather than before, so the peak is both at once. And an unreadable `df`
refuses rather than passing, because an empty answer must not read as plenty
of room, which is the same mistake F161 made when an unmeasured campaign
priced at zero hours and opened a gate.

The margin is 1,024 MB in `config/thresholds.toml`, and it is the room the
droplet needs to keep working rather than slack on the measurement: the same
deploy pip installs into a virtualenv and the service writes logs, and a
deploy should not be the thing that fills the disk.

The honest limit of this: the only real test of the check is a real deploy,
which I cannot run, since ssh to the droplet is not mine to make. So the
arithmetic sits in `tools/space_check.py` where it can be tested directly,
the ten tests cover the boundary, the inclusive case, the difference-not-
total mistake, both exit statuses and the missing-bundle case, and two of
them read the ordering out of `deploy.sh` to confirm the check runs before
the first rsync and after the guard on an empty `df`.

Two of those tests failed first time and both were my fault rather than the
code's. One asserted the configured margin does not appear in the tool's
source, which hit the `/ 1024` byte conversions. The other anchored an
ordering test on the first mention of `tools/space_check.py` in the script,
which is the comment above the call, so it compared the rsync against the
comment rather than against the command. Both now anchor on the invocation.

## F176. The same mistake one layer down: the LM answer shipped the whole row

F174 was a page embedding fields it never reads. Having found it there, the
question is where else the same shape occurs, and `/api/ask` is the answer.

`lm.execute` applies a `select` clause when the model supplies one, and when
it does not it returned the whole score row. The answer panel on the campaign
page renders one field from it, `pair_id`, for at most ten rows. So a default
25-row answer was 514 KB of JSON and a 100-row one, the schema's own maximum,
was 2,056 KB, to print ten strings.

The default is now the published schema rather than everything, which takes
those to 12 KB and 49 KB. The schema is the right default and not just a
convenient one: it is the vocabulary the model is given and the only one a
question can be asked in, so an answer carrying its twenty fields is
complete with respect to anything askable. `seed_records`, `plip`,
`contact_map` and `convergence` are not in it, cannot be queried, and cannot
be displayed, and `/api/pair/<pair_id>` still serves the whole row.

One detail that is not a detail. The projection is intersected with the keys
the row actually carries rather than taken as a fixed list of twenty.
Projecting onto the schema outright invents a null for every field a row does
not have, which reports "not computed" as a measured null, and that
distinction is one this project has already paid for twice: F130, where a NaN
passed a truthiness test, and the abstention path, which exists to say what
is missing rather than to return a zero. A test holds that case with a
two-field row.

Three of the seven tests were checked against the old behaviour rather than
assumed to bite: the schema-only assertion, the heavy-key assertion and the
size bound all fail when the previous `execute` is put back, the last at
2,056 KB against a 200 KB bound.

This is the second instance of one pattern in one session, which is worth
stating plainly: the project's read-only atlas design hands whole records to
consumers that render a few fields, and it was invisible for as long as the
only atlas was 7 pairs.

I first wrote that the two places returning record sets are now both
bounded. That was wrong, and checking it before committing the sentence is
the only reason it is not in the repository. There are three.
`/api/pairs` returns every scored pair whole, 3.1 MB at campaign scale, and
is left unbounded deliberately: it is the full-fidelity export, the client
never calls it, and a bulk route that silently truncated would be worse than
a large one. The two that feed a renderer are bounded, one by a per-pair
byte budget and one by the schema; the one that exists to hand over
everything still does. Naming it here rather than leaving it to be
rediscovered, which is what F172 asked for.

## F177. An 87-word disclaimer on a 40-word panel, and a checker that allowed 40

Browser QC on the trimmed pages came back clean on every count but one:
`/benchmark` was over the copy budget, worst panel 110 words against 40 and
page total 219 against 150.

The panel was the recovery-against-bridge correlation, and 87 of those words
were a single paragraph. It said the correlation is a hypothesis rather than
a metric, that it was noticed after looking at seven points rather than
predicted, that it displaced an earlier hypothesis about the substrate
construct, that RBM39 recovers at 6.0 A from a 15-mer cut out of a folded
domain which the earlier idea said should fail, and that the Sievers arm
multiplies the sample and is the test that matters.

Every clause of that is true and most of it is reasoning, which CLAUDE.md
puts in FINDINGS.md rather than on screen, and which allows a disclaimer
"only where a figure would be actively misread without one, and then one
sentence". The disclaimer earns its place, because a correlation shown beside
a p-value reads as a measurement. The rest does not. It is one sentence now:
a hypothesis, not a metric, the correlation noticed in these seven points
rather than predicted before them. The sample size was never the problem,
since the tile beside it already reads "far too few to validate on" and a
stat tile is not counted as prose.

The construct-comparison panel went from 71 words to 37 the same way, and one
of its sentences moved rather than going: the definition of the Bridged
column is now a tooltip on the column header, where it is a label rather than
narrative and is not counted. That is the better home regardless of the
budget, because a reader wanting to know what a column means looks at the
column.

Then the part worth more than the copy. With the panel at 40 words the
checker passed it, because it flagged `worst > 40`, and a panel at exactly 40
is not under 40. That is the sixth boundary this session drawn a notch wide
or narrow, after F139, F158, F161, F166 and F172. It is now `>= 40` and
`>= 150`, and the panel is at 39. Every other page still passes, with Delta
at 39, which is worth knowing: it is one word from the limit, and the next
sentence added to it will be caught rather than absorbed.

The test that was supposed to hold this was part of the problem. It asserted
the literal strings `> 40` and `> 150` appear in the tool, which pinned the
tool to a number rather than to the rule and made the test the second place
the budget was written down. It now reads both numbers out of CLAUDE.md,
which is the only file anybody would edit to change the rule, and a second
test requires the comparison to be inclusive. Both were checked against a
loose source, a tight one and a tight one whose comment quotes the loose
form, because the first version of the inclusive test failed by matching my
own explanation of why there is no longer a bare `> 40`. That is the third
check in this session to match prose rather than code, after the two in
F175, and the remedy is the same each time: strip the comments and look at
what runs.

One process note. The first remeasurement after the rewrite reported the same
110 words, because Flask caches templates and the server was still serving
the old ones. That is F159 exactly, which was about QC verifying against a
stale server, and it took a restart to see the change. The QC harness prints
a build fingerprint for this reason and it moved, from `63ca5ccb786e7f46` to
`03c53510b53074d7`, which is how the clean run is known to be a run against
the new templates rather than a second look at the old ones.

## F178. The publish path's two remaining unknowns, both measured

Not a defect, a pair of answers. The chain has thirty-eight hours of queue
left and then runs a sequence that has never run at this size, so the useful
thing now is to find out what it will cost and whether it will work, while
there is time to act on the answer.

**The atlas build.** Four seconds for 100 structures and 25 MB, measured by
building the benchmark campaign into a scratch directory through
`NOBBLE_ATLAS_OUT` rather than over the published bundle. At 2,360
structures and 265 MB that is around two minutes. Scoring is ten minutes,
projected from a full rescore of the benchmark campaign at 25.6 s for 7
pairs over 100 jobs. So nothing slow is hiding behind the queue: the whole
post-compute path is minutes, and the long stages after it are tier 2 and the
design scan, which are compute rather than bookkeeping.

**The F47 correction.** This is the one that mattered, because the atlas
build refuses while `bench02_BRD4_VHL` holds results run on a YAML the fixed
rule no longer emits, and `tools/rerun_pair.py` refuses outright when any job
has no known-good reference. If that refusal fired, the campaign would not
publish and the thirty-eight hours would buy nothing.

It will not fire. `_known_good` resolves a reference for all fifteen jobs,
each from the benchmark campaign, which is the F145 fix working on the real
layout rather than on a fixture. And the references are checked rather than
counted: the benchmark YAML carries no `modifications` block at all, while
the live one carries `ccd: HYP`. A reference that happened to share the bug
would have made the correction a copy of it, and counting fifteen references
would have looked exactly the same.

Worth saying what this does not establish. `--apply` has still never run,
and the dry run does not exercise the lookup, which is why the lookup was
called directly. What is established is that the precondition the refusal
tests is satisfied on the live campaign today, and that the file it would
copy from is correct.

## F179. Two functions called free_disk_gb, 37 GB apart

Found by making the mistake the divergence invites. `tools/status.sh` had
reported 535.6 GB free, I read 498 from `df -g` half an hour later, and spent
a few minutes looking for what had eaten 37 GB. Nothing had: `df -g` reports
gibibytes whatever the flag is called, and 535.6 GB is 498.8 GiB. The same
number twice.

That is my error, not the project's. But it sent me to look at how the G5
gate measures free space, and there the project has the same confusion
written down twice:

- `nobble/execute/runner.py` divides by `1e9` and the gate compares the
  result against `min_free_disk_gb = 50`, which is CLAUDE.md's "below 50 GB".
  Correct.
- `tools/hwprobe.py` divided by `1024 ** 3` and returned it from a function
  of the same name, under the key `free_gb_project_volume`, printed as
  "free disk : 507.0 GB". Gibibytes labelled gigabytes, 7.4 per cent low, 37
  GB out on this volume.

Nothing decides on the probe's figure: it is recorded in
`config/hardware.toml` and printed once. It still mattered. That printed line
is where a reader goes to find out how much room there is, and a number
there that disagrees with the gate by 37 GB is worse than no number, because
it reads as a measurement of the same thing. It is what I compared the gate's
reading against.

Fixed in the probe, since the gate and CLAUDE.md agree on decimal GB and the
probe was the one out of step. The two are now pinned by a test rather than
merged: the probe deliberately imports nothing from the `nobble` package,
because it is Phase 0 and runs before the package is necessarily usable, and
that is worth keeping. So the test requires the two to return the same number
for the same path, with a tolerance of 1 GB that admits two readings a moment
apart and not a unit disagreement, which on any volume large enough for this
project is tens of gigabytes. A second test reads both function bodies with
their docstrings stripped, after F177 taught me that a check on source text
matches its own explanation, and requires `1e9` and no power of 1024 in
either.

`config/hardware.toml` still records 507.0 from its last probe and corrects
itself the next time the probe runs. It is not hand-edited: it is generated,
and writing a figure into it that no probe measured is the worse of the two
states. Re-running the probe now would rewrite `config/tuning.toml`, which
the campaign on the GPU is reading, and that is not a risk worth taking for
a number nothing decides on.

## F180. A test of mine named a distinction its function cannot represent

Re-reading yesterday's additions for the patterns that keep recurring, one
of F175's ten tests was called
`test_it_compares_the_whole_bundle_not_the_difference` and asserted that a
bundle larger than free space is refused.

A difference-based check would have passed that assertion too. `judge` takes
`free_kb`, `bundle_kb` and `margin_mb` and has no parameter for what is
already on the droplet, so the design the name contrasts itself with is not
representable in the signature: there is nothing for the test to tell apart.
The name read as a guarantee and the body was a weaker statement that
happened to be true.

Renamed to what it checks, `the whole bundle is subtracted from free space`,
and it now asserts the identity rather than one consequence of it:
`remaining_after_mb` equals free minus bundle. The reason the function takes
no existing size, that `--delete` removes the old copy after the transfer so
the peak is both at once, stays in the module docstring where it was, which
is the right place for a decision no test can enforce.

Worth separating the two failure modes, because I have now hit both in two
days. F139, F158, F161, F166, F172 and F177 were checks narrower than their
names, where the name was right and the code fell short. This is the
opposite: the code is right and the name promised a check that cannot exist.
The first kind leaves a defect uncaught. The second leaves a reader believing
something is pinned when it is only documented, which is worse in one
specific way, because the next person to change `judge`'s signature will
read the test name and think the test will stop them.

## F181. I put one of two sibling budgets in config and left the other in a test

F174 created a per-pair page payload budget and put it in
`config/thresholds.toml`, because a number deciding an acceptance belongs
there. F176 created its sibling two hours later, a bound on how large an
`/api/ask` answer may be, and left it as a bare `200` inside the assertion.

Neither is read by anything but its own test, so the inconsistency is not
between a product setting and a test fixture: it is between two identical
things treated differently. `tests/test_no_hardcoded_cutoffs.py` walks
`nobble/`, `tools/`, `deploy/` and `qc/` and deliberately not `tests/`,
which is the right scope, since a test tree is full of expected values that
are not cutoffs. So nothing was going to tell me.

Both are now in `config/thresholds.toml` under `[app]`, beside each other,
which is the point: a reader tuning the page's weight should see the answer's
weight in the same place. The test reads it rather than carrying it.

A second thing in the same re-read. `test_no_sync_conflict_files.py` had a
bare `return` where the published bundle is missing, which makes a test that
examined nothing indistinguishable from one that examined everything and
found it clean. That is the shape F152 was built to find, in a file I wrote
yesterday. It skips now, and the suite's skip count is the thing that would
have told me: it has stayed at 4 through twenty-nine added tests.

Three of the last four findings are about my own work from the preceding
hours rather than about the pipeline: F180's name claiming an unrepresentable
distinction, this one's inconsistency, and the bare return. That is the
re-read earning its place. Writing a check and reading it back an hour later
catches a different class of thing than writing it carefully does, and the
class it catches is the one where the check looks right.

## F182. Making the Tier B gate cheaper to answer without answering it

D-NOB-068 keeps `config/tier_b_constructs.toml` a form: which domain of a
ligase binds its substrate is science knowledge, both mechanical routes are
ruled out, and no code closes the gap. It also says what code can do is make
answering cheap, and the form as it stood did half of that. It lists each
ligase's InterPro candidates with ranges and lengths, which shows what fits
the tier-1 cap and nothing about whether a candidate is folded.

`tools/tier_b_candidates.py` adds two measured columns: the mean pLDDT over
each candidate's own range, read from the same cached AlphaFold models the
Tier B selection used, and how much of the candidate falls inside the frozen
selection's best 200-residue window.

That turns out to matter. KCND2's IPR024587 at 471-545 sits at pLDDT 42.0 and
RAG1's importin-binding region at 12-291 at 59.2: both are annotated domains
within the cap that the model places in disorder, and ruling them out is a
modelling fact rather than a biology claim. The reverse case is just as
useful. CCNF's whole-model pLDDT is 71.5, which reads as a poor target, while
its cyclin boxes are 94 to 97: exactly the shape spec 3.3's domain-window
proxy was introduced for, now visible per candidate rather than once per
protein.

The line not crossed is ranking. Ordering by pLDDT would be a recommendation
in all but name, since the most confident domain would head every list, and
that is the mechanical route F41 and D-NOB-068 both reject. The order stays
the form's, longest first, and a test asserts it: if the listing is ever
sorted by confidence the test fails.

Two bugs while writing it, both mine and both worth the record. The frozen
`best_window` column is text, `"[302, 501]"`, not a list, and `list()` on it
yields ten single characters, so the first run printed `n/a` in every window
cell: a string that iterates without complaining, which is the shape F130's
NaN had. And `interpro.domains` returns member database signatures beside the
InterPro entries, so CCNF's seven choices came out as thirteen rows
describing the same handful of regions, which is the opposite of making a
decision cheap. Both are now covered, including the case that decides how
wide the collapse may be: CCNF carries IPR013763 twice, at 315-399 and
416-494, and those are two options rather than one annotated twice.

The form now points at the tool rather than embedding its output, so there is
one place the numbers come from and the file the reader edits stays a form.

## F183. I wrote F181 and then did it again in the next hour

F181 was about putting one of two sibling budgets in config and leaving the
other as a literal in a test. The tool I wrote immediately afterwards,
F182's, compared candidate domain lengths against a bare `60`.

It is the same mistake with the same shape. The number decides an
acceptance, which domains are offered as candidates at all, and it already
existed in a second place, the form's header prose, which states "between 60
residues and 326". The 326 was derived from config properly, through the same
`thresholds` lookup the validator uses, because that one looked like a
threshold. The 60 did not look like one, and that is the whole of the error:
a cutoff is a number that decides an acceptance, not a number that looks
important.

Now `tier_b.construct_min_residues`, read by a `floor()` function, with a
test that asserts no literal is compared against a length again.

The test for it had a flaw of its own, caught by reading it back rather than
by running it. It strips docstrings before searching the source, because the
docstrings discuss the very literal it forbids, and the pattern was written
`"""].*?"""` with a stray bracket, so it matched nothing and the search ran
over the prose as well. It passed, and would have raised a false alarm the
moment a docstring quoted `length < 60`. The strip is now verified by the
test itself, which asserts no triple quote survives it.

Three notes on this pair of findings, because two instances in two hours is
a pattern rather than a slip. The rule in CLAUDE.md is mechanical and the
judgement it needs is not: deciding whether a number is a cutoff requires
asking what it decides, and the literals that get missed are the ones that
read as facts about the domain rather than as policy. The cutoff sweep cannot
help here, because it walks `nobble/`, `tools/`, `deploy/` and `qc/` for
floats and `nobble/` for integers, and a new integer in a tool falls in the
gap. And the thing that caught both was reading my own work back an hour
later, which is now four findings in a row from that habit.

## F184. Closing the gap F183 fell through, and one real cutoff in it

F183 ended by naming the gap rather than closing it: the cutoff sweep walks
`nobble/`, `tools/`, `deploy/` and `qc/` for float literals in comparisons,
but only `nobble/` for integers. A new integer in a tool is invisible to
both, which is how a bare `60` got into F182's tool an hour after F181
recorded the same mistake.

Measured before widening, because a sweep that names fifty things to read is
a sweep nobody runs twice: there are seven integer comparisons across the
three directories. Six are not cutoffs. Two are display truncations in
messages, `and N more` after six moved keys in the drift report and after
three paths in `rerun_pair`'s refusal, and in both the decision itself is
made elsewhere on a non-empty list. Two are structural tests in `preflight`
for whether a pair has more than one arm, where the thing detected is
disagreement rather than a quantity. One is argument parsing. One is my own
guard against dividing by an empty range.

The seventh was real. `deploy/build_atlas.py` had `if len(points) >= 3`
deciding whether the recovery-against-bridge panel computes a Pearson and a
Spearman coefficient at all, which is to say whether a correlation is
published. That is a threshold by the only definition that matters, a number
deciding an acceptance, and it is now
`validation.recovery_correlation_minimum_points`. The config comment says
what it is and is not: three is the fewest points for which a coefficient is
defined, not a judgement that three points are enough, and what says the
latter is F177's one-sentence caveat on the panel and the tile beside it
reading "far too few to validate on".

The new sweep allowlists by comparison rather than by file, because a file
may hold both a cutoff and a truncation, and it carries three tests rather
than one: no unaccounted comparison, no stale allowance, and a floor on how
many comparisons the scan finds at all. That last one is there because both
of the others pass by scanning nothing, which is the shape that has now
caught me several times. Verified by simulation too: a reintroduced
`len(points) >= 3` in `build_atlas.py` is flagged, and the scan finds exactly
the six allowed comparisons and no seventh.

The refactor is behaviour-preserving, checked rather than assumed. Rebuilding
the benchmark atlas into a scratch directory produces a
`recovery_vs_bridge.json` identical to the published one, which is the
property that matters for a change to a published statistic.

## F185. The atlas published its settings and not which model produced them

`campaign.json` records the tuning a campaign ran under: token caps, recycle
counts, diffusion samples, seeds, the pocket list. It did not record the
model version. Every number in the atlas is a Boltz-2 prediction, so the one
fact needed to reproduce a pose was the one fact missing, and the About page
said "Boltz-2" and named no version either.

Measured rather than written down, for the same reason nothing here
hard-codes a core count: the environment is the fact and a version in a
config file is a claim about it. `nobble/execute/software.py` reads
`boltz` and `torch` from the BoltzMaker environment that the runner invokes,
following `hwprobe.mps_state()`'s pattern including its sentinel prefix,
because a pixi environment can print a warning and the last line of stdout
is not reliably the answer. Boltz 2.2.1 and torch 2.10.0, in 40 ms: metadata
only, never an import, since `importlib.metadata.version("torch")` reads the
distribution's metadata without importing torch and the atlas build runs this
on every publish.

Recorded in three places, deliberately differently.

Both campaign assemblers record it at assembly, because that is when the
environment is the one the queue will run in. The atlas build fills it in for
campaigns assembled before this existed, which includes the one on the GPU
and which will not be reassembled, and labels it `at publish, not at
assembly`. That label is the point: a publish-time reading describes the
environment now and only the assembler's describes the one the jobs ran in,
and publishing the weaker claim as the stronger one would be worse than
publishing nothing. The app reads the published record and never measures,
because the droplet is not the machine that ran the jobs and has no Boltz
install at all: measuring there would report a version confidently and
wrongly.

Two things found by doing it. The probe was built with `str.format` and its
own source contains `out = {}`, which format read as a positional field, so
it raised IndexError before the subprocess started. It surfaced as the
recorded status `unreadable: IndexError` rather than as a traceback, which is
the failure path working on my own bug, and a test now forbids `format` in
that file. And the edit to the assembler was refused by its own guard: the
line I was replacing appears twice, once in each of two campaign summaries,
and asserting a single occurrence stopped me editing one and believing I had
done both. Both now record it, and a test counts two.

The knock-on was predictable and worth chasing before committing rather than
after. A rebuild now adds five keys the published bundle lacks, so
`atlas_drift` reported drift: `campaign.json` 7502 to 7677 bytes, naming the
five `software.*` leaves. The right resolution is to rebuild rather than to
record a known drift, because the drift is real and the published atlas
should carry its model version. Rebuilt, back in step at 11,214 leaves
compared against 11,209, and browser QC clean on a moved fingerprint: 14
pages, no non-200, within the copy budget, no console errors, no serious axe
violations. The version sits in the About page's Provenance panel as a `mono`
paragraph, which the copy budget counts as a figure rather than as prose, and
renders nothing at all when no version is recorded.

One note on the test that guards the published bundle. It skips when the
bundle predates this and asserts when it does not, and I wrote here that the
suite's skipped count would therefore move from 4 to 5 "until the next atlas
build". That was already false when I wrote it, because the rebuild in the
paragraph above is that build: the test asserts now and the count stays at 4.
Written and corrected inside one finding, which is the same stale-figure
habit as F136, F157, F167 and F168, and the reason this project stopped
writing counts into PROGRESS.md at all.

## F186. The same sync-conflict copy again, caught earlier, and the gap it showed

A second iCloud sync-conflict copy appeared in the published bundle:
`bench06_RBM39_DCAF15__ternary__unconstrained__seed3 2.cif`, byte-identical
to the real file, mode `-rw-------`, carrying the pre-rebuild mtime of
18:14:54 beside the real file's 19:21:50. That is F173's mechanism confirmed
rather than inferred: iCloud held its copy of the file the rebuild replaced
and restored it afterwards, with its own timestamp and its own permissions.

Two things are better this time and one was missing.

Better: F173's check caught it while it was still untracked, so I found it in
`git status` before `git add -A` could commit it, which is exactly the
failure F173 was about. And the mechanism is now evidence rather than a
hypothesis, because the duplicate's mtime is the previous build's.

Missing: the thing that publishes the bundle is `deploy/deploy.sh`, and it
does not run the suite. A check living only in `pytest` does not stop a
conflict copy reaching the droplet on any run where nobody ran the tests, and
I was about to deploy. So the deploy now refuses before it sends anything,
listing the offending paths and the `rm` to clear them, using the same
pattern as the test rather than a second one: two checks for one thing that
disagreed about what a conflict name looks like would be worse than one.

Verified by planting a file rather than by reading the regex. A planted
`planted 2.cif` is named and refused, and four names the project does
generate are not: `nobble_icon_300.png`, `peptide_v2.html`, `scores.jsonl`
and `bench01__seed5.cif`. That last pair matters most, since a check firing
on `_v2.html` or on a seed number would be worse than none.

The refusal message needed the same treatment as the pattern, and did not
get it first time. It held the paths in one string, so with two conflicts the
listing indented only the first line and the suggested command came out as
`rm a\ 2.cif$'\n'b\ 3.json`: one mangled argument instead of two commands.
Running it with two planted files is what showed that, and the paths are now
an array printed one per line. A guard that refuses correctly and then prints
an unusable command is a guard someone will work around, and the only way to
know was to trigger it in the plural rather than the singular.

What I am not doing is making the builder sweep its own output, which was the
first idea. iCloud restores the copy asynchronously, after the build has
finished: a sweep at the end of a build would have missed both of these,
which arrived minutes later. The net has to be at the point of publication,
and now there are two, one in the suite and one in the deploy.

## F188. The sweep caught F185, and the way I was reading the suite could not

Two things, found together, both about whether the suite's answer reaches me.

**The sweep worked.** `nobble/execute/software.py`, written for F185, declares
`def versions(timeout: int = 60)`. The cutoff sweep's default-argument scan
walks `nobble/` and caught it, which is the rule F183 and F184 are about
catching me on, in the module I wrote immediately after them.

The number is allowed, and allowed in the project's existing terms rather
than by exception. It is how long to wait for a child process, the same kind
of number as `KILL_GRACE_SECONDS` in the module-level allowances, and it is
runtime control flow and not a judgement about data: the probe it bounds
takes 40 ms, so sixty seconds fires only when something is badly wrong, and
when it fires the result is a recorded `status` saying the version is
unavailable rather than a number that was thresholded. An allowlist records
what was looked at and waved through, so it is recorded with that reasoning.

What I did wrong was not re-running the sweep after adding a module under
`nobble/`. I ran it after F184, before `software.py` existed, and then wrote
three findings without running it again.

**The way I was reading the suite could not have told me cleanly.** Every
full-suite run this session ended with `pytest … | tail -6; echo "SUITE
EXIT=${PIPESTATUS[0]}"`. `PIPESTATUS` is a bash array. This shell is zsh,
where the variable is `pipestatus` and is one-indexed, so `${PIPESTATUS[0]}`
expanded to nothing: every `SUITE EXIT=` line I printed was blank. What sat
below it was the harness's own `[exited with code 0]`, which is the pipeline's
status, meaning `tail` succeeded.

So the check F168 taught me to make, reading the suite's status as a step of
its own rather than letting `&&` bind to the wrong command, was inert for the
whole session. No wrong conclusion came of it, because pytest's summary line
is authoritative and that is what I actually read. But it is a safeguard that
reported success unconditionally, which is worse than no safeguard, and it is
the same shape as the thing it was built to prevent.

It also cost real time here. `tail -6` keeps the summary line and discards
the `FAILED` line above it when a run is long, so "1 failed, 1111 passed"
arrived without a name and I spent several turns running subsets to find it.
`--tb=line` with the exit status captured before any pipe gives both, and
that is the pattern from here:

    pytest tests/ -q --tb=line > out 2>&1; code=$?; tail -5 out; echo "exit=$code"

The lesson I take is narrower than "test your tooling". It is that a status
line nobody has ever seen fail is not evidence of anything, and the way to
find that out is to make it fail on purpose: `(exit 3) | tail -1` prints an
empty `PIPESTATUS[0]` here in one line.

## F189. Deploying answered three questions I had been guessing at

The deploy ran end to end and verified: the space check reported 88,406.9 MB
free against a 24.6 MB bundle and a 1,024 MB margin, the sync-conflict guard
passed, the atlas was in step at 11,214 leaves, all nine routes returned 200,
and the droplet's `/healthz` now reports `source_fingerprint
ff0a3791278352e9`, which is the tree that was shipped. That last one matters
because the fingerprint check treats *absent* as a failure, and absent is what
the droplet reported before this: the comparison was vacuous until now and is
not any more.

Three things I had been asserting turned out to be wrong or imprecise, and
all three were settled by measuring the live site rather than reasoning about
it.

**The droplet has 86 GB free, not an unknown.** F175 added the space check
without knowing the answer, which was the right order, and the answer is that
the projected 265 MB bundle fits with room to spare. The check is still worth
having; the gate it guards is simply not close.

**HTML was already being gzipped.** I had written in F174 that
`enable_gzip.sh` is what takes the landing page from 514 KB to 18 KB, and
repeated it. It is wrong: nginx compresses `text/html` whatever `gzip_types`
says, and the live page serves 52,632 bytes plain and 14,064 gzipped today,
with the script not yet run. `enable_gzip.sh`'s own comment says the default
is `gzip_types text/html`, so the information was in the file I was citing. I
measured locally, where there is no nginx, and carried the conclusion across.
F174's paragraph is corrected in place.

**The script was missing the type that matters most.** Its `gzip_types`
covers CSS, JavaScript, JSON, SVG and plain text, and not
`chemical/x-mmcif`, which is what the structures are served as. Measured on
the published bundle, mmCIF compresses 3.5 times: a pose download drops from
243 KB to 37 KB and the campaign-scale bundle from 265 MB to 75 MB.
Structures are the only thing a reader fetches repeatedly, one per pose
viewed, and they were the largest thing not on the list. Added.

So the pending item is unchanged in name and different in substance. It was
"gzip, which makes the pages lighter"; it is now "compress the JSON and the
structures, because the pages already are". The value is also higher than I
had it, since 265 MB to 75 MB across a campaign is the dominant transfer and
the pages were never the problem.

The general lesson is the one this session keeps producing: a measurement
taken on the build machine is not a measurement of the service. F138 and F159
were the same thing for browser QC against a stale server, and F140 for the
deploy trusting 200s. This is it for compression, and the fix is the same
each time, which is to ask the thing that is actually serving.

## F190. F57's lesson was learned in one file out of four

A campaign is complete when it has written `campaign.json`, which every
assembler writes last. `ls -d campaigns/<prefix>_* | tail -1` names the
newest directory instead, and a failed assembly leaves one holding an empty
`yaml/` and an empty `outputs/`. F57 recorded that: three such directories
sat in `campaigns/` from a failing design scan, and the newest was what the
chain would have handed to `run_design.sh`.

F57 fixed `run_chain.sh`. It did not fix `refresh.sh`, which used the naive
form twice, or `run_corrected.sh`, or `run_design.sh`. So a finding about a
rule that must be applied everywhere was applied in one of four places and
left for a year of build-hours in the others, which is the shape F172 asked
me to stop repeating: when a fix names a category, enumerate the category.

The rule is now `tools/newest_complete.sh`, sourced the way
`tools/wait_for_gpu.sh` already is, and `run_chain.sh`'s local copy is a
one-line wrapper around it. One definition per language, with
`campaign.latest()` the Python side. It also returns exit 1 and prints
nothing when no complete campaign exists, which the naive form cannot: with
no match the glob stays unexpanded, `ls -d` prints an error, and the variable
ends up holding a path that does not exist.

Verified behaviour-preserving on the real tree. All four scripts resolve the
same campaigns they did before: corrected, design, benchmark, and the main
campaign with its 718 scored rows. And the difference is demonstrated rather
than described, in a temporary tree with three design campaigns where the
newest is incomplete: the helper picks the newest complete one, the naive
rule picks the incomplete one, and the test asserts both halves so it fails
if either stops being true.

**The second defect in the same file.** `run_corrected.sh` logged

    echo "=== finished $(date -u +%Y-%m-%dT%H:%M:%SZ) exit=$? ==="

A command substitution runs a subshell and sets `$?`, and expansion is left
to right, so `$(date ...)` clobbered the runner's status before `exit=$?`
was read. That line reported `exit=0` whether the corrected campaign's
runner succeeded or failed, and `tools/status.sh` scans these logs for
failure patterns that `exit=0` can never match: a failure of that stage was
invisible in the one line written to report it. The status is captured into a
variable now, and the test demonstrates the mechanism with `bash -c 'false;
echo "x $(true) exit=$?"'` printing `exit=0` against the captured form
printing `exit=1`.

That is the same family as F188's `PIPESTATUS` and F168's `&&` binding to
`tail`: three different ways for a status line to be unable to say "failed",
two of them in my own work and one in the project's. The common thread is
that none of them can be found by reading, only by making the command fail
on purpose and looking at what the line says.

One more instance of a smaller habit. The test asserting `exit=$?` is gone
matched the comment above the fix, which quotes the bug it describes. That is
the fourth check today to match prose rather than code, after two in F175 and
one in F177. Comments are stripped before the search now, and I should treat
"searching source text" as implying "strip the comments" rather than
rediscovering it each time.

## F191. Two of the ledger's four Tier options were dead in production

The pair table's Tier control offered `all`, `benchmark`, `A` and `B`, and
compared its value with `p.tier === tier`. A score row's `tier` is the arm
the pair belongs to: `benchmark`, `sievers_zf`, `scramble` or `design`. The
LM schema says so in as many words, "this is the arm the pair belongs to, not
the Tier A/Tier B curation tier", which is the distinction the control
collapsed: it was built against the curation tier and wired to the arm.

Measured on the live site by driving the control rather than reading the
code. `benchmark` returned all 7 rows, `A` returned 0 and `B` returned 0. Two
of four options were dead in production, today, not at some future scale.

And the file explains the rule it broke, three lines above, in the comment
saying why `furniture` is deliberately not offered: "a control that can never
match anything is worse than no control". That comment was written about a
field whose value is permanently null. The Tier control had two such options
and nobody noticed, because with seven benchmark pairs the correct answer and
the broken answer look identical for the only option anyone would use.

At campaign scale it stops being cosmetic. Of the 158 pairs the running
campaign will publish, 120 are `sievers_zf` and the rest `scramble` and
`design`: 151 of them could not be selected at all.

The fix is not to retype the list. That is the same failure waiting for the
next arm, and it is what produced this one. The options are derived from the
arms the payload carries, so a dead option is impossible and a new arm
appears without an edit. Derived in the route rather than in Jinja, because
`map(attribute='tier')` yields Undefined for a row without the key and
`reject('none')` does not filter Undefined, which would put a blank option in
the list for a sparse row.

Verified in three steps rather than one. The test was written first and
failed for the right reason, naming `['A', 'B']` as matching nothing. Then
the options were checked against a 158-pair atlas carrying all four arms, and
all four are offered, with `sievers_zf` shown as "sievers zf" while the value
stays the arm. Then the control was driven in a browser against that atlas:
40, 39, 39 and 40 rows for the four arms and 158 for "all", which sums
correctly and is the thing a reader will actually do.

The tests hold both directions, because each catches a different mistake.
"Every arm in the data can be selected" is the one that matters at campaign
scale. "No option matches nothing" is the one that was live. A fourth test
forbids writing any arm into the template as a literal, since a correct
hard-coded list would pass the first two and fail the next time an arm is
added.

## F192. A test that rebuilt the atlas to check one line of text

`tests/test_model_version_is_recorded.py` verified that the provenance report
names the model by running `tools/provenance.py` as a subprocess and reading
its output. That script prints at module level, so running it is the only way
to see what it prints, and one of the things it does on the way is a drift
check, which rebuilds the whole atlas.

So a test asserting one line of text cost about seven seconds and a full
atlas rebuild on every suite run. It also wrote `validation.json` and
`weights.json` into the campaign directory, because `atlas_drift` refreshes
the derived documents before comparing, which is F172's fix doing exactly
what it should in a context that had no business triggering it.

I first called that a race. It is not: pytest is single-threaded, the rewrite
completes inside one test, and the content is idempotent, so no other test
can see a partial file. The honest objections are cost and purity, which are
enough on their own. A test session that rewrites campaign files is a test
session whose results depend on what else ran, and seven seconds for one
assertion is seven seconds.

The line is a function now, `software.provenance_line`, and the script calls
it. Three cases rather than two, because they are three different claims: a
campaign with no record at all, a record carrying versions, and a record
whose probe failed. The middle one reuses `summary()` instead of
reimplementing the formatting, and the third is the one a two-case split
would have collapsed into "not recorded", which would report a failed probe
as an absent one.

Measured rather than assumed: the file runs in 0.20 s against 7.58 s, and
`validation.json`'s mtime is unchanged across a run of it, which is the side
effect being gone rather than merely faster.

A test asserting the script still prints exactly one model line and still
calls the function stays, because the point of extracting it was that the
script and the function cannot drift. Testing the function alone would leave
`provenance.py` free to format its own line again.

## F193. Tier 2 would have refined a selection it did not make

`tools/tier2.sh` runs the selector, then the refiner, then the scorer. It
keyed the decision to refine on the selector's exit code and handled one
value, 3, for Gate G1. Its own comment explains why that guard exists, and
the explanation is wider than the guard: "without that the refiner runs next
with no queue to read, which is harmless and reads in the log as though the
refinement had been done".

Exit 0 covers four outcomes. A selection that queued jobs. A refusal with
nothing rankable, which `main()` deliberately returns 0 for, because "a
selection that refused is not a failure of this step". An unpriceable
refusal, which F161 made distinct from Gate G1. And "no tier-1 queue to
refine", which I found only by running the thing and had not enumerated when
I wrote the finding up the first time. Only the first writes
`queue_tier2.jsonl`, so no exit code can carry the decision.

And it is worse than the no-op the comment describes, because the queue file
persisted between runs.
`campaigns/benchmark_20261103T192126Z/queue_tier2.jsonl` holds ten jobs for
`bench02_BRD4_VHL`, written on 3 November, with `tier2.json` recording that
selection as `selected`. A refusal on that campaign would have sent the
refiner at those ten jobs: twenty-five diffusion samples each, hours of GPU
time on a selection made days earlier, logged as a fresh decile. I had
described this as "the refiner does nothing"; the evidence on disk says it
would have done the wrong thing.

Two changes, because the problem has two halves.

`run()` clears any existing queue before it selects. That makes "the queue
exists" mean "this call wrote one", which is the property the shell needs and
which every caller should have: arranging it is not a shell script's job. The
order is load-bearing and a test pins it, because clearing after the
selection would delete the queue the selection had just written.

The selector then prints `TIER2_QUEUE=<path>` or `TIER2_QUEUE=none`, and the
shell reads that instead of inferring from a status. A sentinel prefix rather
than the last line, for the reason `hwprobe.mps_state` and F185's probe both
use one: a pixi environment can print a warning and the last line of stdout
is not reliably the answer. The shell distinguishes three cases, and the
third is the one I would have missed: no sentinel at all, meaning an older
build or a selector that died before reporting, which exits 4 rather than
falling through.

Proven by running each path rather than by reading. A planted stale queue is
gone after a refusal. The selector prints exactly one sentinel and prints
`none` on a fixture with no tier-1 queue, while still exiting 0. And the
shell's parse was exercised on three outputs: `none` skips, a real path
refines that path, and no sentinel refuses.

This is the third postcondition-versus-status finding in a row, after F188
and F190, and they share a shape worth naming. A status says what a step
thinks happened. A postcondition says what is on disk. When the two can
disagree, the step that follows should read the second, and the way to find
out that they can disagree is to make the step refuse and see what the next
one does.

## F194. The refresh said it had refreshed when the atlas had refused

`tools/refresh.sh` runs score, validate, throughput and atlas, and it is the
step between a finished campaign and the deploy. Two of those four were
invoked as `… 2>&1 | tail -N`, which makes `$?` the status of `tail`. Nothing
read either one.

The atlas half was live. `build_atlas.py` returns 1 when
`stale_inputs` reports anything, which is the main campaign's state today:
fifteen `bench02_BRD4_VHL` jobs run on a YAML the fixed rule no longer emits.
So the chain would have spent thirty-six hours on the queue, reached refresh,
had the build refuse, and printed `=== refreshed. Deploy separately with
deploy/deploy.sh ===`. D-NOB-069 predicted the refusal. It did not occur to
me that the refusal would be invisible, and an operator reading that log
would have had every reason to think the campaign was published.

Worse, the printed tail is not reliable either. The refusal goes to stderr
and `publishing <campaign>` to stdout, and under redirection those interleave
by buffering, so the last line shown can be the one that reads like success.
The status was the only trustworthy signal and it was the one discarded.

The scoring half is quieter and the same shape. A failed score leaves
`scores.jsonl` holding the previous run's values, the atlas copies them, and
the drift check cannot notice because a rebuild reads the same stale file.
That is F171's compare-stale-against-stale, one layer up from where F171
found it.

The fix captures each status before anything pipes it, and then treats the
steps differently on purpose. Score and atlas gate publication: a failure
stops the refresh with a non-zero exit and leaves the previously published
atlas in place, which is stale rather than wrong, the F59 principle the build
already applies to itself. Throughput does not gate: it feeds a panel, and
refusing to publish a valid campaign because a timing summary failed is the
wrong trade. That asymmetry is why these runners deliberately avoid `set -e`,
and a test pins both halves of it so neither drifts into the other.

`run_design.sh` had the same gap, in the other script that scores and then
consumes what it scored: its lift step reads those scores, and a lift
computed from the previous run's values is a number that looks like a
measurement of this scan. Checked now, and the test enumerates the category,
"every script that runs the scorer and then uses the scores", rather than
naming the two files.

Two things checked rather than assumed, both of which could have made this
fix pointless. The scorer's status does carry information: it returns 2 for
no campaign, propagates a crash as 1, and returns 0 on completion, with
per-pair failures recorded in the data as the fallback ladder intends. Had it
always returned 0 a status check would have been theatre and a file-level
postcondition would have been needed, which is the distinction F193 turned
on. And `run_design.sh` already captured the inference runner's status
correctly, on its own line before the echo, which is exactly the idiom
`run_corrected.sh` lacked in F190: the right pattern was in the repository
and simply not applied uniformly, for the second time in three findings.

One incidental confirmation. Running the refused build against the real
`deploy/atlas` left it untouched, 111 files and 100 structures, because the
stale check precedes `rmtree`. A refusal cannot leave a half-built atlas,
which is the property F59 claims and which I had not actually tested.

## F195. Four runners that could not say "failed", one of them mine

Low severity, and worth saying so before the detail: the chain calls the
runner and the scorer directly, and `run_queue.sh` with a deliberate `||
true`, so none of this was breaking the live publish path the way F194's
refresh was. It matters for an operator running a script by hand, and for
`tools/status.sh`, which scans these logs for failures that `exit=0` can
never match.

The family had four states. `run_queue.sh` and `run_msa.sh` captured a status
on its own line, reported it and exited with it. `run_corrected.sh` captured
it, reported it and exited 0 anyway. `run_substrate_msa.sh` ended on an
`echo`, so its status was the echo's. `run_design.sh` and `tier2.sh` had
later steps whose statuses nobody read at all.

The `run_corrected.sh` one is mine, from F190, committed a few hours ago. That
finding was about a status line that could not say "failed", and it fixed the
line and stopped there: the log told the truth and the script still exited 0.
Fixing the instance and not the category, in a finding about fixing the
category.

What the enumeration bought is the point. I set out to fix two scripts. The
test, written against the family rather than the two, failed on three more
cases: `run_design.sh` ending on an echo so a failed lift reported success,
`tier2.sh` doing the same after its refined scoring, and `tier2.sh`'s
refinement step itself, whose status nothing read.

That last one needed care rather than the obvious fix. The runner exits 1
when any job failed, so aborting on it would skip scoring the jobs that
succeeded, which `tests/test_scripts.py` forbids and which `tier2.sh` did
once. So the refinement's status is remembered, the poses it produced are
scored anyway, and the status has the last word at the end. The warning says
that is what is happening, because a script that prints a failure and carries
on should say why it is carrying on.

My test was wrong once too, in both directions. It required a capture of the
form `NAME=$?` and so reported `tier2.sh`, which captures
`${PIPESTATUS[0]}` because its selector is piped through `tee`, as having no
capture at all: more correct than `$?` there, not less. And it asserted "the
last line is not an echo", which is a proxy rather than the property. A
multi-step script may end on an echo if every failure path has already
exited, which is exactly what `tier2.sh` does. The assertion is now the thing
itself: somewhere the script exits with a status it captured.

## F196. The crystal overlay was dead in production, and five routes knew why

`curl https://nobble.mdeller.com/crystal/6H0F.cif` returned 500. The pose
page loads that URL into the viewer to superpose a prediction on its
deposited structure, so the crystal overlay was broken on the live site for
every benchmark pair, and had been since the app was first deployed.

The cause is one line. `crystal()` began with `from nobble.curate import
structures`, which imports gemmi at module level, and the droplet's
virtualenv holds flask and gunicorn and nothing else.

The project had already learned this twice and fixed it four times. Every
other route that touches that stack imports it only behind `if not
precomputed`, and two carry the reasoning in comments: "Importing
nobble.curate here is what made this route 500 on the droplet while passing
every local check", and "Two routes have already returned 500 in production
by importing that stack unconditionally". Even the crystal *mapping* was
moved to read from the atlas for this reason. The file serving was the one
place the lesson was not applied, which is the same shape as F190 and F195:
a rule held everywhere but one.

It survived because of how it was checked. The deploy fetches nine routes
and every one of them is a fixed path, so a parameterised URL was never
requested; locally gemmi is installed, so every local check passed. The one
observation that would have caught it is the one nobody made: ask the live
site for a crystal.

The assemblies are published into the bundle now, seven files and 4.2 MB,
and the route serves them with no scientific import. It serves the stored
gzip when the client accepts it, 988,048 bytes for 6H0F against the
4,127,262 it expands to, and expands it otherwise, because a client that
sends no `Accept-Encoding` is not hypothetical: plain curl sends none, which
is how the 500 was found. The deploy now fetches a crystal URL with its id
read from the bundle it is shipping, so the gap that hid this closes with it.

Nothing restricted travels with the assemblies, checked rather than assumed.
An assembly carries coordinates and no SMILES, InChI or chem_comp
descriptor, and spec 2.1's restrictions name PROTAC-DB, UbiBrowser and
BioLiP2 rather than the PDB, whose content the bundle already publishes.

The verification that matters is not that the route returns 200 here. It is
that it returns 200 with gemmi, duckdb, scipy and numpy made unimportable by
a meta-path hook, which is the droplet as far as this route can tell. 200
and 988,048 bytes.

One completion, because fixing the instance is the mistake this session
keeps recording. The deploy now builds a URL for every parameterised route
rather than only the one that was broken: `/crystal/<id>.cif`,
`/structure/<job>.cif`, `/api/pair/<id>` and `/api/pair/<id>/structures`,
with the ids read from the bundle being shipped. Asked of production before
deploying, the crystal route was the only one of the four that was failing,
which is the reason to check all four rather than evidence that checking one
would have done.

Adding the parameterised URLs broke an existing test, which is the second
half of the same point. `test_docs_match_reality` parses the deploy's route
loop and holds PROGRESS, DECISIONS and `run_chain.sh` to the number it finds,
because PROGRESS said eight for as long as the design arm existed and nothing
read it. Putting `$EXTRA_PATHS` in the loop made the parse fail, so the test
reported that the loop was gone. Its regex now allows the variable and
asserts it is there, which is a stronger check than before: the prose counts
the fixed routes, since the dynamic ones depend on what the bundle holds, and
PROGRESS now says what the dynamic ones are. A documentation test catching a
change to the thing it documents is the behaviour wanted, not a nuisance.

Three mistakes of mine on the way, all found by running the thing.

The publishing step was placed 58 lines before `benchmark.json` is written,
so its guard was falsy and the step was skipped in silence: a step that does
nothing and says nothing, which is the bug this session has spent its day
finding in other people's code. It reads the document it is given now, and
says so when the mapping is absent rather than skipping quietly.

The import check matched the route's own new comment, which names the import
it exists to forbid. That is the fifth check today to match prose rather than
code and the second written in full knowledge of the trap, so the strip is no
longer a remedy I apply after being bitten: any check on source text strips
comments first, and this one asserts the strip worked.

And one of the six tests passed before the fix existed, because it looped
over a glob of a directory that did not exist. An assertion inside an empty
loop, which is exactly what `tools/vacuous_tests.py` reports, found by
running that sweep twenty minutes after writing the file. It skips now.

## F197. The bundle began redistributing structures and credited nobody

F196 put seven deposited assemblies into the published bundle. The About
page, whose job is to record where everything comes from, mentioned neither
the RCSB nor the Protein Data Bank.

Nothing required it. PDB content is CC0, and the viewer already labels each
overlay `deposited <id>`, so a reader looking at a superposition can see
which structure it is. The reason to name them is consistency: that page
credits every other source the project draws on, lists which were reachable,
and since F185 states the model version that produced every coordinate.
Beginning to redistribute someone else's structures without saying so was out
of step with the page's own standard rather than with any licence.

The panel names the RCSB and lists the identifiers, as a `mono` paragraph
because identifiers are figures rather than prose as far as the copy budget
is concerned, and renders nothing at all when no assembly is published.

One thing worth getting right rather than nearly right. The list is built
from the `crystals/` directory, not from `crystal_by_pair`. Those differ: the
mapping says which deposition a pair refers to, and when an assembly is
missing from the cache `build_atlas` warns and publishes nothing for it. A
panel built from the mapping would credit a structure the bundle does not
carry, which is a worse error than silence, because it is a claim about
redistribution that is not true. The list is also deduplicated, since two
pairs may name one deposition: BRD4 appears twice here, on VHL and on CRBN.

A test holds both halves, that the ids credited are exactly the files
published and that nothing is published which no pair refers to.

Also this session, and clean: the browser QC harness was pointed at
production for the first time rather than at localhost. It reports the build
it tested, `7fbe332a3de6083a`, which is the tree that was shipped, and then
fourteen pages, no non-200, within the copy budget, no console errors and no
serious axe violations. The harness was built to interrogate a server and had
only ever interrogated one on this machine, which is the same subject
confusion F138 and F159 were about; asking it about the live site was overdue
and found nothing wrong.

## F198. The headline verdict stated its confidence for every outcome but the good one

`_verdict` turns the ROC's bootstrap interval into one of three sentences.
Two carried a qualifier and one did not:

- above chance: `"above chance"`
- below chance: `"below chance at 95 per cent confidence: the statistic
  separates the two classes in the opposite direction to the prediction,
  which is a result rather than an absence of one"`
- neither: `"not distinguishable from chance at 95 per cent confidence"`

The interval is the same object in all three branches, so this was not about
how much evidence there was. It meant the project's headline claim, the one
falsifiable test in the whole build, would have been published without the
qualifier that both unfavourable outcomes carry. A reader comparing "above
chance" against "not distinguishable from chance at 95 per cent confidence"
would reasonably take the first as the firmer statement, when they are the
same statement about the same interval in opposite directions.

It is out of character for the file it sits in. That file refuses to draw a
curve at all without matched negatives, insists that a below-chance result
"is a result rather than an absence of one", and has a comment explaining
that this very function was written as three branches because two of them
used to collapse into "reads as exhaustive and is not". The level was already
computed, in a local variable, and used twice out of three.

Now stated in all three. The test holds the property rather than the strings,
since the wording will change and the property should not: every branch names
the configured level, all three branches are shown reachable so the check
cannot pass by never seeing one, an interval touching or straddling 0.5 is
never called above chance, and the below-chance sentence still says it is a
result.

One test had to move with it. `test_roc_scope` asserted
`interpretation == "above chance"` by equality, which is what pinned the bare
form in place; it now asserts the prefix and the level separately. The two
other places that mention the phrase use substring checks and needed nothing,
which is the difference between pinning a value and pinning a shape.

Found by reading what the site will say when the campaign finishes, rather
than by a test failing. Nothing was broken: the number was right, the
interval was right, and the sentence reporting them was quietly asymmetric.
That is a class of defect no suite catches, because every assertion about it
passed.

## F199. The design caveat had two branches where the layer has three

Found by continuing F198's method: reading what the site will say when the
campaign lands, rather than waiting for a test to fail.

`_score_validation` in `nobble/design/report.py` turns the ROC's verdict into
the sentence under the design tab's lift chart. It read:

    if interpretation.startswith("above chance"):
        ... "above chance"
    else:
        ... "and is not distinguishable from chance"

The layer produces three verdicts. A curve separating in the opposite
direction fell into the `else` and was described as showing no separation at
all: an AUC of 0.25 with its whole interval below 0.5, reported as "not
distinguishable from chance". That is not a hedge, it is wrong. An interval
wholly below 0.5 is distinguishable from chance, and the layer that computed
it says so in as many words, calling it "a result rather than an absence of
one".

It also understates the more interesting outcome. A composite that orders
pairs backwards is a finding about the composite, and the project's whole
posture is that a failed control is published rather than hidden. Describing
it as an absence of signal is the one reading that loses the information.

This is the mistake `_verdict`'s own comment records, two files away: "the
middle case is the one that used to swallow the third: `low > 0.5` else 'not
distinguishable' reads as exhaustive and is not". The function was split into
three branches for that reason. The code consuming it kept two.

Three now, with the below-chance branch saying the composite separates the
controls in the opposite direction to the prediction, and still saying the
composite is not validated, because a backwards composite is not a validated
one either.

The test enumerates rather than illustrates. It drives all three of the
layer's verdicts through the caveat, asserts the three verdict kinds are
covered, and asserts the three caveats are distinct, so a fourth verdict
cannot silently reuse a third's words and two verdicts cannot collapse into
one sentence again. That last assertion is the one that would have caught
this: the two-branch form produced the same caveat for below chance and for
indistinguishable.

F198 and F199 are the same defect in two places, and neither was a broken
number. Both were correct arithmetic reported in a sentence that said
something else, which is a class of defect the suite cannot reach by
asserting on values. The only way I found them was to ask what the page will
read like, which is worth doing once more before the campaign finishes rather
than after it publishes.

## F200. "Mixed" was doing the work of two opposite results

`compare`'s conclusion is the sentence on the benchmark page that says
whether F6 held: whether submitting a substrate as its whole domain rather
than a 15-mer recovers poses better. It had a label for better, a label for
nothing changed, and `mixed` for everything else.

Everything else is two results. Some better and some worse is mixed. None
better and several worse is not mixed at all: it is F6 contradicted, the
whole domain recovering poses less well than the fragment. Rendered, the
all-worse case read "mixed: 0 improved, 4 worse, control held", which is a
sentence whose first word contradicts its own numbers.

Nothing was hidden, because the counts are printed either way. The headline
word was wrong for one of its two cases, and since the function has explicit
F6 labels for the other directions, the omission is an asymmetry rather than
a decision not to judge. It also softens the result the project's posture
says to publish plainly: a failed control is reported, not described as an
absence.

There is now a branch for it, saying the pairs got worse, the control held,
and none improved, which is the mirror of the supported sentence.

A second thing in the same branch, which the exercise turned up rather than
the reading. `control {'held' if control_ok else 'moved'}` has a false arm
that cannot run: the two branches above the F6 ones return for every state in
which the control has not held, so `control_ok` is True by construction
there. The conditional is gone and the sentence says what it always said.

The test checks the ordering rather than only the presence of the new label,
because a contradicted branch placed after the catch-all would leave every
all-worse run reporting mixed exactly as before, and a test that only
asserted the words existed would pass.

F198, F199 and F200 are one defect three times: a number computed correctly
and a sentence that does not say what the number means. None of them was
reachable by asserting on values, which is why a suite of 1,166 assertions
had nothing to say about any of them. What found them was asking what the
page will read like when the campaign lands, and the useful generalisation is
narrow: wherever a function turns a measurement into prose, count its
branches against the cases its input can take.

One more of my own, for the record. Verifying the dead arm was gone, my check
matched the comment I had just written explaining that it was gone: the sixth
prose match of the session and the first in a verification rather than a
test. The habit is now to strip comments by default, and I had still not
applied it to an ad-hoc check.

## F201. The verdict that opens a gate was the one that stated no conclusion

`gate_g1`'s verdict is what a person reads when refinement is priced, and
`tier2.sh` prints it after "GATE G1 OPEN:". Four cases, rendered:

- fits:                  "costs 20.0 h or less against 67.7 h remaining"
- over, bounded range:   "costs 29.2 to 219.3 h, and the upper end exceeds
                          the 67.7 h remaining of the 96 h budget"
- over, measured factor: "costs 150.0 h against 67.7 h remaining of the 96 h
                          budget"
- unpriceable:           "a refusal to guess"

The third says nothing. It states two numbers and leaves the reader to
compare them, and it is the branch for a cost that is *known* to exceed the
budget rather than bounded above it: the strongest case of the four and the
one that opens the gate. It also reads almost exactly like the passing
verdict, where the distinguishing words are "or less". "Costs 150.0 h against
67.7 h remaining" and "costs 20.0 h or less against 67.7 h remaining" are
one glance apart and mean opposite things.

It is mitigated where `tier2.sh` prints it, because that prefixes "GATE G1
OPEN:", and not mitigated in `tier2.json` or the atlas, where the sentence
stands alone.

It says "which exceeds" now, like its sibling.

The tests are worth a note of their own, because I wrote them twice. The
first version asserted on source text, and failed twice on my own fix: the
f-string wraps across lines so "which exceeds the" is not a substring of the
file, and `code.index('"verdict": (')` found the unpriceable dict rather than
the main one. Its own docstring said to drive the function rather than read
the source. I read the source anyway, which is the seventh time this session
a check on source text has gone wrong and the first where the method was
written down in the same file and then not followed.

They drive `gate_g1` now, by substituting the two things it reads, and one of
them checks the thing neither the old nor the first new version did: that the
sentence and the flag agree. A verdict saying "exceeds" while
`gate_g1_open` is False, or the reverse, would be worse than either alone,
and that is F161's shape, where an unmeasured campaign priced at 0.0 hours
with `fits` True.

With F198, F199 and F200 this is the fourth measurement-to-prose defect in
one session, and the branch counting is now mechanical: `_verdict` three
cases three branches, the design caveat three and three, `compare` four
directions and four labels, `gate_g1` four cases and four conclusions.

## F202. A deliberate 404 crashed the page that asked for it

The browser QC harness had only ever run against a seven-pair atlas. Pointed
at a campaign-scale one for the first time, it reported four console errors
that seven pairs never produce:

    Failed to load resource: the server responded with a status of 404
    Uncaught (in promise) SyntaxError: Unexpected token '<', "<!doctype "...

`pose.html` fetches `/api/pair/<pair_id>/structures` and called `r.json()`
whatever came back, so a 404 handed `JSON.parse` the error page's HTML and
the promise rejected unhandled. The seed overlay then fails without saying
anything, and browser QC counts the rejection as a console error, which is a
gate this project holds at zero.

The 404 is correct and must stay. F122 changed that route from 200 with an
empty list precisely because "a pair that produced nothing" and "a pair this
campaign has no record of" are different states, and the viewer would
otherwise render an empty overlay for a pair that was never run. So the fix
belongs on the client: a 404 now yields an empty catalogue that records why
it is empty, in `unavailable`, and a network failure is caught separately
rather than being read as a 404.

The guard is on `r.ok` rather than on the number 404, so a 500 is handled
too, and a test checks that rather than trusting it.

What the fixture did and did not show. My first campaign-scale atlas had 158
scored pairs against results rows for the original seven, which is what fired
the 404; a real atlas has scores as a subset of results and never does. So I
built a consistent one, 158 pairs with 2,255 results rows and 2,255
structures, close to the shape the running campaign will publish, and the
harness came back clean: fourteen pages, no non-200, within the copy budget,
no console errors, no serious axe violations. That is the answer to the
question I had actually set out to ask, and it is worth separating from the
defect the inconsistent fixture happened to expose.

The handling gap is real either way. The route 404s by design, so a client
that cannot survive one is wrong regardless of how rare the state is, and an
atlas whose scores and results disagree is a state the fallback ladder
permits: a pair can be scored from tier-2 results alone.

The test runs the template's own `fetchCatalogue` under node against a
stubbed fetch, rather than matching the source, which is F50's lesson. And it
was checked against the original unguarded form, which rejects with exactly
the SyntaxError the QC run reported, so the test is known to bite rather than
assumed to.

## F203. A panel that had only ever been rendered empty

`#refinement` on the pose page sits beside the pose and compares what the
refined structure measured against the coarse one. It is hidden until a
refinement exists, and none ever has: `measured_scaling` reports no tier-2
job has completed on any campaign, which is why F135's budget had to bound
the cost rather than measure it. So the panel had been rendered only in its
empty state, and the empty state is the one thing about it that was known to
work.

Built an atlas with `scores_tier2.jsonl` and `results_tier2.jsonl` for one
pair and rendered it. The mechanics are sound: the wrapper unhides, four rows
appear with their tier-1 and tier-2 values and the change, the withheld note
explains why the ipTM minima are absent, and there are no console errors.
`nobble/sampling.py`'s partition held too, with `iptm_min_ternary` moved
deliberately in the fixture and correctly not shown.

What it did show is that the rows were labelled with field names:
`bridge_formation_rate`, `bridge_percentile`, `convergence_score`,
`plip_fingerprint_match`, in a panel beside a ledger whose own columns read
"Bridge %ile", "Converge" and "PLIP". Nobody had seen it because seeing it
required data that does not exist yet.

The labels come from `data.COMPONENTS`, attached in the route. Three of the
four keys are labelled there already, and the alternative, a parallel list in
`nobble/sampling.py`, is the duplication F181, F183 and F187 were each about.
It is attached in the route rather than in `sampling.compare` for layering:
a scoring module importing the app's label table inverts the dependency, and
a test asserts `nobble/sampling.py` does not import `nobble.app`.

`bridge_formation_rate` is not in COMPONENTS, because COMPONENTS drives the
weight sliders and that rate is not a composite component. It falls back to
its key with the underscores opened out and the first letter raised, which is
a transformation of the key rather than a name invented in the route. That
leaves the ledger calling the same quantity "Bridge rate" and this panel
calling it "Bridge formation rate", which is a difference I am recording
rather than hiding: what identifies the row is its tooltip, "proportion of
seeds whose glue bridged both chains", and inventing a fourth COMPONENTS
entry to make the two agree would make a non-component look like one.

The useful generalisation is about when a thing gets looked at. This panel,
the crystal overlay in F196 and the Tier facet in F191 were all broken or
rough in a state nobody had reached: no refinement, no request to that route,
no atlas with more than one arm. Three defects in one session from the same
cause, which is that a conditional branch of the interface is as untested as
the data that would reach it.

## F204. The headline statistic is computed twice and nothing compared them

Rendering the ROC panel with a computed curve, which F203's method says to
do because no campaign has ever produced one, showed the AUC twice on one
page:

- the sentence above the chart: `AUC 0.7747`, `roc_summary.auc`, computed in
  Python from the rank statistic and published in `validation.json`
- the chart's own title: `AUC 0.775`, a trapezoid the browser integrates over
  points the browser builds from `PAIRS`

They agree, and that is the same number to the precision the title shows.
Nothing compared them. `tests/test_composite_agreement.py` exists for exactly
this pair one statistic down, and its reasoning transfers without alteration:
"They are also the kind of pair that agrees until it does not, and nothing
compared them: a normalisation changed on one side would silently give the
page a different ranking from the pipeline, and the page is where the ranking
is read." For the ROC the stake is higher, because the AUC is the project's
one falsifiable result.

So `qc/roc_harness.mjs` now runs `delta.html`'s own `buildRoc` under node and
reports the AUC from the title it builds, and a test drives both
implementations over the same rows and compares. The JavaScript is run rather
than transcribed, which is F123's point: a Python copy of the formula would
test the copy.

Getting the harness to run the real function took three stubs and each one
is a fact about the code worth knowing. `ROC_MINIMUM_PER_SIDE` is injected
into the template from `config/thresholds.toml`, so the harness takes it as
an argument rather than carrying a literal, and a test asserts it carries
none. `NOBBLE.plotLayout` is nobble.js's shared layout helper, returned
unchanged here because this measures the number and not the palette. And the
page writes its counts into `#roc-counts`, which is how the harness reports
an empty curve rather than guessing from an absent title.

Two tests guard against the comparison passing vacuously: both values must
be a plausible AUC strictly between 0 and 1, and Python's must exceed 0.5,
because the fixture is built to separate and an AUC at chance would mean the
fixture had changed rather than the implementations agreeing.

What this does not do is reduce the two implementations to one. The browser
needs points to draw a curve, so it has to build them, and once it has them
the trapezoid is free. The duplication is reasonable; the absence of a
comparison was not.

## F205. Three sliders went on contributing to a column labelled as fitted

`weights.json` has reported `fitted: false` on every campaign the project has
run, so the weights panel had never once been rendered with a fit. F203's
method says to render the states that have never been rendered, so I fitted on
the Sievers fixture: 127 labelled pairs, objective 0.8515, and
`components_used` naming two of the five components, `bridge_percentile` at
0.2 and `delta_iptm` at 0.8.

The fitted branch rendered correctly, down to its sentence: "Fitted on 127
labelled pairs, never by hand." Under that sentence the ledger's composite
column read 0.6578 for `bench04_IKZF1_CRBN`, while the `nobble_score` Python
had computed and stored for the same pair was 0.6189.

The three components the fit did not select had kept their hand-set defaults,
0.25, 0.15 and 0.00, and were still contributing:

```
fitted two only          0.6189
fitted + defaults        0.6578
fitted + explicit zeros  0.6189
```

A fit that leaves a component out has not declined to answer for it. It has
answered zero: `components_used` names the two it selected, and the fit's
answer for the other three is that they carry no weight. Falling back to the
hand-set default there puts a hand-set number into a figure presented as
fitted, which is the one thing the panel's sentence promises it is not.

This is F106's shape surviving one layer down. There, the alias map meant a
component the fit *had* used rendered as its default; the fix made the lookup
go through one function so the template and the JavaScript could not resolve
the name differently. The miss was that the same function still treated "the
fit has no value for this" as "no fit applies here", which is right when
nothing has been fitted and wrong for every component a fit passed over.

So `data.fitted_weight` now returns zero rather than the default when a fit
exists, and the sliders read 0.20, 0.80, 0.00, 0.00, 0.00 with the ledger's
first composite at 0.619, matching the stored score. With no fit the defaults
stand and the panel still says they are starting values, which is the branch
the live site is in.

Fixing the server alone did not fix the page. `campaign.html` initialises the
sliders in JavaScript, because the browser recomputes the composite on every
move, and it carried its own copy of the fallback: `FITTED[k] !== undefined ?
FITTED[k] : COMPONENTS[k].default_weight`. The server rendered zero into the
input's `value` and the script immediately overwrote it with 0.25. The rule
has to exist on both sides, the same necessity the alias map already carries,
so the test pins both and the comment on each points at the other.

The defect was not reachable on the live site, and it was one campaign away
from being the first thing anyone read. It needed a fit to exist, and the fit
needs the Sievers arm, which runs after the panel.

## F206. A plan, an estimate, and fifteen measured results between them

No design campaign has run, so `design.json` carries `lifts: {"status": "no
design campaign has run yet", "lifts": []}` and the design tab had only ever
been rendered unscanned. Rendering it with a completed alanine scan, by
computing lifts through `nobble/design/lift.py` from synthesised scores for
IKZF1's fifteen variants, put the measured state on screen for the first
time.

The measurements were right. Fifteen lifts, ordered as the construction
intended, with `C7A` most sensitive at -0.2806; three substitutions that lost
the bridge outright and six more that weakened it without losing it, the
latter correctly excluding the three that had lost it. The per-position
profile, the chart, the scan-parent line and the two bridge sentences all
rendered.

The two lines wrapped around them did not. The panel's heading read "Planned
scan", and under the table sat a projection: "15 variants, 225 jobs, about
4.4 hours." Both were static. A reader saw a proposal, and an estimate of
what the proposal would cost, bracketing its own results.

The Lift column had the same defect and was already fixed. Its comment in
`design.html` says the column "said 'not run' regardless, so after a scan the
same page disagreed with itself about whether the scan had run". That is this
finding's sentence too. The fix stopped at the column, which is the part that
shows a number, and left the prose that frames it.

This keeps happening and the shape is always the same. A panel's state is not
one field. F203 found a panel whose mechanics worked and whose row labels were
field names; F160's lesson, quoted in this same template, is that getting the
data right and leaving the label wrong is worse than the silence it replaced.
Here the data was right in every cell and the heading above it named a
different state of the world.

`data.scan_state` now returns the heading and the counts, keyed on the
substitutions the profile has a lift for, which is the mapping the Lift
column already builds: the heading cannot claim a scan the table does not
show. Three states, because there are three. Unscanned keeps the plan and the
projection, which is the right line before the scan runs and the branch the
live site is in. Part way through says "Scan in progress", reports what has
been scored and keeps the projection, because the rest of the work still
costs what it costs. Complete says "Completed scan" and reports the count
alone: a forecast of work already done is a forecast of nothing.

It is computed in the route rather than the template because the route blanks
the profile when the chosen parent is not the one that was scanned, so the
count has to follow the profile and not the atlas. Switching parents on a
scanned atlas is tested for exactly that: the heading goes back to "Planned
scan" with the profile panel gone, rather than inheriting a completion that
belongs to another peptide, which is F147's defect one field over.

One thing the profile computes and nothing renders: `most_sensitive` and
`least_sensitive`. The chart carries the ordering those two summarise, and the
ordering is the arm's durable claim, so this is left as it is rather than
spending panel copy restating the chart.

## F207. The tool that finds silent failures was failing silently

`tools/vacuous_tests.py` traces the suite under `sys.settrace` and reports
every assertion that never executed. Under settrace this suite takes minutes,
so having just written two test files I ran it on those two files.

It accepted the paths and discarded them. `main` called `assertion_lines()`,
which globs all of `tests/`, and then `pytest.main([..., str(TESTS)])`, which
runs all of it. The two arguments reached neither. I waited past the timeout
and stopped it, having concluded from the delay that it was doing something
other than what I had asked for, which was the right conclusion for the wrong
reason.

A tool that ignores an argument is worse than one that refuses it. The
refusal is information; the silence is a wrong answer delivered slowly, and
the only reason I noticed is that this particular wrong answer is slow. Had
the suite been small the tool would have printed a correct-looking report
about the wrong set of files.

So the paths now narrow both halves, the AST sweep and the pytest run, and a
path that does not exist exits 2 with its name rather than being skipped.
Two files now take 0.68 seconds instead of minutes.

Two things came out of testing it that are worth more than the fix.

**The test file recursed.** Its first draft pointed the tool at itself, since
that was a real test file that was cheap to run. The tool runs pytest on what
it is given, so pytest ran the file, which ran the tool, which ran pytest. It
hung. The constraint generalises past the hang: the gate runs the tracer bare
over all of `tests/`, so any test in this suite that invokes this tool must
target a file it generated, or the gate recurses. Every subprocess here does,
and a test checks that they do.

**The check on that constraint had the session's own recurring defect.** I
wrote it as a list of forbidden spellings searched for in the file's own
source, and it matched the list it was written with: it failed against clean
code, pointing at its own line. That is the seventh time this session a
source check has matched its own text, after F175 twice, F177, F183, F196,
F200 and F201. The adopted remedy, stripping comments first, does not help
when the text being matched is the check's own data. An AST walk over the
call sites does, because it reads what the code does rather than how the file
reads, and it is the same lesson as F123: run the thing rather than
transcribe it.

## F208. The check that decides whether to publish crashed instead of refusing

`stale_inputs` compares every queue row against the YAML it names, and
`deploy/build_atlas.py` calls it before publishing: it is what stops a
fifty-hour run reaching the site when the inputs on disk are not the inputs
the code would emit. It has a branch for the row whose YAML is missing.

A row with no `yaml` field at all went past that branch. `Path("")` is not
absolute, so `campaign / Path("")` is the campaign directory, and a directory
exists, so `path.exists()` was true and `path.read_text()` raised
`IsADirectoryError`. The guard written to produce a refusal produced a
`pathlib` traceback mentioning neither queues nor YAML, in the publish step
of an unattended chain.

`is_file()` rather than `exists()`, which covers the empty field and any
other path that exists without being a file.

Two honest qualifications. The current selector builds each tier-2 row by
copying the whole tier-1 job dict, so it always writes `yaml`, and no queue
on disk has a row without one: 2,810 rows across five campaigns, all
carrying it. This hardens a guard rather than fixing a reachable defect. And
I found it by writing bad queue rows myself, while building a tier-2
rehearsal, rather than by reasoning about the code.

It was still worth fixing, for the same reason the guard exists: the cost of
a bad refusal here is measured in days of GPU time, and a diagnostic that
dies on the input it was written to diagnose is the shape this project keeps
finding (F193 and F195 were both "the script reports success for a thing
that did not happen", one layer out).

The reason string is branched as well. "The YAML the queue row names is not
on disk" describes a file the row never claimed to have, and a campaign whose
inputs were moved is not the same fault as a row that names nothing: one
message for two input cases, which is F198 through F201 exactly.

## F209. Eighteen test files were wired to campaigns that are about to change

Found by reading the skip list rather than the code.
`test_the_live_tier2_queue_shares_the_tier1_yaml` skipped with "tier 2 has
not been selected on this checkout" while the benchmark campaign had held a
ten-row `queue_tier2.jsonl` the whole time. It was keyed on the main
campaign's directory name, so the property it guards, that tier 2 names only
YAML that tier 1 also names and therefore that correcting a tier-1 input
corrects the refinement, had never been checked against the one campaign
that could check it.

That was one visible skip. Behind it, eighteen files named a campaign
directory by its timestamp, twenty-nine references in all. A pinned name is
right until the campaign it names is superseded or pruned, and then the test
does not fail. It finds nothing, its own `.exists()` guard returns false, and
it skips. Both triggers were already in the diary: the campaign running now
will produce a new directory, and G5 prunes old ones when disk gets tight.

This is F190 again, which fixed exactly this in the shell after `ls -d
campaigns/design_* | tail -1` handed a failed assembly to the design runner,
and noted at the time that the fix had landed "in one file out of four". It
turns out the Python side of the test suite was the fifth through
twenty-second.

They now resolve through `campaign.latest_or_absent(prefix)`: `latest`, but
returning a path that does not exist instead of None. That choice is what
kept the change small and safe. Every call site already guarded on
`.exists()`, so with no campaign of that prefix the tests skip exactly as
before, and with one they read the newest complete one. One definition, in
the module that already owns the rule, rather than a copy per file, which is
what F181, F183 and F187 were each about.

The check that the rewrite was behaviour-neutral is the skip count, not the
pass count. Before: 1,223 passed, 3 skipped. After: 1,227 passed, the same 3
skipped. A test that had quietly stopped reading its campaign would have
shown up as a fourth skip, which is the whole defect in one number.

Three references remain and are all something else: prose in a docstring
recording a historical fact, a string handed to a path-shape matcher that
reads nothing, and synthetic campaigns built in a `tmp_path` fixture to test
`campaign.latest` itself.

Two mistakes of my own, both the kind this session keeps producing. The
mechanical rewrite inserted an import inside a multi-line `import (`, which
is the sort of thing that only shows up when every file is compiled, so the
fix was to compile every file. And the guard's first version matched any
dated name anywhere in a test, which flagged nine files that invent one in a
fixture: the discriminator is not the shape of the name but whether it is
joined to the real campaigns root. The guard also found its own allowlist
going stale in the same run, which is the property
`tests/test_template_cutoffs.py` already asks of its own.

## F210. The answer to a gate was recorded where nothing could read it

Two findings from closing Gate G1's construct half, both about a thing being
correct and out of reach.

**The candidate floor hid the only right answer for SMURF2.**
`tier_b.construct_min_residues` was 60, on the stated reasoning that "below
this a domain is a motif rather than a fold that can present a surface, and
listing it adds an option nobody would take". SMURF2 falsified it. Its
substrate recognition runs through WW domains of about 40 residues, so at 60
the shortlist could offer only its HECT catalytic domain, its C2
membrane-binding domain and the whole protein: three options nobody would
take, with the one anybody would take filtered out. Lowered to 35, so a WW
domain sits inside the floor rather than on it.

The lower floor added 23 rows across the fifteen genes and all but SMURF2's
three were machinery: SOCS boxes, F-boxes, RINGs, B-boxes. So the original 60
was right about the general case and wrong about the one gene whose answer it
was hiding, which is the harder kind of wrong to notice: the filter looked
well calibrated everywhere a reader would have checked.

**The eleven named constructs were unreachable.**
`config/tier_b_constructs.toml` is the form F163 built, and filling it in
made `tier_b_constructs.report()` say `ready` with eleven constructs and no
problems. Nothing could use them. `nobble/execute/campaign.py` resolved a
receptor with `C.CONSTRUCTS[construct_name]`, indexing spec 1.1's six Tier A
constructs directly, so a Tier B name would have raised `KeyError` at
assembly. The arm was selected, frozen, gate-passed, *answered*, and still
unrunnable.

Widened rather than given a second lookup at the call site, which is
D-NOB-007's rule and F181's lesson: `constructs.by_name` consults the Python
registry and then the form, and the assembler goes through it. A test
asserts the two key sets are disjoint, because `by_name` lets Tier A win a
collision rather than checking there is none.

**And the form could not express a "no".** Four of the fifteen cannot have a
construct, and `missing()` returned every gene not covered by one, so
excluding a gene left Tier B permanently unassemblable: `assemblable`
required `not absent`. Exclusions now carry a required reason, and an
exclusion without one is reported as a problem rather than counted as
covered. Without that the table is a way to make a gate pass by deleting the
genes that fail it, which is the shape of F193 and F195 one level up: a step
reporting success for work it did not do.

`report()` also checks spec 3.3's `min_ligases_for_gate` of 10, since
excluding genes shrinks the arm and a short arm answers a narrower question
than the gate was written for. Eleven constructs clear it by one.

**One trap avoided by reading rather than testing.** Three constructs name an
InterPro entry annotated more than once, so each needs an `occurrence`.
`domain_by_accession` counts occurrences from the N-terminus, and the
candidate shortlist prints in order of length. Had I taken the shortlist's
index, FBXW4 would have got 266-412 instead of 133-265 and SMURF2 would have
got a WW domain modelled in disorder at pLDDT 58 instead of the one at 82.5,
and nothing would have failed: both are valid annotations of the right entry.
F41 and F107 are both exactly this, and the docstring says so in the file.
The residue counts are now pinned per construct, which is what turns a wrong
occurrence into a failure.

## F211. I wrote the defect I had spent the session fixing, twice, in one function

Building the Tier B manifest produced two faults of my own, both of them
shapes this session has a name for.

**I asserted a count instead of deriving it.** The builder returned
`"errors": 0` as a literal. It was false. `validate()` had found ten
`token_cap_exceeded` errors, DCAF8L1's 326-residue propeller against the
69-heavy-atom 759 glue coming to 410 tokens against a cap of 400, and the
literal would have carried them straight past `assemble_tier_b`'s refusal,
which keys on exactly that field. So the arm would have assembled 1,540 jobs
with ten of them over the cap and nothing would have said so.

That is F193 and F195 precisely: a step reporting success for work it did
not do. I had read both earlier in the same session, written about both, and
then typed a zero into a field whose entire purpose is to be counted. The
count is now `sum(... if issue.severity == "error")`, and the finding it
exposed was real.

**The fix for the cap overrun then did nothing, twice.** Marc declared
DCAF8L1_WD40 an exception, the form recorded it, 140 jobs carried the
`token_cap_declared_exception` flag, and the manifest went on reporting ten
errors. `validate()` built its set of permitted constructs as
`{name for name, item in C.CONSTRUCTS.items() if item.exception}`, over the
six Tier A receptors, so a Tier B construct could not be in it whatever the
form said. `tools/preflight.py` held the same comprehension verbatim, so
preflight would have rejected the same ten jobs for the same reason.

Two copies of one rule is F181. A rule that spans one of two registries is
F210. This was both, which is why it is one fix: `constructs.declared_exceptions()`,
built from `all_constructs()`, called from both places.

**And my own guard had the same blind spot as the bug it guarded.** F210's
sweep replaced fourteen `CONSTRUCTS[...]` subscripts and added a test
forbidding them. The test matched `CONSTRUCTS[` and `CONSTRUCTS.get(` and
nothing else, so it was blind to the two call sites that reached the
registry by iterating it, `.items()`, and to a third, `msa.required_sequences`,
which used `.values()` and which I had found by reading rather than by the
guard. A guard that enumerates one spelling of an access pattern is the same
error as fixing one call site of fourteen: I enumerated the instances I had
just edited rather than the thing they had in common.

Widened to `.items()`, `.values()`, `.keys()` and `in CONSTRUCTS`, and it
immediately flagged a line of mine that was correct but hand-rolled, the
union `[*C.CONSTRUCTS.values(), *T.load().values()]` in `msa.py`, which is a
third place expressing "both registries" where `all_constructs()` now
exists. That is the guard earning its place on the first run after being
widened.

**What this says about the method.** Every one of these was found by running
the thing and reading what it printed: the ten errors by building the
manifest, the inert exception by rebuilding it after the form changed, the
iteration blind spot by widening a regex and watching it fail. None of them
would have been found by reading the code I had just written, which I had
done.

## F212

The pose-recovery positive control has failed across the benchmark panel, and
the failure is real rather than a mapping artefact.

Sixty-five ternary poses over seven deposited complexes: 0 per cent within
3 A, 1.5 per cent within 5 A, median 17.54 A. Per pair, the best RMSD over
five seeds:

| pair | PDB | best RMSD | median |
|---|---|---|---|
| bench04_IKZF1_CRBN | 6H0F | 4.99 | 5.36 |
| bench06_RBM39_DCAF15 | 6Q0W | 5.46 | 6.00 |
| bench05_CSNK1A1_CRBN | 5FQD | 11.81 | 12.18 |
| bench02_BRD4_VHL | 5T35 | 14.44 | 17.92 |
| bench03_BRD4_CRBN | 6BNB | 17.99 | 20.40 |
| bench01_GSPT1_CRBN | 5HXB | 24.54 | 29.06 |
| bench07_CDK12_DDB1 | 6TD3 | 44.28 | 44.40 |

Three things establish that this is a measurement of the prediction and not of
the frame, which is the distinction `recovery_against_crystal` was written to
make and which nothing had read off the current campaign:

- the receptor anchors superpose at 0.539 to 1.883 A over 424 to 1,240
  backbone atoms, so the frame each peptide is judged in is correct
- peptide sequence identity is 1.0 on all seven pairs, so the residues being
  compared are the residues intended, not a window at the wrong offset
- both numbers are recorded, not inferred: `validation.json` carries all 65
  per-pose records under `layers.pose_recovery.detail`, each with its
  `receptor_rmsd`, `receptor_anchor_atoms` and `peptide_identity`, and an
  independent recomputation reproduces them. The failure was legible on disk
  from the moment the campaign scored; nothing had read it

And ipTM is high while the poses are wrong. Median ternary ipTM on the same
seven pairs runs 0.887 to 0.933: the model is confident about interfaces it
has placed 5 to 44 A from where they sit in the crystal. A confident wrong
answer is worse for this project than a diffident one, because the headline
statistic is a difference of ipTM minima and nothing in it can notice.

Two rungs of the fallback ladder, read off structures already on disk:

- **pocket conditioning does nothing.** Conditioned median 14.95 A against
  unconstrained 17.92 A, and per pair the two arms differ by less than 0.5 A
  on six of seven. The conditioned arm restrains the glue into the E3 pocket
  and moves the degron by less than the width of a residue.
- **tier 2 cannot test it.** The top-decile selection took 16 pairs by
  `nobble_score` and none of them is a benchmark pair, so the refinement
  running now produces no recovery measurement at all. The one rung that
  might rescue the poses is being spent entirely on pairs with no ground
  truth.

This is what Gate G6 is for. The matched-control ROC reads AUC 0.4583, 95 per
cent CI 0.3316 to 0.5842, "not distinguishable from chance", over 24 positives
and 96 matched negatives from the Sievers screen. With the positive control
failing, that null cannot be read: a Delta-ipTM that does not separate glue
from control is indistinguishable from a Delta-ipTM computed over poses that
are in the wrong place. The campaign has measured something; it has not yet
established what.

## F213

Two tests broke on F212's change, and neither broke for the reason it looked
like. Both are the same category: **a test that asserts something about the
environment while reading as an assertion about the code.**

`tests/test_refinement_budget.py` stood a four-line stub in for `Selection`,
carrying only the field the test needed. When `build_tier2_queue` learned to
read `recovery_controls`, the stub did not have it, so a test about per-pair
timeout budgets failed with an `AttributeError` about a field it does not
care about. The stub is gone: it now builds the real dataclass, which cannot
drift from the thing it stands in for.

`tests/test_provenance_report.py::test_the_disagreement_is_marked_when_they_differ`
is the more interesting one, because it was not failing at all. Its second
half restores the published `design.json` and asserts the disagreement marker
goes away. That only demonstrates something when the published bundle and the
ranking agree to begin with, and they do not: the ranking reads the finished
campaign and chooses `sievers_dc66fdefdc` (ZN565), while the published bundle
is the 3 November benchmark and says `benchmark_888fd2c63e`. They differ
because the atlas build is refusing on the F47 stale inputs, so publication is
blocked and the published bundle is necessarily older.

So the test was reporting the publication backlog as a defect in the marker.
It now names that precondition and skips on it, quoting the live provenance
line, which makes the skip a statement about the state of the build rather
than a silent pass. The marker itself is working: F89 was the case where these
two values disagreed for the project's life with nothing printing both, and
here it printed both and was believed.

The general shape, worth keeping: when a test fails after an unrelated change,
the first question is whether it is asserting about the code or about the
machine it is running on. Four of the twelve failures on the ceiling lift were
the second kind, and so are both of these.

## F214

**After any kill, the stall detector was tripped for the rest of the
campaign.** It fired on two jobs nobody was running, and that is the state
every one of this build's kills has left behind.

`state.jsonl` is append-only, and a job killed between its `running` record
and its outcome leaves `running` as its last word forever. The resume path is
built for that and does not mind: `running` is not in `TERMINAL_STATUSES`, so
the job is re-run, which is what F111's eight resume tests establish.

The watchdog reads the same log for a different question, and for that question
a stale record is a lie. Run against tier 2 while the refinement was working
normally:

```
   overdue  bench01_GSPT1_CRBN__ternary__conditioned__seed1__tier2 30.9 min against 5.8 min expected
   overdue  sv_pos_ZN582_ba3680__ternary__conditioned__seed5__tier2 38.9 min against 5.7 min expected
exit=1
```

Both were jobs I killed by hand, half an hour earlier, when I stopped the
stale chain and relaunched the refinement. The GPU was working through
`bench04_IKZF1_CRBN__ternary__unconstrained__seed1`, which is neither of them.
Nothing was overdue, nothing was wrong, and the detector could no longer say
so.

This matters because of how it is consumed. `run_chain.sh` arms the watchdog
on a ten-minute loop and prints only when the verdict stops being "ok", which
is the right design: the chain log carries a line only when there is something
to see. A permanently non-zero verdict turns that into a line every ten
minutes for days, and every later real stall arrives inside noise that never
stops. It is F112 one layer down. F112 was a detector nothing consulted; this
is a detector that cannot stop firing, and the two fail the same way.

Fixed in the runner rather than in the watchdog, because the runner is where
it is knowable. A new runner process means the previous one is gone, and
`tools/wait_for_gpu.sh` allows one runner at a time, so every `running` record
present at startup is stale by construction. The watchdog reading the same
file cannot tell "killed" from "hung" without asking the operating system
about a process that has already exited.

`abandoned_in_progress` reads the last record per job and the runner appends
an `abandoned` record for each before it counts anything. Not `failed`, which
carries a reason this does not have, and not terminal, so the job is still
re-run. Idempotent, so a restart does not append a second record for the same
job and grow the log without bound. Eight tests, including the torn-tail case,
which is exactly the line a kill writes.

**Still to do, and deliberately not done now:** `tools/tier2.sh` does not arm
a watchdog at all. Only `run_chain.sh` does, so a refinement started on its
own has no stall detection, which is how this run began. The arming has to go
near the top of the file and `tier2.sh` is executing: bash reads a script
incrementally and keeps a file offset, so inserting lines above the point it
has reached is what left the 4 November chain running a script that no longer
existed on disk. It waits until the refinement finishes.

## F215. Refinement sharpens the poses and does not recover them

Gate G6's last untested rung, measured rather than argued. Tier 2 refines with
25 ternary samples against tier 1's 1, and the question was whether the
benchmark pairs' poses move toward the deposited peptide when it does.

Five of the seven control pairs refined before tier 2 was stopped:

```
pair                         n    tier1    tier2     move  anchor
bench01_GSPT1_CRBN          10    29.14    24.91    -4.98  stable
bench03_BRD4_CRBN            5    20.40    17.40    -2.70  stable
bench04_IKZF1_CRBN          10     5.35     4.96    -0.39  stable
bench05_CSNK1A1_CRBN        10    12.21    12.27    +0.03  stable
bench07_CDK12_DDB1           7    44.92    44.66    -0.25  stable
```

Two pairs move by more than the 2.0 Å `campaign_change_margin_a`, so this is
not a null result in the sense of nothing happening: `bench01` improves by
5.0 Å and `bench03` by 2.7 Å. Both still sit 17 to 25 Å away. `bench05` does
not move at all, and `bench07`, the worst pair at 44.9 Å, moves a quarter of
an angstrom. The receptor anchor is stable on all five, so the two tiers are
measured in the same frame and the moves are moves rather than a reframing.

The reading: more sampling converges the model on its own answer, and its own
answer is in the wrong place. That is a different failure from a noisy one,
and it is the more useful of the two to know, because it says the remedy is
not compute.

Three things this result does not say, worth writing down because each was
tempting:

- It is not evidence that Boltz-2 cannot fold ternaries. It is evidence about
  this pipeline's inputs and this receptor-frame comparison on seven pairs.
- `bench04` crossing from 5.35 to 4.96 Å moves six poses inside the 5.0 Å
  breakpoint. That is a breakpoint being straddled by four hundredths of an
  angstrom, not a recovery, and `tools/recovery_delta.py` is ordered so the
  sub-margin verdict is stated first and the crossing second.
- Two pairs never refined (`bench02_BRD4_VHL`, `bench06_RBM39_DCAF15`), so
  this is five of seven. `bench06` was the one pair where tier 1 was close
  (6.09 Å) and it is the one most likely to change the picture. The chain's
  tier-2 stage resumes the same queue and will reach both.

What follows from it is D-NOB-076: publication held, and held by the scripts
rather than by a note.

## F216. The watchdog called a killed campaign healthy

Found by reading the output of a change rather than by the change failing.
Having armed a tier-2 watchdog inside `tools/tier2.sh`, I ran it once against
the campaign whose tier 2 I had killed ten minutes earlier, and it said:

```
   ok       campaign_20261104T004632Z: 1 running, none overdue
```

There was no tier-2 runner on the machine. The one job it counted as running
was the job that was mid-flight when I killed the tmux session.

The watchdog's whole purpose, in its own docstring, is to tell a running
campaign apart from a stopped one, and F20 named the ambiguity precisely:
"the queue sat still for 3h45m while every check that asked 'is the process
alive' answered yes." The watchdog answered that question better than the
checks F20 broke on, by comparing elapsed time against the campaign's own
completed work and against the bound the runner allows. What it never did was
ask whether there was a runner at all. Both of its signals are about a job
taking too long, and a job that is not running takes no time.

So the state after a kill reported ok, and would have gone on reporting ok
until the record aged past the hard bound, at which point it would have
reported STALLED: a job to go and kill, which was already dead. Two wrong
answers in sequence, the first of them the worse, because a watchdog answering
ok is the only evidence that anything checked.

`abandoned` is now a third state rather than a degree of the other two, asked
before the timings, with exit code 3. The remedy is what separates them: a
stalled job needs the runner killed, an abandoned one needs it started, which
is also the moment F214's close-out fires and re-runs the job.

Three things the implementation had to get right, each of which is a way this
could have been worse than the bug:

- **Liveness is read per tier.** `tools/tier2.sh` produces a live tier-2
  runner alongside an idle tier 1 on every chain run, so a single "is a runner
  alive" answer would let the busier tier mask the other. The tier is read off
  the command line, and a runner with no `--tier` flag is tier 1, matching the
  runner's own default.
- **"I cannot tell" is not "nothing is running".** `pgrep` missing, or exiting
  above 1, returns None, which is read the same way as alive. An alarm raised
  because the probe broke would train whoever reads it to ignore the alarm.
- **The default is not a probe.** `stall_report(..., alive=True)` keeps every
  existing caller and test describing the state it means to describe; only
  `main` probes the machine. A function whose answer depends on what else is
  running on the computer is not testable, and the tests that matter here are
  the ones that feed it the same record with and without a runner.

Both verdicts, immediately after, on the same campaign: tier 2 names the
killed job and exits 3; tier 1 reports ok and exits 0, because the chain's
tier-1 runner genuinely is alive. That contrast is the whole fix.

## F217. The correction re-ran the stale input and reported success

**Superseded in part by F219, which is the same investigation finished. The
conclusion recorded here first was wrong and the reasoning is kept because
the way it was wrong is the point.**

The F47 correction fired for the first time in the 6 November chain rerun:
`tools/rerun_pair.py bench02_BRD4_VHL --apply` rewrote the pair's fifteen
YAMLs, dropping

```
    modifications:
    - position: 1
      ccd: HYP
```

from chain P, the peptide, and the runner re-ran all fifteen jobs. 0 failed,
exit 0, fresh structures on disk, 163 s of real compute each.

Every re-run job returned ipTM bit-identical to sixteen significant figures.
Boltz with a fixed seed is deterministic, so I read identical output as an
identical input tensor and concluded the `modifications` block never reached
the model. That conclusion is false, and what made it attractive is that it
explained the observation completely while requiring nothing to be checked.

The observation has a second explanation that I did not look for: that the
input really was identical, because the re-run never read the corrected YAML.
Boltz writes `boltz_results_<job>/processed/` beside its predictions and
reuses it. `processed/` and `msa/` are dated 11-04 03:57, from the original
run; `predictions/` and `lightning_logs/` are from the re-run. The cached
`processed/structures/*.npz` holds chain P residue 1 as **HYP** while the
corrected YAML says PRO.

So the hydroxyproline was in the model all along, and still is. See F219.

Two wrong turns before that, both worth keeping.

I first suspected stale data and ran two checks that said the structures were
old. Both were wrong the same way: a literal `Z` appended to a local-time
`stat` format, and a local timestamp passed to `-newermt`, on a machine
running UTC-5. Corrected, the structures are unambiguously fresh, which was
true and which I then over-read as "so the inputs must have been fresh too".

Acting on the false conclusion, I made an undeliverable PTM a manifest error,
on the reasoning that a phosphodegron folded without its phosphate is a
different molecule. The reasoning is sound and the premise was not: there is
no evidence Boltz ignores `modifications`, and the cache proves it applies
them. Reverted, along with its test.

What should have stopped me: only bench02's fifteen jobs drifted between the
two campaigns, and the other eighty-five shared jobs reproduced exactly. A
model that silently drops a declaration would not produce drift confined to
the one pair whose declaration differed. I had that figure in front of me
before I wrote the finding and read it as corroboration.

## F218. The licensing guarantee was announced, not checked

`deploy/build_atlas.py` ended with:

```python
    print(f"\nverified: no PROTAC-DB chemistry in the published bundle")
```

An f-string with nothing to interpolate, no condition in front of it, and no
scan of the bundle anywhere above it. It was printed every time the build
reached its last line, whatever the bundle held. The sentence it printed is
the project's one verbatim licensing constraint (spec 2.1: "PROTAC-DB stays
internal-use-only and is never redistributed").

Found while explaining why two tests had started failing, which is worth
saying: the failing tests were not the defect, they were the only thing that
had ever actually looked inside the bundle, and they were looking for the
wrong thing.

F72 is the same shape one level down: a redaction count initialised to 0 and
incremented nowhere, so the bundle reported `redactions: 0` while containing
a `smiles_withheld` field. This is worse than F72, because a count of zero at
least invites the question and a sentence beginning "verified" closes it.

**The check now behind it.** `redact()` keys on `source in
REDACT_WHEN_SOURCE`, a deny-list, so a record arriving with its source
spelled `PROTAC-DB`, or blank, or as something nobody has thought of yet, is
published untouched. A verifier keyed on the same field and the same list
could only confirm redact() agreed with itself. So the verifier is keyed the
other way round: an allow-list of sources whose chemistry may be
redistributed, each with the reason it may, and an unrecognised source fails
closed. That asymmetry is the whole value of having a second opinion, and the
tests prove it by feeding four spellings that the deny-list does not contain.

**I got this wrong first, and the way it failed is worth recording.** The
first version compared every published SMILES against PROTAC-DB's own table
(15,502 records, as RDKit canonical SMILES), on the reasoning that provenance
can be misspelled and chemistry cannot. It passed its own negative controls
and then refused a real build of the benchmark campaign, naming PROTAC-DB
compound 335 in `campaign.json`. The record was CCD 759, MZ1, sourced
`deposited_ternary`: wwPDB's chemistry, read from a deposited structure.

MZ1 is in the PDB and in PROTAC-DB at once, and publishing wwPDB's version
redistributes wwPDB's data. `redact()` says exactly this in a comment written
long before I arrived: "What makes a record unpublishable is where the
chemistry came from, not how it happens to be written." I had read that
comment, quoted the half of it that supported the check I was building, and
missed that the other half ruled it out. A chemistry comparison flags every
molecule that appears in both and catches nothing a provenance check does
not: not a stronger test, a different and wrong one.

What survived from the wrong version is the part that was actually a finding:
that a verifier must not key on the same field as the thing it verifies.

**What the live bundle holds.** No `smiles` field anywhere: the 158-pair
campaign publishes its ligands by CCD code, so the guarantee holds by a
stronger route than redaction, and `redactions: 0` is the true answer rather
than a detection that stopped firing. The two tests that failed had encoded
the 100-pair benchmark bundle's assumption that chemistry is published and
therefore redacted. They now precondition on the bundle publishing a SMILES
at all and skip with the live figure quoted, which keeps their guard against
passing vacuously while not failing on a true state.

## F219. Boltz reuses its featurised input, so a corrected YAML corrects nothing

The end of F217's investigation, and the finding that matters.

`tools/rerun_pair.py` does two things: replace the YAMLs from a known-good
campaign, and drop the result rows so the jobs re-run. Its comments reason
carefully about the second depending on the first, and about what happens if
the YAML cannot be verified (F146). What neither it nor anything downstream
accounted for is that Boltz caches the featurised input under the job's own
output directory and reuses it when the job runs again.

So the correction: rewrote fifteen YAMLs correctly, dropped thirty state rows
and fifteen result rows correctly, re-ran fifteen jobs for 163 s each, wrote
fifteen fresh structures, and folded the hydroxyproline again from a cache
dated two days earlier. It reported success at every step, because every step
succeeded.

The proof is in `processed/structures/*.npz`, which carries a `residues`
record array with the CCD code of each residue as folded:

```
chain A    res_num= 140 first residue = ARG
chain B    res_num= 118 first residue = MET
chain C    res_num= 112 first residue = MET
chain P    res_num=  15 first residue = HYP      <- the YAML says PRO
chain L    res_num=   1 first residue = 759
```

**Why nothing caught it.** `nobble/validate/inputs.py:stale_inputs` compares a
YAML against the queue row that describes it, which answers "is the input on
disk the one we meant to run". The question that came apart from it is "is the
input on disk the one that was run", and no check asked it. `tests/
test_stale_inputs.py` began skipping with "the F47 correction has been
applied" on the strength of the YAML alone. The atlas built for the first time
in two days not because the defect was gone but because the guard had been
satisfied.

This is worse than F47 itself. F47 was a wrong input that every check
reported as wrong. This is the same wrong input with every check reporting it
as fixed, and it cost the GPU time of a correction to produce that state.

**Fixed in two places, because one of them is not enough.**

`tools/rerun_pair.py` now removes the whole output directory for each job it
clears, not just `processed/`: the structures under it were folded from the
input being removed, and leaving them lets the scorer read poses that no
longer correspond to any input on disk.

`tools/stale_featurisation.py` is the instrument, and it exists because the
fix above only helps the next correction. It reads each cached structure's
first residue per chain and compares it against what the YAML asks for at
position 1, both ways round: a modified residue folded where the YAML asks
for none is a cache predating the YAML, and an unmodified one where the YAML
asks for a modification would be Boltz dropping the block, which is the thing
F217 wrongly concluded and which this would have settled in a minute. Scoped
to position 1 rather than the whole sequence on purpose: resolving every
position of a `modifications` block against the cache means reimplementing
Boltz's tokenisation, which is a second thing to be wrong about, and spec
2.3's degron classes are N-terminal anyway.

`deploy/build_atlas.py` consults it after the YAML check and refuses, so the
state cannot read as publishable while the poses come from an input that is
no longer on disk.

**Still to do:** the correction has to be run again, now that it will take.
The GPU is on the chain's tier-2 stage, and this touches the main campaign's
bench02 results, which the chain has already passed, so it waits rather than
competing for the device. Until it runs, `bench02_BRD4_VHL`'s fifteen jobs in
`campaign_20261104T004632Z` hold poses folded with a hydroxyproline the
degron rule no longer asks for, the `KNOWN_DRIFT` allowlist entry in
`tests/test_cross_campaign_reproducibility.py` is correct and stays, and the
build refuses to publish the campaign.

## F220. Boltz read the modifications block all along, and groups chains by sequence alone

F217 left one question open: whether Boltz wanted the `modifications` block
somewhere else in its schema. It was recorded as needing the GPU. It did not.
The answer is in the parser, and reading it costs nothing while the device is
busy with tier 2.

`boltz/data/parse/schema.py:1166`:

```python
# Apply modifications
for mod in items[0][entity_type].get("modifications", []):
    code = mod["ccd"]
    idx = mod["position"] - 1  # 1-indexed
    seq[idx] = code
```

The block is read from inside the entity dict, as a list of `position` and
`ccd` pairs, one-indexed. That is exactly what `nobble/execute/yaml_gen.py`
emitted and what the fifteen `.bak` files still carry. So the declaration
always reached the parser, and the featurisation cache is the whole of F219's
cause rather than most of it. Nothing to change, and the open item is closed
without spending a GPU hour on it.

Reading the same function turned up something else. The grouping key, thirty
lines earlier at `schema.py:1036`, is:

```python
items_to_group.setdefault((entity_type, seq), []).append(item)
```

under a comment that reads "First group items that have the same type,
sequence and modifications". Modifications are not in the key, and the loop
above applies `items[0]`'s modifications to every chain in the group. Two
protein chains with an identical sequence and different `modifications` would
both be folded with the first chain's, silently, which is F219's failure mode
arriving by a different route: a declaration that every check reads off the
YAML and the model never sees.

It is not guarded, because it is not reachable. Of 4,340 YAML files across
every campaign on disk, none has a duplicated protein sequence: a ternary is
a receptor, an adaptor, a substrate and a peptide, and the scramble arm swaps
the peptide rather than duplicating it. A guard against a state the assembly
cannot produce is a test that cannot fail, which is the thing F218 and the
`or True` assertion both already cost a rewrite. Recorded here so that the
first campaign to fold a homodimer, or to modify one copy of a shared chain,
is read against it rather than discovering it a second time.

**What it changes for the pending correction:** only confidence. The corrected
`bench02_BRD4_VHL` YAML carries no `modifications` block at all, since F47's
rule no longer asks for the hydroxyproline, so the re-run needs the stale
cache cleared and nothing else. `nobble/execute/runner.py` removes the job's
output directory before each job and `tools/rerun_pair.py` removes it when it
drops the rows, so both routes now clear it.

## F221. The rehearsal left out the step that failed

`tools/rerun_pair.py` without `--apply` is how the F47 correction gets
checked before it spends 40 minutes of GPU time. It printed this:

```
bench02_BRD4_VHL: 15 job(s) in the queue
  30 row(s) in state.jsonl would be dropped
  15 YAML(s) would be regenerated
  rerun with --apply to do it
```

Two things are wrong with it, and both are versions of a mistake this session
has already made twice.

**It does not mention the cached featurised inputs.** That is the step whose
absence made the 6 November correction re-fold the hydroxyproline it was
correcting (F219), and the step added to fix it. A rehearsal that omits the
operation that failed rehearses a different operation, and reading this one
would have produced exactly the confidence that was misplaced the first time.
The `--apply` path removes fifteen directories and says so; the dry run, which
is the only one anybody reads before deciding, did not know they existed.

**It resolved no references, so it could promise a correction the real run
refuses.** `--apply` exits 2 without touching anything when any job has no
unambiguous known-good copy (F146), and under F145 that was every job on every
invocation. The dry run skipped the lookup entirely, so in precisely that case
it reported fifteen YAMLs regenerated and exited 0. The rehearsal and the run
disagreed about whether the operation was possible at all, and the rehearsal
was the optimistic one.

The lookup now happens before the `--apply` branch and both paths read the
same dictionary, so the dry run predicts the refusal and exits 2 with it.
`_belongs` is one predicate used by the rewrite and by the count that predicts
it, because two copies of that test are two things to keep in step. A
featurisation comparison that cannot be run prints as unknown rather than as
clean, which is F216 in a second file.

What it now reports, which is the measured state the pending correction starts
from:

```
bench02_BRD4_VHL: 15 job(s) in the queue
  0 of 15 YAML(s) differ from their known-good reference and would be
    rewritten; 15 already match
  30 row(s) would be dropped from state.jsonl
  15 row(s) would be dropped from results.jsonl
  1 row(s) would be dropped from scores.jsonl
  15 cached output directory/ies would be removed
  15 of those hold a featurisation that disagrees with the YAML today
```

So the 6 November run did correct the YAMLs, and the only thing left undone is
the cache. That is worth knowing before the re-run rather than after it: the
re-run is not a correction being made again, it is a correction being allowed
to take. Four mutations of the new behaviour were caught by the tests,
including the refusal exiting 0 and the unknown featurisation reading as
clean.

## F222. The status report promised a build that was refusing in the same report

Found by sweeping for printed assurances, which is what F218 was: a guarantee
announced rather than checked. One survivor, and it was live.

`bash tools/status.sh` prints `tools/provenance.py`, which is the file an
operator reads to decide whether to rebuild. It printed this:

```
   stale inputs  none; the atlas build has nothing to refuse
   superseded    no substrate differs from the current plan
   atlas         the rebuild refused: REFUSED: the cached featurisation does
                 not match the YAML for these jobs (F219)
```

Two lines apart, in one report, the opposite answers to one question.

The `stale inputs` line was computed from `inputs.stale_inputs`, which
compares the YAML against the queue row that describes it. The build has two
input checks, and the second compares the cached featurisation against the
YAML (F219). While both were failing on `bench02_BRD4_VHL` the line was true
by accident. Once the 6 November run corrected the fifteen YAMLs the first
check went clean and the second did not, and the line started asserting the
opposite of its own next paragraph. The claim was never scoped to what it
measured: "the atlas build has nothing to refuse" is a statement about the
build, made from one of the build's two checks.

It now consults both and names which found what, so the two lines agree. A
featurisation comparison that cannot be run prints as unknown rather than as
clean, because the direction this file errs in is the one that tells the
operator everything is fine.

The test checks the report against the featurisation rather than against a
fixed string, so it keeps working once the correction has run and the answer
flips. **Not covered:** the unknown branch. `provenance.py` resolves the
import from `tools/` at the head of `sys.path`, so a deliberately broken shim
cannot be injected without restructuring the script for the test's benefit,
which is a larger change than this fix warrants. The branch is reasoned, not
exercised, and this is the record of that.

## F223. The script run by hand against production was the untested one

`deploy/enable_gzip.sh` splices compression directives into the live nginx
vhost, as root. It is deliberately separate from `deploy.sh`, because certbot
owns lines in that file and regenerating it would take HTTPS off the site. A
direct ssh to the vhost is declined to me, so the script is written to be read
before Marc runs it.

Every other script here has tests. This one had none, and it is the one with
the highest cost of being wrong: the others can be re-run, and this one can
take the site off the air. "Written to be read" was carrying the whole of the
verification.

Read is weaker than run, and run was available all along. The remote half is a
self-contained heredoc; with the vhost path and the block path taken from the
environment it runs against a fixture with a fake `nginx` and `systemctl` on
PATH. Seven tests now hold it: the block lands after the anchor and before the
`location`, a second run is a no-op, nginx is reloaded once and only after a
passing `nginx -t`, a vhost with no anchor is refused and left byte-identical,
a configuration nginx rejects is restored and nothing is reloaded, the
original is kept, and the block under test is extracted from the script rather
than copied into the test, so it cannot pass against a splice the script no
longer performs. Four mutations were caught, including removing the restore
and removing the `nginx -t` gate.

Writing them found a real defect, though not one production would ever have
hit. The splice used `sed -i` with no suffix, which is a GNU extension: BSD
sed reads the next argument as the backup extension, so off Ubuntu it consumed
the script and failed with `invalid command code`. The droplet is Ubuntu, so
the script would have worked where it matters. The point is the other
direction: a splice that only runs on the target cannot be demonstrated
anywhere else, which is why it had no test and why "read it carefully" was the
plan.

It now writes a sibling and renames it, which is portable and is also the
right shape for the live web server's configuration: an in-place rewrite is a
window in which the file is half a vhost, and `mv` within a directory is
atomic. The same reasoning as `state.jsonl` in F109, arrived at from the
opposite direction.

**Unchanged:** F132 is still Marc's to run, since the ssh is not mine. What
changed is that reading it is no longer the only check on it.

## F224. The bundle on disk is one no current guard would produce

`deploy/atlas` holds the 158-pair bundle, 30 `bench02_BRD4_VHL` structures
among them, written at 2026-11-06T23:01:38Z by the chain's refresh stage. The
two guards that would now stop it landed after that:

```
23:01:38Z  the bundle was written
23:38:48Z  F218's provenance allow-list on published SMILES
00:27:48Z  the featurisation comparison the build refuses on (F219)
```

So the local bundle was built by code that had neither check, from a campaign
whose bench02 poses hold the hydroxyproline, and its build log says
`verified: no PROTAC-DB chemistry in the published bundle`, which is the
unconditional sentence F218 replaced. Nothing is wrong with the bundle that
was not already wrong with the campaign; the point is that it is on disk, it
looks like output, and a rebuild of it refuses.

**What keeps it off the site, checked rather than assumed.** Both gates were
run:

```
tools/publication_hold.py   exit 2   held by D-NOB-076
tools/atlas_drift.py        exit 1   the rebuild refused (F219)
```

`deploy/deploy.sh` asks the hold first, before it opens a connection, and asks
the drift gate at line 159, which is before the atlas rsync at line 170 and
not after it. Either one alone would stop the deploy. That ordering is the
thing worth having verified, because the code rsync does run first and a
reader skimming the script could reasonably think the atlas goes with it.

**Also checked:** both watchdogs are alive, one armed by `run_chain.sh` over
the whole queue and one by `tools/tier2.sh` over tier 2, each a `sleep 600`
parented to its own script, with no verdict in four and a half hours. An
armed watchdog that is not running is the same class of claim as a verified
build that was not verified, and `pgrep` for the module name finds nothing
either way, because between polls there is no Python process to find.

**A timezone slip, for the third time this session.** I read the two commit
times with `git log --date=format-local` and a literal `Z` in the format
string, which prints local time wearing a UTC label, and concluded the fixes
landed two hours before the chain's correction stage rather than two hours
after. The order mattered: it is the difference between "the chain ran the
corrected code and the correction still did not take", which would be a new
defect, and "the chain ran the old code", which is F219 behaving exactly as
recorded. `%ct` and an explicit conversion settle it. The rule that keeps
being relearned is that a timestamp should carry its own offset, not a letter
I appended.

## F225. The design scan rehearses clean, and my own budget figure was wrong

The design scan's inference half is recorded as unrehearsed and GPU-bound.
Its gate is not. `campaigns/design_20261104T094939Z` is assembled and has
never run: no `state.jsonl`, no results. Everything up to the inference call
was exercised against it, read-only:

```
tools/preflight.py        ok: true, 240 jobs, 16 pairs,
                          pairs_with_asymmetric_cofactor: 0
240 of 240 YAMLs          present
MSA paths referenced       1 distinct, present; 240 `msa: empty` for the
                           peptide chain, which is the expected shape
tokens                     124 to 144, median 144, against a 400 ceiling
```

So the one gate that can refuse 240 jobs passes, every input it names is on
disk, and nothing in the queue is near the token ceiling. What remains
unrehearsed is the runner call itself, which has run thousands of jobs on
three other campaign shapes. Worth knowing seventeen hours before the chain
reaches that stage rather than at it.

**And a correction to a number I gave.** I reported the chain projecting to
roughly 133 hours. It projects to 141.1, from the project's own instruments:

```
78.48  spent            budget.hours_spent(), 2,708 jobs
19.3   tier 2 left      77 jobs, each priced from its own tier-1 seconds
                        times the measured factor 4.614 (n=148)
 4.4   design scan      projected_hours, 240 jobs in 4 token bands
38.9   Tier B           measured, 1,540 jobs
```

Two errors, and both are F45 in miniature. The design scan was simply missing:
I had added tier 2 and Tier B to the spent figure and not the stage between
them. And I priced the tier-2 remainder at the flat median of finished jobs,
2.2370 s/token, giving 16.1 hours. Banded by job size it is 19.5, and the
instrument's own per-job method gives 19.3. The flat median underprices it
because the remaining mix is not the finished mix: 9 of the 148 finished
tier-2 jobs are 400 tokens or larger, against 21 of the 77 left, and large
jobs run at 2.9491 s/token against 2.2354 for the rest.

F45 is exactly this mistake, made by the code, found and fixed in the code.
`budget.tier2_projection` prices every job from its own measured tier-1 time
and is right. I reached past it for a one-line median and reproduced the bug
it was written to remove.

Nothing operational changes: G1 is defined against 240 hours and 141.1 leaves
about 99 spare. The figure was simply wrong when I said it.

**Minor, noted not fixed:** once any refinement has run, `scaling_range`
collapses to the measured factor, so `hours_low` and `hours_high` come back
identical and the projection's "as a range" is a point. That is the right
answer, since a measured factor beats a bounded one, but the two keys and the
docstring still say range.

## F226. The gate that refuses to spend a stage never said what it cost

`tools/preflight.py` opens with "before spending days of GPU on it". Every
caller's refusal is phrased the same way: `run_design.sh` prints "refusing to
spend 240 jobs on it", `run_chain.sh` "refusing to start a 52-hour run on it".
The report named the jobs, the pairs, the chain layouts and the cofactor
symmetry, and never the hours. The one quantity the refusal is about had to be
fetched from somewhere else, with whatever rate the reader had to hand.

Three times in two days that reader was me, and twice I got it wrong (F225).

It now prices the queue through `projected_hours`, which bands each job by its
own token count, and the projection never contributes to `ok`: Gate G1 is
decided by `budget.gate_g1` against `max_compute_hours`, and a preflight that
refused on cost would be a second, quieter gate with no decision recorded
against it. Five tests, including that a 4,000-job queue priced over 24 hours
still passes, and that a queue with no token counts comes back unpriced rather
than free.

**It disagrees with the record immediately.** Tier B is on file at 38.9 hours.
Preflight prices the same 1,540-job queue at 32.8. Both used the same
function; the 38.9 was taken on 5 November, before the throughput bands were
remeasured over the main campaign's 2,360 jobs, and the bands moved. 32.8 is
the better-founded figure: Tier B's median job is 198 tokens and the bands it
now falls in were measured over a distribution much closer to that than the
corrected campaign's 397.

**So last tick's correction was also wrong.** I replaced 133 hours with 141.1
and that figure mixed a tier-2 remainder priced minutes earlier with a Tier B
figure priced two days earlier. Every stage priced from the same instruments
at the same moment:

```
spent              78.48   budget.hours_spent(), 2,708 jobs
tier 2 left        19.28   77 jobs, each from its own tier-1 seconds
                           times the measured factor 4.614
design scan         4.40   preflight, banded
Tier B             32.80   preflight, banded
                 -------
total             134.96   of 240
```

The pattern across F225 and this one is not arithmetic. It is quoting a number
from where it was written down rather than from the thing that measures it, and
the fix is the same both times: put the measurement in the report that gets
read. Gate G1 stays closed with about 105 hours spare.

**Also verified this tick, since the 32.8 is about to be spent:** Tier B's
preflight is `ok: true` over 1,540 jobs and 154 pairs, 770 binary against 770
ternary, no asymmetric cofactor, all 1,540 YAMLs present, eleven distinct MSAs
all present and query-matched to their chains. Ten jobs sit at 410 tokens,
over the 400 cap, and all ten are `DCAF8L1_WD40`, one of the three declared
exceptions, which is why preflight passes them. I had written my own YAML and
MSA scan before running preflight, which already does both and checks the a3m
contents as well: the same habit as the budget figures, in the same tick.

## F227. The pose-recovery failure is two different failures, and the split is per pair

Pose recovery reports 0 of 65 poses within 3 A and a median of 17.54 A (F212),
and refinement sharpens without recovering (F215). One RMSD cannot say whether
the model never found the degron site or found it and laid the chain along it
in the wrong register, and the headline reads differently in each case.

`tools/pose_site.py` asks the question the RMSD cannot. It superposes on the
receptor exactly as `poses.recovery_against_crystal` does, then compares
footprints: which receptor residues the deposited degron window touches, which
the predicted peptide touches, and how many of the window's own fifteen
residues the prediction lands on. The window is resolved through
`peptide_start_res` and `substrate_frame.to_deposited`, not from the whole
substrate chain, which for CSNK1A1 and GSPT1 is a domain rather than a degron.
Contacts at 4.5 A, from `contact_cutoff_a` in `config/thresholds.toml`.

Over all 65 poses, not the best one per pair:

```
pair                      n   window 15/15   any contact   jaccard   rmsd
bench04_IKZF1_CRBN       10         10/10         10/10     0.909    5.35
bench06_RBM39_DCAF15     10          7/10         10/10     0.533    6.04
bench05_CSNK1A1_CRBN     10          0/10         10/10     0.500   12.21
bench01_GSPT1_CRBN       10          0/10          0/10     0.022   29.14
bench07_CDK12_DDB1       10          0/10          0/10     0.000   44.66
bench02_BRD4_VHL         10          0/10          9/10     0.182   18.20   confounded
bench03_BRD4_CRBN         5          0/5           2/5      0.000   20.40   not measurable
```

jaccard and rmsd are medians over the pair's poses.

**Three of the five measurable pairs put the degron on its own footprint, in
every one of ten poses.** bench04 touches all fifteen window residues in all
ten and shares ten of eleven receptor contacts. bench06 touches all fifteen in
seven of ten and some in all ten. bench05 touches some in all ten and shares
thirteen of fifteen receptor contacts at its best. Their median RMSDs are
5.35, 6.04 and 12.21 A: the site is right and the backbone is placed along it
wrongly.

**Two put it on a different surface of the same protein, in every one of ten
poses.** bench01 and bench07 touch none of the fifteen window residues in any
pose, share two and zero receptor contacts, and sit 22 and 43 A from the
window's centroid. They contact the receptor chain heavily, 59 residues each,
so the peptide is bound, just not there.

**There is no pair where some seeds find the site and others do not.** The
split is a property of the pair, which is why the every-pose check was worth
running: on the best pose per pair alone, three pairs agreeing could have been
one seed in ten agreeing three times.

**What this changes and what it does not.** It does not rescue the control:
nothing reaches 3 A, bench04's best pose is 4.99 A, and the matched-control
ROC is still a null at AUC 0.4583. It does mean "the poses are in the wrong
place" was too coarse a reading of the failure. For three of five measurable
pairs the model identifies the correct degron footprint reliably and misplaces
the backbone by 5 to 12 A. That is a different negative result, and whether it
re-scopes the headline is a G6 decision for Marc rather than one this records.

**Two pairs are excluded and both for stated reasons.** bench03's deposited
window makes no contact with CRBN at all within the cutoff: it sits on BRD4
against the glue, so its overlap is zero whatever the pose, and the tool says
`not_measurable` rather than printing a 0.0 beside bench07's measured 0.0.
bench02's poses came from a superseded input (F219), so its 9 of 10 window
contacts and 0.182 median are not a measurement of the current input; the
correction may make it a fourth measurable pair.

**No verdict and no new threshold.** Printing "right site" above some Jaccard
would be inventing an acceptance cutoff to decide a failed positive control,
which is exactly what D-NOB-076 refused to do for pose recovery. The numbers
are reported and the reading is in this paragraph, where it can be argued with.
A test enforces that structurally through `ast`, after its first version
failed on the docstring explaining the absence it was checking for.

## F228. Neither mechanism explains the register, and the error is at the window's ends

F227 left the three site-finding pairs at 5 to 12 A with the site correct.
Two mechanisms would explain that, and both are testable in the frame the RMSD
already uses: the chain threaded backwards, or offset along the groove.

Neither holds. Comparing predicted residue i against deposited residue i+k for
k from -7 to +7, and against the reversed mapping, on each pair's best pose:

```
pair                      as-is   best k   at k   reversed
bench04_IKZF1_CRBN         5.06        0   5.06      10.34
bench06_RBM39_DCAF15       5.50        0   5.50      12.49
bench05_CSNK1A1_CRBN      11.64       -2  10.04       9.97
bench01_GSPT1_CRBN        24.68       +4  24.14      25.00
bench07_CDK12_DDB1        44.32       +7  36.41      46.87
```

No pair is reversed: the reversed mapping is worse everywhere except bench05,
where it is better by 1.67 A, which is noise rather than a reversal signature.
And for both pairs that find the footprint cleanly the optimal shift is already
zero, so the register is not off either. The improvements at non-zero k for
bench01 and bench07 are one or eight angstrom on twenty-four and forty-four:
sliding along a groove you are not in.

**So the error is conformational, and the per-residue profile says where.**
Median CA deviation along the fifteen-residue window, over all ten poses of
each pair, N to C:

```
bench04_IKZF1_CRBN     8.3  5.9  3.6  2.2  1.8  1.4  0.8  0.5  0.5  2.1  2.7  2.9  4.2 10.4 10.8
bench06_RBM39_DCAF15   3.0  3.3  4.1  3.5  1.9  2.5  3.2  2.6  1.4  1.1  2.9  7.7 13.5 12.4  7.1
bench05_CSNK1A1_CRBN  19.9 12.8  7.8  0.7  5.0  9.5 10.2  9.8  7.5  2.2  3.3  9.1 13.6 19.0 23.8
bench01_GSPT1_CRBN    33.9 28.7 24.3 21.5 17.1 17.3 19.2 18.6 24.7 27.5 29.5 33.9 37.1 40.8 41.8
bench07_CDK12_DDB1    40.6 41.3 45.6 45.8 47.8 46.8 46.5 46.8 47.2 46.3 46.9 44.3 44.9 43.3 41.7
```

bench04 places its three central residues at 0.5 to 0.8 A and nine of fifteen
within 4.2 A, with the error at positions 1 to 2 and 14 to 15. bench06 places
eleven of fifteen within 4.1 A, its core at 1.1 to 1.4 A, with the error at 12
to 14. The worst pose of each pair differs from the median by under 1.5 A at
every position, so this is not one lucky seed: the predictions are very nearly
deterministic, which is consistent with the bit-identical ipTM values F217
mistook for a dropped declaration.

bench05 pins position 4 at 0.7 A and positions 10 to 11 at 2 to 3 A and is
wrong in between, which is not the same pattern. bench01 and bench07 are
uniformly 17 to 48 A: nowhere near, as F227 said.

**What this licenses, and what it does not.** Spec 5.1 defines pose recovery
as backbone RMSD over the fifteen-residue window, and by that definition the
control fails: bench04's best pose is 4.99 A and nothing reaches 3 A. The
profile does not change that. What it shows is where the 4.99 comes from.

> **The cause proposed here was wrong, and F229 has the number that refutes
> it.** The paragraph below read: the window is cut around the degron, and its
> terminal residues are held in place in the deposited structure by the rest
> of the parent protein, which the prediction does not contain, so residues
> that are only ordered because of a domain outside the input are carrying the
> RMSD. It is a tidy story and it is not what the structures say. Contacts
> between each window residue and the substrate chain outside the window
> correlate with the deviation at r = +0.076 for bench04 and +0.092 for
> bench06: no relationship at all. Kept rather than deleted, because asserting
> a mechanism and then testing it is the only reason it was caught, and
> because this is the third explanation this session that fitted the
> observation and failed its own check (F217, F218).

**I am not redefining the metric.** Reporting a core RMSD and calling the
control passed would be inventing an acceptance criterion after seeing the
data, which is precisely what D-NOB-076 refused when it declined to invent a
success radius. Whether spec 5.1's window is the right definition is a
specification question, and it belongs to Marc at G6 along with everything
else the gate holds. What is recorded here is that two of five measurable
pairs place the degron's central residues within 1 A of the deposition in
every pose, and that the whole-window number does not show it.

`tools/pose_site.py` carries the profile as `ca_deviation_a`, one value per
peptide residue, so the claim is re-runnable rather than a figure in a note.

## F229. The parent domain does not hold the window's ends, and the occupancy alarm was mine

F228 explained its own profile: the window's terminal residues deviate because
the deposition holds them with the rest of the parent protein, which the
prediction does not contain. The explanation is testable on the deposited
structure alone. If it is right, the window residues with the largest CA
deviation are the ones making the most contact with substrate-chain residues
outside the window.

```
bench04_IKZF1_CRBN  (6H0F chain C)
  CA dev     8.3   5.9   3.6   2.2   1.8   1.4   0.8   0.5   0.5   2.1   2.7   2.9   4.2  10.4  10.8
  parent       2     2     3     5     1     3     3     0     3     1     4     5     4     3     3
  pearson r = +0.076

bench06_RBM39_DCAF15  (6Q0W chain D)
  CA dev     3.0   3.3   4.1   3.5   1.9   2.5   3.2   2.6   1.4   1.1   2.9   7.7  13.5  12.4   7.1
  parent       6     3     3     1     2     4     2     0     2     8     1     0     6     3     3
  pearson r = +0.092
```

No relationship. bench04's three worst positions make two or three parent
contacts each, while its best-placed residue makes none and a 2.9 A position
makes five. The explanation is refuted for both pairs it was proposed about.
bench05, whose profile F228 already called a different pattern, does correlate
at r = +0.617, which is a hint about bench05 and not a rescue of the claim.

**A partial correlate, offered as that and nothing more.** Deviation against
the deposited residue's mean B-factor: r = +0.328 for bench04 and +0.566 for
bench06, whose window runs 96 to 129 square angstrom with its highest values
at exactly the fraying positions. So for bench06 the reference is least certain
roughly where the prediction is judged most wrong. For bench04, at r = +0.33
over fifteen points, that is not an explanation.

What remains for bench04 is the plain reading: a free fifteen-mer's termini
have nothing to place them, and the model puts them somewhere plausible and
wrong while holding the centre at 0.5 A. That is a statement about the
prediction rather than the reference, and these data cannot test it. It is left
as the candidate, not written up as the cause, which is what F228 should have
done with its own.

**And an alarm I raised and then withdrew.** Reading occupancies, I took the
minimum over each residue's heavy atoms and found 0.00 at every window residue
of 6H0F chain C, which would have meant the bench04 control was measured
against unsupported coordinates. The raw file says chain C carries 248 atoms at
1.00 and 237 at 0.00, so a single zero-occupancy atom anywhere in a residue
zeroed the whole residue's minimum. Every window residue's CA is at occupancy
1.00 and no window residue has any zero-occupancy heavy atom: the zeros are
elsewhere in the chain. The reference is sound and the statistic was wrong,
which is the same error as F225's flat median, one aggregate standing in for a
different question.

## F230. Every benchmark window is held mostly by its own protein, and two almost entirely

The question was whether each pair's nominal receptor is the chain the
deposited degron actually binds, since bench07's window touches only five
receptor residues (F227). It is: excluding the substrate chain, the top
contact partner is the nominal receptor for all seven pairs. The assignments
are right and that was worth confirming rather than assuming.

The first version of the check said the opposite about all seven, which is how
a flag that fires on everything usually reads. It excluded only the window
residues from the substrate chain, so each window's own sequence neighbours
dominated its count and the "top partner" was always the substrate chain
itself. Intra-chain neighbours are not a binding partner.

Separating them is the useful answer:

```
pair                     own chain   receptor   other
bench01_GSPT1_CRBN              11         11   none
bench02_BRD4_VHL                12          7   none
bench03_BRD4_CRBN               32          0   none
bench04_IKZF1_CRBN              17         10   none
bench05_CSNK1A1_CRBN            35         15   none
bench06_RBM39_DCAF15            23         13   C:9
bench07_CDK12_DDB1              48          5   C:3
```

Residues in contact with the fifteen-residue window at 4.5 A, counted on the
window's own chain outside the window, on the nominal receptor, and elsewhere.

**Every window is held more by its own protein than by the receptor**, bench01
excepted at eleven apiece. For bench03 it is thirty-two to nothing and for
bench07 forty-eight to five: those windows are embedded in BRD4 and CDK12, not
presented to CRBN and DDB1. bench04 and bench06, at seventeen to ten and
twenty-three to thirteen, are the most receptor-facing of the seven, and they
are also the two the model places best, core at 0.5 to 1.4 A.

**That last sentence is an observation and not an explanation, deliberately.**
Across the seven pairs the relation is not monotonic in either variable:
bench01 has the lowest own-chain count of all, eleven, and a median RMSD of
29.14 A. With five measurable pairs and no clean dependence, fitting a story to
the ordering is how F228 went wrong one finding ago. What is recorded is the
descriptive fact.

It is also a different claim from F228's, which F229 refuted, and the
difference matters. F228 said that within bench04 and bench06 the per-residue
deviation tracks each residue's contact with the parent chain outside the
window; that is false, at r = +0.08 and +0.09. This says that across pairs,
some windows are overwhelmingly intramolecular. The second does not rescue the
first.

**What it bears on.** Spec 5.1 measures pose recovery over all seven pairs
equally. Two of them, bench03 and bench07, are windows whose deposited
conformation is maintained by the rest of their own protein with little or no
receptor contact, and the prediction folds a free fifteen-mer. Whether such a
window is a pose-recovery target at all is a panel-composition question, and it
goes to G6 with the rest: "0 of 65 poses within 3 A" is computed over a panel
that includes two targets of that kind, and bench03 is already excluded from
the footprint comparison for the same reason (F227).

## F231. The ROC null is not a seed-collapse artefact

D-NOB-081 found the design scan's parent being chosen by one collapsed binary
seed, which makes an obvious question about the headline: the matched-control
ROC uses the same statistic, so is its null an artefact of the same thing.

It is not. The layer takes the statistic as a parameter, so the check runs on
the same matched rows rather than dropping any, which would break the
matching:

```
statistic            auc      positives   matched negatives   reading
delta_iptm        0.4583             24                  96   not distinguishable
                                                              from chance at 95%
delta_iptm_median 0.4147             24                  96   the same
```

The collapse-robust companion is slightly worse, not better, and both readings
are the layer's own. `non_finite_dropped` is zero in both, and the seed balance
reads "every pair on both sides contributed 10 ternary and 5 binary seeds", so
neither the denominator nor the seed counts move between them.

Why it barely moves: 21 of the arm's 120 rows carry
`seed_collapse_affects_delta`, 4 of the 24 positives and 17 of the 96
negatives. That is 16.7 per cent against 17.7 per cent, so the collapse falls
on both sides alike. The layer already guards the related failure, a seed-count
imbalance between the arms, and names it in the summary; this is the same
concern for seeds that ran and collapsed rather than seeds that never
finished, and it comes out even.

**Recorded because it is a negative.** The temptation with a result like
D-NOB-081 is to look for the same defect behind the headline, and if the AUC
had moved to 0.6 on the robust statistic that would be the most important
number in the project. It moved to 0.41. The null stands, the pose-recovery
failure (F212) that makes it uninterpretable stands, and nothing about G6
changes.

## F232. Four aggregates in one session, each hiding the thing it was asked about

Job 14 of the tier-2 queue passed its projection, so I checked whether it was
computing. `ps -eo ... | awk '$5+0 > 20'` returned no NOBBLE process at all,
only Time Machine, iCloud's `fileproviderd` and Spotlight, and the runner
itself showed 0.13 seconds of CPU over five and a half hours. That reads as a
dead job.

It is not. The Boltz process is pid 52096, a child of the runner, 65 minutes
elapsed with 7 minutes 44 seconds of CPU at 12.6 per cent. The runner sleeps
while its child works, and an MPS job is meant to sit low on CPU because the
work is on the GPU. My filter cut at 20 per cent and excluded the only process
that mattered.

**That is the fourth time in this session.** The others:

* `min()` over a residue's heavy-atom occupancies made every window residue of
  6H0F chain C read 0.00, which looked like a control measured against
  unsupported coordinates. Every window CA is at 1.00; the zeros are elsewhere
  in the chain (F229).
* a flat median seconds-per-token underpriced the tier-2 remainder by three
  hours, because the remaining job mix is larger than the finished mix (F225).
  That is F45, which the code had already fixed and `thresholds.toml` already
  explains in words beside `token_bands`.
* counting contacts while excluding only the window's own residues made every
  pair's top binding partner its own chain, so a check of receptor assignment
  flagged all seven as wrong (F230).

One shape, four times: a convenient aggregate or filter standing in for the
question, and the error always in the direction of a confident wrong answer
rather than a visible gap. The occupancy one and this one both read as alarms;
the budget one read as reassurance; the contacts one read as a panel-wide
defect.

The rule that would have caught all four, written down because apparently
knowing it is not enough: **before concluding absence, print what the filter
excluded.** `min` over a set that may be heterogeneous, a median over a
distribution that differs from the one being projected, a threshold on a
quantity whose scale is not understood, and an exclusion that leaves the
dominant term in: in each case one line showing the discarded rows would have
ended it.

Nothing is wrong with the chain. Job 14 is a 1,223-token job, the largest in
the tier-2 queue, and the watchdog reports it as running and not overdue,
which was the correct answer throughout.

## F233. The pair missing from the G6 refinement table is the one whose jobs are too large to have ever run

Tier-2 job 14 showed a Boltz child of 84 minutes replaced by a fresh one of
nine, with no `done` line in the chain log between them. The runner does one
retry per job, and a timeout is explicitly not retried, so attempt 1 did not
overrun: it crashed, and attempt 2 is running.

What makes that worth more than a note is the size. Of the 149 tier-2 jobs
that have finished, the largest is 454 tokens. Job 14 is 1,223.

```
pair                        queued   done   tokens
bench01_GSPT1_CRBN              10     10      155
bench02_BRD4_VHL                10     10      454
bench03_BRD4_CRBN                5      5      173
bench04_IKZF1_CRBN              10     10      144
bench05_CSNK1A1_CRBN            10     10      143
bench06_RBM39_DCAF15            10      0     1223
bench07_CDK12_DDB1              10     10      357
```

Every benchmark pair between 143 and 454 tokens finished every queued job.
`bench06_RBM39_DCAF15` has finished none of ten, and it is the only one above
454. The construct is `DCAF15_DDB1_DDA1`, 1,223 tokens by construction and one
of the three declared token-cap exceptions, so this is the largest thing in the
project.

**So the gap in the G6 table has a cause, and it is not a confound.** The
refinement table reports five pairs. bench02 is excluded because its tier-1
poses came from a superseded input (F219). bench06 is absent because its
tier-2 jobs have never completed, which until now read as "the queue has not
reached it". It had reached it; the jobs do not finish.

**What it costs if it holds.** Ten of the 76 remaining tier-2 jobs are these,
all bench06. At two attempts of roughly 84 minutes each that is about 28
hours producing nothing, against 19.3 hours for the whole remainder as priced.
The other 66 are at proven sizes.

That 28 hours is the likely case and not the worst one. The queue row carries
`timeout_seconds: 39000`, overriding the tier-2 default of 21,600, and the
budget is per job rather than per attempt (F100), so one of these jobs may
spend up to 10.8 hours across its two attempts before being recorded as
failed. Ten of them at the full budget is 108 hours, which against 78.5 spent
and 37.2 for the design scan and Tier B would reach the 240-hour ceiling that
Gate G1 is defined against. The likely case leaves the projection at about
151 hours; the worst case is a G1 question.

The automatic scope reduction available is to drop bench06 from tier 2, which
costs one pair's refinement and is the pair whose refinement is most worth
seeing. That is why this waits for the error rather than being decided on the
arithmetic.

**What it costs scientifically.** More than the hours. bench06 is one of the
three pairs that put the degron on its own footprint in every one of ten
poses, at contact Jaccard 0.533 with eleven of fifteen window residues within
4.1 A (F227, F228). Of the pairs whose site is right, it is the one whose
refinement would be most worth seeing, and it is the one that cannot run.

**Not decided here.** Attempt 1 crashing once is not proof that the size
cannot run: its stderr is held in memory until the job resolves and the output
directory it left was recreated, so the reason is not yet readable. Attempt 2
will write a results row carrying the detail. If it fails, the question is
whether to drop bench06 from tier 2 and record the refinement table as five of
seven for a stated reason, or to reduce its sampling so the job fits. Both are
scope decisions and both want the error message first.

## F234. The stall detector's bound was twice the runner's, and two errors were cancelling

The watchdog's `stalled` verdict is the one that matters, and its docstring
says why: the bound is "derived from the runner rather than configured, so it
cannot drift away from the behaviour it describes". It had drifted, twice, in
opposite directions.

**It multiplied by attempts.** The bound was
`job_timeout_seconds * (RETRIES + 1) + kill grace + margin`. That was the
runner's arithmetic until F100 made the budget cover the job rather than each
attempt: `remaining = budget - elapsed`, so two attempts share one allowance
and the runner cannot hold a job past `budget` plus the kill grace.
Multiplying made the bound twice what the runner can allow, 11,520 seconds
against 6,120 at tier 1 and 43,920 against 22,320 at tier 2. A genuinely hung
runner went uncalled for an extra hour and a half, or six.

Pinned in two places and described in a third:
`test_the_bound_comes_from_the_runner_not_from_a_constant` asserted the bound
exceeded `job_timeout_seconds * (RETRIES + 1) + KILL_GRACE_SECONDS`, so the
stale model had a test defending it, and the docstring said "once per attempt"
throughout. F100 changed the runner and left all three.

**It read the tier default, not the job's own timeout.** The runner reads
`job.get("timeout_seconds") or settings[...]`. The main campaign's tier-2 rows
carry 39,000 seconds against a tier default of 21,600, so a bound from the
default alone would call such a job stalled at 22,320 while the runner was
still inside its allowance.

**The two cancelled.** 21,600 doubled is 43,920 with the margin, comfortably
above 39,000, so no queue on disk could produce a false stall today: measured
across every queue, zero. That is why this survived. The bound was wrong in
both directions at once and right by accident, which is worse than being
wrong, because the arithmetic that saved it is not the arithmetic anyone
intended.

Both fixed. The bound is now the job's own budget plus the kill grace plus the
margin, taken per running job: 6,120 at tier 1, 22,320 at tier 2, and 39,720
for the bench06 job that carries the override. The test that pinned the old
model now asserts the new one and also that the bound cannot reach a second
attempt's worth, which is the property that went missing.

Worth saying plainly: this is the instrument I have quoted all session as
saying the chain is healthy. Its `overdue` reading, which is the one I was
actually relying on, never depended on this bound, and the live job sits at
about 5,800 seconds against 39,720 either way. But I was reading a detector
whose headline verdict was calibrated to a runner that changed five findings
ago.

## F235. The overdue yardstick divided by tokens and called that size-corrected

`stall_report`'s comment says the yardstick is "the campaign's own completed
work, per token, so a large job is not called overdue for being large".
Dividing by tokens removes the linear part of the cost and leaves the rest,
and the rest is not small: on this campaign's tier 2, jobs of 400 tokens or
more run at 2.953 s/token against 2.237 for the others.

So a 1,223-token job was "expected" at 2,736 seconds and overdue at three
times that, 8,208. bench06's first attempt ran about 5,040 seconds
legitimately before crashing, and with its retry the job passes 8,208 while
doing exactly what it should. The verdict was about to be wrong on the only
job in the campaign that has ever needed a retry.

This is F45 and F225 for the third time, and `thresholds.toml` already states
it in words beside `token_bands`, which `projected_hours` already uses.

**Two fixes, in order of preference.**

The rate is now banded by the job's own token band, same bands and same
config, so there is one definition of a job size in the project rather than
two. Where a band has no finished job the campaign-wide median is used and
the entry records `rate_basis` saying no rate was measured at this size,
because a yardstick borrowed from another size is the thing being corrected.

Better than any rate, for tier 2: the job's own tier-1 time times the
refinement factor this campaign measured. A tier-2 job is the same input at
different settings, so its tier-1 time measures that molecule rather than
jobs its size. For bench06 that is 902 seconds times 4.614, giving 4,162
against an attempt that really ran about 5,040. The flat median was 46 per
cent under; this is 21 per cent under, and it moves the overdue line from
8,208 to 12,486, which the retried job does not cross.

**A near miss while fixing it.** The first version looked up `TIER2_SUFFIX`
on `runner` behind a `hasattr` guard. It lives on `budget`, so the guard was
always false, the lookup would have compared tier-2 job ids against tier-1
records, found nothing, and fallen back silently to the rate it was
replacing. The correction would have reported itself as working and changed
nothing, which is F218's shape, and it is the fifth time this session that a
convenient shortcut hid its own subject. Caught by printing the resolved
yardstick for the live job rather than trusting that the branch was taken,
which is the F232 rule applied to my own fix.
