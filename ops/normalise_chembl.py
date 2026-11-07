#!/usr/bin/env python3
"""Normalise raw ChEMBL pages into the dataset.csv format the modelling tools expect.

Each target's ki/raw/page-*.json holds activity records pulled from ChEMBL.
The modelling tools need dataset.csv with columns:
  molecule_chembl_id, canonical_smiles, standard_type, value_nM, px, label,
  n_measurements, spread_ratio, conflict, activity_ids, documents

Rules (matching the existing three datasets):
  - keep only standard_relation '=' and standard_type in (Ki, IC50, EC50, AC50)
  - value_nM is the geometric mean of replicates
  - px = 9 - log10(value_nM / 1e9)  (i.e. -log10[M])
  - label: 1 if value_nM < 1000, 0 if > 10000, drop 1000-10000
"""

import csv
import glob
import json
import math
import os
import sys
from collections import defaultdict


def normalise(raw_dir: str, out_path: str) -> tuple[int, int]:
    per_mol: dict[str, dict] = defaultdict(lambda: {"values": [], "ids": [], "docs": set()})
    total = 0
    for page in sorted(glob.glob(os.path.join(raw_dir, "page-*.json"))):
        with open(page, encoding="utf-8") as handle:
            activities = json.load(handle).get("activities", [])
        for act in activities:
            total += 1
            rel = act.get("standard_relation", "=")
            if rel not in ("=", None, ""):
                continue
            val = act.get("standard_value")
            if val is None:
                continue
            smiles = act.get("canonical_smiles")
            mol_id = act.get("molecule_chembl_id")
            if not smiles or not mol_id:
                continue
            try:
                value = float(val)
            except (TypeError, ValueError):
                continue
            if value <= 0:
                continue
            entry = per_mol[mol_id]
            entry["smiles"] = smiles
            entry["values"].append(value)
            entry["ids"].append(str(act.get("activity_id", "")))
            if act.get("document_chembl_id"):
                entry["docs"].add(act["document_chembl_id"])
            entry["type"] = act.get("standard_type", "Ki")

    rows = []
    for mol_id, entry in per_mol.items():
        values = entry["values"]
        geo = math.exp(sum(math.log(v) for v in values) / len(values))
        nM = round(geo, 2)
        px = round(9 - math.log10(geo / 1e9), 4)
        spread = round(max(values) / min(values), 2) if min(values) > 0 else 0
        if nM < 1000:
            label = 1
        elif nM > 10000:
            label = 0
        else:
            continue
        rows.append({
            "molecule_chembl_id": mol_id,
            "canonical_smiles": entry["smiles"],
            "standard_type": entry.get("type", "Ki"),
            "value_nM": nM,
            "px": px,
            "label": label,
            "n_measurements": len(values),
            "spread_ratio": spread,
            "conflict": str(len(values) > 1 and spread > 10),
            "activity_ids": ";".join(entry["ids"][:5]),
            "documents": ";".join(sorted(entry["docs"])[:3]),
        })

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    fieldnames = ["molecule_chembl_id", "canonical_smiles", "standard_type", "value_nM",
                  "px", "label", "n_measurements", "spread_ratio", "conflict",
                  "activity_ids", "documents"]
    with open(out_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    return total, len(rows)


def main():
    base = "scientific/.artifacts/chembl"
    for slug in sorted(os.listdir(base)):
        raw_dir = os.path.join(base, slug, "ki", "raw")
        out_path = os.path.join(base, slug, "ki", "dataset.csv")
        if not os.path.isdir(raw_dir):
            continue
        if os.path.exists(out_path):
            print(f"{slug}: already normalised")
            continue
        total, kept = normalise(raw_dir, out_path)
        print(f"{slug}: {total} raw -> {kept} molecules")
    return 0


if __name__ == "__main__":
    sys.exit(main())
