#!/usr/bin/env python3
"""W: an established AutoML baseline, not a hand-built grid.

The design calls for W to be a real open-source AutoML with no LLM in the loop,
searching a bounded space of algorithm families and feature representations. The
first version of this file walked a grid I had invented, which measures my grid
rather than the state of the art. This one drives FLAML (Microsoft, Apache-2.0),
which is what "use an existing authoritative AutoML" means here.

Parity with the agent arms is kept on three axes:

* **feature representations** — the same five ECFP variants, produced by the same
  `rdkit.featurize` CLI, so both sides see identical matrices;
* **algorithm families** — FLAML's search is restricted to the families the agent
  arms can also choose (linear, random forest, extra trees, xgboost, catboost,
  lightgbm);
* **trial budget** — FLAML gets `max_iter = budget / n_representations` per
  representation, so total evaluated configurations equal the agent's draw budget.
  `time_budget` is only a safety cap, and the record says which bound fired.

The best model by frozen-validation AUROC is then screened and locked with the same
CLI the agent arms use, so the delivered artifacts are format-identical.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

import numpy as np

ROOT = "/home/linhan_cluster/evo_vs_rsi"
DATA = os.path.join(ROOT, "scientific/.artifacts")
PYTHON = os.path.join(ROOT, "scientific/.venv/bin/python")
RUNS = os.path.join(ROOT, "ops/phase7_runs")
sys.path.insert(0, os.path.join(ROOT, "scientific/src"))
from evovs_science.search.space import FEATURE_SPECS, fingerprint  # noqa: E402

ESTIMATORS = ["lrl1", "rf", "extra_tree", "xgboost", "catboost", "lgbm"]

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


def run(argv: list[str], cwd: str) -> dict:
    started = time.time()
    done = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
    return {"argv": argv, "exit_code": done.returncode,
            "wall_seconds": round(time.time() - started, 2),
            "stderr_tail": done.stderr.strip().splitlines()[-2:]}


def read_dataset(path: str) -> tuple[dict[str, str], dict[str, int]]:
    import csv
    smiles, labels = {}, {}
    with open(path, encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            mol_id = (row.get("molecule_chembl_id") or "").strip()
            if not mol_id:
                continue
            smiles[mol_id] = (row.get("canonical_smiles") or "").strip()
            labels[mol_id] = int(float(row.get("label") or 0))
    return smiles, labels


def features(spec_id: str, dataset: str, scratch: str) -> tuple[np.ndarray | None, list[str], dict]:
    spec = FEATURE_SPECS[spec_id]
    rel = f"features/{spec_id}.npz"
    path = os.path.join(scratch, rel)
    if not os.path.exists(path):
        record = run([PYTHON, "-m", "evovs_science.chemistry.featurize",
                      "--input", dataset, "--output", rel, "--report", f"features/{spec_id}.json",
                      "--id-column", "molecule_chembl_id", "--smiles-column", "canonical_smiles",
                      "--desc-set", spec["desc_set"], "--radius", str(spec["radius"]),
                      "--n-bits", str(spec["n_bits"])], scratch)
        if record["exit_code"] != 0:
            return None, [], record
    else:
        record = {"cached": True, "exit_code": 0}
    data = np.load(path, allow_pickle=True)
    ids = [str(item) for item in data["ids"]]
    matrix = np.hstack([data["X"], data["D"]]).astype(np.float32)
    return matrix, ids, record


def one(seq: int, name: str, slug: str, code: str, budget: int, label: str, scratch_root: str) -> dict:
    import joblib
    from flaml import AutoML

    dataset = os.path.join(DATA, "chembl", slug, "ki", "dataset_p7b.csv")
    frozen = os.path.join(DATA, "chembl", slug, "ki", "splits", f"frozen_p8_{slug}.json")
    library = os.path.join(DATA, "zinc", "library_100k.smi")
    tag = code.lower()
    scratch = os.path.join(scratch_root, tag)
    os.makedirs(scratch, exist_ok=True)

    split = json.load(open(frozen, encoding="utf-8"))["rows"]
    _smiles, labels = read_dataset(dataset)
    reps = list(FEATURE_SPECS)
    per_rep = max(1, budget // len(reps))

    started = time.time()
    trials: list[dict] = []
    best = None

    for rep in reps:
        matrix, ids, featurize_record = features(rep, dataset, scratch)
        if matrix is None:
            trials.append({"representation": rep, "status": "featurize_failed",
                           "stderr": featurize_record.get("stderr_tail")})
            continue
        index = {mol_id: row for row, mol_id in enumerate(ids)}
        train_rows = [index[m] for m in ids if split.get(m) == "train" and m in labels]
        val_rows = [index[m] for m in ids if split.get(m) == "validation" and m in labels]
        if len(train_rows) < 50 or len(val_rows) < 20:
            trials.append({"representation": rep, "status": "too_few_rows",
                           "train": len(train_rows), "val": len(val_rows)})
            continue
        x_train = matrix[train_rows]
        y_train = np.asarray([labels[ids[r]] for r in train_rows], dtype=int)
        x_val = matrix[val_rows]
        y_val = np.asarray([labels[ids[r]] for r in val_rows], dtype=int)

        # 97% of rows are positive on this task, so an unweighted fit is close to a
        # constant predictor: unweighted FLAML scored 0.58-0.65 val AUROC where a
        # balanced logistic regression scored 0.94. ml.train exposes --sample-weights
        # for exactly this reason, so the baseline gets the same lever.
        n_pos = max(int(y_train.sum()), 1)
        n_neg = max(len(y_train) - n_pos, 1)
        weights = np.where(y_train == 1, len(y_train) / (2.0 * n_pos),
                           len(y_train) / (2.0 * n_neg))

        automl = AutoML()
        rep_started = time.time()
        timed_out = False
        try:
            automl.fit(X_train=x_train, y_train=y_train, X_val=x_val, y_val=y_val,
                       sample_weight=weights,
                       max_iter=per_rep, time_budget=max(120, 45 * per_rep), metric="roc_auc",
                       estimator_list=ESTIMATORS, eval_method="holdout",
                       seed=17, verbose=0, early_stop=True)
        except Exception as error:  # a family that cannot run must not kill the arm
            trials.append({"representation": rep, "status": "automl_error",
                           "error": str(error)[:200]})
            continue
        wall = round(time.time() - rep_started, 2)
        timed_out = wall >= max(120, 45 * per_rep) - 10
        try:
            from sklearn.metrics import roc_auc_score
            val_auroc = float(roc_auc_score(y_val, automl.predict_proba(x_val)[:, 1]))
        except Exception:
            val_auroc = None
        entry = {"representation": rep, "best_estimator": getattr(automl, "best_estimator", None),
                 "best_config": json.loads(json.dumps(getattr(automl, "best_config", {}), default=str)),
                 "val_auroc": val_auroc, "trials": per_rep, "wall_seconds": wall,
                 "stopped_by": "time_budget" if timed_out else "max_iter"}
        print(f"  [{tag}] {rep:8s} {str(entry['best_estimator']):10s} val {val_auroc} "
              f"trials {per_rep} wall {wall}s", flush=True)
        trials.append(entry)
        if val_auroc is not None and (best is None or val_auroc > best["val_auroc"]):
            rel_dir = f"models/automl_{rep}"
            os.makedirs(os.path.join(scratch, rel_dir), exist_ok=True)
            joblib.dump(automl.model, os.path.join(scratch, rel_dir, "model.joblib"))
            best = {**entry, "model_dir": rel_dir}

    locked = None
    steps: list[dict] = []
    if best:
        model = f"{best['model_dir']}/model.joblib"
        steps.append(run([PYTHON, "-m", "evovs_science.screening.predict",
                          "--model", model, "--library", library,
                          "--output", f"runs/{tag}_all.csv", "--top-output", f"runs/{tag}_topK.csv",
                          "--report", "runs/screening_report.json", "--top-k", "100"], scratch))
        steps.append(run([PYTHON, "-m", "evovs_science.evaluation.locked",
                          "--target", code, "--endpoint", "Ki",
                          "--desc-set", FEATURE_SPECS[best["representation"]]["desc_set"],
                          "--radius", str(FEATURE_SPECS[best["representation"]]["radius"]),
                          "--n-bits", str(FEATURE_SPECS[best["representation"]]["n_bits"]),
                          "--model", model, "--workspace", ".",
                          "--receipt", f"evaluation/{tag}_locked.json"], scratch))
        receipt = os.path.join(scratch, "evaluation", f"{tag}_locked.json")
        if os.path.exists(receipt):
            try:
                locked = (json.load(open(receipt, encoding="utf-8")).get("metrics") or {}).get("auroc")
            except (ValueError, OSError):
                locked = None

    used = sum(int(entry.get("trials") or 0) for entry in trials if entry.get("val_auroc") is not None)
    return {
        "group": "w", "seq": seq, "target": name, "slug": slug, "label": label,
        "panel": "AutoML baseline: FLAML, no LLM, bounded estimator list and feature set",
        "automl": {"framework": "flaml", "estimators": ESTIMATORS, "seed": 17,
                   "trial_budget_rule": "budget divided evenly across the five representations"},
        "space_version": fingerprint(),
        "budget_limit": budget, "configs_used": used,
        "stop_reason": "budget_exhausted" if used >= budget else "stopped_early",
        "per_representation": trials,
        "best_representation": best["representation"] if best else None,
        "best_estimator": best["best_estimator"] if best else None,
        "best_config": best["best_config"] if best else None,
        "scratch": scratch,
        "auroc": best["val_auroc"] if best else None,
        "locked_auroc": locked,
        "wall_seconds": round(time.time() - started, 2),
        "jobs_failed": sum(1 for step in steps if step["exit_code"] != 0),
        "success": locked is not None,
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="p8 automl baseline (group W)")
    parser.add_argument("--slug", default=None)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--budget", type=int, default=100)
    parser.add_argument("--label", default="p8a100")
    parser.add_argument("--scratch-root", default=os.path.join(DATA, "p8_automl"))
    args = parser.parse_args(argv)
    if not args.all and not args.slug:
        parser.error("give --all or --slug")

    chosen = [row for row in TARGETS if args.all or row[2] == args.slug]
    if not chosen:
        parser.error(f"--slug must be one of {[row[2] for row in TARGETS]}")

    os.makedirs(RUNS, exist_ok=True)
    ok = 0
    for seq, name, slug, code in chosen:
        record = one(seq, name, slug, code, args.budget, args.label,
                     os.path.join(args.scratch_root, f"{args.label}-b{args.budget}"))
        path = os.path.join(RUNS, f"w_{seq:02d}_{code.lower()}_{args.label}.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(record, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        ok += 1 if record["success"] else 0
        print(json.dumps({"seq": seq, "target": name, "budget": args.budget,
                          "trials": record["configs_used"],
                          "best_rep": record["best_representation"],
                          "best_estimator": record["best_estimator"],
                          "val": record["auroc"], "locked": record["locked_auroc"],
                          "wall": record["wall_seconds"]}, ensure_ascii=False), flush=True)
    print(json.dumps({"runs": len(chosen), "succeeded": ok}), flush=True)
    return 0 if ok == len(chosen) else 1


if __name__ == "__main__":
    raise SystemExit(main())
