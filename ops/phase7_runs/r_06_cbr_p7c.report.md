# R #6 cbr

- task: `p7c_r_cbr`
- ticket: `92e0be60a018755ea14ea7dfef57599b`
- state: ready
- wall: 4123.6s, jobs 24 (failed 1), models 15
- best validation model (any split): runs/cbr/rf_v2_s42 AUROC=1.0 AUPRC=1.0 EF@1%=1.016
- best scaffold model: runs/cbr/rf_v2_s42 AUROC=1.0 EF@1%=1.016
- refits excluded from ranking: []
- top-100 artifacts: 3

## agent report

P7c CBR (Ki) Target 6 completed: frozen split honored, experience store queried (empty), predictor trained, one locked evaluation, 100k library ranked.

DELIVERABLES (paths are relative to the ticket/Session workspace):
- Frozen split: passed `.../ki/splits/frozen_cannabinoid_receptor.json` as --split-manifest to ml.train (train 1679 / val 196 / locked-test 88); data.split was never called.
- Experience: experience.retrieve on `.../experience/experience_r.json` returned count 0 (store empty) → 0 experience ids reused.
- Features: `data/cbr_features_v1.npz`, `data/cbr_features_v2.npz` (1963/1963 rows valid, 0 invalid; id→molecule_chembl_id, smiles→canonical_smiles; radius 2, 2048 bits).
- Model comparison on the frozen validation set (seed 17; val = 196 molecules, 193 positives / 3 negatives):
  | desc_set | logreg AUROC/AUPRC | rf AUROC/AUPRC | xgboost AUROC/AUPRC | catboost AUROC/AUPRC |
  | v1 | 0.9136/0.9985 | 0.9983/1.0000 | 0.8946/0.9982 | 0.9965/0.9999 |
  | v2 | 0.9603/0.9994 | 1.0000/1.0000 | 0.7202/0.9937 | 1.0000/1.0000 |
  All models: validation EF@1% = 1.016, EF@5% = 1.016.
- Selected predictor: random forest on desc_set v2, seed 17 → `runs/cbr/rf_v2/model.joblib` (val AUROC 1.000, AUPRC 1.000, EF@1% 1.016; stable AUROC 1.000 at seeds 1/42/2024; rf on v1 = 0.9983). Rationale: tied-best validation discrimination, seed/desc-set stable, robust bagging under 35 training negatives (xgb was unstable; catboost tied but its 100k screening was computationally infeasible, see cost), fast to screen.
- Library ranking: `screening/cbr_ranked.csv` (100000/100000 scored, 0 invalid), top-100 = `screening/cbr_top100.csv`, report = `screening/cbr_screening_report.json` (model sha256 f57df570…, library sha256 09446ea1…).
- Locked evaluation (the single allowed one): `evaluation/cbr_locked.json` → AUROC 0.7551, AUPRC 0.9962, EF@1% 1.012, EF@5% 1.012, desc_set v2; raw metrics stayed in protected/chembl37_ki_cbr/metrics_test_locked_agent_Ki_v2_._CBR.json. No further locked evaluations remain for CBR/Ki on this ticket.

COST: 24 scientific tool jobs (23 succeeded, 1 timed out): end-to-end 67 min 15 s (21:26:28→22:33:43 UTC); summed successful compute 241 s (~4 min); ~60 min lost to one CatBoost 100k screening job that exceeded its 3600 s cap and was SIGKILLed with no artifacts (a parameterization/cost miss, disclosed).

MATERIAL LIMITATIONS (do not overclaim):
1) Labels are 98.1% positive (1925/1963; validation 193/196), so AUPRC and EF@1%/5% are degenerate (EF ≈ 1/base rate). AUROC is the only informative discrimination metric.
2) RF library probabilities saturate at 1.0: all top-100 scores are exactly 1.0, so the within-tie order is arbitrary — the file is a tied candidate set, not a fine-grained ranking. Full ranked CSV also has large 1.0 ties.
3) Validation AUROC 1.000 was optimistic (3 validation negatives); the unbiased locked AUROC is 0.7551, a substantial generalisation gap. Recommended follow-up (needs a new ticket for another locked evaluation): prefer a regularised linear model (logreg v2: val AUROC 0.9603/AUPRC 0.9994, graded scores) or recalibrate before ranking.
4) The 100k library is unlabeled; no hit rate/enrichment is claimed for it.

No code/PR was produced: this is a scientific-computation task; deliverables are the workspace artifacts above.
