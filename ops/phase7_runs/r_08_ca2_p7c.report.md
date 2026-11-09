# R #8 ca2

- task: `p7c_r_ca2`
- ticket: `060aed292a2aeb51c06d93fd7236fa3e`
- state: ready
- wall: 229.7s, jobs 25 (failed 2), models 9
- best validation model (any split): runs/ca2_ki_rf_v1_seed42 AUROC=0.9852 AUPRC=0.9992 EF@1%=1.056
- best scaffold model: runs/ca2_ki_rf_v1_seed42 AUROC=0.9852 EF@1%=1.056
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

CA2/Ki target 8 complete: frozen-split training, one locked evaluation, 100k library ranked.

DATA/SPLIT: dataset_p7b.csv featurized 6206/6206 valid rows (0 invalid); frozen manifest used as-is (train 5306, val 621, test 279); data.split never called. Label column is binary with 5751/6206 positives (92.7%); validation 588/621. I could not inspect the raw CSV through the available read-only interfaces, so exact activity threshold/censoring handling is taken from the delivered P7b dataset rather than re-verified.

MODEL CHOICE (validation only; test never touched before the locked call). Features: Morgan ECFP4 2048 bits + 7 RDKit 2D descriptors (desc_set v1, radius 2). Comparison on the same frozen split:
- rf v1 seed17: AUROC 0.9838, AUPRC 0.9991, EF@1% 1.056  <- selected
- rf v1 seed42 / 7 / 123: 0.9852 / 0.9830 / 0.9845 AUROC (seed stability, ±0.001)
- xgboost v1: 0.9716, AUPRC 0.9983
- catboost v1: 0.9675, AUPRC 0.9981
- logreg v1: 0.9156, AUPRC 0.9936
- rf v1 radius3/4096: 0.9814, AUPRC 0.9989
RF on ECFP4+descriptors was the best and most stable; seed fixed at 17 (pre-declared default) instead of cherry-picking the best seed. desc_set v2 featurization succeeded but ml.train rejected the v2 matrix for both rf and logreg (exit 1, no error detail exposed); not needed since v1 was compatible.

LOCKED EVALUATION (exactly one call): evaluation/ca2_locked.json, target CA2, endpoint Ki, desc_set v1, model runs/ca2_ki_rf_v1/model.joblib. Receipt metrics: AUROC 0.9687, AUPRC 0.9969, EF@1% 1.063, EF@5% 1.063. Raw locked metrics stay in the protected tree.

SCREENING: model runs/ca2_ki_rf_v1/model.joblib (sha256 70b7b02c…, same model as locked eval) scored all 100000 library rows, 0 invalid. Outputs: screening/ca2_ki_ranked.csv (full 100k), screening/ca2_ki_top100.csv (top-100), screening/ca2_ki_report.json. Top-100 score range 1.000–0.985; top hits are primary benzenesulfonamides (e.g. zinc042824, zinc030977, zinc054520), i.e. the known CA2 zinc-binding warhead. No hit rate/enrichment is claimed for the unlabeled library.

COST: 25 tool jobs submitted (23 succeeded, 2 failed on the v2 feature incompatibility), ~63 s summed job runtime, ~186 s wall clock from first to last job (22:39:42–22:42:49 UTC), 1 GPU-hour=0 (CPU only).

EXPERIENCE: 7 experience.retrieve calls (CA2 model/dataset/screening, MOR model/dataset, no-target model/transfer/harness) all returned {"count":0,"records":[]}; the store appears empty at query time, so no experience ids were reused.

LIMITATIONS/RISK: 92.7% positive base rate makes AUPRC (floor 0.947) and EF@1%/5% saturated — EF@1% 1.056 on 621 val molecules is the maximum achievable with 6 picks, so AUROC is the meaningful headline (val 0.9838, locked 0.9687). Scaffold split gives a real generalisation gap; no random-split result is reported. Artifacts are workspace-relative under the ticket directory; no PR (scientific deliverable, not a code change).
