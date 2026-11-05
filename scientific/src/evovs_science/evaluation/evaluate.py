"""Independent evaluator for the locked final test set (Blueprint §9.4, P2-04).

Only this component may read final-test labels. It is run by the operator or the
evaluation service, never registered as an Agent tool, and it writes its metrics
next to the protected file rather than into any workspace a modelling agent can
read. The model artifact is hashed so a result can always be tied to exactly one
fitted pipeline.
"""

from __future__ import annotations

import argparse
import csv
import json
import os

import numpy as np

from ..chemistry.featurize import featurize, read_smiles
from ..manifest import describe_input, sha256_file, utc_now, write_manifest
from ..modeling.train import enrichment

TARGET_ORDER = ("MOR", "KOR", "DRD2")  # pre-registered in docs/TRANSFER_DESIGN.md


def read_test_rows(path: str, id_column: str, smiles_column: str, label_column: str) -> list[dict]:
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = {name.lower(): name for name in (reader.fieldnames or [])}
        for required in (id_column, smiles_column, label_column):
            if required.lower() not in fields:
                raise SystemExit(f"{path} has no {required!r} column; found {reader.fieldnames}")
        return [
            {
                "id": row[fields[id_column.lower()]],
                "smiles": row[fields[smiles_column.lower()]],
                "label": int(float(row[fields[label_column.lower()]])) if row[fields[label_column.lower()]] != "" else None,
            }
            for row in reader
        ]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evovs-science evaluate")
    parser.add_argument("--test-csv", required=True, help="protected final-test CSV (labels included)")
    parser.add_argument("--model", required=True, help="fitted pipeline from modeling.train")
    parser.add_argument("--output", required=True, help="metrics_test_locked.json path")
    parser.add_argument("--radius", type=int, default=2, help="must match the featurization the model was trained on")
    parser.add_argument("--n-bits", type=int, default=2048)
    parser.add_argument("--id-column", default="molecule_chembl_id")
    parser.add_argument("--smiles-column", default="canonical_smiles")
    parser.add_argument("--label-column", default="label")
    parser.add_argument("--label-source", required=True, help="recorded verbatim, e.g. chembl37_ki_pX7_6")
    parser.add_argument("--desc-set", choices=("v1", "v2"), default=None,
                        help="must match the descriptor set the model was trained on")
    parser.add_argument("--target-indicator", choices=list(TARGET_ORDER), default=None,
                        help="pooled model: append the pre-registered one-hot for this target")
    parser.add_argument("--dump-predictions", default=None,
                        help="write per-molecule scores here (protected directory; input to bootstrap CIs)")
    args = parser.parse_args(argv)

    import joblib
    import sklearn

    rows = read_test_rows(args.test_csv, args.id_column, args.smiles_column, args.label_column)
    featurizable = [(row["id"], row["smiles"]) for row in rows if row["label"] is not None]
    ids, matrix, descriptors, invalid = featurize(featurizable, radius=args.radius, n_bits=args.n_bits,
                                                  desc_set=args.desc_set)
    if not ids:
        raise SystemExit("no test molecule could be featurized")

    labels_by_id = {row["id"]: row["label"] for row in rows}
    y = np.asarray([labels_by_id[molecule_id] for molecule_id in ids], dtype=int)
    features = np.hstack([matrix.astype(np.float32), descriptors]).astype(np.float32)

    if args.target_indicator:
        onehot = np.zeros((features.shape[0], len(TARGET_ORDER)), dtype=np.float32)
        onehot[:, TARGET_ORDER.index(args.target_indicator)] = 1.0
        features = np.hstack([features, onehot]).astype(np.float32)

    model = joblib.load(args.model)
    scores = model.predict_proba(features)[:, 1]

    single_class = len(np.unique(y)) < 2
    metrics = {
        "auroc": None if single_class else round(float(__import__("sklearn.metrics", fromlist=["roc_auc_score"]).roc_auc_score(y, scores)), 4),
        "auprc": None if single_class else round(float(__import__("sklearn.metrics", fromlist=["average_precision_score"]).average_precision_score(y, scores)), 4),
        "ef_at_1pct": None if single_class else enrichment(y, scores, 0.01),
        "ef_at_5pct": None if single_class else enrichment(y, scores, 0.05),
    }

    if args.dump_predictions:
        dump_path = os.path.abspath(args.dump_predictions)
        os.makedirs(os.path.dirname(dump_path), exist_ok=True)
        with open(dump_path, "w", encoding="utf-8") as handle:
            json.dump({"target": args.target_indicator or args.label_source,
                       "records": [{"id": ids[index], "label": int(y[index]), "score": float(scores[index])}
                                   for index in range(len(ids))]}, handle, ensure_ascii=False, indent=2)
        os.chmod(dump_path, 0o600)

    record = {
        "schema_version": "1",
        "created_at": utc_now(),
        "test_locked": True,
        "evaluator": "evovs_science.evaluation.evaluate",
        "label_source": args.label_source,
        "target_indicator": args.target_indicator,
        "desc_set": args.desc_set,
        "featurization": {"radius": args.radius, "n_bits": args.n_bits, "fingerprint": "morgan"},
        "counts": {"test_rows": len(rows), "featurized": len(ids), "invalid_smiles": len(invalid),
                   "positives": int(y.sum()), "negatives": int((y == 0).sum())},
        "metrics": metrics,
        "model_sha256": sha256_file(args.model),
        "test_csv_sha256": sha256_file(args.test_csv),
        "versions": {"sklearn": sklearn.__version__, "numpy": np.__version__},
        "notes": [
            "These metrics cover the locked final test set only; the modelling agent never reads these labels.",
            "Re-run this evaluator after any model acceptance; the output file is the only sanctioned release channel.",
        ],
    }

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.chmod(args.output, 0o600)

    write_manifest(
        os.path.dirname(os.path.abspath(args.output)),
        [{"path": args.output, "content_type": "application/json", "description": "locked final-test metrics"}],
        generator="evovs_science.evaluation.evaluate",
        inputs=[describe_input(args.test_csv), {"path": os.path.basename(args.model), "sha256": record["model_sha256"]}],
        parameters={"label_source": args.label_source, "radius": args.radius, "n_bits": args.n_bits},
        extra={"test_locked": True, "metrics": metrics},
    )

    print(json.dumps({"counts": record["counts"], "metrics": metrics, "output": args.output}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
