# M #9 pt

- task: `p7b_m_pt`
- ticket: `2b8f9d5cd4e2dc1574aab6029537a423`
- state: ready
- wall: 199.1s, jobs 16 (failed 0), models 10
- best validation model (any split): models/pt_v1_rf_r2 AUROC=0.9423 AUPRC=0.9754 EF@1%=1.437
- best scaffold model: models/pt_v1_rf_r2 AUROC=0.9423 EF@1%=1.437
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

PT/Ki (target 9/9, arm M) pipeline complete in workspace /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/prothrombin-frozen-m-2b8f9d5cd4e2. No code change/PR: the deliverable is the ranked library plus the locked receipt.

Choices and why:
- Frozen split used directly: ml.train --split-manifest scientific/.artifacts/chembl/prothrombin/ki/splits/frozen_prothrombin.json; data.split never called. Split: 2052 train / 240 validation / 108 held-out (scaffold-manifest).
- Labels: dataset_p7b.csv, ChEMBL Ki binary (1905 positives / 2400 joined, 79.4%), label_source "chembl_ki_binary"; labels matched on molecule_chembl_id, column "label".
- Featurization: Morgan radius 2, 2048 bits + 7 RDKit descriptors, desc_set v1 (the set trained on) vs v2 compared; v1 won. Default radius/bits used so screening.rank and evaluation.locked featurize identically.
- Model sweep on the frozen validation set: RF v1 0.9423 AUROC / 0.9754 AUPRC; RF v2 0.9404/0.9732; XGB v1 0.9039/0.9522; XGB v2 0.9347/0.9699; CatBoost v1 0.9132/0.9581; CatBoost v2 0.9367/0.9699; logreg v1 0.8197/0.8996; logreg v2 0.8318/0.9068. RF+Morgan v1 selected on AUPRC, the primary metric for the 79% positive class.
- Seed stability check (RF v1): seeds 17/23/42 -> AUPRC 0.9754/0.9707/0.9716, AUROC 0.9423/0.9390/0.9370; seed 17 kept (differences ~0.005 AUPRC, so not a fragile selection).

Selected-model validation metrics (n=240, 167 positives): AUROC 0.9423, AUPRC 0.9754, EF@1% 1.437, EF@5% 1.437. EF caveat: 1% of 240 = 2.4 molecules, so top-1% EF is quantized (2/2 top-ranked validation molecules positive) and identical across all models; AUROC/AUPRC are the discriminating evidence.

Locked evaluation (one call, evaluation.locked --target PT --endpoint Ki --desc-set v1 --receipt evaluation/pt_locked.json): receipt quotes AUROC 0.9545, AUPRC 0.9933, EF@1% 1.134, EF@5% 1.134. Protected output path recorded in receipt only; raw locked metrics not read.

Library ranking: screening.rank scored all 100,000 ZINC molecules (0 invalid) with the evaluated model; top-100 path: screening/pt_rf_v1_top100.csv (ranks 1-100, scores 0.935 -> 0.880; full ranking screening/pt_rf_v1_full_ranking.csv; report screening/pt_rf_v1_report.json, model_sha256 matches models/pt_v1_rf_r2/model.joblib). Top hits are plausible polars/amides (e.g. rank 1 zinc072072, rank 2 zinc058631). No hit-rate/EF is claimed for the unlabeled library per policy.

Experience: experience.retrieve on experience_m.json returned 0 PT records (PT-filtered result experience/pt_retrieval.json). The full store has 16 records for D2/5HT/ADR/DRD2/MOR/CBR/KOR/CA2; each applicability note limits it to its own dataset/size/positive-rate, so no experience id was applicable or reused.

Cost: 16 scientific jobs, 73.3 s summed compute (all CPU, no GPU); end-to-end 134 s (18:25:07 -> 18:27:21 UTC). Main artifacts: features/pt_v1_r2_2048.npz, models/pt_v1_rf_r2/{metrics.json,predictions.csv,model.joblib}, screening/, evaluation/pt_locked.json. Limitation: validation is 240 molecules, so AUPRC/AUROC are the reliable evidence and EF@1% is coarse; PT store has no prior experience.
