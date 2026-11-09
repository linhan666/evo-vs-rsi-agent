# M #6 cbr

- task: `p7d_m_cbr`
- ticket: `410912a805ce2b07ac4902b98ffca2fc`
- state: ready
- wall: 277.8s, jobs 19 (failed 0), models 12
- best validation model (any split): runs/p7d_cbr/model_rf_v2_s7 AUROC=1.0 AUPRC=1.0 EF@1%=1.016
- best scaffold model: runs/p7d_cbr/model_rf_v2_s7 AUROC=1.0 EF@1%=1.016
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

CBR Ki (arm M) complete. Frozen split used via --split-manifest; data.split not called. One locked evaluation consumed. 100k library ranked.

DELIVERABLES
- Top-100: /home/linhan_cluster/evo_vs_rsi/scientific/runs/p7d_cbr/top100.csv (100 rows; rank 1 = zinc016128, score 0.999459; score range 0.999074-0.999459)
- Full ranking: /home/linhan_cluster/evo_vs_rsi/scientific/runs/p7d_cbr/library_ranked.csv (100000/100000 scored, 0 invalid; scored as provided, no dedup)
- Locked receipt: /home/linhan_cluster/evo_vs_rsi/scientific/evaluation/cbr_locked.json (sha256 e03ef62d726da78f3b29e44572780e9dcd8983357fef7509603d85317dde827f)
- Fitted model: runs/p7d_cbr/model_catboost_v2/model.joblib (sha256 33f5a2236227bcbd0cd1210423a48fc724f14f0b8198ce2278814ae7527d9e76)

CHOICE + WHY
Featurized 1963/1963 valid molecules (Morgan r2 2048 + 7 2D descriptors, v1 and v2). Compared logreg/xgboost/rf/catboost on v1: AUROC 0.9136 / 0.8946 / 0.9983 / 0.9965. v2 descriptors improved rf to 1.000 and catboost to 1.000. Selected CatBoost with desc_set v2, seed 17: perfect validation classification and stable across seeds 7/17/42 (val AUROC 1.000 all seeds). Split: 1679 train / 196 validation, 1925/1963 positives, 193 validation positives.

VALIDATION (selected model, scaffold-validation)
AUROC 1.000; AUPRC 1.000; EF@1% 1.016; accuracy 0.9949. Caveat: validation has only 3 negatives, so AUROC/AUPRC are fragile and EF@1% is at the positive-prevalence ceiling (~1.018), not evidence of enrichability.

LOCKED RECEIPT (target CBR, endpoint Ki, desc_set v2)
AUROC 0.6586; AUPRC 0.9943; EF@1% 1.012; EF@5% 1.012. The validation was strongly optimistic (1.000 -> 0.6586), so the top-100 list is model prioritization only, not a validated hit set; no hit rate/enrichment claim is made for the 100k library.

COST
19 jobs, all exit 0; wall clock 3m44s (08:47:43.6-08:51:27.1 UTC); sum of job wall times 124.3 s; ~101 CPU-seconds; no GPU. Screening dominated (80.2 s wall).

EXPERIENCE
Store experience_m_rep2.json queried via experience.retrieve. 10 records returned: dataset_D2_001, model_D2_002, dataset_5HT_003, model_5HT_004, dataset_ADR_005, model_ADR_006, dataset_DRD2_007, model_DRD2_008, dataset_MOR_009, model_MOR_010. CBR-filtered query: count 0. None were numerically reused: every record's applicability ties it to its own ChEMBL Ki set and prevalence, and the store has no CBR record, so they served only as provenance context.

LIMITATIONS
98% positive labels make AUPRC/EF uninformative; 3-negative validation; one locked evaluation only, no re-run; library not deduplicated. No PR applies (local experiment).
