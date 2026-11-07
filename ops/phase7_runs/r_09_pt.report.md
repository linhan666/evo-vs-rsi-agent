# R #9 pt

- task: `seq_r_pt`
- ticket: `62fb51ec2683277810cbe0bcb558b9a6`
- state: ready
- wall: 555.3s, jobs 33 (failed 4), models 11
- best validation model (any split): diag_rf_random AUROC=0.9698 AUPRC=0.9895 EF@1%=1.24
- best scaffold model: train_rf_s29 AUROC=0.9031 EF@1%=1.124
- refits excluded from ranking: []
- top-100 artifacts: 3

## agent report

Prothrombin Ki predictor + 100k ranking complete. No PR (scientific deliverable; no repo change requested). Artifacts under the ticket workdir /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/prothrombin-seq-62fb51ec2683/:

DELIVERABLE PATHS
- Top-100: prothrombin/screening/top100.csv (verified 100 unique molecules; columns rank,id,smiles,score; scores 0.955→0.870)
- Full ranking: prothrombin/screening/ranked_full_100k.csv (verified 100,000 rows, 0 invalid SMILES)
- Screening report: prothrombin/screening/report.json
- Validated model: prothrombin/model_rf/model.joblib (sha256 650f690b…), metrics: prothrombin/model_rf/metrics.json, per-molecule val scores: prothrombin/model_rf/predictions.csv
- Features: prothrombin/features_morgan2_2048_v1.npz (sha256 1163801f…); scaffold split: prothrombin/split_scaffold_seed17.json

(a) CHOICES + RATIONALE
- Data: 2,824 ChEMBL prothrombin Ki molecules with the dataset's pre-binarised `label` (2,279 positives, 80.70%); Ki only; no negatives invented; no test-set labels touched.
- Representation: Morgan FP radius 2 / 2,048 bits + 7 RDKit 2D descriptors (desc_set v1). Beat radius 3 / 4,096 (val AUROC 0.8937) and desc_set v2 (0.8809) under the same split/model.
- Split: Bemis–Murcko scaffold, 70/10/30, seed 17 → train 1,695 / val 282 (251 positive) / test 847. Scaffold split is the generalisation check; random split run only as an optimistic diagnostic. data.split's scaffold assignment was identical for seeds 17/23/29 (deterministic), so split-seed variance could not be estimated.
- Model: scikit-learn RandomForest (seed 17), chosen on scaffold-validation AUPRC then AUROC over CatBoost (0.8829/0.9836), XGBoost (0.8670/0.9746), logistic regression (0.7854/0.9573) on identical features/split. Rationale: n=1,695, sparse binary fingerprint features, strong small-data robustness, no tuning. No fusion: ml.fuse produced no validation metric, so a fused ranking could not be justified without an unvalidated claim.

(b) METRICS (scaffold validation, 282 molecules, 251 positives, AUPRC baseline = prevalence 0.8901)
- AUROC 0.9031; AUPRC 0.9857; EF@1% 1.124; EF@5% 1.124.
- EF caveat: both EF values are saturated at the maximum attainable 1/0.890 = 1.124 (top 3 of 282 and top 14 are all active), so EF does not discriminate models here.
- Random-split diagnostic (optimistic): AUROC 0.9698, AUPRC 0.9895, EF@1% 1.240.
- Held-out scaffold test (847) NOT evaluated: evaluation.locked only supports MOR/KOR/DRD2; no locked evaluator exists for prothrombin. No test performance or library enrichment is claimed (unlabeled 100k library; screening report states predictions only).

(c) TOP-100: prothrombin/screening/top100.csv. Ranked by uncalibrated RF class probability; ranking only, not Ki values.
Top 5: zinc042885 0.955; zinc088904 0.945; zinc034201 0.935; zinc095814 0.930; zinc007194 0.930.

(d) COST: final pipeline 26.4 s wall / ~15.9 CPU-s (featurise 1.0 s, split 2.2 s, train 4.0 s, screen 100k 19.2 s). Full session incl. model/feature comparison ≈127 s wall / ≈685 CPU-s (CatBoost dominates with 616 CPU-s); no GPU; peak RSS not recorded by the tool service (null).

(e) EXPERIENCE REUSE: retrieved 16 records (8 dataset + 8 model) from the exact store path; count=16, not zero.
- Nearest profile used: dataset_MOR_009 / model_MOR_010 (2,790 mol, 0.7953 pos). Secondary comparisons: dataset_KOR_013/model_KOR_014 (1,899, 0.7899), dataset_DRD2_007/model_DRD2_008 (3,293, 0.6657), dataset_CBR_013/model_CBR_014 (2,309, 0.9818).
- What the store exposes: applicability summary (n, positive rate, "scaffold split") + payload_sha256, not hyperparameter payloads (verified with kind+target filter). So reuse is protocol-level, reused as recorded: ChEMBL Ki binary target class and Bemis–Murcko scaffold-split validation for the ~2.8k/0.8 profile. Adapted locally (not documented in the records): representation, model family and split fractions.
- Store left untouched (declared read-only).

VERIFICATION: repeat screening with the same model+library reproduced identical rankings (RF deterministic, identical model hash across repeats); top-100 parses to exactly 100 unique molecules and full ranking to 100,000; schema checks passed (labels 0/1, 2,824 joins, no ID loss).

LIMITATIONS: 282-molecule validation with 89% positives → wide CIs, inflated AUPRC, saturated EF; screened model uses the 1,695-label train split for metric/model consistency (refit on all 2,824 labels is an untested follow-up); store payloads not retrievable through experience.retrieve.
