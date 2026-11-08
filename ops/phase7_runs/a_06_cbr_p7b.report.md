# A #6 cbr

- task: `p7b_a_cbr`
- ticket: `53ceb8562de829ca7994cebccab0a833`
- state: ready
- wall: 445.9s, jobs 19 (failed 0), models 12
- best validation model (any split): cbr/model_rf_v2_s42 AUROC=1.0 AUPRC=1.0 EF@1%=1.016
- best scaffold model: cbr/model_rf_v2_s42 AUROC=1.0 EF@1%=1.016
- refits excluded from ranking: []
- top-100 artifacts: 2

## agent report

CBR Ki (P7b arm A) completed end-to-end with the frozen manifest; no experience store used.

CHOICES & WHY
- Featurized dataset_p7b.csv with rdkit.featurize desc_set=v2 (Morgan r=2, 2048 bits + 7 RDKit 2D descriptors); 1,963/1,963 molecules valid, 0 invalid.
- Trained with ml.train on the frozen split (train 1,679 / validation 196; frozen_cannabinoid_receptor.json; data.split never called).
- Model screen (frozen-split validation): v1 logreg 0.9136, rf 0.9983, xgboost 0.8946, catboost 0.9965 AUROC; v2 logreg 0.9603, rf 1.0000, xgboost 0.7202, catboost 1.0000 AUROC. All EF@1% = 1.016.
- Selected CatBoost v2 (seed 17): validation AUROC 1.0000, AUPRC 1.0000, EF@1% 1.016 (EF@5% 1.016), accuracy 0.9949; stable at seed 42 (AUROC/AUPRC 1.0). Chosen over RF (val AUROC 1.0 too) because RF probabilities saturate at exactly 1.0 (top-100 all tied), while CatBoost yields graded scores (0.99907–0.99946) and a meaningful ranking; CatBoost also had slightly better validation accuracy.
- Caveat: validation contains only 3 negatives (193/196 positives), so AUROC/AUPRC/EF@1% are saturated and statistically fragile; EF@1% is near the 98.5% base rate (2/196 snapshot).

LOCKED RESULT (evaluation.locked, target CBR, endpoint Ki, desc_set v2, receipt evaluation/cbr_locked.json, sha256 e03ef62d…)
- Locked AUROC 0.6586, AUPRC 0.9943, EF@1% 1.012, EF@5% 1.012 (quoted from receipt). Raw metrics are in the protected tree; only the summary receipt is readable.
- Material limitation: the locked AUROC is far below the saturated validation AUROC, i.e. weak generalisation to the protected test. Only one locked evaluation per ticket was permitted, so no second estimate exists; this must be reported honestly rather than presented as a strong model.

LIBRARY SCREENING
- screening.rank with the same CatBoost v2 model over library_100k.smi: 100,000/100,000 scored, 0 invalid, 0 duplicates removed (library scored as provided), elapsed 84.9 s.
- Full ranking: cbr/ranking_100k_cat.csv (sha256 71992622…); top-100: cbr/top100_cbr_cat.csv (sha256 93a32c38…); screening report cbr/screening_report_cat.json. An RF-v2 screening was also run (cbr/top100_cbr.csv) but rejected because of exact-1.0 score ties.
- Unlabeled library: no hit rate/enrichment is defined or claimed.

ARTIFACTS
- Model cbr/model_cat_v2/model.joblib (sha256 b8af3c28…), metrics cbr/model_cat_v2/metrics.json; features cbr/features_v2.npz.

COST
- 19 scientific tool jobs (5 featurize probes/versions, 9 training comparisons, 2 100k screenings, 1 locked eval), 237 s total tool wall clock; longest job 96.7 s; end-to-end ~7 min; CPU only, no GPU.

EXPERIENCE IDS REUSED: none (no experience store in this arm).

DELIVERABLE PATHS are workspace-relative as recorded by the tools: evaluation/cbr_locked.json, cbr/top100_cbr_cat.csv, cbr/ranking_100k_cat.csv. This ticket made no code changes and opens no PR.
