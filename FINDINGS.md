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
