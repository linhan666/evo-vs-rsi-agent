"""Train a small classifier on featurized molecules and report screening metrics.

Blueprint §9.5: report AUROC/AUPRC, Precision@K and EF@1%, and say plainly when a
metric is undefined (single-class test fold) instead of writing a misleading 0.
Labels here come from a **fixture**, never from real assay data; the output
records `label_source` so a report cannot quietly present it as measured activity.
"""

from __future__ import annotations

import argparse
import csv
import json
import os

import numpy as np

from ..manifest import describe_input, utc_now, write_manifest


def read_labels(path: str) -> dict[str, int]:
    labels: dict[str, int] = {}
    with open(path, newline="", encoding="utf-8") as handle:
        reader = csv.DictReader(handle)
        fields = {name.lower(): name for name in (reader.fieldnames or [])}
        if "id" not in fields or "label" not in fields:
            raise SystemExit(f"{path} needs 'id' and 'label' columns; found {reader.fieldnames}")
        for row in reader:
            labels[str(row[fields["id"]])] = int(float(row[fields["label"]]))
    return labels


def split_indices(y: np.ndarray, test_fraction: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
    rng = np.random.default_rng(seed)
    train_parts, test_parts = [], []
    for value in (0, 1):
        index = np.flatnonzero(y == value)
        rng.shuffle(index)
        cut = max(1, int(round(len(index) * test_fraction))) if len(index) > 1 else 0
        test_parts.append(index[:cut])
        train_parts.append(index[cut:])
    train = np.sort(np.concatenate(train_parts)) if train_parts else np.array([], dtype=int)
    test = np.sort(np.concatenate(test_parts)) if test_parts else np.array([], dtype=int)
    return train, test


def enrichment(y_true: np.ndarray, scores: np.ndarray, fraction: float) -> float | None:
    """EF@fraction: hits in the top fraction over the hits expected at random."""
    positives = int(y_true.sum())
    if positives == 0 or len(y_true) == 0:
        return None
    top = max(1, int(round(len(y_true) * fraction)))
    order = np.argsort(-scores)[:top]
    hits = int(y_true[order].sum())
    return round((hits / top) / (positives / len(y_true)), 3)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evovs-science train")
    parser.add_argument("--features", required=True, help="npz from rdkit.featurize")
    parser.add_argument("--labels", required=True, help="CSV with id,label")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--model", choices=["logreg", "rf"], default="logreg")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--test-fraction", type=float, default=0.3)
    parser.add_argument("--label-source", default="fixture")
    args = parser.parse_args(argv)

    import joblib
    import sklearn
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.linear_model import LogisticRegression
    from sklearn.metrics import accuracy_score, average_precision_score, f1_score, roc_auc_score
    from sklearn.pipeline import make_pipeline
    from sklearn.preprocessing import StandardScaler

    data = np.load(args.features, allow_pickle=True)
    ids = [str(item) for item in data["ids"]]
    matrix, descriptors = data["X"], data["D"]

    labels = read_labels(args.labels)
    keep = [index for index, molecule_id in enumerate(ids) if molecule_id in labels]
    if len(keep) < 4:
        print(json.dumps({"error": "NOT_ENOUGH_RELIABLE_DATA", "joined": len(keep)}))
        return 3

    features = np.hstack([matrix[keep].astype(np.float32), descriptors[keep]]).astype(np.float32)
    y = np.asarray([labels[ids[index]] for index in keep], dtype=int)
    kept_ids = [ids[index] for index in keep]

    train, test = split_indices(y, args.test_fraction, args.seed)
    if len(test) == 0 or len(train) == 0:
        print(json.dumps({"error": "NOT_ENOUGH_RELIABLE_DATA", "train": len(train), "test": len(test)}))
        return 3

    estimator = LogisticRegression(max_iter=2000, class_weight="balanced") if args.model == "logreg" \
        else RandomForestClassifier(n_estimators=200, random_state=args.seed, n_jobs=1)
    model = make_pipeline(StandardScaler(), estimator)
    model.fit(features[train], y[train])

    scores = model.predict_proba(features[test])[:, 1]
    predicted = (scores >= 0.5).astype(int)
    single_class = len(np.unique(y[test])) < 2

    metrics = {
        "schema_version": "1",
        "created_at": utc_now(),
        "label_source": args.label_source,
        "model": args.model,
        "seed": args.seed,
        "counts": {"joined": int(len(y)), "train": int(len(train)), "test": int(len(test)),
                   "positives": int(y.sum()), "test_positives": int(y[test].sum())},
        "metrics": {
            "auroc": None if single_class else round(float(roc_auc_score(y[test], scores)), 4),
            "auprc": None if single_class else round(float(average_precision_score(y[test], scores)), 4),
            "accuracy": round(float(accuracy_score(y[test], predicted)), 4),
            "f1": round(float(f1_score(y[test], predicted, zero_division=0)), 4),
            "ef_at_1pct": None if single_class else enrichment(y[test], scores, 0.01),
            "ef_at_5pct": None if single_class else enrichment(y[test], scores, 0.05),
        },
        "notes": ["Metrics come from a fixture label set; they describe the pipeline, not GPCR activity."]
                 + (["Test fold has a single class; ranking metrics are undefined."] if single_class else []),
        "versions": {"sklearn": sklearn.__version__, "numpy": np.__version__},
    }

    os.makedirs(args.output_dir, exist_ok=True)
    metrics_path = os.path.join(args.output_dir, "metrics.json")
    with open(metrics_path, "w", encoding="utf-8") as handle:
        json.dump(metrics, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    predictions_path = os.path.join(args.output_dir, "predictions.csv")
    with open(predictions_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "label", "score", "split"])
        for index in train:
            writer.writerow([kept_ids[index], int(y[index]), "", "train"])
        for position, index in enumerate(test):
            writer.writerow([kept_ids[index], int(y[index]), round(float(scores[position]), 6), "test"])

    model_path = os.path.join(args.output_dir, "model.joblib")
    joblib.dump(model, model_path)

    write_manifest(
        args.output_dir,
        [
            {"path": metrics_path, "content_type": "application/json", "description": "metrics and counts"},
            {"path": predictions_path, "content_type": "text/csv", "description": "per-molecule scores"},
            {"path": model_path, "content_type": "application/octet-stream", "description": "fitted pipeline"},
        ],
        generator="evovs_science.modeling.train",
        inputs=[describe_input(args.features), describe_input(args.labels)],
        parameters={"model": args.model, "seed": args.seed, "test_fraction": args.test_fraction},
        extra={"label_source": args.label_source, "metrics": metrics["metrics"]},
    )

    print(json.dumps({"metrics": metrics["metrics"], "counts": metrics["counts"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
