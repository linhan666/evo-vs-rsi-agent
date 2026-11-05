"""Normalize a ChEMBL activity snapshot into one modelling-ready dataset (Blueprint §9.2).

Decisions this module makes explicit, because each one changes what a model learns:
  * **one endpoint per dataset.** Binding affinity (`Ki`/`Kd`) and potency
    (`IC50`/`EC50`) are never mixed. `--endpoint Ki` produces a Ki dataset; the
    other endpoints are counted and left in `measurements.csv` with their own type.
  * **`=` only enters the regression column.** `<`, `>`, `>=` go to a censored
    channel with the relation kept; they are never coerced into exact numbers.
  * **no cross-endpoint averaging.** Rows are merged only within the same molecule
    and the same endpoint; a spread of 10x or more is flagged, not smoothed away.
  * **no invented negatives.** A label comes only from a measured value that clears
    a pre-registered pX threshold; the grey zone and every censored row stay unlabeled.
  * **scaffold split.** Bemis–Murcko scaffolds are assigned to exactly one split, so
    no scaffold crosses train/validation/test.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
from collections import Counter, defaultdict

from ..manifest import describe_input, utc_now, write_manifest

UNIT_TO_NM = {"nM": 1.0, "uM": 1e3, "µM": 1e3, "mM": 1e6, "pM": 1e-3, "M": 1e9, "fM": 1e-6}
SCIENTIFIC = re.compile(r"^10\^(-?\d+)\s*(microM|µM|uM|nM|mM|M)$")
ENDPOINTS = ("Ki", "Kd", "IC50", "EC50")


def to_nanomolar(value: float | None, units: str | None) -> float | None:
    """Convert a ChEMBL standard value to nM; `None` when the unit cannot be read."""
    if value is None or not units:
        return None
    units = units.strip()
    if units in UNIT_TO_NM:
        return value * UNIT_TO_NM[units]
    match = SCIENTIFIC.match(units)
    if match:
        exponent, base = int(match.group(1)), match.group(2)
        multiplier = UNIT_TO_NM.get(base if base != "microM" else "uM")
        if multiplier is not None:
            return value * (10.0 ** exponent) * multiplier
    return None


def pchembl(nm: float | None) -> float | None:
    """pX = -log10(X[M]); a non-positive value has no logarithm."""
    if nm is None or nm <= 0:
        return None
    return round(9.0 - math.log10(nm), 4)


def load_rows(path: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as handle:
        return list(csv.DictReader(handle))


def classify(row: dict, endpoint: str, min_confidence: int) -> tuple[bool, str]:
    """Why a row is kept or excluded, before any value is looked at."""
    if row.get("standard_type") != endpoint:
        return False, "other_endpoint"
    try:
        confidence = int(float(row.get("confidence_score") or 0))
    except ValueError:
        return False, "confidence_unreadable"
    if confidence < min_confidence:
        return False, "low_confidence"
    if (row.get("assay_type") or "").strip() not in ("B", "F"):
        return False, "assay_type_other"
    if not (row.get("canonical_smiles") or "").strip():
        return False, "no_smiles"
    return True, "kept"


def normalize_row(row: dict, endpoint: str) -> dict:
    relation = (row.get("standard_relation") or "").strip() or None
    try:
        value = float(row["standard_value"]) if row.get("standard_value") else None
    except (TypeError, ValueError):
        value = None
    nm = to_nanomolar(value, row.get("standard_units"))
    return {
        "activity_id": row.get("activity_id"),
        "molecule_chembl_id": row.get("molecule_chembl_id"),
        "canonical_smiles": row.get("canonical_smiles"),
        "standard_type": row.get("standard_type"),
        "standard_relation": relation or "",
        "standard_value": value,
        "standard_units": (row.get("standard_units") or "").strip(),
        "value_nM": round(nm, 6) if nm is not None else None,
        "px": pchembl(nm),
        "assay_type": (row.get("assay_type") or "").strip(),
        "confidence_score": row.get("confidence_score"),
        "document_chembl_id": row.get("document_chembl_id"),
        "channel": "exact" if relation == "=" else ("censored" if relation in ("<", ">", ">=", "<=") else "unknown_relation"),
        "usable_for_regression": relation == "=" and nm is not None,
    }


def merge_exact(rows: list[dict]) -> tuple[list[dict], dict]:
    """Median within (molecule, endpoint); conflicts are flagged, never averaged across endpoints."""
    groups: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        if row["channel"] == "exact" and row["value_nM"] is not None:
            groups[row["molecule_chembl_id"]].append(row)

    merged: list[dict] = []
    conflicts = 0
    for molecule_id, items in groups.items():
        values = sorted(item["value_nM"] for item in items)
        middle = len(values) // 2
        median = values[middle] if len(values) % 2 else (values[middle - 1] + values[middle]) / 2
        spread = (values[-1] / values[0]) if values[0] > 0 else float("inf")
        conflict = spread >= 10
        conflicts += 1 if conflict else 0
        best = min(items, key=lambda item: (-int(float(item["confidence_score"] or 0)), str(item["activity_id"])))
        merged.append({
            "molecule_chembl_id": molecule_id,
            "canonical_smiles": best["canonical_smiles"],
            "standard_type": best["standard_type"],
            "value_nM": round(median, 6),
            "px": pchembl(median),
            "n_measurements": len(items),
            "spread_ratio": round(spread, 3) if math.isfinite(spread) else None,
            "conflict": conflict,
            "activity_ids": "|".join(sorted(str(item["activity_id"]) for item in items)),
            "documents": "|".join(sorted({str(item["document_chembl_id"]) for item in items})),
        })
    return merged, {"molecules_with_exact_value": len(merged), "conflict_molecules": conflicts}


def assign_label(px: float | None, strong: float, weak: float) -> int | None:
    if px is None:
        return None
    if px >= strong:
        return 1
    if px <= weak:
        return 0
    return None  # grey zone: measured, but deliberately unlabeled


def scaffold_of(smiles: str) -> str:
    from rdkit import Chem, RDLogger
    from rdkit.Chem.Scaffolds import MurckoScaffold

    RDLogger.DisableLog("rdApp.*")
    mol = Chem.MolFromSmiles(smiles)
    if mol is None:
        return smiles
    scaffold = MurckoScaffold.MurckoScaffoldSmiles(mol=mol)
    # Acyclic molecules have an empty scaffold; using the molecule itself keeps them
    # from all collapsing into one group and leaking across splits.
    return scaffold or smiles


def scaffold_split(rows: list[dict], fractions: tuple[float, float, float], seed: int) -> dict:
    scaffold_map = {row["molecule_chembl_id"]: scaffold_of(row["canonical_smiles"]) for row in rows}
    groups: dict[str, list[str]] = defaultdict(list)
    for molecule, scaffold in scaffold_map.items():
        groups[scaffold].append(molecule)

    # Largest scaffolds first; ties broken deterministically by a seeded hash.
    def order(item: tuple[str, list[str]]) -> tuple[int, str]:
        return (-len(item[1]), hashlib.sha256(f"{seed}:{item[0]}".encode()).hexdigest())

    total = len(scaffold_map)
    targets = [fractions[0] * total, fractions[1] * total]
    splits: dict[str, list[str]] = {"train": [], "validation": [], "test": []}
    for _, members in sorted(groups.items(), key=order):
        if len(splits["train"]) < targets[0]:
            splits["train"].extend(members)
        elif len(splits["validation"]) < targets[1]:
            splits["validation"].extend(members)
        else:
            splits["test"].extend(members)

    occurrences: Counter[str] = Counter()
    for members in splits.values():
        occurrences.update(members)
    duplicated = [molecule for molecule, count in occurrences.items() if count > 1]

    scaffold_sets = {name: {scaffold_map[molecule] for molecule in members} for name, members in splits.items()}
    crossing = (scaffold_sets["train"] & scaffold_sets["validation"]) | (scaffold_sets["train"] & scaffold_sets["test"]) \
        | (scaffold_sets["validation"] & scaffold_sets["test"])
    return {
        "schema_version": "1",
        "strategy": "bemis-murcko-scaffold",
        "generated_at": utc_now(),
        "seed": seed,
        "fractions_requested": {"train": fractions[0], "validation": fractions[1], "test": fractions[2]},
        "counts": {name: len(members) for name, members in splits.items()},
        "scaffold_counts": {name: len(values) for name, values in scaffold_sets.items()},
        "molecules": splits,
        "checks": {
            "no_molecule_in_two_splits": not duplicated,
            "no_scaffold_crosses_splits": not crossing,
            "crossing_scaffolds": sorted(crossing)[:20],
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evovs-science normalize")
    parser.add_argument("--input", required=True, help="activities_normalized.csv from data.chembl")
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--endpoint", default="Ki", choices=ENDPOINTS)
    parser.add_argument("--min-confidence", type=int, default=9,
                        help="ChEMBL target confidence; 9 is a direct single-protein assignment")
    parser.add_argument("--strong-px", type=float, default=7.0, help="pX at or above which a molecule is labeled active")
    parser.add_argument("--weak-px", type=float, default=6.0, help="pX at or below which a molecule is labeled inactive")
    parser.add_argument("--fractions", default="0.7,0.15,0.15")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--min-molecules", type=int, default=100,
                        help="below this the run reports NOT_ENOUGH_RELIABLE_DATA and writes no split")
    args = parser.parse_args(argv)

    if args.strong_px <= args.weak_px:
        raise SystemExit("--strong-px must be greater than --weak-px")
    fractions = tuple(float(item) for item in args.fractions.split(","))
    if len(fractions) != 3 or abs(sum(fractions) - 1) > 1e-6:
        raise SystemExit("--fractions must be three values that sum to 1")

    rows = load_rows(args.input)
    counts = Counter()
    normalized: list[dict] = []
    for row in rows:
        keep, reason = classify(row, args.endpoint, args.min_confidence)
        counts[reason] += 1
        if keep:
            normalized.append(normalize_row(row, args.endpoint))

    channel_counts = Counter(row["channel"] for row in normalized)
    unit_counter = Counter(row["standard_units"] for row in normalized)
    unusable = [row["activity_id"] for row in normalized if row["value_nM"] is None]

    merged, merge_stats = merge_exact(normalized)
    for row in merged:
        row["label"] = assign_label(row["px"], args.strong_px, args.weak_px)
    labeled = [row for row in merged if row["label"] is not None]
    grey = [row for row in merged if row["label"] is None]

    os.makedirs(args.outdir, exist_ok=True)
    measurements_path = os.path.join(args.outdir, "measurements.csv")
    with open(measurements_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(normalized[0].keys()) if normalized else ["activity_id"])
        writer.writeheader()
        writer.writerows(normalized)

    dataset_path = os.path.join(args.outdir, "dataset.csv")
    fields = ["molecule_chembl_id", "canonical_smiles", "standard_type", "value_nM", "px", "label",
              "n_measurements", "spread_ratio", "conflict", "activity_ids", "documents"]
    with open(dataset_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows([{key: row.get(key, "") for key in fields} for row in merged])

    sufficiency = "OK" if len(labeled) >= args.min_molecules else "NOT_ENOUGH_RELIABLE_DATA"
    split_manifest = None
    if sufficiency == "OK":
        split_manifest = scaffold_split(labeled, fractions, args.seed)
        split_path = os.path.join(args.outdir, "split_manifest.json")
        with open(split_path, "w", encoding="utf-8") as handle:
            json.dump(split_manifest, handle, ensure_ascii=False, indent=2)
            handle.write("\n")

    audit = {
        "schema_version": "1",
        "created_at": utc_now(),
        "input": os.path.basename(args.input),
        "endpoint": args.endpoint,
        "parameters": {"min_confidence": args.min_confidence, "strong_px": args.strong_px,
                       "weak_px": args.weak_px, "fractions": fractions, "seed": args.seed},
        "rows_in": len(rows),
        "exclusions": dict(counts),
        "rows_normalized": len(normalized),
        "channels": dict(channel_counts),
        "units_seen": dict(unit_counter),
        "rows_without_usable_value": len(unusable),
        "molecules_with_exact_value": merge_stats["molecules_with_exact_value"],
        "conflict_molecules": merge_stats["conflict_molecules"],
        "labeled": len(labeled),
        "grey_zone_unlabeled": len(grey),
        "positives": sum(1 for row in labeled if row["label"] == 1),
        "negatives": sum(1 for row in labeled if row["label"] == 0),
        "sufficiency": sufficiency,
        "label_rule": f"exact '=' value with pX >= {args.strong_px} is active, pX <= {args.weak_px} inactive; "
                      f"grey zone and all censored rows are unlabeled; unmeasured pairs are never negatives",
        "caveats": [
            "One endpoint only; Ki and IC50 are different physical quantities and are not mixed here.",
            "Censored rows keep their relation and are excluded from the regression column.",
            "Labels are thresholded measurements, not assay ground truth for a different endpoint.",
        ],
    }
    audit_path = os.path.join(args.outdir, "dataset_audit.json")
    with open(audit_path, "w", encoding="utf-8") as handle:
        json.dump(audit, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    artifacts = [
        {"path": measurements_path, "content_type": "text/csv", "description": "every kept row with its channel"},
        {"path": dataset_path, "content_type": "text/csv", "description": "one row per molecule, exact values only"},
        {"path": audit_path, "content_type": "application/json", "description": "dataset audit"},
    ]
    if split_manifest:
        artifacts.append({"path": os.path.join(args.outdir, "split_manifest.json"),
                          "content_type": "application/json", "description": "scaffold split manifest"})
    write_manifest(
        args.outdir, artifacts,
        generator="evovs_science.data.normalize",
        inputs=[describe_input(args.input)],
        parameters={"endpoint": args.endpoint, "strong_px": args.strong_px, "weak_px": args.weak_px},
        extra={"sufficiency": sufficiency, "split_checks": (split_manifest or {}).get("checks")},
    )

    print(json.dumps({
        "endpoint": args.endpoint, "rows_in": len(rows), "normalized": len(normalized),
        "channels": dict(channel_counts), "molecules": merge_stats["molecules_with_exact_value"],
        "labeled": len(labeled), "positives": audit["positives"], "negatives": audit["negatives"],
        "sufficiency": sufficiency,
        "split": (split_manifest or {}).get("counts"),
        "checks": (split_manifest or {}).get("checks"),
    }, ensure_ascii=False))
    return 0 if sufficiency == "OK" else 3


if __name__ == "__main__":
    raise SystemExit(main())
