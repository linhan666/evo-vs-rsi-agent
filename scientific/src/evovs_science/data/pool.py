"""Build the pooled multi-target training set (Blueprint §12, TRANSFER_DESIGN.md).

Pre-registered rules live in docs/TRANSFER_DESIGN.md; the target order below is
part of that registration and must not change (the evaluator appends the same
one-hot in the same order).
"""

from __future__ import annotations

import argparse
import csv
import json
import os

import numpy as np

from ..chemistry.featurize import featurize
from ..manifest import describe_input, utc_now, write_manifest

TARGET_ORDER = ("MOR", "KOR", "DRD2")


def read_dataset(path: str) -> tuple[list[dict], dict[str, str]]:
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        return list(reader), {name.lower(): name for name in (reader.fieldnames or [])}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evovs-science pool")
    parser.add_argument("--specs", required=True,
                        help="comma-separated TARGET:dir under the data root, e.g. MOR:oprm1,KOR:oprk1,DRD2:drd2")
    parser.add_argument("--data-root", required=True)
    parser.add_argument("--output-dir", required=True)
    args = parser.parse_args(argv)

    specs = [(part.split(":")[0].strip(), part.split(":")[1].strip()) for part in args.specs.split(",") if part.strip()]
    if [target for target, _ in specs] != list(TARGET_ORDER):
        raise SystemExit(f"--specs targets must be exactly {','.join(TARGET_ORDER)} in that order")

    pooled_rows: list[dict] = []
    per_target_counts: dict[str, int] = {}
    inputs: list[dict] = []
    for target, directory in specs:
        dataset_path = os.path.join(args.data_root, "chembl", directory, "ki", "dataset.csv")
        manifest_path = os.path.join(args.data_root, "chembl", directory, "ki", "split_manifest.json")
        rows, columns = read_dataset(dataset_path)
        manifest = json.load(open(manifest_path, encoding="utf-8"))
        train_ids = set(manifest["molecules"]["train"])
        kept = 0
        for row in rows:
            molecule = row[columns["molecule_chembl_id"]]
            if molecule not in train_ids:
                continue
            pooled_rows.append({
                "molecule_chembl_id": molecule,
                "canonical_smiles": row[columns["canonical_smiles"]],
                "label": row[columns["label"]],
                "target": target,
            })
            kept += 1
        per_target_counts[target] = kept
        inputs.append(describe_input(dataset_path))
        inputs.append(describe_input(manifest_path))

    os.makedirs(args.output_dir, exist_ok=True)
    pooled_csv = os.path.join(args.output_dir, "pooled_train.csv")
    with open(pooled_csv, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["molecule_chembl_id", "canonical_smiles", "label", "target"])
        writer.writeheader()
        writer.writerows(pooled_rows)

    # Featurize the pooled training rows and append the pre-registered one-hot.
    pairs = [(row["molecule_chembl_id"], row["canonical_smiles"]) for row in pooled_rows]
    ids, matrix, descriptors, invalid = featurize(pairs, radius=2, n_bits=2048)
    label_of = {row["molecule_chembl_id"]: row["label"] for row in pooled_rows}
    target_of = {row["molecule_chembl_id"]: row["target"] for row in pooled_rows}
    keep = [index for index, molecule in enumerate(ids) if label_of.get(molecule, "") != ""]
    ids = [ids[index] for index in keep]
    matrix = matrix[keep]
    descriptors = descriptors[keep]

    onehot = np.zeros((len(ids), len(TARGET_ORDER)), dtype=np.float32)
    for index, molecule in enumerate(ids):
        onehot[index, TARGET_ORDER.index(target_of[molecule])] = 1.0
    descriptors_aug = np.hstack([descriptors, onehot]).astype(np.float32)

    features_path = os.path.join(args.output_dir, "features_aug.npz")
    np.savez_compressed(features_path, X=matrix.astype(np.float32), D=descriptors_aug,
                        ids=np.asarray(ids, dtype=object))

    labels_csv = os.path.join(args.output_dir, "labels.csv")
    with open(labels_csv, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "label"])
        for molecule in ids:
            writer.writerow([molecule, label_of[molecule]])

    audit = {
        "schema_version": "1",
        "created_at": utc_now(),
        "target_order": list(TARGET_ORDER),
        "per_target_train_rows": per_target_counts,
        "rows_pooled": len(pooled_rows),
        "rows_featurized": len(ids),
        "rows_invalid": len(invalid),
        "features_dim": int(matrix.shape[1] + descriptors_aug.shape[1]),
        "rule": "train splits only; one target-hot block appended after descriptors; grey-zone rows excluded",
    }
    audit_path = os.path.join(args.output_dir, "pooled_audit.json")
    with open(audit_path, "w", encoding="utf-8") as handle:
        json.dump(audit, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    write_manifest(
        args.output_dir,
        [
            {"path": features_path, "content_type": "application/npz", "description": "pooled features with target one-hot"},
            {"path": labels_csv, "content_type": "text/csv", "description": "pooled labels"},
            {"path": audit_path, "content_type": "application/json", "description": "pooling audit"},
        ],
        generator="evovs_science.data.pool",
        inputs=inputs,
        parameters={"target_order": list(TARGET_ORDER)},
    )

    print(json.dumps({"per_target": per_target_counts, "featurized": len(ids), "features_dim": audit["features_dim"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
