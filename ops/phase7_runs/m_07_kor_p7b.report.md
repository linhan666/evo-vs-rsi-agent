# M #7 kor

- task: `p7b_m_kor`
- ticket: `66f28c843a9d3e961eae0c0d9b7cb5f0`
- state: ready
- wall: 265.4s, jobs 20 (failed 2), models 11
- best validation model (any split): runs/cat_v1_s42 AUROC=0.9857 AUPRC=0.9943 EF@1%=1.387
- best scaffold model: runs/cat_v1_s42 AUROC=0.9857 EF@1%=1.387
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

P7b KOR (Ki, arm M) complete. Frozen split consumed as given (no data.split); one locked evaluation run; 100k library ranked with the same model.

DELIVERABLES (workspace /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/kor-frozen-m-66f28c843a9d):
- top-100: rankings/kor_top100.csv ; full ranking: rankings/kor_ranked.csv ; screening report: rankings/kor_rank_report.json
- locked receipt: evaluation/kor_locked.json
- chosen model: runs/rf_v1/model.joblib (+ metrics.json, predictions.csv, artifact_manifest.json)
- features: features/dataset_v1.npz + report ; experience retrievals: experience/kor_retrieve.json, experience/all_retrieve.json

PROTOCOL: dataset_p7b.csv loaded with 1899/1899 valid molecules (id=molecule_chembl_id, smiles=canonical_smiles); labels from ChEMBL OPRK1 Ki (label_source=chembl_oprk1_ki). Frozen manifest frozen_oprk1.json gave train=1624, validation=190 (137 pos), joined=1899, so held-out test=85; test not touched during selection. No data.split call.

CHOICES AND WHY:
- Desc set v1 (Morgan r=2, 2048 bits) beat v2 (Morgan + 7 RDKit 2D descriptors) for every model family (e.g. RF val AUROC 0.9843 vs 0.9738; CatBoost 0.9787 vs 0.9772), so v1 chosen: better generalisation and simpler.
- Compared logistic regression, RF, XGBoost, CatBoost on the same frozen split. RF won on validation AUROC/AUPRC and was stable across seeds 17/7/42 (AUROC 0.9843/0.9847/0.9807; AUPRC 0.9935/0.9935/0.9919). CatBoost was close (0.9787-0.9857) but no better on average. Seed 17 (pre-registered default) kept as final model; no seed cherry-picking, no hyperparameter tuning on the 190-molecule validation set, no test-driven selection. Fusion not used because evaluation.locked consumes one fitted pipeline and fused rankings cannot be locked-evaluated.
- Same v1 featurisation used for the library (radius 2, 2048 bits).

VALIDATION (frozen scaffold validation, RF v1 seed 17, n=190, 137 pos): AUROC 0.9843, AUPRC 0.9935, EF@1% 1.387 (EF@5% 1.387; only ~2 molecules in the top 1%, so EF is high-variance). Other val: XGB 0.9757/0.9905, CatBoost 0.9787/0.9916, logreg 0.9464/0.9762.

LOCKED AUROC (quoted from evaluation/kor_locked.json): AUROC 0.9129, AUPRC 0.9576, EF@1% 1.459. Receipt records target KOR, endpoint Ki, desc_set v1, protected_output /home/linhan_cluster/evo_vs_rsi/protected/chembl37_ki_oprk1/metrics_test_locked_agent_Ki_v1_._KOR.json (raw metrics not readable from the ticket). Scaffold test is harder than validation, as expected; this is the honest held-out number.

RANKING: screening.rank on library_100k.smi: 100000/100000 read and featurised, 0 invalid; top-100 written (top scores 0.904 down to 0.83). The library is unlabeled — scores are predictions only, no hit rate or EF@1% is defined or claimed. Library scored as provided (no dedup/filters applied; tool notes dedup is caller preprocessing).

COST: 20 tool jobs total (18 succeeded, 2 failed: logreg+v2 exits 1 deterministically with no surfaced message, twice — not competitive, not used). All CPU, no GPU. Wall clock from first job to locked receipt 160.6 s (2m41s); 210.9 s (3m31s) including a final store-metadata check; sum of job runtimes 86.2 s. Largest single job: library ranking 27.6 s.

EXPERIENCE REUSED: 0 experience ids. The store holds 12 records (dataset_D2_001, model_D2_002, dataset_5HT_003, model_5HT_004, dataset_ADR_005, model_ADR_006, dataset_DRD2_007, model_DRD2_008, dataset_MOR_009, model_MOR_010, dataset_CBR_011, model_CBR_012), all target-specific; a KOR-filtered retrieval returned count 0, and the unfiltered retrieval exposes only applicability metadata (no payload/fact text), whose notes explicitly limit them to their own datasets. Nothing was transferable to KOR, so no id is claimed as reused.

RISKS/LIMITS: (1) unlabeled 100k library cannot yield measured enrichment — none claimed; (2) validation/test sets are small (190/85), so EF@1% and the val-test AUROC gap are noisy; (3) logreg on desc_set v2 fails deterministically in the tool (exit 1, no message); (4) frozen-split duplicate hygiene is inherited from the operator manifest and was not re-derived (data.split explicitly forbidden). No code/PR changes were needed; this is an analysis deliverable.
