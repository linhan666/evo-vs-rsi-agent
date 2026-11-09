# M #3 adr

- task: `p7d_m_adr`
- ticket: `ae4449ead3686ae204db62b7e06e56e7`
- state: ready
- wall: 198.0s, jobs 11 (failed 0), models 5
- best validation model (any split): models/adr_ki_v1_rf AUROC=0.934 AUPRC=0.9962 EF@1%=1.04
- best scaffold model: models/adr_ki_v1_rf AUROC=0.934 EF@1%=1.04
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

P7d arm M, ADR/Ki: complete. Frozen split honored (passed the frozen scaffold manifest to ml.train; data.split never called), one locked evaluation, 100k library ranked.

Setup: labels dataset_p7b.csv (2870 molecules joined; 2454 train / 287 validation; 2748 positives = 95.75%), Morgan r=2/2048 + 7 RDKit descriptors. Frozen manifest split_strategy=scaffold-manifest (test_fraction ignored).

Choices and why (validation AUROC/AUPRC/EF@1%): rf v1 0.9340/0.9962/1.04 -> chosen (best on both AUROC and AUPRC); logreg v1 0.8814/0.9929/1.04; xgboost v1 0.8231/0.9893/1.04; catboost v1 0.8518/0.9876/1.04; rf with desc_set v2 0.9153/0.9940/1.04. EF@1% is saturated (~1.04) at 96% prevalence (top 1% = 2-3 molecules), so model choice used AUROC/AUPRC; EF@1% is reported but non-discriminative here.

Locked evaluation receipt (evaluation/adr_locked.json, sha256 03f1c44cd61f4badb0dd819a876a4afc0d2002e56ff5f12dc40dff1272ed9101): AUROC 0.8072, AUPRC 0.9908, EF@1% 1.035, EF@5% 1.035. Honest gap vs validation (0.934 -> 0.807) on the protected test set; no per-sample test data was accessed.

Screening: 100000/100000 library molecules featurized, 0 invalid, 23.9 s. Top-100: $DSH_SUPERAGENT_DIR/screening/adr_ki_top100.csv (sha256 4517646abd06d8a94b8c92aebfc93e95b1565b1ed62ce46a5d1e1eaaa29226a7); full ranking $DSH_SUPERAGENT_DIR/screening/adr_ki_ranked.csv (sha256 fe31a51451e64bfa96944eb79a721d6922b8a6f0647914066404205ca9ad2aa3). Top-100 score range 0.995-1.000 with many ties at 1.000, so order within ties is arbitrary. No hit-rate/EF claim is made for the unlabeled library.

Supporting artifacts: features/adr_ki_p7b_v1.npz(+report), models/adr_ki_v1_rf/{model.joblib,metrics.json,predictions.csv}, screening/adr_ki_rank_report.json, evaluation/adr_locked.json (all under $DSH_SUPERAGENT_DIR).

Experience store experience_m_rep2.json: target=ADR retrieval returned 0 records; unfiltered retrieval returned 4 cross-target records, all consulted as priors only - dataset_D2_001, model_D2_002, dataset_5HT_003, model_5HT_004 (applicability: ChEMBL Ki binary sets ~6811/~4828 molecules, positive rate 0.9621/0.9803, scaffold split). Applicability re-checked: ADR set is smaller (2870) though similarly imbalanced (0.9575), so their numeric priors were not applied; no ADR-specific experiences exist yet.

Cost: 11 scientific jobs, all SUCCEEDED; 52.7 s total tool wall time (screening 24.5 s, training 20 s, featurization 4.6 s, retrieval/eval 3.8 s); ticket end-to-end ~98 s. No code change, no PR required. Draft/limitations: validation EF@1% non-discriminative; val-to-locked AUROC gap should be stated whenever this model's reliability is cited.
