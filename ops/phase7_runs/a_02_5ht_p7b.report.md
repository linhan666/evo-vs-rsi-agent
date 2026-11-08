# A #2 5ht

- task: `p7b_a_5ht`
- ticket: `f66bbb3de529acbce11f04e1fcd08a35`
- state: ready
- wall: 351.8s, jobs 21 (failed 1), models 11
- best validation model (any split): p7b_5ht/train_rf_v1_seed7 AUROC=0.9992 AUPRC=1.0 EF@1%=1.025
- best scaffold model: p7b_5ht/train_rf_v1_seed7 AUROC=0.9992 EF@1%=1.025
- refits excluded from ranking: []
- top-100 artifacts: 4

## agent report

5-HT (Ki) target 2, arm A (no experience store) — complete.

APPROACH (derived independently): featurized the full dataset_p7b.csv (4104 molecules, all valid; Morgan r2/2048 bits + v1 descriptor set of 7 RDKit 2D descriptors) and trained candidates with ml.train on the provided frozen scaffold manifest (train 3509 / validation 410 / test 185). Selection used validation AUROC/AUPRC plus a verification step that library scores are resolvable. No data.split call, no test labels read.

CANDIDATE VALIDATION (frozen scaffold val, 400 pos / 10 neg):
- logreg v1: AUROC 0.9693, AUPRC 0.9991, EF@1% 1.025 (seed 17)
- rf v1: AUROC 0.9990/0.9992/0.9992, AUPRC 1.0000, EF@1% 1.025 (seeds 17/7/42)
- xgboost v1: AUROC 0.9918/0.9900, AUPRC 0.9998/0.9997, EF@1% 1.025 (seeds 17/7)
- catboost v1: AUROC 0.9953/0.9882, AUPRC 0.9999/0.9997, EF@1% 1.025 (seeds 17/7)
- rf v2: AUROC 0.9990, AUPRC 1.0000 (v2 adds no gain); logreg on v2 failed (exit 1 — likely infinite descriptor values; tree models fine).

CHOICE: xgboost (seed 17, v1). Reason: RF had the highest val AUROC but its 100k-library scores saturate at exactly 1.0 — the whole top-1000 is 1.0, so its "top-100" order is arbitrary library tie order (verified with a top_k=1000 run). XGBoost is seed-stable (0.9918/0.9900) and produces a strictly ordered, granular top-100 (0.999996→0.999977). CatBoost was less seed-stable and its top-100 score range (0.99977–0.99921) is nearly as compressed. The RF-vs-XGB val AUROC gap is small in absolute terms (10 val negatives).

LOCKED EVALUATION (called once): receipt evaluation/5ht_locked.json (sha256 e458314e6de88e1bf0dc703b2eaeba529d6d571331df61cbc3733b80256410c0).
- locked AUROC: 0.9044
- locked AUPRC: 0.9991
- locked EF@1%: 1.008; EF@5%: 1.008
The locked AUROC is materially below validation (0.9918); the scaffold test set is harder and only 185 molecules, and the raw locked metrics are not readable from the ticket (protected tree).

ARTIFACTS (paths relative to the scientific workspace, as the trigger's receipt convention uses):
- top-100 (final, XGBoost): p7b_5ht/top100_xgb_v1.csv — 100 rows, rank/id/smiles/score, sha256 978b13b9cf1e58d9e57b45ab125d3552a0b81eaa9c600ee901c3c9b71d6d9961
- full 100k ranking: p7b_5ht/rank_xgb_v1.csv (100000 rows, sha256 044fef41fbfa63bdd1f55dd3ec899ea88d0c7a1389c70bde74d57939d50516f4)
- model: p7b_5ht/train_xgb_v1/model.joblib (sha256 acec637a3fe9c6af313a693029f637b80f4e9785a474ff1d4d4b3e4f4b9a0679)
- metrics: p7b_5ht/train_xgb_v1/metrics.json; ranking report: p7b_5ht/rank_xgb_v1_report.json (model sha and library sha 09446ea1… match)
- features: p7b_5ht/features_v1.npz (sha256 e5e9548def0140ba14db180a7de504b8b457d043fdbb405a037c5e49714aba85) and report p7b_5ht/report_features_v1.json
- comparison artifacts retained: top100_rf_v1.csv (degenerate ties), top100_cat_v1.csv, train_* metrics for all candidates.

COST: 21 scientific jobs (20 pipeline incl. probes + 1 locked evaluation; 1 failed probe = logreg-on-v2). Summed tool wall time 152.4 s; end-to-end 2026-11-08 18:35:20 → 18:39:46 UTC ≈ 266 s (~4.4 min). CPU only; no GPU; no /tmp; frozen manifest untouched; no other projects touched.

EXPERIENCE IDS REUSED: none (arm A has no experience store; no experience ids exist for this arm).

LIMITATIONS / HONEST NOTES: (1) The dataset's binary `label` column is heavily imbalanced — 4015 positives / 89 negatives overall, 400/10 in validation — so AUPRC (base rate 0.976) and EF@1% (top 1% of 410 = 4 molecules, EF 1.025 = ceiling) are baseline-dominated and not informative beyond AUROC. (2) The exact Ki threshold used to binarize labels is not recorded in artifacts I could read; this session exposes no shell/file-read tool, so I could not inspect the raw CSV header. (3) The single allowed locked evaluation is now consumed; I did not see the per-sample locked errors. (4) Only 185 test molecules and ~10-20 negatives imply a coarse locked AUROC estimate. No PR/code change: this ticket is a computation + report deliverable.
