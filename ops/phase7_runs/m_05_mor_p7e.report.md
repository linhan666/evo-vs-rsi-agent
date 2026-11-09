# M #5 mor

- task: `p7e_m_mor`
- ticket: `73d6f88b1a82686ccc5a23e2c0cb9d5f`
- state: ready
- wall: 318.7s, jobs 16 (failed 0), models 8
- best validation model (any split): runs/oprm1_ki_v2_rf AUROC=0.941 AUPRC=0.9738 EF@1%=1.416
- best scaffold model: runs/oprm1_ki_v2_rf AUROC=0.941 EF@1%=1.416
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

MOR/OPRM1 Ki — Target 5/9 (arm M), complete. Scientific run only; no repo change and no PR. All 16 tool jobs exited 0.

CHOICES AND WHY
- Frozen split honored exactly: ml.train --split-manifest .../chembl/oprm1/ki/splits/frozen_oprm1.json reported split_strategy="scaffold-manifest", joined 2790, train 2385 / validation 279 (126 test molecules stayed with the locked evaluator, never used). data.split was never called.
- Featurized dataset_p7b.csv twice (rdkit.featurize, Morgan r=2, 2048 bits + 7 2D descriptors, desc_set v1 and v2; 2790 rows, 0 invalid), then trained 8 candidates (logreg / rf / xgboost / catboost x v1 / v2, seed 17) on the frozen train split and compared only validation metrics.
- Selected random forest on desc_set v2 (highest validation AUPRC, then AUROC): val AUROC 0.9410, AUPRC 0.9738, EF@1% 1.416 (EF@5% 1.416). Runner-up rf v1: 0.9362 / 0.9722 / 1.416. Others: xgboost v2 0.9277/0.9621/1.416; catboost v2 0.9253/0.9637/1.416; xgboost v1 0.9289/0.9637/1.416; catboost v1 0.9128/0.9565/1.416; logreg v2 0.8781/0.9374/1.416; logreg v1 0.8747/0.9348/1.416.

LOCKED EVALUATION (one shot)
- evaluation.locked --target MOR --endpoint Ki --desc-set v2 --model runs/oprm1_ki_v2_rf/model.joblib --receipt evaluation/mor_locked.json (sha256 6ea308740a0590b0f22a7a0de4251ca068fc4eae9703d47ac6cd997c149adb8b).
- Receipt metrics, quoted: locked AUROC 0.9425, AUPRC 0.9745, EF@1% 1.379, EF@5% 1.379. Raw result stayed in the protected tree and was not read.

LIBRARY RANKING
- screening.rank with the same model/desc_set on library_100k.smi: 100000 rows read, 100000 featurized, 0 invalid, 79.4 s. Top-100 path: screening/mor_top100.csv (workspace-relative; /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/mor-p7e-m-73d6f88b1a82/screening/mor_top100.csv; sha256 61c3c0c231f35f4c6a6d3e08c28ab81520b568c4d5a34a6cd64a617f1f72f4be), scores 0.832917-0.945000 descending, rank 1 = zinc025392. Full ranking screening/mor_100k_ranked.csv (sha256 78d3c202073ada6dea65dd6ecddce124d740e82a9a31dc3bc99d7ed36c0ba300); report screening/mor_100k_report.json (sha256 d3858dfda89b68d4282695a46a6104b7908da4fbba50d4cbdd2dcebee0a2b15a). Predictions only: no hit rate or EF is claimed for the unlabeled library.

COST
- 16 scientific jobs (4 experience.retrieve, 2 rdkit.featurize, 8 ml.train, 1 evaluation.locked, 1 screening.rank); total tool wall 113.9 s (screening.rank 80.0 s dominates), end-to-end ~208 s from first tool call; CPU-only, no GPU.

EXPERIENCE
- experience.retrieve on the specified store experience_m_rep3.json: target=MOR -> 0 records (target=OPRM1 -> 0 too); unfiltered/kind-filtered -> 8 cross-target records only (D2, 5HT, ADR, DRD2).
- Experience ids reused: none directly — no MOR-tagged experience existed. Consulted: dataset_D2_001, model_D2_002, dataset_5HT_003, model_5HT_004, dataset_ADR_005, model_ADR_006, dataset_DRD2_007, model_DRD2_008. The tool returns only applicability summaries plus payload hashes (no model payload/facts), and their applicability notes describe ~0.96 positive-rate sets, unlike MOR's 0.795 (2219/2790 positives), so model selection had to be made on this target's own validation split.

CAVEATS / EVIDENCE NOTES
- 79.5% positive prevalence (2219/2790) means a high AUPRC baseline (0.795); the 0.9738/0.9745 values should be read against that.
- Validation EF@1% is saturated at 1.416 (precision 1.0 at top 1%, the ceiling for 197/279 validation positives), so EF@1% cannot discriminate models here; the v2-vs-v1 rf margin is small on 279 validation molecules. Locked AUROC 0.9425 tracks the 0.9410 validation value.
- Deliverable artifacts: evaluation/mor_locked.json; screening/mor_top100.csv, screening/mor_100k_ranked.csv, screening/mor_100k_report.json; runs/oprm1_ki_v2_rf/{metrics.json,predictions.csv,model.joblib}; features/oprm1_ki_{v1,v2}.npz; experience/*_retrieval.json.
