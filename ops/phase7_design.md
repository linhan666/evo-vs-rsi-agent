# Phase 7: Sequential RSI Experiment Design

## Problem restated

For each drug target, the best modelling pipeline differs: representation,
feature fusion, classification vs regression, algorithm family, hyperparameters.
Existing approaches (DTI models, AutoML) explore from scratch per target.
The question is whether a self-improving harness (RSI) can **leverage historical
modelling experience** to build reliable target-specific predictors with **less
compute and less human intervention**, and keep improving.

## Two comparisons

| Comparison | Question | Metric |
|---|---|---|
| **Budget efficiency** | How much less compute/tokens does RSI need to reach optimal quality? | Wall clock, tokens, jobs at matched AUROC |
| **Fixed-budget quality** | At the same budget, does RSI find a better model? | AUROC / AUPRC / EF@1% at matched cost |

## Macro + micro indicators

| Level | Indicator | What it measures |
|---|---|---|
| **Macro** | Models tried, jobs run, wall clock, tokens | Exploration breadth |
| **Micro: code content** | Feature encoding (radius, n_bits, desc_set), feature type, interaction algorithm, classification/regression algorithm, hyperparameters | What the agent actually wrote |
| **Micro: writing efficiency** | Code lines (new vs reused), edit count, time-to-first-success | Code production cost |

## Experiment protocol

```
10 GPCR targets (ordered by activity count), sequential per group
For each group (W / A / M / R):
  1. Clear experience store
  2. Run target 1 → record all indicators
  3. Run target 2 → record indicators + whether experience was used
  4. ... through target 10
  5. Compute marginal cost / marginal quality curves
```

## Experience schema

```json
{
  "target": "OPRM1",
  "data_characteristics": {
    "n_samples": 2790, "positive_rate": 0.795,
    "px_median": 7.8, "assay_type": "Ki"
  },
  "best_configuration": {
    "representation": "morgan_r2_2048_v1",
    "model": "RandomForest", "split": "scaffold",
    "metrics": {"auroc": 0.9416, "ef_at_1pct": 1.379}
  },
  "rejected": [{"model": "catboost", "reason": "10x cost, marginal gain"}],
  "code_pattern": {
    "feature_args": "--radius 2 --n-bits 2048 --desc-set v1",
    "train_args": "--model rf --split-manifest splits/scaffold.json",
    "reusable": true
  }
}
```

## Expected result

```
Target index:    1    2    3    4    5    6    7    8    9    10
R cost (s):    285  180  120  100   90   80   75   70   65   60  ← decreasing
A cost (s):    285  280  275  270  270  265  260  260  255  250  ← flat
R AUROC:      0.94 0.95 0.96 0.96 0.97 0.97 0.97 0.98 0.98 0.98  ← increasing
A AUROC:      0.94 0.94 0.95 0.94 0.95 0.94 0.95 0.95 0.94 0.95  ← flat
```

## Micro-level code evidence

The strongest evidence for RSI is **code reuse**: the agent copies/adapts code
from previous targets instead of writing from scratch. Track:
- Feature args in `ml.train` / `rdkit.featurize` calls
- Model family choices per target
- Split strategy choices per target
- Whether `experience.retrieve` was called and what it returned
- Code lines per ticket (new code vs tool invocations)
