# A #7 kor

- task: `p7b_a_kor`
- ticket: `7ab8a3f3989cc53dffe85d42236b667f`
- state: ready
- wall: 252.3s, jobs 16 (failed 1), models 10
- best validation model (any split): runs/kor_ki_v1_rf AUROC=0.9843 AUPRC=0.9935 EF@1%=1.387
- best scaffold model: runs/kor_ki_v1_rf AUROC=0.9843 EF@1%=1.387
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

P7b KOR (Ki) arm A complete: frozen split, no experience store, one locked evaluation, full 100k ranking.

DELIVERABLES (workspace-relative):
- Model: runs/kor_ki_v1_rf/model.joblib (sha256 4f035d8d16308caaa809653ba44397b5d7343c8372c1acb6c2d9baec05fe4d97)
- Locked receipt: evaluation/kor_locked.json (sha256 ef187309ffcd9124529349476c134c9c0b9327c2bee992d46bd2ecabe415a03c)
- Top-100: rankings/kor_top100.csv (100 rows, sha256 fa77e456ad6fb237e6a16bd6a6af43315389aaa472e67f1de184dafd0e0c06e7)
- Full ranking: rankings/kor_library_ranked.csv (100,000 rows)
- Screening report: rankings/kor_screening_report.json
- Metrics: runs/kor_ki_v1_rf/metrics.json

CHOICES AND WHY.
- Data: 1,899 labeled ChEMBL OPRK1 Ki molecules; frozen manifest used exactly as given via --split-manifest (data.split never called). Counts: 1,624 train / 190 validation, remaining 85 hidden test.
- Features: desc_set v1 = Morgan radius 2, 2048 bits + 7 RDKit 2D descriptors. v1 beat v2 on validation for every model family; v1 is also the locked-eval default, so train/serve featurization matches.
- Model: RandomForest selected after a controlled validation comparison (scaffold val only; test never touched): v1 RF AUROC 0.9843 / AUPRC 0.9935; v1 XGB 0.9757/0.9905; v1 CatBoost 0.9787/0.9916; v1 logreg 0.9464/0.9762; v2 RF 0.9738/0.9882; v2 XGB 0.9747/0.9898; v2 CatBoost 0.9772/0.9913. RF handles sparse Morgan bits + few dense descriptors well at this train size and had the best validation AUROC/AUPRC.
- Seed: kept default seed 17. Seed-robustness scan on v1 RF: AUROC 0.9837 (s1), 0.9807 (s42), 0.9842 (s2024) vs 0.9843 (s17); differences are within noise, so no seed cherry-picking.
- No experience store: approach derived from scratch; 0 experience IDs reused.

VALIDATION (190 molecules, 137 positives = 72.1% prior; AUPRC baseline 0.721):
- AUROC 0.9843, AUPRC 0.9935, accuracy 0.9368, F1 0.958, EF@1% 1.387, EF@5% 1.387. EF@1% saturates at this size (top 1% = 2 molecules, both active), so AUROC/AUPRC are the meaningful validation evidence.

LOCKED EVALUATION (single shot, target KOR, endpoint Ki, desc_set v1):
- Receipt quotes AUROC 0.9129, AUPRC 0.9576, EF@1% 1.459, EF@5% 1.459. Raw locked metrics remain in the protected tree; only the summary receipt is readable. Locked AUROC is lower than validation, consistent with scaffold distribution shift.

LIBRARY RANKING:
- 100,000/100,000 library molecules featurized, 0 invalid; top-100 exactly 100 rows, score range 0.830-0.904, best-first. No hit-rate/EF claims: the library is unlabeled.

COST / VERIFICATION:
- 16 scientific-tool jobs: 15 successful + 1 deliberate path-resolution probe (screening.rank with a missing library) that failed as expected with no artifacts and no effect on results.
- Productive wall clock 140 s (19:04:59-19:07:19Z; 194 s including the probe), summed job wall time ~69 s; CPU only, no GPU used.
- Verification: featurization 1,899/1,899 and 100,000/100,000 valid; ml.train exit 0 with 1,624/190/85 counts; locked eval exit 0; screening.rank exit 0 and report rows_featurized=100000, rows_invalid=0; top-100 row count checked.

RISKS / LIMITATIONS:
- Only 190 validation molecules with a 72.1% positive prior; AUPRC/EF are inflated by class imbalance, and the model is a single seed trained on the frozen train split only (validation held out by the pipeline).
- Locked test AUROC 0.9129 < validation 0.9843; expect real scaffold-shift degradation.
- The 100k library is unlabeled, so no true enrichment can be computed; scores are model predictions only.
- No code change was requested or made, so there is no PR; this is a scientific-run deliverable.
