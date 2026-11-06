"""Train a small classifier on featurized molecules and report screening metrics.

Blueprint §9.4/§9.5 and P2-04:
  * when `--split-manifest` is given, fitting uses **only** the manifest's train
    molecules and the reported metrics come from its validation molecules — the
    internal random split is then not used at all;
  * the final test set is never read here; only the independent evaluator sees it;
  * single-class folds report `null` instead of a misleading 0;
  * labels carry `label_source` so fixture data can never masquerade as assay data.
"""

from __future__ import annotations

import argparse
import csv
import json
import os

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, average_precision_score, f1_score, roc_auc_score
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from ..manifest import describe_input, utc_now, write_manifest

MODELS = ("logreg", "rf", "xgboost", "catboost")


def build_model(kind: str, seed: int):
    """Construct a classifier; a missing optional library is a clear error."""
    if kind == "logreg":
        return LogisticRegression(max_iter=2000, class_weight="balanced")
    if kind == "rf":
        return RandomForestClassifier(n_estimators=200, random_state=seed, n_jobs=1)
    if kind == "xgboost":
        try:
            from xgboost import XGBClassifier
        except ImportError as error:
            raise SystemExit("xgboost is not installed in this environment; pip install xgboost") from error
        return XGBClassifier(n_estimators=300, max_depth=6, learning_rate=0.1, subsample=0.9,
                             colsample_bytree=0.9, min_child_weight=1.0, random_state=seed, n_jobs=1,
                             eval_metric="logloss", tree_method="hist", verbosity=0)
    if kind == "catboost":
        try:
            from catboost import CatBoostClassifier
        except ImportError as error:
            raise SystemExit("catboost is not installed in this environment; pip install catboost") from error
        return CatBoostClassifier(iterations=300, depth=6, learning_rate=0.1, random_seed=seed,
                                  verbose=False, allow_writing_files=False)
    raise SystemExit(f"unknown model kind: {kind}")


def read_labels(path: str, id_column: str = "id", label_column: str = "label",
                resolution: dict | None = None) -> tuple[dict[str, int], dict[str, float]]:
    """Read (id -> label) weights from a table.

    Column names go through the shared alias resolution (molecule_chembl_id stands
    in for id, and so on): the failure this fixes is a ticket that retried `id`
    against a ChEMBL export twelve times. `resolution` receives any substitution
    that happened, so a caller can report it instead of doing it silently.
    """
    from ..chemistry.featurize import resolve_columns

    columns = resolve_columns(path, {"id": id_column, "label": label_column})
    if resolution is not None:
        resolution.update(columns.get("resolved", {}))
    if "id" not in columns or "label" not in columns:
        raise SystemExit(f"{path} needs an id and a label column; resolved {columns}")
    labels: dict[str, int] = {}
    weights: dict[str, float] = {}
    with open(path, newline="", encoding="utf-8-sig") as handle:
        reader = csv.DictReader(handle)
        fields = {name.lower(): name for name in (reader.fieldnames or [])}
        weight_field = fields.get("weight")
        for row in reader:
            raw = row[columns["label"]]
            if raw == "":
                continue  # grey-zone rows are present but deliberately unlabeled
            molecule = str(row[columns["id"]])
            labels[molecule] = int(float(raw))
            if weight_field:
                weights[molecule] = float(row[weight_field])
    return labels, weights


def read_split_ids(manifest_path: str) -> dict[str, set[str]]:
    with open(manifest_path, encoding="utf-8") as handle:
        manifest = json.load(handle)
    molecules = manifest.get("molecules") or {}
    if not {"train", "validation"} <= set(molecules):
        raise SystemExit(f"{manifest_path} lacks train/validation molecule lists")
    return {name: set(members) for name, members in molecules.items()}


def split_indices(y: np.ndarray, test_fraction: float, seed: int) -> tuple[np.ndarray, np.ndarray]:
    """Stratified random fallback used only when no scaffold manifest is supplied."""
    rng = np.random.default_rng(seed)
    train_parts, val_parts = [], []
    for value in (0, 1):
        index = np.flatnonzero(y == value)
        rng.shuffle(index)
        cut = max(1, int(round(len(index) * test_fraction))) if len(index) > 1 else 0
        val_parts.append(index[:cut])
        train_parts.append(index[cut:])
    train = np.sort(np.concatenate(train_parts)) if train_parts else np.array([], dtype=int)
    val = np.sort(np.concatenate(val_parts)) if val_parts else np.array([], dtype=int)
    return train, val


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
    parser.add_argument("--labels", required=True, help="CSV with id,label (or matching columns)")
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--model", choices=list(MODELS), default="logreg")
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--test-fraction", type=float, default=0.3,
                        help="internal random split, used only without --split-manifest")
    parser.add_argument("--split-manifest", default=None,
                        help="split_manifest.json from data.normalize; train/validation then follow scaffolds")
    parser.add_argument("--no-validation", action="store_true",
                        help="pooled mode: fit on every row; metrics come from the locked evaluator per target")
    parser.add_argument("--sample-weights", action="store_true",
                        help="use the weight column from --labels as per-row fit weights (candidate2 recalibration)")
    parser.add_argument("--label-source", default="fixture")
    parser.add_argument("--label-id-column", default="id")
    parser.add_argument("--label-column", default="label")
    args = parser.parse_args(argv)

    data = np.load(args.features, allow_pickle=True)
    ids = [str(item) for item in data["ids"]]
    matrix, descriptors = data["X"], data["D"]

    resolved: dict = {}
    labels, sample_weights = read_labels(args.labels, args.label_id_column, args.label_column, resolved)
    keep = [index for index, molecule_id in enumerate(ids) if molecule_id in labels]
    if len(keep) < 4:
        print(json.dumps({"error": "NOT_ENOUGH_RELIABLE_DATA", "joined": len(keep)}))
        return 3

    features = np.hstack([matrix[keep].astype(np.float32), descriptors[keep]]).astype(np.float32)
    y = np.asarray([labels[ids[index]] for index in keep], dtype=int)
    kept_ids = [ids[index] for index in keep]

    if args.no_validation:
        train = np.arange(len(y))
        val = train
        split_strategy = "pooled-fit-all"
    elif args.split_manifest:
        split_ids = read_split_ids(args.split_manifest)
        train = np.asarray([index for index, molecule_id in enumerate(kept_ids)
                            if molecule_id in split_ids["train"]], dtype=int)
        val = np.asarray([index for index, molecule_id in enumerate(kept_ids)
                          if molecule_id in split_ids["validation"]], dtype=int)
        split_strategy = "scaffold-manifest"
        if len(train) == 0 or len(val) == 0:
            print(json.dumps({"error": "NOT_ENOUGH_RELIABLE_DATA", "strategy": split_strategy,
                              "train": len(train), "validation": len(val)}))
            return 3
    else:
        train, val = split_indices(y, args.test_fraction, args.seed)
        split_strategy = "internal-random"

    model = make_pipeline(StandardScaler(), build_model(args.model, args.seed))
    if args.sample_weights:
        step_name = model.steps[-1][0]
        weight_vector = np.asarray([sample_weights.get(kept_ids[index], 1.0) for index in train], dtype=np.float64)
        model.fit(features[train], y[train], **{f"{step_name}__sample_weight": weight_vector})
    else:
        model.fit(features[train], y[train])
    if args.no_validation:
        metrics = {
            "schema_version": "1", "created_at": utc_now(), "label_source": args.label_source,
            "model": args.model, "seed": args.seed, "split_strategy": split_strategy,
            "sample_weights": bool(args.sample_weights),
            "counts": {"fitted_rows": int(len(train)), "positives": int(y.sum())},
            "metrics": {key: None for key in ("auroc", "auprc", "accuracy", "f1", "ef_at_1pct", "ef_at_5pct")},
            "notes": ["Pooled fit-all model: per-target metrics come only from the locked evaluator."],
            "versions": {"sklearn": __import__("sklearn").__version__, "numpy": np.__version__},
        }
        os.makedirs(args.output_dir, exist_ok=True)
        if resolved:  # only when a requested column stood in for another
            metrics["columns_resolved"] = resolved
        metrics_path = os.path.join(args.output_dir, "metrics.json")
        with open(metrics_path, "w", encoding="utf-8") as handle:
            json.dump(metrics, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        model_path = os.path.join(args.output_dir, "model.joblib")
        __import__("joblib").dump(model, model_path)
        write_manifest(
            args.output_dir,
            [
                {"path": metrics_path, "content_type": "application/json", "description": "counts only"},
                {"path": model_path, "content_type": "application/octet-stream", "description": "pooled pipeline"},
            ],
            generator="evovs_science.modeling.train",
            inputs=[describe_input(args.features), describe_input(args.labels)],
            parameters={"model": args.model, "seed": args.seed, "split_strategy": split_strategy},
            extra={"label_source": args.label_source},
        )
        print(json.dumps({"split_strategy": split_strategy, "fitted_rows": int(len(train))}))
        return 0
    scores = model.predict_proba(features[val])[:, 1]
    predicted = (scores >= 0.5).astype(int)
    single_class = len(np.unique(y[val])) < 2

    metrics = {
        "schema_version": "1",
        "created_at": utc_now(),
        "label_source": args.label_source,
        "model": args.model,
        "seed": args.seed,
        "split_strategy": split_strategy,
        "counts": {"joined": int(len(y)), "train": int(len(train)), "validation": int(len(val)),
                   "positives": int(y.sum()), "validation_positives": int(y[val].sum())},
        "metrics": {
            "auroc": None if single_class else round(float(roc_auc_score(y[val], scores)), 4),
            "auprc": None if single_class else round(float(average_precision_score(y[val], scores)), 4),
            "accuracy": round(float(accuracy_score(y[val], predicted)), 4),
            "f1": round(float(f1_score(y[val], predicted, zero_division=0)), 4),
            "ef_at_1pct": None if single_class else enrichment(y[val], scores, 0.01),
            "ef_at_5pct": None if single_class else enrichment(y[val], scores, 0.05),
        },
        "notes": [
            f"Metrics are computed on the {split_strategy} validation molecules.",
            "The locked final test set is evaluated separately by evovs_science.evaluation.evaluate.",
        ] + (["Validation fold has a single class; ranking metrics are undefined."] if single_class else []),
        "versions": {"sklearn": __import__("sklearn").__version__, "numpy": np.__version__},
    }

    os.makedirs(args.output_dir, exist_ok=True)
    if resolved:  # only when a requested column stood in for another
        metrics["columns_resolved"] = resolved
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
        for position, index in enumerate(val):
            writer.writerow([kept_ids[index], int(y[index]), round(float(scores[position]), 6), "validation"])

    model_path = os.path.join(args.output_dir, "model.joblib")
    __import__("joblib").dump(model, model_path)

    write_manifest(
        args.output_dir,
        [
            {"path": metrics_path, "content_type": "application/json", "description": "metrics and counts"},
            {"path": predictions_path, "content_type": "text/csv", "description": "per-molecule scores"},
            {"path": model_path, "content_type": "application/octet-stream", "description": "fitted pipeline"},
        ],
        generator="evovs_science.modeling.train",
        inputs=[describe_input(args.features), describe_input(args.labels)],
        parameters={"model": args.model, "seed": args.seed, "split_strategy": split_strategy},
        extra={"label_source": args.label_source, "metrics": metrics["metrics"]},
    )

    print(json.dumps({"metrics": metrics["metrics"], "counts": metrics["counts"],
                      "split_strategy": split_strategy}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
