# R #4 drd2

- task: `p7c_r_drd2`
- ticket: `2e35dcecacc8c7df5d69259b8854b7d7`
- state: ready
- wall: 385.7s, jobs 21 (failed 0), models 12
- best validation model (any split): models/drd2_ki_v1_rf_s42 AUROC=0.9589 AUPRC=0.9713 EF@1%=1.705
- best scaffold model: models/drd2_ki_v1_rf_s42 AUROC=0.9589 EF@1%=1.705
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

READY — DRD2 (Ki) predictor built, 100k library ranked, one locked evaluation completed. All 21 scientific tool runs SUCCEEDED; no failures.

ARTIFACTS (absolute, under ticket workspace /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/chembl-drd2-p7c-2e35dcecacc8):
- Locked receipt: evaluation/drd2_locked.json (sha256 f30023e4b6…)
- Final model: models/drd2_ki_v2_rf_s42/model.joblib (+ metrics.json, predictions.csv, artifact_manifest.json)
- Full ranking: screening/drd2_ki_ranked.csv (100k rows)
- TOP-100: screening/drd2_ki_top100.csv
- Screening report: screening/drd2_ki_screening_report.json
- Experience retrieval outputs: experience/drd2_retrieval.json, experience/all_retrieval.json, experience/all_records.json

EXPERIENCE REUSE: store /home/linhan_cluster/evo_vs_rsi/scientific/.artifacts/experience/experience_r.json returned {"count": 0, "records": []} for target=DRD2, for kind=model, and unfiltered. It is empty — 0 experience ids available/reused. (If records were expected, the store itself may need to be populated; retrieval call signature was exactly as instructed.)

PROTOCOL: labels = dataset_p7b.csv, 3293 rows / 3293 valid SMILES, 2192 positives. Featurized with rdkit.featurize (Morgan r=2, 2048 bits + 7 descriptors; desc_set v1 and v2). Frozen split passed as --split-manifest …/splits/frozen_drd2.json to every ml.train; data.split was never called. Counts: train 2816, validation 329 (193 positives); the remaining 148 joined rows were untouched and only the locked evaluator can reach the test channel. No test-set peeking; one evaluation.locked call total.

CHOICES: compared logreg/rf/xgboost/catboost on desc v1 and v2 at seed 17, plus rf seed stability (17/42/123).
val AUROC/AUPRC (seed 17): v1 logreg .8764/.8971, rf .9481/.9640, xgb .9423/.9608, cat .9444/.9595; v2 logreg .8833/.9038, rf .9544/.9678, xgb .9440/.9612, cat .9457/.9626.
rf seeds v1: s42 .9589/.9713, s123 .9537/.9668; v2: s42 .9565/.9712, s123 .9535/.9678.
RF clearly best; desc v2 better on seed-mean (AUROC .9548 vs .9536; AUPRC .9689 vs .9674); seed 42 best/consistent. Final: RandomForest, desc_set v2, seed 42. 14 training runs were validation-only; the locked test was not used for selection.

VALIDATION (final model): AUROC 0.9565, AUPRC 0.9712, EF@1% 1.705, EF@5% 1.705. EF@1% is at the mathematical ceiling here (329 val molecules, 1% ≈ 3.3 → top-4, all 4 positive; base rate 193/329 = 0.587; max EF = 1/0.587 = 1.705), so EF@1% does not discriminate between models; AUROC/AUPRC drove selection.

LOCKED RECEIPT (quoted): target DRD2, endpoint Ki, desc_set v2, metrics {auroc: 0.9241, auprc: 0.9438, ef_at_1pct: 1.824, ef_at_5pct: 1.824}; receipt notes "summary only; the raw locked metrics file is not readable from the ticket" (protected_output: /home/linhan_cluster/evo_vs_rsi/protected/chembl37_ki_drd2/metrics_test_locked_agent_Ki_v2_._DRD2.json, not opened). Locked AUROC = 0.9241.

RANKING: 100,000/100,000 library molecules featurized and scored (desc_set v2), 0 invalid. Top-100 score range [0.755, 0.86875]; top hits zinc082630 0.86875, zinc046207 0.86500, zinc083695 0.85250. These are model scores on an UNLABELED library: no hit rate or EF@1% is defined and none is claimed (per tool report and AGENTS.md). Library was scored as provided (no dedup by screening tool).

COST: 21 scientific tool runs; ~230 s tool wall time; ~5.5 min end-to-end (21:15:40–21:21:07Z); CPU only, no GPU. Largest costs: library featurization v2 84 s, ranking 80 s.

LIMITATIONS: (1) ml.train with a split manifest trains on the train split only (2816 molecules), with no train+val refit option, so the final predictor did not use the 329 validation molecules; (2) 329-molecule validation gives ±~0.005 AUROC seed variance, and the locked AUROC is 0.032 below validation (expected scaffold generalization gap); (3) validation EF saturated, and library enrichment is undefined; (4) v1/v2 descriptor reports list identical 7 descriptor names, so the v2 fingerprint composition is not documented in the report (v2 npz is ~1.9× larger).
