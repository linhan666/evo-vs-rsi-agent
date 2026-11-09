# M #5 mor

- task: `p7d_m_mor`
- ticket: `7c0cafd2c7a2f233cc09f28725e8a0c7`
- state: ready
- wall: 326.5s, jobs 21 (failed 1), models 9
- best validation model (any split): model_mor_v2_rf_s7 AUROC=0.9427 AUPRC=0.9744 EF@1%=1.416
- best scaffold model: model_mor_v2_rf_s7 AUROC=0.9427 EF@1%=1.416
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

MOR (Ki) predictor + 100k ranking + one locked evaluation are complete. Deliverable is scientific artifacts, not a code PR (so no PR number).

TICKET: P7d MOR target 5 (arm M)
Workspace: /home/linhan_cluster/evo_vs_rsi/scientific

CHOICES AND WHY
- Frozen split: passed …/ki/splits/frozen_oprm1.json as --split-manifest to every ml.train run; data.split was never called. Manifest used 2,385 train / 279 scaffold-validation molecules (2,219 positives; 197 validation positives); the frozen test remainder was never inspected.
- Featurization: RDKit Morgan radius 2, 2048 bits, desc_set v2 (identity SMILES default). 2,790/2,790 molecules valid, 0 invalid. v1 (209 KB npz) vs v2 (381 KB npz) compared under identical labels/split.
- Model selection on validation only (7 configs):
  v1 logreg 0.8747/0.9348; v2 logreg 0.8781/0.9374;
  v1 RF 0.9362/0.9722; v2 RF 0.9410/0.9738;
  v1 XGB 0.9289/0.9637; v2 XGB 0.9277/0.9621;
  v2 CatBoost 0.9253/0.9637. (AUROC/AUPRC)
  RF on desc_set v2 won clearly. RF seed stability check: seeds 7/17/42 gave AUROC 0.9427/0.9410/0.9422 and AUPRC 0.9744/0.9738/0.9747; I kept the default seed 17 rather than cherry-picking a seed.
- Final model: model_mor_v2_rf/model.joblib (RF, desc_set v2, seed 17, split_strategy scaffold-manifest).
- Library ranked with the same model and featurization (radius 2, 2048 bits, v2): 100,000/100,000 molecules featurized, 0 invalid.

VALIDATION (model_mor_v2_rf, seed 17)
AUROC 0.9410 | AUPRC 0.9738 | EF@1% 1.416 | EF@5% 1.416 | accuracy 0.8674 | F1 0.9086. Validation positive prevalence is 70.6% (197/279), so the AUPRC baseline is high.

LOCKED EVALUATION (exactly one call)
evaluation.locked --target MOR --endpoint Ki --desc-set v2 --model model_mor_v2_rf/model.joblib --receipt evaluation/mor_locked.json.
Receipt (sha256 6ea308740a0590b0f22a7a0de4251ca068fc4eae9703d47ac6cd997c149adb8b): AUROC 0.9425, AUPRC 0.9745, EF@1% 1.379, EF@5% 1.379. Raw protected metrics were not readable from the ticket, as designed. Locked AUROC 0.9425 is quoted directly from this receipt.

RANKING / TOP-100
- Top-100: /home/linhan_cluster/evo_vs_rsi/scientific/mor_ki_top100.csv (100 rows, best-first; score range 0.832917–0.945000; rank 1 zinc025392; sha256 61c3c0c231f35f4c6a6d3e08c28ab81520b568c4d5a34a6cd64a617f1f72f4be).
- Full ranking: /home/linhan_cluster/evo_vs_rsi/scientific/mor_ki_library_ranking.csv (100,000 scored; sha256 fa6819f79e0731302252cb335153d05101e38d5694262577a87f3689b52e1eb2).
- Screening report: /home/linhan_cluster/evo_vs_rsi/scientific/mor_ki_screening_report.json (rows_read 100000, rows_featurized 100000, rows_invalid 0, elapsed 91.1 s). The library is unlabeled, so these are model scores only; no hit rate or enrichment is claimed for it.

KEY ARTIFACTS
- Features/report: mor_ki_v2.npz (desc v2), mor_ki_v2_report.json; comparison v1 mor_ki_v1.npz + mor_ki_v1_report.json.
- Model: model_mor_v2_rf/{model.joblib, metrics.json, predictions.csv, artifact_manifest.json}; model sha256 e5fc73cad0d7370172d72cb68ae37a62f3f58424442b1a98072772c3617de4b2.
- Candidate runs: model_mor_v1_logreg, model_mor_v2_logreg, model_mor_v1_rf, model_mor_v1_xgboost, model_mor_v2_xgboost, model_mor_v2_catboost, model_mor_v2_rf_s7, model_mor_v2_rf_s42.
- Receipt: evaluation/mor_locked.json. All paths relative to the workspace above.

COST
- 21 scientific tool jobs total (20 succeeded, 1 failed), of which 19 ran up to and including the locked evaluation; the last 2 were experience-store verification queries. Breakdown: 3 rdkit.featurize (one failed on a relative input path, immediately retried with the required absolute path), 9 ml.train, 1 screening.rank, 1 evaluation.locked, 7 experience.retrieve.
- Wall clock: first job 2026-11-09T08:42:26.269Z, last 08:46:28.171Z = 241.9 s (~4m02s) end-to-end; 208.7 s from start to locked receipt. Summed tool wall time 138.0 s; screening.rank alone 91.8 s. CPU only, 0 GPU seconds (one-GPU rule respected; none needed).

EXPERIENCE REUSE
None. experience.retrieve on .artifacts/experience/experience_m_rep2.json returned {"count": 0, "records": []} for every query: target MOR (model + dataset), target OPRM1, target KOR, kind screening, kind harness, and unfiltered. The store contains no records, so no experience ids were reused and no transfer prior was applied.

LIMITATIONS / NOTES
- The provided experience store is empty; experience-guided transfer was impossible, not skipped.
- Validation EF@1% is tool-computed on 279 validation molecules and equals 1.416 across models; interpreted only as the tool's reported validation value.
- The one featurize failure was a path-resolution issue (relative input not resolved from the workspace); the absolute path from the assignment worked and no data was altered.
- Test-set integrity preserved: only evaluation.locked touched the locked test data; no per-sample test errors were read.
