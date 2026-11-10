#!/usr/bin/env python3
"""Is the FLAML baseline wrong, or is the data pipeline wrong?

The first FLAML run scored 0.582 val AUROC where our own models reach ~0.92 on the
same target. Two candidates: (a) the feature/label/split join is misaligned, or
(b) one trial per representation is simply too few draws for FLAML to find anything.

Distinguishing them is cheap: fit plain sklearn models on exactly the same matrices.
If sklearn also scores ~0.58 the join is broken; if it scores ~0.92 the join is fine
and the budget is the explanation.
"""
from __future__ import annotations

import json
import os
import sys

import numpy as np

ROOT = "/home/linhan_cluster/evo_vs_rsi"
DATA = os.path.join(ROOT, "scientific/.artifacts")
SLUG = "d(2)_dopamine_recept"
CODE = "D2"

dataset = os.path.join(DATA, "chembl", SLUG, "ki", "dataset_p7b.csv")
frozen = os.path.join(DATA, "chembl", SLUG, "ki", "splits", f"frozen_p8_{SLUG}.json")
npz = os.path.join(DATA, "p8_automl", "p8atest-b5", CODE.lower(), "features", "v1.npz")

import csv
labels, smiles = {}, {}
with open(dataset, encoding="utf-8") as handle:
    for row in csv.DictReader(handle):
        mol_id = (row.get("molecule_chembl_id") or "").strip()
        if mol_id:
            labels[mol_id] = int(float(row.get("label") or 0))
            smiles[mol_id] = row.get("canonical_smiles")

split = json.load(open(frozen, encoding="utf-8"))["rows"]
data = np.load(npz, allow_pickle=True)
ids = [str(x) for x in data["ids"]]
X = np.hstack([data["X"], data["D"]]).astype(np.float32)
print(f"matrix {X.shape} | ids {len(ids)} | labels {len(labels)} | split {len(split)}")

index = {mol_id: i for i, mol_id in enumerate(ids)}
train = [index[m] for m in ids if split.get(m) == "train" and m in labels]
val = [index[m] for m in ids if split.get(m) == "validation" and m in labels]
print(f"train {len(train)} | val {len(val)}")
ytr = np.array([labels[ids[i]] for i in train])
yva = np.array([labels[ids[i]] for i in val])
print(f"pos rate train {ytr.mean():.3f} | val {yva.mean():.3f}")

from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score

for name, model in (("logreg", LogisticRegression(max_iter=2000, class_weight="balanced")),
                    ("rf", RandomForestClassifier(n_estimators=200, random_state=17, n_jobs=4))):
    model.fit(X[train], ytr)
    score = roc_auc_score(yva, model.predict_proba(X[val])[:, 1])
    print(f"sklearn {name:7s} val AUROC {score:.4f}")

from flaml import AutoML
# class balance: 97% of rows are positive, so an unweighted fit is nearly constant.
# our ml.train exposes --sample-weights, so W must have the same lever.
pos = max(ytr.sum(), 1)
neg = max(len(ytr) - pos, 1)
w_tr = np.where(ytr == 1, len(ytr) / (2 * pos), len(ytr) / (2 * neg))
w_va = np.where(yva == 1, len(yva) / (2 * max(yva.sum(), 1)), len(yva) / (2 * max(len(yva) - yva.sum(), 1)))
for trials, weighted in ((5, True), (20, True)):
    automl = AutoML()
    kwargs = {"sample_weight": w_tr} if weighted else {}
    automl.fit(X_train=X[train], y_train=ytr, X_val=X[val], y_val=yva,
               max_iter=trials, time_budget=420, metric="roc_auc",
               estimator_list=["lrl1", "rf", "extra_tree", "xgboost", "lgbm"],
               eval_method="holdout", seed=17, verbose=0, **kwargs)
    score = roc_auc_score(yva, automl.predict_proba(X[val])[:, 1])
    print(f"flaml max_iter={trials:2d} weighted={str(weighted):5s} -> {str(automl.best_estimator):10s} "
          f"val AUROC {score:.4f}", flush=True)
