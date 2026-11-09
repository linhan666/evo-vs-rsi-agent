# M #9 pt

- task: `p7d_m_pt`
- ticket: `f8474924c22c05f552ee493d8ca10934`
- state: ready
- wall: 381.1s, jobs 20 (failed 0), models 14
- best validation model (any split): train/v1_rf AUROC=0.9423 AUPRC=0.9754 EF@1%=1.437
- best scaffold model: train/v1_rf AUROC=0.9423 EF@1%=1.437
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

PT (prothrombin, Ki) arm-M/rep2 run complete. Frozen split used directly; data.split was never called. All outputs are under the ticket workspace; no repository files were modified (no code PR).

CHOICES AND WHY
- Data/protocol: ChEMBL Ki binary set dataset_p7b.csv, 2,400 molecules (1,905 positives, 79.4% prevalence); labels are Ki only. Passed the frozen scaffold manifest to ml.train: 2,052 train / 240 scaffold-disjoint validation (167 positives, 69.6%); 108 remaining manifest-test ids never entered training. label_source=chembl_ki, id column molecule_chembl_id, label column label.
- Features: rdkit.featurize, Morgan r=2, 2048 bits + 7 descriptors; compared desc_set v1 vs v2 on the same fixed validation only.
- Model selection on validation (never on the locked set): logreg/rf/xgboost/catboost on both desc sets, plus RF seeds 1/7/42. Selected random forest on desc_set v2 for accuracy + stability: 4-seed validation AUROC 0.9393 ± 0.0020 and AUPRC 0.9730 ± 0.0014, vs v1 RF 0.9352 ± 0.0058 / 0.9709 ± 0.0034. Alternatives: xgboost v2 0.9347/0.9699, catboost v2 0.9367/0.9699, logreg v2 0.8318/0.9068. Deployed the default seed 17 (0.9404/0.9732) rather than the best-scoring seed 42 (0.9415/0.9748), which is inside seed noise, to avoid seed cherry-picking.
- Single locked evaluation was used exactly once, on the selected model with --desc-set v2.

METRICS
- Validation (240 scaffold-disjoint molecules): AUROC 0.9404, AUPRC 0.9732, EF@1% 1.437 (EF@5% 1.437); AUPRC prevalence baseline 0.696. EF@1% is saturated/coarse here (top 1% ≈ 2-3 molecules, all positive), so AUPRC lift is the informative discrimination evidence.
- Locked receipt evaluation/pt_locked.json (single call): AUROC 0.9416, AUPRC 0.9912, EF@1% 1.134, EF@5% 1.134. Verified target PT, endpoint Ki, desc_set v2; protected raw file protected/chembl37_ki_pt/metrics_test_locked_agent_Ki_v2_._PT.json is not readable by design (summary receipt only). Locked AUROC is consistent with validation (+0.0012), no generalisation drop.
- Model sha256 7ece2869d9bdce3054c258e63f40f921775d498a0da23a9923d995388a1a1937; receipt sha256 a52efa7ec739c00c508fd613ae5da09496bf71f385cc4b54af125afeb313b5ab.

LIBRARY RANKING
- screening.rank scored 100,000/100,000 library molecules (0 invalid; scores 0.91-0.96). Top-100 path (absolute): /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/prothrombin-p7d-m-f8474924c22c/screening/pt_top100.csv (sha256 f4b9c40e93e6cb909b16cbda4250e6e9bdf4d754a30495412b998c056377a1b1); full best-first ranking: screening/pt_library_ranked.csv (100k rows). The library is unlabeled, so no hit rate/EF@1% is claimed for it.

COST
- 20 scientific tool jobs total (1 experience retrieve, 2 featurize, 14 ml.train, 1 screening.rank, 1 evaluation.locked, 1 filtered experience re-check); summed job wall time 138.5 s; 4 min 42 s from trigger to locked receipt (5 min 38 s including the final experience re-check). Slowest job 84.9 s (100k library scoring). CPU only.

EXPERIENCE IDS REUSED
- All 16 records of experience_m_rep2.json (8 prior targets) were consulted; the store exposes applicability envelopes and payload hashes, not model hyperparameters, so no configuration was copied. Envelopes actually applied: dataset_KOR_013/model_KOR_014 (1,899 molecules @ 0.7899 positive — nearest prevalence), dataset_MOR_009/model_MOR_010 (2,790 @ 0.7953), dataset_CBR_011/model_CBR_012 (2,309 molecules), dataset_CA2_015/model_CA2_016 (latest/most recent). Reused lessons: keep the frozen scaffold-disjoint validation, judge AUPRC against the high prevalence baseline, and make no enrichment claim on the unlabeled 100k library.

EVIDENCE FILES
features/pt_labels_v1.json, features/pt_labels_v2.json; train/v2_rf/{metrics.json,model.joblib,artifact_manifest.json}; train/v2_rf_s{1,7,42}/metrics.json; screening/pt_rank.json; screening/pt_top100.csv; screening/pt_library_ranked.csv; evaluation/pt_locked.json; retrieval/pt_m_rep2.json.

LIMITATIONS
- 100k library is unlabeled: ranking only, no true hit rate or EF@1%.
- RF scores are discrete (multiples of 0.005), so the top-100 cutoff can split a tie band; ordering within ties is deterministic but not model-preference.
- Locked raw metrics stay protected; only the summary receipt is available.
