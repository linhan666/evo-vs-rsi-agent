# A #9 pt

- task: `p7b_a_pt`
- ticket: `01206cb5a0ef571ea50659b025caabf7`
- state: ready
- wall: 387.1s, jobs 34 (failed 1), models 20
- best validation model (any split): pt/rf_v2_r3_s42 AUROC=0.9481 AUPRC=0.9786 EF@1%=1.437
- best scaffold model: pt/rf_v2_r3_s42 AUROC=0.9481 EF@1%=1.437
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

PT (Ki) arm A complete: frozen-split predictor trained, 100k library ranked, one locked evaluation consumed.

APPROACH (no experience store used; none consulted)
- Passed chembl/prothrombin/ki/splits/frozen_prothrombin.json as --split-manifest to ml.train; data.split never called. Joined 2,400 labelled molecules; manifest counts: train 2,052 / validation 240 / test 108 (2,400-2,052-240), 1,905 positives overall, 167 validation positives.
- Featurized the labels with rdkit.featurize: Morgan radius 2/3/4, 2,048/4,096 bits, desc_set v1 and v2; trained logreg/rf/xgboost/catboost with ml.train.
- Selected on scaffold-validation only: RandomForest, desc_set v2, radius 3, 2,048 bits, seed 17. Best validation AUROC 0.9473 / AUPRC 0.9773; seed robustness s17 0.9473, s42 0.9481, s7 0.9472 AUROC. Alternatives: v2-r4 0.9464, v2-r3-4096 0.9468, v1-r2 0.9423, xgb-v2-r3 0.9395, cat-v2-r3 0.9370. Chose the simplest tied configuration; no test set used for selection.
- Ranked the 100k library with the same fitted pipeline and desc_set v2: 100,000/100,000 featurized, 0 invalid.

VALIDATION (scaffold-validation, 240 molecules, 167 positives)
- AUROC 0.9473, AUPRC 0.9773 (prevalence baseline 0.696), EF@1% 1.437, EF@5% 1.437.
- EF is saturated in this 240-molecule validation bucket (every selected molecule positive), so it does not discriminate models; model selection used AUROC/AUPRC.

LOCKED RECEIPT (evaluation/pt_locked.json, sha256 6fc0bab6bd7447be731bb15cde397ebfa7eb6f3fe95b74c644135f78831c6238)
- Quoted locked AUROC: 0.907. AUPRC 0.9854, EF@1% 1.134, EF@5% 1.134.
- target PT, endpoint Ki, desc_set v2, model pt/rf_v2_r3/model.joblib (sha256 b3fc6df735149968045e6734405df5d6e929fbf5704c793a1a54a5b18b29b06d). Raw locked metrics stayed in the protected tree; the receipt is summary-only. Exactly one evaluation.locked call.

ARTIFACTS (workspace-relative, ticket workspace)
- Top-100: pt/top100.csv (100 rows best-first, score range 0.900-0.945; rank 1 zinc032341 0.945).
- Full ranking: pt/ranking_100k.csv. Screening report: pt/screening_report.json (model_sha256 matches the trained model). Model/metrics: pt/rf_v2_r3/model.joblib, pt/rf_v2_r3/metrics.json, artifact_manifest.json.

COST
- 34 tool runs total (33 succeeded, 1 failed initial relative-path probe), CPU only, 0 GPU.
- Aggregate job wall time ~216 s; end-to-end ticket wall clock 5m26s (19:17:29-19:22:55 UTC). Ranking dominated at 87 s.

EXPERIENCE IDS REUSED: none (this arm has no experience store).

LIMITATIONS
- The 100k library is unlabeled: only model scores/ranking are reported; no true EF@1% or hit rate is defined or claimed.
- Locked test has 108 molecules, so the locked AUROC carries wide sampling uncertainty relative to validation.
