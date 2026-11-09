# M #2 5ht

- task: `p7d_m_5ht`
- ticket: `e9ca34c7b2b71b795e0e52b7f5ff4503`
- state: ready
- wall: 332.6s, jobs 17 (failed 1), models 9
- best validation model (any split): models/5ht_v1_rf_seed7 AUROC=0.9992 AUPRC=1.0 EF@1%=1.025
- best scaffold model: models/5ht_v1_rf_seed7 AUROC=0.9992 EF@1%=1.025
- refits excluded from ranking: []
- top-100 artifacts: 2

## agent report

5HT/Ki pipeline complete in the ticket workspace (no PR — scientific deliverable, not a code change).

DATA/SPLIT: dataset_p7b.csv 4104 valid molecules (4015 positive, 97.8% positive rate), 0 invalid SMILES; frozen scaffold manifest passed to ml.train --split-manifest (data.split never called): train 3509 / validation 410 (400 pos) / locked test 185. Labels: label column, label_source "chembl_ki", endpoint Ki.

FEATURES: Morgan r=2, 2048 bits + 7 descriptors, desc_set v1 (v2 was tested and gave no gain). Library: 100000 read, 100000 featurized, 0 invalid.

MODEL SELECTION (validation only, frozen split): logreg v1 AUROC .9693/AUPRC .9991; rf v1 .9990/1.0000 (rf seeds 7 and 42: .9992/1.0000); xgboost v1 .9918/.9998; catboost v1 .9953/.9999; rf v2 .9990/1.0000; xgboost v2 .9938/.9998; catboost v2 .9895/.9997; logreg v2 failed (exit 1, no artifacts, cause not surfaced). Selected catboost v1: validation AUROC 0.9953, AUPRC 0.9999, EF@1% 1.025, accuracy 0.9902. Why: AUPRC is tied at the ceiling; the .0037 AUROC gap to RF equals ~2 of only 10 validation negatives (noise-level); RF probabilities saturate at exactly 1.000000 for the whole top-100, so its top-100 order is arbitrary within the tie, while catboost gives graded library scores (top-100 0.99921–0.99977) and a resolved, reproducible ranking.

LOCKED TEST (one call, receipt evaluation/5ht_locked.json, sha256 0cfbd439e02dcc89edbfdd1ea8d3ec09834e5c9a9f2196ed68891bb6e14de5ea): AUROC 0.9264, AUPRC 0.9993, EF@1% 1.008, EF@5% 1.008. Raw locked metrics stay in the protected tree; receipt is summary-only. Model evaluated: models/5ht_v1_catboost/model.joblib (sha256 b6e5eec8189a7bda3d35586cd5e7bcc60bc65593e3ee8158798d52a6c557f08a), desc_set v1, target 5HT.

DELIVERABLES (absolute): top-100 /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/ht-p7d-m-e9ca34c7b2b7/rankings/5ht_v1_catboost_top100.csv; full 100k ranking .../rankings/5ht_v1_catboost_ranked.csv; screening report .../rankings/5ht_v1_catboost_report.json; model .../models/5ht_v1_catboost/model.joblib; receipt .../evaluation/5ht_locked.json. Comparison artifacts from the runner-up: .../rankings/5ht_v1_rf_* (RF top-100 is score-saturated at 1.0).

EXPERIENCE: experience.retrieve on experience_m_rep2.json returned 2 records, both target D2 (dataset_D2_001, model_D2_002, created 08:26:10Z); target-filtered 5HT retrieval = 0 records. Experience ids reused/applicable: 0.

COST: 17 scientific jobs total (16 succeeded, 1 failed logreg-v2 training), 08:26:34.8Z–08:30:48.5Z = 253.8 s (~4m14s), CPU only, no GPU.

LIMITATIONS: single locked evaluation by design; test AUROC rests on 185 molecules at ~97% positives, so a couple of negatives move it a lot and it sits well below validation (scaffold shift + small negative count); EF@1% is at its ceiling for this class balance and is not evidence of enrichment; the fitted model uses split-train only (ml.train does not refit on train+val); the 100k library is unlabeled, so no hit-rate/EF claim is made for it.
