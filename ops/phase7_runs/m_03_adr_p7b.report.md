# M #3 adr

- task: `p7b_m_adr`
- ticket: `5c32acaa3fe6af5aa267bef16533d3cc`
- state: ready
- wall: 278.0s, jobs 16 (failed 1), models 9
- best validation model (any split): models/adr_rf_v1 AUROC=0.934 AUPRC=0.9962 EF@1%=1.04
- best scaffold model: models/adr_rf_v1 AUROC=0.934 EF@1%=1.04
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

P7b ADR Ki (arm M) complete. Frozen-split training (no data.split), one locked evaluation, 100k library ranked.

APPROACH. Featurized labels/dataset_p7b.csv (ChEMBL ADR Ki binary; 2,870 rows, 2,748 positives = 95.7%; 0 invalid SMILES) with rdkit.featurize: v1 = Morgan r=2/2048, v2 = v1+2D descriptors. Trained only on the frozen manifest's train molecules, model selection on its 287 validation molecules (276 positives) for logreg/rf/xgboost/catboost. RF/v1 won on validation, was stable across seeds 7/17/42 (AUROC 0.922-0.934), so RF/v1/seed 17 was locked (default seed, no seed cherry-picking).

VALIDATION (rf/v1, seed 17): AUROC 0.9340, AUPRC 0.9962, accuracy 0.9686, F1 0.984, EF@1% 1.04, EF@5% 1.04. (Alternatives: logreg/v1 0.8814/0.9929; rf/v2 0.9153/0.9940; xgboost/v1 0.8231/0.9893; xgboost/v2 0.7441/0.9851; catboost/v1 and v2 0.8518/0.9876; logreg/v2 failed exit 1, no artifacts, excluded.) With 276/287 positives, EF@1% is at its technical ceiling (~1.04 = 1/prevalence) and does not separate models; the 11 val negatives make AUROC noisy.

LOCKED (receipt evaluation/adr_locked.json, sha256 03f1c44c...): target ADR, endpoint Ki, desc_set v1, model models/adr_rf_v1/model.joblib → AUROC 0.8072, AUPRC 0.9908, EF@1% 1.035, EF@5% 1.035. Locked AUROC (0.8072) is below validation (0.9340), consistent with scaffold transfer; raw test file stays protected.

RANKING: screening.rank on the 100k library: 100,000 read/featurized, 0 invalid; top-100 at screening/adr_top100.csv, full ranking at screening/adr_ranked.csv, report at screening/adr_report.json. Scores best-first 1.000→0.995; 76 molecules tie exactly at 1.0, so fine ordering inside the tie group is not chemically resolved — predictions only, no hit-rate/EF claim on an unlabeled library.

COST: 16 scientific jobs (15 succeeded, 1 failed logreg/v2 in 2.4 s); sum of job wall time 145.3 s; end-to-end 3 min 23 s. Workspace artifacts:
- models/adr_rf_v1/model.joblib (+metrics/predictions/manifest)
- evaluation/adr_locked.json
- screening/adr_ranked.csv, screening/adr_top100.csv, screening/adr_report.json
- features/adr_p7b_v1.npz (+report), features/adr_p7b_v2.npz
- experience/retrieved_m.json, experience/retrieved_all.json

EXPERIENCE: experience_m.json held 4 records — dataset_D2_001, model_D2_002, dataset_5HT_003, model_5HT_004; no ADR record, so no ADR-specific id was reused. The D2/5HT applicability notes (ChEMBL Ki binary, ~96-98% positive rate, scaffold split) were re-checked against this set (2,870 molecules, 95.7%) — broadly consistent in kind but smaller, so used as context only (they guided expectation of near-ceiling AUPRC/EF and scaffold-based evaluation, not hyperparameters).

CAVEATS: no data.split call; split manifest honored; only Ki labels used; no per-sample test errors accessed; validations above are scaffold-manifest validation, not the locked test.
