#!/usr/bin/env python3
"""Probe AutoGluon on one target before building the W baseline around it.

Run under scientific/.venv-automl. Checks, in order:
  1. it accepts our precomputed dense matrix (not just CSV paths),
  2. its model types can be bounded to the families the agent arms can also choose,
  3. it reports a validation AUROC in the range our own models reach (0.90-0.95;
     a 0.58 like FLAML's would mean the matrix or the metric is wrong),
  4. how many models it actually enumerates, which is what the trial budget must count,
  5. wall time, so the sweep can be sized.

Usage: .venv-automl/bin/python ops/p8_automl_probe.py
"""
from __future__ import annotations

import json
import time

import numpy as np
import pandas as pd

ROOT = "/home/linhan_cluster/evo_vs_rsi"
DATA = f"{ROOT}/scientific/.artifacts"
SLUG = "d(2)_dopamine_recept"
NPZ = f"{DATA}/p8_automl/p8at10-b10/d2/features/v1.npz"
FROZEN = f"{DATA}/chembl/{SLUG}/ki/splits/frozen_p8_{SLUG}.json"
DATASET = f"{DATA}/chembl/{SLUG}/ki/dataset_p7b.csv"

# The bounded model-type list: exactly the families the agent arms can pick from.
HYPERPARAMETERS = {"GBM": {}, "CAT": {}, "XGB": {}, "RF": {}, "XT": {}, "LR": {}}

import csv

labels = {}
with open(DATASET, encoding="utf-8") as handle:
    for row in csv.DictReader(handle):
        mol_id = (row.get("molecule_chembl_id") or "").strip()
        if mol_id:
            labels[mol_id] = int(float(row.get("label") or 0))

split = json.load(open(FROZEN, encoding="utf-8"))["rows"]
data = np.load(NPZ, allow_pickle=True)
ids = [str(x) for x in data["ids"]]
matrix = np.hstack([data["X"], data["D"]]).astype(np.float32)
print(f"matrix {matrix.shape}")

index = {m: i for i, m in enumerate(ids)}
train = [index[m] for m in ids if split.get(m) == "train" and m in labels]
val = [index[m] for m in ids if split.get(m) == "validation" and m in labels]
print(f"train {len(train)} | val {len(val)}")

columns = [f"f{i}" for i in range(matrix.shape[1])]
train_df = pd.DataFrame(matrix[train], columns=columns)
train_df["label"] = [labels[ids[i]] for i in train]
val_df = pd.DataFrame(matrix[val], columns=columns)
val_y = np.array([labels[ids[i]] for i in val])
val_df["label"] = val_y
print(f"pos rate train {train_df['label'].mean():.3f}")

from autogluon.tabular import TabularPredictor

started = time.time()
predictor = TabularPredictor(label="label", eval_metric="roc_auc",
                             path=f"{DATA}/p8_automl/probe_d2").fit(
    train_data=train_df,
    tuning_data=val_df,
    hyperparameters=HYPERPARAMETERS,
    num_bag_folds=0,          # no bagging: one model per family, so trials stay countable
    num_stack_levels=0,       # no stacking: keeps "models trained" equal to "configs tried"
    auto_stack=False,
    time_limit=420,
    verbosity=1,
)
wall = round(time.time() - started, 1)

probability = predictor.predict_proba(val_df.drop(columns=["label"]))[1]
from sklearn.metrics import roc_auc_score
val_auc = float(roc_auc_score(val_y, probability))
board = predictor.leaderboard(silent=True)

print(json.dumps({
    "wall_seconds": wall,
    "val_auroc": round(val_auc, 4),
    "models_enumerated": int(len(board)),
    "best_model": str(predictor.model_best),
    "families_present": sorted(board["model"].astype(str).str.split("_").str[0].unique().tolist()),
}, ensure_ascii=False))
print(board[["model", "score_val"]].to_string(index=False))
