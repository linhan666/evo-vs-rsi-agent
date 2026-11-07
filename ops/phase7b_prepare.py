#!/usr/bin/env python3
"""Prepare the redesigned round (phase7b): protected test set + frozen split, per target.

Three defects this fixes
------------------------
1. Six of the nine sequence targets have no protected test set, so no arm can be
   compared on a common yardstick. `evaluation.locked` only knows MOR/KOR/DRD2.
2. `data.split --strategy scaffold` ignores `--seed` (verified: same val set for
   seeds 17/23/42/7/2024), so a "multi-seed" claim is vacuous. What actually moves
   the validation set is `test_fraction`, which each ticket chose freely — the two
   arms of DRD2 ended up with **zero** validation overlap.
3. Therefore the split must be frozen by construction, not by instruction.

What it writes (non-destructive: the original dataset.csv is untouched)
----------------------------------------------------------------------
  protected/chembl37_ki_<slug>/final_test_Ki.csv   held-out molecules, never trained on
  protected/chembl37_ki_<slug>/artifact_manifest.json
  scientific/.artifacts/chembl/<slug>/ki/dataset_p7b.csv   training pool = original minus held-out
  scientific/.artifacts/chembl/<slug>/ki/splits/frozen_<slug>.json   fixed train/val/test manifest

For MOR / KOR / DRD2 the protected set already exists and `dataset.csv` is already
carved, so those three only get the frozen manifest.

Usage:  scientific/.venv/bin/python ops/phase7b_prepare.py [--dry-run]
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "scientific" / ".artifacts" / "chembl"
PROTECTED = ROOT / "protected"

# sequence position, display name, artifact slug, locked code, existing protected dir
TARGETS = [
    (1, "D2", "d(2)_dopamine_recept", "D2", None),
    (2, "5HT", "5-hydroxytryptamine_", "5HT", None),
    (3, "ADR", "adenosine_receptor_a", "ADR", None),
    (4, "DRD2", "drd2", "DRD2", "chembl37_ki_drd2"),
    (5, "MOR", "oprm1", "MOR", "chembl37_ki"),
    (6, "CBR", "cannabinoid_receptor", "CBR", None),
    (7, "KOR", "oprk1", "KOR", "chembl37_ki_oprk1"),
    (8, "CA2", "carbonic_anhydrase_2", "CA2", None),
    (9, "PT", "prothrombin", "PT", None),
]

TEST_FRACTION = 0.15   # held out for the locked test set
VAL_FRACTION = 0.10    # validation slice inside the training pool
INTERNAL_TEST = 0.05   # ml.train wants a test partition; keep it small and disjoint


def scaffolds(rows: list[dict]) -> dict[str, str]:
    """molecule id -> Bemis-Murcko scaffold."""
    from rdkit import Chem, RDLogger
    from rdkit.Chem.Scaffolds import MurckoScaffold
    RDLogger.DisableLog("rdApp.*")
    out = {}
    for row in rows:
        mol_id = (row.get("molecule_chembl_id") or "").strip()
        smiles = (row.get("canonical_smiles") or "").strip()
        if not mol_id or not smiles:
            continue
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            continue
        try:
            out[mol_id] = MurckoScaffold.MurckoScaffoldSmiles(mol=mol, includeChirality=False)
        except Exception:
            out[mol_id] = ""
    return out


def carve(rows: list[dict], scaffold_of: dict[str, str], fraction: float,
          seed: int = 17) -> tuple[list[dict], list[dict]]:
    """Hold out whole scaffolds until `fraction` of rows is reached.

    Order is a seeded shuffle, not largest-first. The harness's own `data.split`
    sorts by scaffold size, which is why its validation set is identical for every
    seed and systematically biased toward the largest scaffolds — a biased
    validation slice makes a model that fits big multi-ring scaffolds look better
    than it generalises.
    """
    import random

    buckets: dict[str, list[dict]] = {}
    for row in rows:
        buckets.setdefault(scaffold_of.get(row["molecule_chembl_id"], ""), []).append(row)
    order = list(buckets.items())
    random.Random(seed).shuffle(order)
    want = int(round(len(rows) * fraction))
    held, kept = [], []
    for _, members in order:
        if len(held) + len(members) <= want:
            held.extend(members)
        else:
            kept.extend(members)
    return held, kept


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def write_csv(path: Path, rows: list[dict], fieldnames: list[str]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key, "") for key in fieldnames})


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    summary = []
    for seq, name, slug, code, existing in TARGETS:
        dataset = DATA / slug / "ki" / "dataset.csv"
        if not dataset.exists():
            summary.append((seq, name, "MISSING dataset.csv", "", "", ""))
            continue
        with dataset.open(encoding="utf-8", errors="ignore") as handle:
            reader = csv.DictReader(handle)
            fieldnames = reader.fieldnames or []
            rows = list(reader)

        if existing:
            protected_dir = PROTECTED / existing
            test_csv = protected_dir / "final_test_Ki.csv"
            with test_csv.open(encoding="utf-8", errors="ignore") as handle:
                held_ids = {row["molecule_chembl_id"] for row in csv.DictReader(handle)}
            # already carved upstream: the training pool is the existing dataset
            pool = rows
            overlap = {row["molecule_chembl_id"] for row in rows} & held_ids
            note = f"existing protected set, pool as-is (overlap {len(overlap)})"
        else:
            scaffold_of = scaffolds(rows)
            held, pool = carve(rows, scaffold_of, TEST_FRACTION)
            held_ids = {row["molecule_chembl_id"] for row in held}
            protected_dir = PROTECTED / f"chembl37_ki_{slug.replace('(', '').replace(')', '').replace('_', '')}"
            test_csv = protected_dir / "final_test_Ki.csv"
            note = "carved now"
            if not args.dry_run:
                write_csv(test_csv, held, fieldnames)
                os.chmod(test_csv, 0o600)
                manifest = {
                    "target": code, "endpoint": "Ki", "source": f"chembl/{slug}/ki/dataset.csv",
                    "rows": len(held), "fraction": TEST_FRACTION, "strategy": "scaffold-largest-first",
                    "sha256": sha256_of(test_csv),
                }
                (protected_dir / "artifact_manifest.json").write_text(
                    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

        pool_csv = DATA / slug / "ki" / "dataset_p7b.csv"
        if not args.dry_run:
            write_csv(pool_csv, pool, fieldnames)

        # frozen manifest over the training pool: val and internal test are whole scaffolds
        scaffold_of_pool = scaffolds(pool)
        val_rows, rest = carve(pool, scaffold_of_pool, VAL_FRACTION)
        test_rows, train_rows = carve(rest, scaffold_of_pool, INTERNAL_TEST)
        manifest_rows = {}
        for row in train_rows:
            manifest_rows[row["molecule_chembl_id"]] = "train"
        for row in val_rows:
            manifest_rows[row["molecule_chembl_id"]] = "val"
        for row in test_rows:
            manifest_rows[row["molecule_chembl_id"]] = "test"
        frozen = {
            "schema_version": "1", "strategy": "frozen-scaffold", "version": "phase7b",
            "source": f"dataset_p7b.csv", "seed": 0,
            "counts": {"train": len(train_rows), "val": len(val_rows), "test": len(test_rows)},
            "rows": manifest_rows,
        }
        frozen_path = DATA / slug / "ki" / "splits" / f"frozen_{slug}.json"
        if not args.dry_run:
            frozen_path.parent.mkdir(parents=True, exist_ok=True)
            frozen_path.write_text(json.dumps(frozen, ensure_ascii=False) + "\n", encoding="utf-8")

        summary.append((seq, name, note, len(rows), len(held_ids & {r["molecule_chembl_id"] for r in pool}),
                        f"{len(train_rows)}/{len(val_rows)}/{len(test_rows)}"))

    print(f"{'#':<3}{'target':<7}{'note':<44}{'orig':>6}{'leak':>6}  train/val/test")
    for row in summary:
        print(f"{row[0]:<3}{row[1]:<7}{str(row[2]):<44}{str(row[3]):>6}{str(row[4]):>6}  {row[5]}")
    print("\nleak = 受保护分子残留在训练池里的数量，必须为 0")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
