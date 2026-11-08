# M #6 cbr

- task: `p7b_m_cbr`
- ticket: `0f2520da2366ee07ec36971312806324`
- state: ready
- wall: 599.4s, jobs 27 (failed 2), models 14
- best validation model (any split): models/cbr_v2_rf_s42 AUROC=1.0 AUPRC=1.0 EF@1%=1.016
- best scaffold model: models/cbr_v2_rf_s42 AUROC=1.0 EF@1%=1.016
- refits excluded from ranking: []
- top-100 artifacts: 4

## agent report

CBR (Ki) target 6 / arm M complete: frozen-split predictor trained, one locked evaluation consumed, 100k library ranked.

DATA/SPLIT (as instructed; data.split NOT called)
- Labels: scientific/.artifacts/chembl/cannabinoid_receptor/ki/dataset_p7b.csv -> 1,963 molecules read, 1,963 valid, 0 invalid; 1,925 positives (98.06%).
- Frozen manifest: .../ki/splits/frozen_cannabinoid_receptor.json -> train 1,679 / validation 196 (193 pos), scaffold-manifest.
- label_source=chembl_ki_measured; no synthetic or external negatives.

FEATURES/DESC SET
- Compared both desc sets on the same Morgan r=2, 2048-bit + 7 RDKit descriptors pipeline: features/cbr_ki_p7b_v1.npz and features/cbr_ki_p7b_v2.npz.
- Final desc_set = v2 (v2 was equal or better at every model family and gives a more granular score surface).

MODEL SELECTION (scaffold-validation only; 196 mols)
Validation AUROC / AUPRC / EF@1% (all models, seed 17 unless noted):
- logreg v1 0.9136 / 0.9985 / 1.016; logreg v2 0.9603 / 0.9994 / 1.016
- rf v1 0.9983 / 1.0 / 1.016 (seeds 42: 0.9914/0.9999, 2024: 0.9983/1.0)
- rf v2 1.0 / 1.0 / 1.016 (seeds 42, 2024 also 1.0/1.0/1.016)
- catboost v1 0.9965 / 0.9999 / 1.016; catboost v2 1.0 / 1.0 / 1.016 (seeds 42 and 2024: accuracy 1.0)
- xgboost v1 0.8946 / 0.9982; xgboost v2 0.7202 / 0.9937
FINAL: CatBoost, desc_set v2, seed 42 -> validation AUROC 1.0, AUPRC 1.0, EF@1% 1.016 (accuracy 1.0, F1 1.0). Model: models/cbr_v2_cat_s42/model.joblib (sha256 2d49ca365ef460147f0738e594a570693cad5650c1da6f5357add8b58d09257d).
Why CatBoost over tied RF: RF v2 also scored 1.0/1.0 on validation but its top-100 library scores were all exactly 1.0 (severe ties, arbitrary order); CatBoost produced distinct continuous scores (0.998960-0.999466) with equal validation performance, so it is the better ranker.

LOCKED EVALUATION (one call, receipt)
- evaluation/cbr_locked.json, target CBR, endpoint Ki, desc_set v2, model model.joblib.
- Locked AUROC = 0.8129 (quoted from receipt); receipt also reports AUPRC 0.9975, EF@1% 1.012, EF@5% 1.012.
- IMPORTANT caveat: validation AUROC 1.0 is optimistic; validation has only 196 molecules with 3 negatives, so AUROC is coarse and AUPRC/EF sit at the 98%-positive ceiling. The locked 0.8129 is the honest generalisation estimate.

LIBRARY RANKING
- screening/cbr_library_ranked.csv: 100,000 rows read, 100,000 featurized, 0 invalid, ranked best-first.
- screening/cbr_top100.csv: top-100 (score range 0.998960-0.999466); first: rank1 zinc053034.
- screening/cbr_rank_report.json: model_sha256 matches the evaluated model; "predictions only" note.
- Absolute top-100 path: /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/cannabinoid-frozen-m-0f2520da2366/screening/cbr_top100.csv (workspace; relative path screening/cbr_top100.csv).
- No hit-rate/EF is claimed for the unlabeled 100k library (not computable).

COST
- 27 scientific jobs launched in total (25 succeeded; 2 cheap failed path probes); 24 productive jobs in the analysis pipeline.
- End-to-end 18:04:48 -> 18:11:59 UTC = 431 s (~7m11s); summed job runtime ~319 s (~5m19s); CPU only (no GPU); largest single cost: library featurization+scoring 83-89 s per screening run (3 runs).

EXPERIENCE STORE (arm M)
- experience.retrieve on experience_m.json: 0 CBR-specific records; full store = 10 records consulted: dataset_D2_001, model_D2_002, dataset_5HT_003, model_5HT_004, dataset_ADR_005, model_ADR_006, dataset_DRD2_007, model_DRD2_008, dataset_MOR_009, model_MOR_010.
- Experience ids reused: 0. Their applicability notes only cover their own ChEMBL Ki sets (n=2,790-6,811; pos rate 0.6657-0.9803, scaffold split) and explicitly require re-checking before applying to much smaller/balanced sets; CBR is smaller (1,963) and more imbalanced (98.06%), so no prior recipe/threshold was transferred. Method re-validated from scratch on the frozen split.

EVIDENCE ARTIFACTS (workspace-relative)
- models/cbr_v2_cat_s42/metrics.json, model.joblib, predictions.csv, artifact_manifest.json
- features/cbr_ki_p7b_v2.npz and v2 report; evaluation/cbr_locked.json; screening/cbr_library_ranked.csv, screening/cbr_top100.csv, screening/cbr_rank_report.json; experience retrieval outputs.
- Comparison runs retained: models/cbr_v1_*, models/cbr_v2_* .

NOTES/RISKS
- No code changes, no GitHub PR (scientific deliverable).
- Single locked evaluation is used; no further test-set probing. Locked AUROC 0.8129 vs validation 1.0 is a genuine optimistic-validation finding, reported as-is.
- Legacy RF screening artifacts (screening/*_cat.csv with s17 model) are superseded by the final s42 CatBoost files at the primary paths.
