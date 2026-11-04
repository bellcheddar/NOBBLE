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
