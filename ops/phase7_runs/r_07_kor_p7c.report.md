# R #7 kor

- task: `p7c_r_kor`
- ticket: `8cbfbfae75f0234c93e5b9bef3e84783`
- state: ready
- wall: 205.9s, jobs 12 (failed 1), models 5
- best validation model (any split): models/kor_v1_rf AUROC=0.9843 AUPRC=0.9935 EF@1%=1.387
- best scaffold model: models/kor_v1_rf AUROC=0.9843 EF@1%=1.387
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

KOR (OPRK1) Ki binding-activity predictor built and used to rank the 100k library; one locked evaluation receipt issued. All outputs are workspace-relative under the ticket workspace (kor-p7c-r-8cbfbfae75f0).

DATA / SPLIT
- Labels: scientific/.artifacts/chembl/oprk1/ki/dataset_p7b.csv — 1,899 molecules, 1,500 positive / 399 negative (binary `label`; id=molecule_chembl_id, smiles=canonical_smiles). Single endpoint Ki; no Kd/IC50 mixing.
- Frozen manifest scientific/.artifacts/chembl/oprk1/ki/splits/frozen_oprk1.json passed to ml.train via --split-manifest; data.split was NOT called. Counts from ml.train: train 1,624 / validation 190 / test 85 held out. Locked test never inspected beyond the receipt summary.

CHOICES / WHY
- Featurization via rdkit.featurize: Morgan radius 2, 2048 bits + 7 RDKit 2D descriptors = desc_set v1; 1,899/1,899 valid, 0 invalid. desc_set v2 was also featurized and tested, then dropped as worse.
- Compared four model families on the scaffold-manifest validation only (seed 17, tool defaults, no tuning on test):
  | model | feats | AUROC | AUPRC | EF@1% |
  | logreg   | v1 | 0.9464 | 0.9762 | 1.387 |
  | rf       | v1 | 0.9843 | 0.9935 | 1.387 |
  | xgboost  | v1 | 0.9757 | 0.9905 | 1.387 |
  | catboost | v1 | 0.9787 | 0.9916 | 1.387 |
  | rf       | v2 | 0.9738 | 0.9882 | 1.387 |
- Selected random forest on desc_set v1: best validation AUROC and AUPRC. Fusion (ml.fuse) was not used because the one locked evaluation must reference a single fitted model file and screening had to use the same model the receipt covers. Normalisation/feature handling is inside the fitted pipeline from ml.train; no leakage across the frozen split.

VALIDATION RESULT (rf/v1, n=190, 137 positives)
AUROC 0.9843 | AUPRC 0.9935 | accuracy 0.9368 | F1 0.9580 | EF@1% 1.387 | EF@5% 1.387.

LOCKED EVALUATION (one call, as instructed: --target KOR --endpoint Ki --desc-set v1 --receipt evaluation/kor_locked.json)
Model: models/kor_v1_rf/model.joblib (sha256 f02e1cfcfe7573782495c079e1fb752e6d6f8c4cbe420b22f5eacc47bb42271d).
Receipt evaluation/kor_locked.json (sha256 ef187309ffcd9124529349476c134c9c0b9327c2bee992d46bd2ecabe415a03c) reports:
- Locked AUROC 0.9129
- Locked AUPRC 0.9576
- EF@1% 1.459, EF@5% 1.459
Raw locked metrics live in the protected tree (path recorded in the receipt: /home/linhan_cluster/evo_vs_rsi/protected/chembl37_ki_oprk1/metrics_test_locked_agent_Ki_v1_._KOR.json) and were not read.

LIBRARY RANKING
- screening.rank with the same fitted rf/v1 model and featurizer: 100,000/100,000 library molecules valid, 0 invalid.
- Top-100 path: screening/kor_rf_top100.csv (sha256 fa77e456ad6fb237e6a16bd6a6af43315389aaa472e67f1de184dafd0e0c06e7); full ranking screening/kor_rf_ranked.csv; report screening/kor_rf_report.json. Top score 0.904 (zinc089789); top-100 score range 0.830–0.904.
- Scores are predictions on an unlabeled library: no hit rate or EF@1% is defined or claimed for the library. Library scored as provided (no dedup).

EXPERIENCE
- experience.retrieve on the given store (.artifacts/experience/experience_r.json) returned count 0 / no records (also 0 unfiltered), i.e. the store currently has no applicable facts. Experience ids reused: none (0).

COST / JOBS
- End-to-end wall clock from trigger (22:35:10Z) to locked receipt (22:37:14Z) ≈ 124 s (~2 min).
- 12 scientific tool jobs: 11 succeeded, 1 failed (ml.train logreg on desc_set v2 failed inside the tool with no stderr; unused because rf-v2 validation was already worse than rf-v1). Summed tool runtime ≈ 39 s; CPU only, no GPU. Largest single job: 100k screening 14.7 s.

CAVEATS / LIMITATIONS
- Validation (190) and locked test (85) are small; AUROC/AUPRC confidence intervals are wide and the validation→locked drop (0.9843→0.9129) is expected under the scaffold split.
- EF@1% is effectively one top molecule at these set sizes, so it is a weak enrichment signal.
- Positive prevalence is high (1,500/1,899; validation 137/190), which inflates AUPRC and EF versus a balanced screen.
- No dataclass/endpoint mixing, no data.split call, no test-set peeking; the frozen manifest was used as-is.

KEY ARTIFACTS: features/kor_v1.npz (sha 090b9f7e…), models/kor_v1_rf/model.joblib + metrics.json, screening/kor_rf_ranked.csv, screening/kor_rf_top100.csv, screening/kor_rf_report.json, evaluation/kor_locked.json. No PR was created (local scientific deliverable, not a GitHub code ticket).
