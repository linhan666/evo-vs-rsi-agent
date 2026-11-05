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


def read_smiles(path: str, limit: int | None = None, id_column: str = "id", smiles_column: str = "smiles") -> list[tuple[str, str]]:
    """Read `(id, smiles)` pairs from a `.csv` or a `.smi` file; column names are configurable."""
    rows: list[tuple[str, str]] = []
    if path.endswith(".csv"):
        with open(path, newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            fields = {name.lower(): name for name in (reader.fieldnames or [])}
            if smiles_column.lower() not in fields:
                raise SystemExit(f"{path} has no {smiles_column!r} column; found {reader.fieldnames}")
            id_field = fields.get(id_column.lower())
            for index, row in enumerate(reader):
                if limit is not None and index >= limit:
                    break
                rows.append((row.get(id_field, f"row{index}") if id_field else f"row{index}", row[fields[smiles_column.lower()]]))
    else:
        with open(path, encoding="utf-8") as handle:
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


def featurize(rows: list[tuple[str, str]], *, radius: int, n_bits: int):
    """Featurize rows into ECFP + descriptors.

    `EVOVS_FEAT_JOBS=N` schedules the same chunks over N workers (candidate
    harness delta); chunk order equals input order, so the output is identical
    to the serial path (shadow-evaluated in Phase 4, candidate1).
    """
    import math

    # PROMOTED 2026-11-05 (candidate1): default 8 after shadow acceptance
    # (equivalence 1.0, featurize 2.1x, screening 3.3x) — see docs/PHASE4_DESIGN.md §6.
    jobs = max(1, int(os.environ.get("EVOVS_FEAT_JOBS", "8")))
    desc_set = os.environ.get("EVOVS_DESC_SET", "v1")
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
    args = parser.parse_args(argv)

    rows = read_smiles(args.input, args.limit or None, args.id_column, args.smiles_column)
    ids, matrix, descriptors, invalid = featurize(rows, radius=args.radius, n_bits=args.n_bits)

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
        inputs=[describe_input(args.input)],
        parameters={"radius": args.radius, "n_bits": args.n_bits},
        extra={"rows_valid": len(ids), "rows_invalid": len(invalid)},
    )

    print(json.dumps({"rows_valid": len(ids), "rows_invalid": len(invalid), "output": args.output}))
    return 0 if ids else 2


if __name__ == "__main__":
    raise SystemExit(main())
