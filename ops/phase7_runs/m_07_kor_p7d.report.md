# M #7 kor

- task: `p7d_m_kor`
- ticket: `8d5b826d4c97a4630c4456b33c8c1bb3`
- state: ready
- wall: 189.6s, jobs 18 (failed 2), models 7
- best validation model (any split): train_kor_v1_rf AUROC=0.9843 AUPRC=0.9935 EF@1%=1.387
- best scaffold model: train_kor_v1_rf AUROC=0.9843 EF@1%=1.387
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

DONE — KOR (Ki) predictor trained on the frozen split, one locked evaluation spent, 100k library ranked. Deliverable is the metric set + artifacts in the ticket workspace (no code change, so no PR).

FILES (workspace kor-p7d-m-8d5b826d4c97/)
- kor_p7b_v1_features.json / kor_p7b_v1.npz — Morgan r=2, 2048 bit features (1899/1899 valid, 0 invalid)
- train_kor_v1_rf/{model.joblib,metrics.json,predictions.csv,artifact_manifest.json} — chosen model (sha256 f02e1cfc…)
- kor_library_ranked.csv (100000 rows), kor_top100.csv (top-100), kor_library_rank_report.json
- evaluation/kor_locked.json — locked receipt (sha256 ef187309…)
- experience/all_records.json — experience store retrieval

CHOICES
- Labels: dataset_p7b.csv resolved as id=molecule_chembl_id, smiles=canonical_smiles, label=label; 1899 molecules, 1500 positives (0.790). Ki only, no Kd/IC50 mixing; truncation relations inherited from the given binary labels.
- Split: passed as --split-manifest frozen_oprk1.json to ml.train; data.split never called. ml.train reports split_strategy=scaffold-manifest, train=1624, validation=190 (137 positives); the locked test set was never touched during development.
- Features: desc_set v1 = Morgan FP (radius 2, 2048 bits). v2 (FP+7 descriptors) was also tried and was slightly worse on both metrics; v1 keeps one representation and avoids descriptor scaling assumptions.
- Model: RandomForest. We compared logreg / rf / xgboost / catboost on v1 and rf / xgboost on v2 (all seed 17, same frozen manifest):

  model/feats      AUROC    AUPRC    EF@1% (val)
  logreg v1        0.9464   0.9762   1.387
  rf     v1        0.9843   0.9935   1.387  <- chosen
  rf     v1 s42    0.9807   0.9919   1.387  (stability check)
  xgboost v1       0.9757   0.9905   1.387
  catboost v1      0.9787   0.9916   1.387
  rf     v2        0.9738   0.9882   1.387
  xgboost v2       0.9747   0.9898   1.387
  RF on v1 was best on both AUROC and AUPRC and stable across seeds. Note the validation differences are small on 190 molecules (AUPRC baseline = 0.79 positive rate, so 0.9935 is well above chance), and validation EF@1% is quantized to the top ~2 molecules, hence identical 1.387 values — EF@1% is not discriminative at this validation size. Model selection used validation only; test never consulted.

LOCKED EVALUATION (receipt evaluation/kor_locked.json, target KOR, endpoint Ki, desc_set v1)
- AUROC 0.9129, AUPRC 0.9576, EF@1% 1.459, EF@5% 1.459 (quoted verbatim from receipt)
- The drop from validation 0.9843 → locked 0.9129 is expected under the larger hidden test; it is the honest generalisation number.

LIBRARY RANKING
- screening.rank on zinc/library_100k.smi with the fitted RF: 100000 rows read, 100000 featurized, 0 invalid, 14.6 s; full ranking kor_library_ranked.csv, top-100 kor_top100.csv, report kor_library_rank_report.json. Top scores 0.904 → 0.830 (top-100), ids zinc089789, zinc057266, zinc002741, zinc030154, zinc047578, …
- The library is unlabeled: no hit rate or EF@1% can be computed for it; the report states "no hit rate or enrichment is defined here". Library scored as provided (dedupe is a caller step; none applied).

COST
- 18 tool jobs total (16 succeeded; 2 early featurize attempts failed on a tool bug: nested report paths are not mkdir'ed — e.g. reports/…, re-run with flat paths), CPU only, no GPU.
- Sum of job wall time ≈ 49 s (featurize 10.5 s, 7 training runs 21.4 s, screening 15.0 s, locked eval 2.2 s); session wall clock ≈ 2.7 min.
- One locked evaluation for KOR/Ki used (one per ticket limit respected).

EXPERIENCE
- experience.retrieve from experience_m_rep2.json: KOR filter returned 0 records; full store has 12 records (dataset/model pairs for D2, 5HT, ADR, DRD2, MOR, CBR). No experience ids reused — none apply to KOR/Ki without a distribution caveat, so the model choice rests on this ticket's validation. Closest family note: dataset_MOR_009/model_MOR_010 (MOR Ki, 0.7953 positive) is consistent with KOR's high positive rate (0.790) but is not a KOR fact.

INTEGRITY
- Ki only; no negative-set invention (labels are the given binary ChEMBL labels); same standardised molecules kept within one split by the frozen manifest; no EF/hit-rate claim for the unlabeled library; no tuning on test; the receipt is summary-only and the raw locked file is in the protected tree.
