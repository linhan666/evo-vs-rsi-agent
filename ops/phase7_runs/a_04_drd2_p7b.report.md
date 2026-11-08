# A #4 drd2

- task: `p7b_a_drd2`
- ticket: `7db81fb60becc17217e3ff0cda6ac829`
- state: ready
- wall: 347.4s, jobs 15 (failed 0), models 10
- best validation model (any split): work/drd2/model_v2_rf_seed42 AUROC=0.9565 AUPRC=0.9712 EF@1%=1.705
- best scaffold model: work/drd2/model_v2_rf_seed42 AUROC=0.9565 EF@1%=1.705
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

DRD2 Ki arm A complete. Used the provided frozen split manifest directly (never called data.split): dataset_p7b.csv 3293 rows, 0 invalid, 2192 positives; train 2816 / validation 329. Featurized at Morgan r=2/2048 (the fixed featurization accepted by evaluation.locked's desc_set-only interface) with both desc sets, trained logreg/rf/xgboost/catboost. Best validation: RF + desc_set v2, AUROC 0.9544, AUPRC 0.9678, EF@1% 1.705; EF is saturated for all 8 candidates at this validation size (top 3 val molecules all positive), so selection was by AUPRC/AUROC. RF seed sensitivity: 17/42/2024 -> AUPRC 0.9678/0.9712/0.9658, AUROC 0.9544/0.9565/0.9508; kept the pre-specified seed 17 rather than selecting the best seed to avoid validation overfitting. Ranked all 100,000 library molecules with the same fitted model (screening report model_sha256 equals model.joblib sha256; 0 invalid): full ranking evaluation/drd2_ranked.csv, top-100 evaluation/drd2_top100.csv (scores 0.7600-0.9100, #1 zinc046207), report evaluation/drd2_screening.json. One and only one locked evaluation: receipt evaluation/drd2_locked.json (sha256 be6030dcb9d64c61b1c540c316598d0739b12c9babaeca578d30ae7b422bee8b), locked AUROC 0.9215, AUPRC 0.9411, EF@1% 1.824; raw test output stayed in the protected tree. Model: work/drd2/model_v2_rf/model.joblib sha256 c339b8662ddbcfc92b09db0be82136d0b8e68b274258bdb2869e5591cdfd845e. Cost: 15 tool jobs (1 format probe, 2 featurizations, 10 trainings, 1 ranking, 1 locked evaluation), summed tool wall 163.7 s, end-to-end 218.6 s, 75.7 s CPU, no GPU. Experience ids reused: none (arm A has no experience store; approach derived independently). Limits: single 329-molecule scaffold validation; unlabeled library so no hit-rate or true EF claim (top-100 is prioritization only); RF scores are uncalibrated vote fractions; artifact manifest records code_commit=unknown. No code change/PR for this arm - deliverable is the evidence/receipt artifacts.
