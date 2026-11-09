# M #7 kor

- task: `p7e_m_kor`
- ticket: `979895b8ce20ad3fabee2d9b8b5b3047`
- state: ready
- wall: 249.0s, jobs 18 (failed 1), models 9
- best validation model (any split): models/kor_cat_v1_s42 AUROC=0.9857 AUPRC=0.9943 EF@1%=1.387
- best scaffold model: models/kor_cat_v1_s42 AUROC=0.9857 EF@1%=1.387
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

P7e KOR (Ki) complete: frozen split honored, one locked evaluation taken, 100k library ranked, top-100 written. No data.split call, no extra locked evaluations.

SETUP
- Labels: dataset_p7b.csv (1899 joined rows; 1500 positives overall = 0.7899). Frozen manifest frozen_oprk1.json passed as --split-manifest to every ml.train: train 1624 / validation 190 (137 positives) / locked test 85 (seen only by evaluation.locked).
- Features: rdkit.featurize, Morgan r=2/2048 bits + 7 RDKit 2D descriptors, desc_set v1 (v2 also tested for RF; worse).
- Experience: experience.retrieve on experience_m_rep3.json -> 12 records (D2, 5HT, ADR, DRD2, MOR, CBR); no KOR record exists. Applicability guidance consulted: dataset_MOR_009 + model_MOR_010 (closest analogue: mu-opioid, 2790 mols, 0.7953 positive, scaffold split, matching KOR's 1899 mols / 0.7899 positive) and dataset_DRD2_007 (0.6657 positive) as contrast. The retrieval output exposes only applicability metadata (no per-record payload/hyperparameters), so no model settings were copied. Full id list reviewed: dataset_D2_001, model_D2_002, dataset_5HT_003, model_5HT_004, dataset_ADR_005, model_ADR_006, dataset_DRD2_007, model_DRD2_008, dataset_MOR_009/model_MOR_010 (reused as applicability context), dataset_CBR_011, model_CBR_012.

CANDIDATES (validation on frozen manifest; AUROC/AUPRC/EF@1%)
- logreg v1: 0.9464 / 0.9762 / 1.387
- RF v1 seed17: 0.9843 / 0.9935 / 1.387  <- selected
- RF v1 seed42: 0.9807 / 0.9919 / 1.387; seed2026: 0.9830 / 0.9929 / 1.387
- XGBoost v1: 0.9757 / 0.9905 / 1.387
- CatBoost v1 seed17: 0.9787 / 0.9916 / 1.387; seed42: 0.9857 / 0.9943 / 1.387; seed2026: 0.9773 / 0.9903 / 1.387
- RF v2: 0.9738 / 0.9882 / 1.387
- logreg v2: FAILED exit 1, no metrics emitted (not pursued; logreg was the weakest v1 candidate)
Why RF v1 seed17: best 3-seed mean AUROC (0.9827) and AUPRC (0.9928), best worst-case AUROC (0.9807), and v1 > v2; seed17 is the tool default. CatBoost seed42 was nominally the single best run (0.9857/0.9943) but less stable across seeds (worst 0.9773), so the more stable RF ensemble was kept. EF@1% on 190 validation molecules is saturated for all candidates (1% ~ 2 molecules; prevalence 0.721), so it did not discriminate; AUPRC/AUROC drove selection.

LOCKED EVALUATION (the only one)
- evaluation.locked --target KOR --endpoint Ki --model models/kor_rf_v1/model.joblib --desc-set v1 --receipt evaluation/kor_locked.json (sha256 ef187309ffcd9124529349476c134c9c0b9327c2bee992d46bd2ecabe415a03c).
- Receipt metrics: AUROC 0.9129, AUPRC 0.9576, EF@1% 1.459, EF@5% 1.459. Raw locked metrics stay in the protected tree; not read. Model sha256 f02e1cfcfe7573782495c079e1fb752e6d6f8c4cbe420b22f5eacc47bb42271d.

RANKING
- screening.rank with the same model on library_100k.smi: 100000/100000 valid, 0 invalid, 17.0 s; top score 0.904, rank-100 score 0.83.
- Full ranking: /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/kor-p7e-m-979895b8ce20/screening/kor_ranked.csv
- Top-100: /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/kor-p7e-m-979895b8ce20/screening/kor_top100.csv
- Library is unlabeled; no hit rate or enrichment is claimed for it.

COST
- 18 interpreter jobs total (17 succeeded, 1 failed), run serially by the interpreter; summed tool wall 63.8 s, including an unused 10.5 s library featurization (screening re-featurizes internally) and the 17.5 s screening job. End-to-end ~3 min (first job 09:47:59Z, receipt 09:50:40Z). CPU only, zero GPU.

LIMITATIONS
- EF@1% resolution is coarse (locked test n=85 -> 1% = 1 molecule; 1.459 = 1/prevalence), so EF values are at their ceiling and should not be over-interpreted.
- RF scores are compressed (top-100 0.83-0.904) and are ranking scores, not calibrated probabilities.
- Validation->locked AUROC gap 0.984 -> 0.913 reflects the harder scaffold-held-out test and its small size (n=85).
- No KOR experience record existed in the arm-M store, so experience reuse is limited to applicability context from MOR/D2/DRD2 records.
