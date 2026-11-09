# M #6 cbr

- task: `p7e_m_cbr`
- ticket: `115d38145ea245d347581ebcced2f259`
- state: ready
- wall: 515.5s, jobs 22 (failed 0), models 13
- best validation model (any split): models/cbr_v2_rf_s7 AUROC=1.0 AUPRC=1.0 EF@1%=1.016
- best scaffold model: models/cbr_v2_rf_s7 AUROC=1.0 EF@1%=1.016
- refits excluded from ranking: []
- top-100 artifacts: 3

## agent report

P7e Target 6/9 CBR (Ki) completed end-to-end with the scientific tools, one locked evaluation, and the 100k library ranked. No data.split call was made; the frozen manifest was passed directly to ml.train.

WORKSPACE: the ticket dir, /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/cannabinoid-p7e-m-115d38145ea2 (tool --workspace "."). Paths below are relative to it.

DATA/PROTOCOL
- Labels: scientific/.artifacts/chembl/cannabinoid_receptor/ki/dataset_p7b.csv (sha256 71b0b6ea…); 1963 joined molecules, 1925 positives (98.06%) — very few inactives.
- Frozen split: scientific/.artifacts/chembl/cannabinoid_receptor/ki/splits/frozen_cannabinoid_receptor.json used as --split-manifest only. Resulting counts: train 1679, validation 196 (193 positives, 3 negatives), test 88 (locked, not read).
- Features: rdkit.featurize, radius 2 / 2048-bit Morgan + v2 descriptor set, 1963/1963 valid (features/cbr_v2.npz, sha256 77281f5e…; features/cbr_v2_report.json). v1 was also built for comparison.

CHOICES AND WHY
- Model selection on the scaffold-manifest validation only. v1/v2 × logreg/rf/xgboost plus catboost, seeds 17/7/42. Validation AUROC: v2 logreg 0.9603, v2 rf 1.0 (all 3 seeds), v2 xgboost 0.7202, v1 logreg 0.9136, v1 rf 0.9983, v1 xgboost 0.8946; catboost v2 1.0 at all 3 seeds (accuracy 0.9949 at seed 17, 1.0 at seeds 7/42). v2 beat v1 for the linear model, and catboost matched the ceiling with the best accuracy and with top-100 library scores that are distinct, whereas Random Forest assigns exactly 1.000000 to at least the whole top 100 (tied ordering, arbitrary top-100), so CatBoost (v2, seed 17) was chosen as the primary and used for both the locked evaluation and the library ranking.
- Final model: models/cbr_v2_cat/model.joblib (sha256 f05b02b8…), metrics models/cbr_v2_cat/metrics.json.
- Validation for the chosen model: AUROC 1.0, AUPRC 1.0, EF@1% 1.016 (196 validation molecules, 3 negatives; EF@1% is quantised to 2 molecules and is uninformative at this size).
- Locked evaluation (one shot, receipt evaluation/cbr_locked.json, desc_set v2, target CBR, endpoint Ki): AUROC 0.6586, AUPRC 0.9943, EF@1% 1.012, EF@5% 1.012. Quoted verbatim from the receipt. Honest reading: the near-perfect validation AUROC was optimistic given only 3 validation negatives; on the 88-molecule locked test discrimination of inactives is weak (AUROC 0.6586) while AUPRC stays high because the positive rate is ~98%. Protected raw output: /home/linhan_cluster/evo_vs_rsi/protected/chembl37_ki_cbr/metrics_test_locked_agent_Ki_v2_._CBR.json (not readable from the ticket, summary only).
- Library: scientific/.artifacts/zinc/library_100k.smi, 100000/100000 scored, 0 invalid (rankings/cbr_cat_report.json; library sha256 09446ea1…). Predictions only — no hit rate or EF can be claimed for an unlabeled library.
  - Top-100: rankings/cbr_cat_top100.csv (sha256 93a32c38…)
  - Full ranking best-first: rankings/cbr_cat_ranked.csv (sha256 71992622…)
  - Screening report: rankings/cbr_cat_report.json; top score range 0.999068–0.999459 (scores compressed near 1 because of the 98% positive label base rate; the top-100 are the extreme tail of that distribution, not a validated hit list).
- Experience store: experience.retrieve on scientific/.artifacts/experience/experience_m_rep3.json. CBR query returned 0 records (experience/cbr_retrieve.json). Full-store read returned 10 records, all for other targets: dataset_D2_001/model_D2_002, dataset_5HT_003/model_5HT_004, dataset_ADR_005/model_ADR_006, dataset_DRD2_007/model_DRD2_008, dataset_MOR_009/model_MOR_010; their applicability notes (scaffold split, 2.8k–6.8k molecules, positive rates 0.66–0.98) do not cover this 1963-molecule / 0.9806 set, so no experience id was reused for any CBR decision — they were read as context only.

COST
- 22 scientific tool jobs (2 experience retrieves, 5 rdkit.featurize, 14 ml.train, 3 screening.rank, 1 evaluation.locked), plus 1 subagent that did no work.
- Wall clock first job start 09:39:03Z → last job end 09:46:24Z = 441 s (7 min 21 s); summed job-exclusive wall time 304 s; summed CPU 137 CPU-s; no GPU used.
- Largest single jobs: three 100k-library screenings (78–97 s each).

LIMITATIONS / RISKS
- Locked test is only 88 molecules and the validation inactives only 3, so both AUROC values are high-variance; the 0.6586 locked AUROC should be read with that in mind.
- The model was trained on the train split only (as ml.train with the frozen manifest does); no refit on train+val was performed, so the validated model and the evaluated model are the same object.
- Top-100 ordering is model-dependent: RF/logreg/catboost rankings of the same library share almost none of their top-100 (compressed scores), and there are no library labels to adjudicate, so the top-100 is a prioritisation list, not a claim of activity.
- No git/GitHub change: this ticket was scientific execution only, so there is no PR.
