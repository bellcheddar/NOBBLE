"""PLIP interaction fingerprints (spec 4.6).

The conversion is done by `cif2plip.py`, reused from the portfolio rather than
reimplemented (D-NOB-007). It already carries the fix spec 4.6 insists on: after
`pdb_tidy`, every ATOM/HETATM/TER serial is renumbered contiguously, because
pdb_tidy leaves a one-number gap at each chain/TER boundary and OpenBabel maps
CONECT serials **positionally**. A gap shifts that map, every CONECT record past
it is silently discarded, and the ligand is then perceived from interatomic
distances instead of its bond table. The result is not an error: it is a
plausible-looking fingerprint with wrong, sometimes invented, interactions.

Spec's Phase 3 gate is explicit that this must be asserted on every structure
and not sample-checked, so `conect_integrity` below runs on each converted PDB
and a failure marks that fingerprint unusable rather than letting it through.
"""
from __future__ import annotations

import csv
import re
import subprocess
from dataclasses import asdict, dataclass, field
from pathlib import Path

from nobble import paths

CIF2PLIP = paths.BOLTZMAKER / ".plip_env" / "cif2plip" / "cif2plip.py"

# NOBBLE's own chain identifiers, before cif2plip renumbers them.
PEPTIDE_SOURCE_CHAIN = "P"
LIGAND_SOURCE_CHAIN = "L"

# Canonical degron contact patterns per E3 class (spec 4.6). These are the
# interaction types and receptor features a real degron of that class makes, used
# as the reference fingerprint the prediction is compared against.
CANONICAL_FINGERPRINTS = {
    "CRBN": {
        "description": (
            "Degron glycine packs into the tri-tryptophan pocket (W380, W386, "
            "W400) with the IMiD glutarimide hydrogen bonding to H378 and W380"
        ),
        "receptor_residues": ["TRP380", "TRP386", "TRP400", "HIS378", "PHE402"],
        "expected_types": ["hydrophobic", "hbond", "pistacking"],
    },
    "VHL": {
        "description": (
            "Hydroxyproline hydrogen-bond network to S111 and H115, with Y98 "
            "stacking: the modification is the recognition element"
        ),
        "receptor_residues": ["SER111", "HIS115", "TYR98", "TRP88"],
        "expected_types": ["hbond", "hydrophobic"],
    },
    "DCAF15": {
        "description": "Aryl sulfonamide wedged between DCAF15 and the RBM39 RRM2 surface",
        "receptor_residues": [],
        "expected_types": ["hydrophobic", "hbond", "saltbridge"],
    },
    "DDB1": {
        "description": "Glue binds the BPC propeller face directly, no substrate receptor",
        "receptor_residues": [],
        "expected_types": ["hydrophobic", "hbond"],
    },
}


@dataclass
class ConectCheck:
    """Whether the converted PDB's serials and CONECT records are coherent."""

    pdb_path: str
    serials_contiguous: bool
    first_serial: int | None
    last_serial: int | None
    atom_count: int
    conect_records: int
    dangling_conect_serials: list[int] = field(default_factory=list)
    gaps: list[int] = field(default_factory=list)
    passes: bool = False
    detail: str = ""

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass
class Fingerprint:
    job_id: str
    status: str
    interactions: list[dict] = field(default_factory=list)
    interaction_types: dict = field(default_factory=dict)
    receptor_contacts: list[str] = field(default_factory=list)
    peptide_contacts: list[str] = field(default_factory=list)
    canonical_e3: str | None = None
    canonical_matched: list[str] = field(default_factory=list)
    canonical_missing: list[str] = field(default_factory=list)
    conect: dict | None = None
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)


def conect_integrity(pdb_path: Path) -> ConectCheck:
    """Assert contiguous serials and resolvable CONECT references.

    Two independent failures are caught. A gap in the serial sequence is the one
    spec 4.6 names, and it is what silently truncates OpenBabel's CONECT map. A
    CONECT record referring to a serial that no atom carries is the second, and
    it would mean the bond table and the coordinates disagree outright.
    """
    # The sequence must include TER records. `renumber_contiguous` assigns each
    # TER its own serial, so a file with three chains has two TER serials sitting
    # between the atom serials. Collecting only ATOM and HETATM therefore shows
    # one apparent gap per chain boundary even on a correctly renumbered file:
    # the first version of this check reported exactly that, two "gaps" at 854
    # and 970 for an A/P/L complex, and would have rejected every structure the
    # fix had just repaired.
    sequence: list[int] = []        # ATOM, HETATM and TER, in file order
    atom_serials: set[int] = set()  # ATOM and HETATM only, for CONECT resolution
    conect_targets: list[int] = []
    conect_records = 0

    for line in pdb_path.read_text(errors="replace").splitlines():
        record = line[:6]
        if record in ("ATOM  ", "HETATM"):
            try:
                serial = int(line[6:11])
            except ValueError:
                continue
            sequence.append(serial)
            atom_serials.add(serial)
        elif record.startswith("TER"):
            field_text = line[6:11].strip()
            if field_text:
                try:
                    sequence.append(int(field_text))
                except ValueError:
                    pass
        elif record == "CONECT":
            conect_records += 1
            for start in range(6, min(len(line), 31), 5):
                field_text = line[start : start + 5].strip()
                if field_text:
                    try:
                        conect_targets.append(int(field_text))
                    except ValueError:
                        continue

    check = ConectCheck(
        pdb_path=str(pdb_path),
        serials_contiguous=False,
        first_serial=sequence[0] if sequence else None,
        last_serial=sequence[-1] if sequence else None,
        atom_count=len(atom_serials),
        conect_records=conect_records,
    )
    if not sequence:
        check.detail = "no ATOM or HETATM records"
        return check

    expected = list(range(sequence[0], sequence[0] + len(sequence)))
    gaps = [
        previous + 1
        for previous, current in zip(sequence, sequence[1:])
        if current != previous + 1
    ]
    check.gaps = gaps[:20]
    check.serials_contiguous = sequence == expected
    check.dangling_conect_serials = sorted(
        {target for target in conect_targets if target not in atom_serials}
    )[:20]

    if not check.serials_contiguous:
        check.detail = (
            f"serial sequence has {len(gaps)} discontinuity(ies) starting at "
            f"{gaps[0] if gaps else '?'}: OpenBabel would discard CONECT records "
            "past the first gap and perceive the ligand from distances instead"
        )
    elif check.dangling_conect_serials:
        check.detail = (
            f"{len(check.dangling_conect_serials)} CONECT serial(s) reference no "
            "atom in the file"
        )
    else:
        check.passes = True
        check.detail = (
            f"{len(sequence)} contiguous serials across atoms and TER records, "
            f"{len(atom_serials)} atoms, {conect_records} CONECT records, all "
            "references resolvable"
        )
    return check


def _parse_interactions(csv_path: Path) -> list[dict]:
    with csv_path.open(newline="") as handle:
        return list(csv.DictReader(handle))


def fingerprint(job: dict, workdir: Path | None = None) -> Fingerprint:
    """Convert one predicted ternary and build its interaction fingerprint."""
    result = Fingerprint(job_id=job["job_id"], status="pending")
    structure = job.get("structure")
    if not structure or not Path(structure).exists():
        result.status = "failed: no predicted structure"
        return result
    if job.get("complex_type") != "ternary":
        result.status = "skipped: binary complex carries no ligand to fingerprint"
        return result
    if not CIF2PLIP.exists():
        result.status = f"failed: cif2plip not found at {CIF2PLIP}"
        return result

    # Absolute, because the subprocess below runs with cwd set to cif2plip's
    # own directory so its sibling imports resolve. A relative structure path
    # then resolves against *that* directory: with the campaign given as
    # "campaigns/corrected_..." every conversion failed with
    # FileNotFoundError on
    # ".plip_env/cif2plip/campaigns/corrected_.../outputs/...". The benchmark
    # campaign happened to be run with an absolute campaign path and worked,
    # which is why this survived a whole campaign's scoring (F32).
    structure_path = Path(structure).resolve()
    target = (workdir or (structure_path.parent / "plip")).resolve()
    target.mkdir(parents=True, exist_ok=True)

    completed = subprocess.run(
        [str(paths.PY_BOLTZ), str(CIF2PLIP), str(structure_path),
         "-o", str(target)],
        capture_output=True, text=True, timeout=1800,
        # pdb_tidy and pdb_validate are console scripts found via PATH, so the
        # environment's bin has to be on it: without that the script fails at
        # step 3 and leaves a PDB with the serial gaps still in it, which then
        # trips the CONECT assertion below for the wrong reason.
        env=paths.tool_env(paths.BOLTZMAKER),
        # Run from the script's own directory so its sibling imports resolve.
        cwd=str(CIF2PLIP.parent),
    )

    stem = structure_path.stem
    converted = target / f"{stem}.pdb"
    if converted.exists():
        check = conect_integrity(converted)
        result.conect = check.to_dict()
        if not check.passes:
            result.status = f"failed: CONECT integrity, {check.detail}"
            return result

    if completed.returncode != 0:
        tail = (completed.stderr or completed.stdout or "").strip().splitlines()[-3:]
        result.status = "failed: cif2plip exit " + str(completed.returncode)
        result.notes.extend(tail)
        return result

    interactions_csv = target / f"{stem}_interactions.csv"
    if not interactions_csv.exists():
        result.status = "failed: no interactions CSV produced"
        return result

    rows = _parse_interactions(interactions_csv)
    result.interactions = rows

    # cif2plip renumbers chains to strict single-letter PDB identifiers in order,
    # so NOBBLE's A.. / P / L become A, B, C. The mapping is printed by the
    # script and parsed here rather than assumed, because assuming it would
    # attribute every peptide contact to the receptor.
    chain_map = {}
    match = re.search(r"chain map\s*:\s*(\{[^}]*\})", completed.stdout or "")
    if match:
        try:
            chain_map = dict(
                (key.strip().strip("'\""), value.strip().strip("'\""))
                for key, value in (
                    pair.split(":") for pair in match.group(1).strip("{}").split(",") if ":" in pair
                )
            )
        except Exception:                       # noqa: BLE001
            chain_map = {}
    if not chain_map:
        result.notes.append(
            "chain map not parsed from cif2plip output: falling back to the "
            "documented A/P/L to A/B/C ordering"
        )
        # Correct only for a three-chain job. With a structural ion the
        # order is A, P, Z, L, so L is D and this map would hand the
        # ligand slot to the zinc. Flagged rather than silently applied.
        chain_map = {"A": "A", "P": "B", "L": "C"}
        result.notes.append(
            "chain map was not parsed: the A/P/L fallback assumes three "
            "chains, and a job carrying a structural ion has four. Treat "
            "this fingerprint as unverified"
        )
    peptide_chain = chain_map.get(PEPTIDE_SOURCE_CHAIN, "B")
    ligand_chain = chain_map.get(LIGAND_SOURCE_CHAIN, "C")
    result.notes.append(f"chain map {chain_map}: peptide is {peptide_chain} in the PLIP output")

    # cif2plip's CSV columns: ligand, interaction_type, prot_resnr, prot_restype,
    # prot_chain, lig_restype, lig_chain, distance_A, prot_atom_idx,
    # lig_atom_idx, geometry. Every row is a ligand-to-protein contact, so the
    # peptide rows are precisely the glue-to-degron half of the bridge.
    # Rows belong to whichever ligand PLIP perceived, and a structural zinc
    # is one of them: on a Sievers finger the CSV carries Y70:D:1 beside
    # ZN:C:1, and the zinc's rows are metal coordination to the receptor.
    # Counting those as glue contacts would put the finger's own fold into
    # a fingerprint that is supposed to measure the glue's grip on the
    # degron, and would do it on all 120 pairs in the arm.
    glue_rows = [r for r in rows if (r.get("lig_chain") or "").strip() == ligand_chain]
    other = len(rows) - len(glue_rows)
    if other:
        dropped = sorted({(r.get("lig_restype") or "?").strip()
                          for r in rows if r not in glue_rows})
        result.notes.append(
            f"{other} row(s) from {', '.join(dropped)} excluded: they are "
            f"contacts of another perceived ligand (a structural ion), not "
            f"of the glue in chain {ligand_chain}"
        )
    rows = glue_rows

    counts: dict[str, int] = {}
    receptor, peptide = set(), set()
    for row in rows:
        kind = (row.get("interaction_type") or "unknown").strip().lower()
        counts[kind] = counts.get(kind, 0) + 1
        chain = (row.get("prot_chain") or "").strip()
        label = f"{(row.get('prot_restype') or '').strip()}{(row.get('prot_resnr') or '').strip()}"
        if label in ("", "None"):
            continue
        if chain == peptide_chain:
            peptide.add(label)
        elif chain and chain != ligand_chain:
            receptor.add(label)
    result.interaction_types = counts
    result.receptor_contacts = sorted(receptor)
    result.peptide_contacts = sorted(peptide)

    e3 = job.get("e3_gene")
    canonical = CANONICAL_FINGERPRINTS.get(e3)
    if canonical:
        result.canonical_e3 = e3
        # Construct numbering, so the canonical residue numbers are mapped onto
        # the construct before comparison.
        from nobble.curate import constructs as C

        construct = C.CONSTRUCTS[job["construct"]]
        start, _end = construct.segments[0].range()
        expected = []
        for residue in canonical["receptor_residues"]:
            match = re.match(r"([A-Z]{3})(\d+)", residue)
            if match:
                expected.append(f"{match.group(1)}{int(match.group(2)) - start + 1}")
        result.canonical_matched = sorted(set(expected) & receptor)
        result.canonical_missing = sorted(set(expected) - receptor)

    result.status = "ok"
    return result
