"""SMILES → ECFP fingerprints + 2D descriptors.

Blueprint §8.2 (Chemistry layer) and T-004: an invalid SMILES is **skipped and
recorded**, never silently replaced or coerced. Every row that reaches the model
keeps its input id so labels can be joined without positional assumptions.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys

import numpy as np

from ..manifest import describe_input, utc_now, write_manifest

def _descriptor_row(mol, extra_names: tuple[str, ...] = ()) -> list[float]:
    from rdkit.Chem import Crippen, Descriptors

    row = [
        Descriptors.MolWt(mol),
        Crippen.MolLogP(mol),
        Descriptors.NumHDonors(mol),
        Descriptors.NumHAcceptors(mol),
        Descriptors.TPSA(mol),
        Descriptors.NumRotatableBonds(mol),
        Descriptors.RingCount(mol),
    ]
    if extra_names:
        all_descriptors = Descriptors.CalcMolDescriptors(mol)
        row.extend(float(all_descriptors.get(name) or 0.0) for name in extra_names)
    return row


DESCRIPTOR_NAMES = ["mol_weight", "logp", "h_donors", "h_acceptors", "tpsa", "rotatable_bonds", "rings"]

# candidate3 (metric-level): descriptor set v2 appends these RDKit 2D descriptors.
# The extra block is appended AFTER the v1 block, so a v2 row is [v1..., extras...].
DESCRIPTOR_EXTRA_V2 = (
    "NumValenceElectrons", "FractionCSP3", "Chi0n", "Chi1n", "Chi2n", "Chi3n", "Chi4n",
    "Chi0v", "Chi1v", "Chi2v", "Chi3v", "Chi4v", "Kappa1", "Kappa2", "Kappa3",
    "HallKierAlpha", "BalabanJ", "BertzCT", "LabuteASA", "MolMR", "NHOHCount", "NOCount",
    "RingCount", "NumAromaticRings", "NumSaturatedRings", "NumAliphaticRings",
    "NumAromaticCarbocycles", "NumAromaticHeterocycles", "NumSaturatedCarbocycles",
    "NumSaturatedHeterocycles", "NumAliphaticCarbocycles", "NumAliphaticHeterocycles",
    "MaxPartialCharge", "MinPartialCharge", "MaxAbsPartialCharge", "MinAbsPartialCharge",
)
DESCRIPTOR_SETS = {"v1": (), "v2": DESCRIPTOR_EXTRA_V2}


# Pre-flight column resolution (candidates auto-failure-recurrence-rdkit-featurize-27384f
# and its sibling for ml.train). The failure it fixes is a real one from the corpus: a
# ticket asked for `smiles` against a ChEMBL export that names the column
# `canonical_smiles`, and retried the same wrong request twelve times. Resolving a known
# alias keeps the success path untouched (exact names win) while making the obvious
# intent work; anything that still cannot be resolved fails immediately with the
# columns that do exist. Shared by every tool that reads a table.
COLUMN_ALIASES = {
    "id": ("id", "molecule_chembl_id", "chembl_id", "compound_id"),
    "smiles": ("smiles", "canonical_smiles", "smiles_std", "structure"),
    "label": ("label", "activity", "value", "px", "target"),
}


def _data_root() -> str:
    return os.environ.get("EVOVS_DATA_ROOT", "")


def _nearest(path: str, root: str) -> list[str]:
    """Up to three files whose name looks like `path`, to make a typo actionable."""
    base = os.path.basename(path)
    stem, suffix = os.path.splitext(base)
    found: list[str] = []
    for dirpath, _dirs, files in os.walk(root):
        for name in files:
            if name == base or (stem and stem in name) or (suffix and name.endswith(suffix) and stem[:4] and stem[:4] in name):
                found.append(os.path.join(dirpath, name))
                if len(found) >= 3:
                    return found
        if dirpath.count(os.sep) - root.count(os.sep) >= 3:
            continue
    return found


def resolve_input_path(path: str) -> str:
    """Return an existing file, trying the data root and the repo root for relative names.

    The failure this fixes is real: five steps in one ticket wrote `scientific/.artifacts/…`
    or `.artifacts/…` and failed, because those are repo-relative while the job runs
    from the ticket directory. A relative name that resolves under EVOVS_DATA_ROOT is
    the same file the caller meant; anything else still fails, now with the closest
    matches that do exist.
    """
    if os.path.isfile(path):
        return path
    root = _data_root()
    tried = [path]
    normalized = path
    for marker in ("scientific/.artifacts/", ".artifacts/"):
        if marker in normalized:
            normalized = normalized.split(marker, 1)[1]
            break
    candidates = []
    if root:
        candidates += [os.path.join(root, normalized), os.path.join(root, path.lstrip("./")),
                       os.path.join(os.path.dirname(os.path.dirname(root)), path)]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate
        tried.append(candidate)
    near = _nearest(path, root) if root else []
    hint = "; closest matches: " + ", ".join(near) if near else "; no file with that name under the data root"
    raise SystemExit(
        f"no such input file: {path} (data root: {root or 'unset'}; tried: {tried}){hint}")


def check_input_file(path: str) -> None:
    """Fail before any work starts, with a message that says what to fix."""
    if os.path.isdir(path):
        raise SystemExit(f"{path} is a directory; give the .csv/.smi file itself")
    resolve_input_path(path)


def resolve_columns(path: str, columns: dict) -> dict:
    """Header-only resolution: exact name first, then a known alias.

    `columns` maps role -> requested name ({'id': 'id', 'smiles': 'smiles'}).
    Returns {role: actual, ..., "resolved": {requested: actual}}. `resolved` is empty
    when every requested name existed, so callers can report that a substitution
    happened instead of doing it silently. A missing `id` is tolerated (rows get
    rowN); a missing `smiles` or `label` is fatal, because there is nothing to use.
    """
    check_input_file(path)
    out: dict = {"resolved": {}}
    if not path.endswith(".csv"):
        return out
    path = resolve_input_path(path)
    with open(path, newline="", encoding="utf-8-sig") as handle:
        header = next(csv.reader(handle), [])
    fields = {name.lower(): name for name in header}
    for role, requested in columns.items():
        if requested.lower() in fields:
            out[role] = fields[requested.lower()]
            continue
        alias = next((name for name in COLUMN_ALIASES.get(role, ()) if name in fields), None)
        if alias is None:
            if role == "id":
                continue
            raise SystemExit(
                f"{path} has no {requested!r} column and no known alias "
                f"({', '.join(COLUMN_ALIASES.get(role, ()))}); found {header}")
        out[role] = fields[alias]
        out["resolved"][requested] = fields[alias]
    return out


def read_smiles(path: str, limit: int | None = None, id_column: str = "id", smiles_column: str = "smiles") -> list[tuple[str, str]]:
    """Read `(id, smiles)` pairs from a `.csv` or a `.smi` file; column names are configurable."""
    rows: list[tuple[str, str]] = []
    if path.endswith(".csv"):
        check_input_file(path)
        path = resolve_input_path(path)
        columns = resolve_columns(path, {"id": id_column, "smiles": smiles_column})
        with open(path, newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            for index, row in enumerate(reader):
                if limit is not None and index >= limit:
                    break
                rows.append((row.get(columns["id"], f"row{index}") if columns["id"] else f"row{index}",
                             row[columns["smiles"]]))
    else:
        check_input_file(path)
        with open(resolve_input_path(path), encoding="utf-8") as handle:
            for index, line in enumerate(handle):
                if limit is not None and index >= limit:
                    break
                parts = line.split()
                if not parts:
                    continue
                rows.append((parts[1] if len(parts) > 1 else f"row{index}", parts[0]))
    return rows


def _featurize_chunk(task: tuple):
    """Featurize one chunk; module-level so multiprocessing can pickle it."""
    _target, chunk, radius, n_bits, extra_names = task
    from rdkit import Chem, RDLogger
    from rdkit.Chem import rdFingerprintGenerator
    from rdkit.DataStructs import ConvertToNumpyArray

    RDLogger.DisableLog("rdApp.*")
    generator = rdFingerprintGenerator.GetMorganGenerator(radius=radius, fpSize=n_bits)
    ids: list[str] = []
    fp_rows: list[np.ndarray] = []
    desc_rows: list[list[float]] = []
    invalid: list[dict[str, str]] = []
    for molecule_id, smiles in chunk:
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            invalid.append({"id": molecule_id, "smiles": smiles, "reason": "unparseable_smiles"})
            continue
        vector = np.zeros((n_bits,), dtype=np.uint8)
        ConvertToNumpyArray(generator.GetFingerprint(mol), vector)
        fp_rows.append(vector)
        desc_rows.append(_descriptor_row(mol, extra_names))
        ids.append(molecule_id)
    return (ids,
            np.vstack(fp_rows) if fp_rows else np.zeros((0, n_bits), dtype=np.uint8),
            np.asarray(desc_rows, dtype=np.float32) if desc_rows else np.zeros((0, len(DESCRIPTOR_NAMES)), dtype=np.float32),
            invalid)


def featurize(rows: list[tuple[str, str]], *, radius: int, n_bits: int, desc_set: str | None = None):
    """Featurize rows into ECFP + descriptors.

    `EVOVS_FEAT_JOBS=N` schedules the same chunks over N workers (candidate
    harness delta); chunk order equals input order, so the output is identical
    to the serial path (shadow-evaluated in Phase 4, candidate1).
    """
    import math

    # PROMOTED 2026-11-05 (candidate1): default 8 after shadow acceptance
    # (equivalence 1.0, featurize 2.1x, screening 3.3x) — see docs/PHASE4_DESIGN.md §6.
    jobs = max(1, int(os.environ.get("EVOVS_FEAT_JOBS", "8")))
    desc_set = desc_set or os.environ.get("EVOVS_DESC_SET", "v1")
    extra_names = DESCRIPTOR_SETS.get(desc_set, ())
    desc_width = len(DESCRIPTOR_NAMES) + len(extra_names)
    if rows:
        chunk_size = max(1, math.ceil(len(rows) / (jobs * 4)))
        chunks = [(f"chunk{i}", rows[i:i + chunk_size], radius, n_bits, extra_names)
                  for i in range(0, len(rows), chunk_size)]
    else:
        chunks = []
    if jobs > 1 and len(chunks) > 1:
        import multiprocessing as mp

        with mp.Pool(min(jobs, len(chunks))) as pool:
            parts = pool.map(_featurize_chunk, chunks)
    else:
        parts = [_featurize_chunk(chunk) for chunk in chunks]
    ids = [molecule_id for part in parts for molecule_id in part[0]]
    matrix = np.vstack([part[1] for part in parts]) if parts else np.zeros((0, n_bits), dtype=np.uint8)
    descriptors = np.vstack([part[2] for part in parts]) if parts else np.zeros((0, desc_width), dtype=np.float32)
    invalid = [item for part in parts for item in part[3]]
    return ids, matrix, descriptors, invalid


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evovs-science featurize")
    parser.add_argument("--input", required=True, help="CSV with id,smiles or a .smi file")
    parser.add_argument("--output", required=True, help="output .npz path")
    parser.add_argument("--report", required=True, help="output feature_meta.json path")
    parser.add_argument("--radius", type=int, default=2)
    parser.add_argument("--n-bits", type=int, default=2048)
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--id-column", default="id")
    parser.add_argument("--smiles-column", default="smiles")
    parser.add_argument("--desc-set", choices=list(DESCRIPTOR_SETS), default=None,
                        help="descriptor set (candidate3); overrides EVOVS_DESC_SET")
    args = parser.parse_args(argv)

    input_path = resolve_input_path(args.input)  # resolve once; the manifest must hash the real file
    rows = read_smiles(input_path, args.limit or None, args.id_column, args.smiles_column)
    columns = resolve_columns(input_path, {"id": args.id_column, "smiles": args.smiles_column})
    ids, matrix, descriptors, invalid = featurize(rows, radius=args.radius, n_bits=args.n_bits,
                                                  desc_set=args.desc_set)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    np.savez_compressed(args.output, X=matrix, D=descriptors, ids=np.asarray(ids, dtype=object))

    import rdkit

    report = {
        "schema_version": "1",
        "created_at": utc_now(),
        "input": os.path.basename(args.input),
        "rows_read": len(rows),
        "rows_valid": len(ids),
        "rows_invalid": len(invalid),
        "invalid": invalid[:200],
        "parameters": {"radius": args.radius, "n_bits": args.n_bits, "fingerprint": "morgan"},
        "descriptor_names": DESCRIPTOR_NAMES,
        "rdkit_version": rdkit.__version__,
    }
    # Only present when a requested column did not exist and a known alias stood in.
    # Absent on the ordinary path, so existing reports stay byte-identical.
    if columns.get("resolved"):
        report["columns_resolved"] = columns["resolved"]
    with open(args.report, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    write_manifest(
        os.path.dirname(os.path.abspath(args.output)),
        [
            {"path": args.output, "content_type": "application/npz", "description": "fingerprints and descriptors"},
            {"path": args.report, "content_type": "application/json", "description": "featurization report"},
        ],
        generator="evovs_science.chemistry.featurize",
        inputs=[describe_input(input_path)],
        parameters={"radius": args.radius, "n_bits": args.n_bits},
        extra={"rows_valid": len(ids), "rows_invalid": len(invalid)},
    )

    print(json.dumps({"rows_valid": len(ids), "rows_invalid": len(invalid), "output": args.output}))
    return 0 if ids else 2


if __name__ == "__main__":
    raise SystemExit(main())
