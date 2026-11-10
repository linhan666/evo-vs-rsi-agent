#!/usr/bin/env python3
"""W: AutoGluon baseline, with locked scoring reproduced inside its own venv.

Why this file exists rather than reusing p8_automl.py
-----------------------------------------------------
AutoGluon ships a *predictor directory*, not a `model.joblib`. The shared
`evaluation.locked` and `screening.predict` tools load a joblib estimator and call
`predict_proba`, so they cannot score an AutoGluon predictor. Rather than teach the
agent-side tools about AutoGluon (and drag autogluon into the agent venv), the W arm
reproduces the scoring here, in `.venv-automl`, against the same protected files with
the same featurization parameters and the same metric code path.

Parity that matters
-------------------
* features: identical five representations, from the same `rdkit.featurize`;
* model families: bounded to linear / RF / extra trees / lightgbm / xgboost / catboost —
  the same vocabulary the agent arms can choose from;
* the ensemble is **kept** (`fit_weighted_ensemble=True`). AutoGluon's weighted ensemble
  is part of what the framework is; suppressing it would understate the baseline. The
  record reports base models and ensemble separately so the comparison can be read
  either way;
* budget: AutoGluon bounds search by time, not by trial count. The conversion is
  explicit (`--seconds-per-model`, measured at ~10 s/model on D2) and both the time
  limit and the number of models actually enumerated are recorded, so a reviewer can
  check the claimed parity instead of taking it on faith.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = "/home/linhan_cluster/evo_vs_rsi"
DATA = f"{ROOT}/scientific/.artifacts"
RUNS = f"{ROOT}/ops/phase7_runs"
sys.path.insert(0, f"{ROOT}/scientific/src")

from evovs_science.search.space import FEATURE_SPECS, fingerprint  # noqa: E402


def digest_of(path: Path) -> str:
    """Stable digest of a predictor directory (files sorted, each hashed in turn)."""
    sha = hashlib.sha256()
    for item in sorted(path.rglob("*")):
        if item.is_file():
            sha.update(str(item.relative_to(path)).encode())
            with item.open("rb") as handle:
                for chunk in iter(lambda: handle.read(1 << 20), b""):
                    sha.update(chunk)
    return sha.hexdigest()


TARGETS = (
    (1, "D2", "d(2)_dopamine_recept", "D2"),
    (2, "5HT", "5-hydroxytryptamine_", "5HT"),
    (3, "ADR", "adenosine_receptor_a", "ADR"),
    (4, "DRD2", "drd2", "DRD2"),
    (5, "MOR", "oprm1", "MOR"),
    (6, "CBR", "cannabinoid_receptor", "CBR"),
    (7, "KOR", "oprk1", "KOR"),
    (8, "CA2", "carbonic_anhydrase_2", "CA2"),
    (9, "PT", "prothrombin", "PT"),
)

HYPERPARAMETERS = {"GBM": {}, "CAT": {}, "XGB": {}, "RF": {}, "XT": {}, "LR": {}}


def read_dataset(path: str) -> tuple[dict[str, str], dict[str, int]]:
    smiles, labels = {}, {}
    with open(path, encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            mol_id = (row.get("molecule_chembl_id") or "").strip()
            if mol_id:
                smiles[mol_id] = (row.get("canonical_smiles") or "").strip()
                labels[mol_id] = int(float(row.get("label") or 0))
    return smiles, labels


def featurized(spec_id: str, rows: list[tuple[str, str]], cache: Path):
    """Featurise in-process with the shared implementation, caching the matrix."""
    import numpy as np
    from evovs_science.chemistry.featurize import featurize as do_featurize

    spec = FEATURE_SPECS[spec_id]
    cached = cache / f"{spec_id}.npz"
    if cached.exists():
        payload = np.load(cached, allow_pickle=True)
        return [str(x) for x in payload["ids"]], payload["X"], payload["D"]
    ids, matrix, descriptors, _invalid = do_featurize(
        rows, radius=spec["radius"], n_bits=spec["n_bits"], desc_set=spec["desc_set"])
    cache.mkdir(parents=True, exist_ok=True)
    np.savez_compressed(cached, ids=np.array(ids), X=matrix, D=descriptors)
    return ids, matrix, descriptors


def score_locked(predictor, target_code: str, endpoint: str, spec_id: str, workspace: Path, receipt: Path) -> dict:
    """Reproduce `evaluation.locked` output exactly, from inside the AutoGluon venv."""
    import numpy as np
    from sklearn.metrics import average_precision_score, roc_auc_score

    from evovs_science.evaluation.evaluate import read_test_rows
    from evovs_science.evaluation.locked import CHANNELS, PROTECTED
    from evovs_science.modeling.train import enrichment

    spec = FEATURE_SPECS[spec_id]
    subdir, test_name = CHANNELS[endpoint][target_code]
    test_csv = os.path.join(PROTECTED, subdir, test_name)
    rows = read_test_rows(test_csv, "molecule_chembl_id", "canonical_smiles", "label")
    usable = [(row["id"], row["smiles"]) for row in rows if row["label"] is not None]
    ids, matrix, descriptors = featurized(spec_id, usable, workspace / "locked_features")

    import pandas as pd
    features = np.hstack([matrix.astype(np.float32), descriptors]).astype(np.float32)
    frame = pd.DataFrame(features, columns=[f"f{i}" for i in range(features.shape[1])])
    probability = predictor.predict_proba(frame)[1]

    labels_by_id = {row["id"]: row["label"] for row in rows}
    y = np.asarray([labels_by_id[m] for m in ids], dtype=int)
    single = len(np.unique(y)) < 2
    metrics = {
        "auroc": None if single else round(float(roc_auc_score(y, probability)), 4),
        "auprc": None if single else round(float(average_precision_score(y, probability)), 4),
        "ef_at_1pct": None if single else enrichment(y, probability, 0.01),
        "ef_at_5pct": None if single else enrichment(y, probability, 0.05),
    }

    ticket = workspace.name
    output = os.path.join(
        PROTECTED, subdir,
        f"metrics_test_locked_agent_{endpoint}_{spec['desc_set']}_r{spec['radius']}_b{spec['n_bits']}_"
        f"{ticket}_{target_code}.json")
    record = {
        "schema_version": "1",
        "evaluator": "evovs_science.evaluation.evaluate (via AutoGluon wrapper)",
        "label_source": f"locked_agent_{endpoint}_{spec['desc_set']}",
        "desc_set": spec["desc_set"],
        "featurization": {"radius": spec["radius"], "n_bits": spec["n_bits"], "fingerprint": "morgan"},
        "counts": {"test_rows": len(rows), "featurized": len(ids), "invalid_smiles": 0,
                   "positives": int(y.sum()), "negatives": int((y == 0).sum())},
        "metrics": metrics,
        "model_sha256": digest_of(workspace / "predictor"),
        "test_csv_sha256": hashlib.sha256(Path(test_csv).read_bytes()).hexdigest(),
        "notes": ["Scored by the AutoGluon wrapper; metric code path shared with evaluate.py."],
    }
    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, "w", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.chmod(output, 0o600)

    receipt.parent.mkdir(parents=True, exist_ok=True)
    receipt.write_text(json.dumps({
        "target": target_code, "endpoint": endpoint, "desc_set": spec["desc_set"],
        "radius": spec["radius"], "n_bits": spec["n_bits"],
        "model": "predictor/", "protected_output": output, "metrics": metrics,
        "framework": "autogluon",
        "note": "summary only; the raw locked metrics file is not readable from the ticket",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return metrics


def screen(predictor, spec_id: str, library: str, workspace: Path, tag: str, top_k: int = 100) -> str | None:
    """Rank the screening library; same two CSV shapes the agent arms produce."""
    import numpy as np
    import pandas as pd
    from evovs_science.chemistry.featurize import read_smiles

    pairs = read_smiles(library, None, "id", "smiles")
    ids, matrix, descriptors = featurized(spec_id, pairs, workspace / "library_features")
    features = np.hstack([matrix.astype(np.float32), descriptors]).astype(np.float32)
    frame = pd.DataFrame(features, columns=[f"f{i}" for i in range(features.shape[1])])
    scores = predictor.predict_proba(frame)[1]

    order = np.argsort(-scores)
    runs = workspace / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    all_path = runs / f"{tag}_all.csv"
    with all_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "score"])
        for index in order:
            writer.writerow([ids[index], f"{scores[index]:.6f}"])
    top_path = runs / f"{tag}_topK.csv"
    with top_path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["rank", "id", "score"])
        for rank, index in enumerate(order[:top_k], 1):
            writer.writerow([rank, ids[index], f"{scores[index]:.6f}"])
    return str(top_path)


def one(seq: int, name: str, slug: str, code: str, budget: int, seconds_per_model: float,
        label: str, scratch_root: str) -> dict:
    import numpy as np
    from autogluon.tabular import TabularPredictor
    from sklearn.metrics import roc_auc_score

    dataset = f"{DATA}/chembl/{slug}/ki/dataset_p7b.csv"
    frozen = f"{DATA}/chembl/{slug}/ki/splits/frozen_p8_{slug}.json"
    library = f"{DATA}/zinc/library_100k.smi"
    tag = code.lower()
    workspace = Path(scratch_root) / tag
    workspace.mkdir(parents=True, exist_ok=True)

    _smiles, labels = read_dataset(dataset)
    split = json.load(open(frozen, encoding="utf-8"))["rows"]
    reps = list(FEATURE_SPECS)
    per_rep_seconds = max(15, int(round(budget * seconds_per_model / len(reps))))

    started = time.time()
    trials: list[dict] = []
    best = None

    for rep in reps:
        usable = [(m, s) for m, s in _smiles.items() if split.get(m) in ("train", "validation")
                  and m in labels]
        ids, matrix, descriptors = featurized(rep, usable, workspace / "features")
        import pandas as pd
        features = np.hstack([matrix.astype(np.float32), descriptors]).astype(np.float32)
        frame = pd.DataFrame(features, columns=[f"f{i}" for i in range(features.shape[1])])
        frame["label"] = [labels[m] for m in ids]
        mask = np.array([split.get(m) == "train" for m in ids])
        train_df, val_df = frame[mask], frame[~mask]
        if len(train_df) < 50 or len(val_df) < 20:
            trials.append({"representation": rep, "status": "too_few_rows"})
            continue

        rep_started = time.time()
        predictor = TabularPredictor(label="label", eval_metric="roc_auc",
                                     path=str(workspace / "predictors" / rep)).fit(
            train_data=train_df, tuning_data=val_df,
            hyperparameters=HYPERPARAMETERS,
            num_bag_folds=0, num_stack_levels=0, auto_stack=False,
            fit_weighted_ensemble=True,      # kept: the ensemble is part of AutoGluon
            time_limit=per_rep_seconds, verbosity=0)
        wall = round(time.time() - rep_started, 1)

        probability = predictor.predict_proba(val_df.drop(columns=["label"]))[1]
        val_auc = float(roc_auc_score(val_df["label"].to_numpy(), probability))
        board = predictor.leaderboard(silent=True)
        base_models = int((~board["model"].astype(str).str.startswith("WeightedEnsemble")).sum())
        entry = {"representation": rep, "val_auroc": round(val_auc, 4),
                 "models_base": base_models, "models_total": int(len(board)),
                 "best_model": str(predictor.model_best), "wall_seconds": wall,
                 "time_limit": per_rep_seconds}
        trials.append(entry)
        print(f"  [{tag}] {rep:8s} {str(predictor.model_best):22s} val {val_auc:.4f} "
              f"models {base_models}+{len(board) - base_models} wall {wall}s", flush=True)
        if best is None or val_auc > best["val_auroc"]:
            best = {**entry, "predictor": predictor}

    locked = None
    top_path = None
    if best:
        receipt = workspace / "evaluation" / f"{tag}_locked.json"
        locked = score_locked(best["predictor"], code, "Ki", best["representation"],
                              workspace, receipt)["auroc"]
        top_path = screen(best["predictor"], best["representation"], library, workspace, tag)

    base_total = sum(t["models_base"] for t in trials if "models_base" in t)
    total = sum(t["models_total"] for t in trials if "models_total" in t)
    return {
        "group": "w", "seq": seq, "target": name, "slug": slug, "label": label,
        "panel": "AutoML baseline: AutoGluon 1.6.3, no LLM, bounded model types x five feature representations",
        "framework": {"name": "autogluon.tabular", "version": _ag_version(),
                      "model_types": list(HYPERPARAMETERS), "ensemble": "kept",
                      "num_bag_folds": 0, "num_stack_levels": 0},
        "space_version": fingerprint(),
        "budget_limit": budget, "seconds_per_model": seconds_per_model,
        "budget_unit": f"wall-clock, {seconds_per_model:.0f}s per expected model; "
                       f"per representation {per_rep_seconds}s",
        "models_enumerated": total, "models_base": base_total,
        "configs_used": total,
        "stop_reason": "time_budget" if any(t.get("wall_seconds", 0) >= per_rep_seconds - 2
                                            for t in trials) else "search_exhausted",
        "per_representation": [{k: v for k, v in t.items() if k != "predictor"} for t in trials],
        "best_representation": best["representation"] if best else None,
        "best_model": best["best_model"] if best else None,
        "scratch": str(workspace),
        "auroc": best["val_auroc"] if best else None,
        "locked_auroc": None if locked is None else round(float(locked), 4),
        "top100": os.path.relpath(top_path, workspace) if top_path else None,
        "wall_seconds": round(time.time() - started, 2),
        "success": locked is not None,
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def _ag_version() -> str:
    try:
        from autogluon.tabular import __version__
        return __version__
    except Exception:
        return "unknown"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="p8 automl (AutoGluon)")
    parser.add_argument("--slug", default=None)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--budget", type=int, default=100)
    parser.add_argument("--seconds-per-model", type=float, default=12.0)
    parser.add_argument("--label", default="p8g100")
    parser.add_argument("--scratch-root", default=f"{DATA}/p8_automl_ag")
    args = parser.parse_args(argv)
    if not args.all and not args.slug:
        parser.error("give --all or --slug")

    chosen = [row for row in TARGETS if args.all or row[2] == args.slug]
    if not chosen:
        parser.error(f"--slug must be one of {[row[2] for row in TARGETS]}")

    os.makedirs(RUNS, exist_ok=True)
    ok = 0
    for seq, name, slug, code in chosen:
        record = one(seq, name, slug, code, args.budget, args.seconds_per_model, args.label,
                     f"{args.scratch_root}/{args.label}-b{args.budget}")
        path = os.path.join(RUNS, f"w_{seq:02d}_{code.lower()}_{args.label}.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(record, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        ok += 1 if record["success"] else 0
        print(json.dumps({"seq": seq, "target": name, "budget": args.budget,
                          "models": record["models_enumerated"],
                          "best_rep": record["best_representation"],
                          "best_model": record["best_model"],
                          "val": record["auroc"], "locked": record["locked_auroc"],
                          "wall": record["wall_seconds"]}, ensure_ascii=False), flush=True)
    print(json.dumps({"runs": len(chosen), "succeeded": ok}), flush=True)
    return 0 if ok == len(chosen) else 1


if __name__ == "__main__":
    raise SystemExit(main())
