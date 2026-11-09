# M #8 ca2

- task: `p7d_m_ca2`
- ticket: `bd4de6c4c38be2db4139f5dfeeeef810`
- state: ready
- wall: 298.8s, jobs 19 (failed 2), models 8
- best validation model (any split): p7d_m_ca2/models/rf_v1_s42 AUROC=0.9852 AUPRC=0.9992 EF@1%=1.056
- best scaffold model: p7d_m_ca2/models/rf_v1_s42 AUROC=0.9852 EF@1%=1.056
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

CA2 (Ki) target 8, arm M — completed: frozen-split training, model selection on scaffold validation, one locked test evaluation, and ranking of the 100k library. No code change; artifacts produced by the scientific tool server (workspace-relative paths).

DATA / SPLIT
- Labels dataset_p7b.csv: 6206 molecules, 0 invalid; binary positives 5751 (92.7%); frozen scaffold manifest gives train 5306, validation 621 (588 positives). data.split was NOT called.
- Features: rdkit.featurize Morgan r=2 / 2048 bits + 7 RDKit 2D descriptors, desc_set v1: ca2_ki_v1.npz (6206 valid) and library_v1.npz (100000/100000 valid, 0 invalid).
- desc_set v2 featurization also completed (ca2_ki_v2.npz, library_v2.npz) but ml.train rejected the v2 npz (exit 1, FEATURE_SHAPE_MISMATCH class, no stderr surfaced) for both logreg and rf; v1 was therefore used throughout and is the desc_set in the locked receipt.

MODEL SELECTION (all on the frozen scaffold validation, seed only affects model randomness)
| model | seed | AUROC | AUPRC | EF@1% |
| logreg | 17 | 0.9156 | 0.9936 | 1.056 |
| rf | 17 | 0.9838 | 0.9991 | 1.056 |
| rf | 7 | 0.9830 | 0.9990 | 1.056 |
| rf | 42 | 0.9852 | 0.9992 | 1.056 | CHOSEN |
| rf | 1234 | 0.9844 | 0.9991 | 1.056 |
| xgboost | 17 | 0.9716 | 0.9983 | 1.056 |
| xgboost | 7 | 0.9716 | 0.9983 | 1.056 |
| catboost | 17 | 0.9675 | 0.9981 | 1.056 |
Random forest seed 42 won on AUROC (primary) and AUPRC; EF@1% is uninformative because validation has only ~6 molecules at 1% and base positive rate is 92.7% (max attainable EF ~1.08). Model: p7d_m_ca2/models/rf_v1_s42/model.joblib, sha256 4630ebaa989a3ef0da1133d9efa8afbfb6c09adfc165533cf13cdce20660286f.

LOCKED EVALUATION (one call, evaluation/ca2_locked.json, sha256 609b1e2892021a4f092003a6dd54fa43c7f62ce78d900f13cfd4a7cdbb0f6110)
- AUROC 0.9683, AUPRC 0.9969, EF@1% 1.063, EF@5% 1.044; target CA2, endpoint Ki, desc_set v1, protected output /home/linhan_cluster/evo_vs_rsi/protected/chembl37_ki_ca2/metrics_test_locked_agent_Ki_v1_._CA2.json (raw not readable from ticket). Generalisation drop vs validation 0.9852 -> 0.9683 is expected.

SCREENING
- screening.rank with the locked model on library_100k.smi: 100000/100000 scored, 0 invalid, 14.3 s. Top scores saturate at 0.99-1.0, so within-tie order is library order; top-100 are dominated by primary sulfonamides (classic CA2 zinc-binding group), e.g. zinc045490, zinc055876, zinc091902.
- top-100: p7d_m_ca2/screening/ca2_top100.csv (sha256 a130062c87f3b7430350abfb89be366a5f1175632fba86ee15cef17d9ee3ddda); full ranking: p7d_m_ca2/screening/ca2_ranked.csv (sha256 91ba60d91320f20aa3738604bd671276d09221c6e7f3620aaabea1320882ced7); report: p7d_m_ca2/screening/ca2_screening.json. No hit rate/EF claimed for the unlabeled library; predictions only.

EXPERIENCE
- experience.retrieve with store experience_m_rep2.json: 14 records (dataset+model pairs for D2, 5HT, ADR, DRD2, MOR, CBR, KOR), 0 CA2-specific. Reused ids: dataset_D2_001/model_D2_002, dataset_5HT_003/model_5HT_004, dataset_ADR_005/model_ADR_006, dataset_DRD2_007/model_DRD2_008, dataset_MOR_009/model_MOR_010, dataset_CBR_011/model_CBR_012, dataset_KOR_013/model_KOR_014. Their applicability notes (ChEMBL Ki binary, scaffold split, ~1900-6800 molecules, 0.67-0.98 positive rate) cover CA2's 6206/0.927, so the prior "tree ensemble over Morgan FP, AUPRC near-saturated, trust AUROC" pattern was applied; the store exposes only applicability + payload hash, no hyperparameters, so no model config was transferred. Retrieval outputs: experience/retrieved_all_m.json, experience/retrieved_ca2_m.json (count 0).

COST
- 19 scientific jobs (17 succeeded, 2 failed = v2 feature incompatibility), 0 GPU, 83.75 CPU-s, 139.5 s aggregate tool wall time; end-to-end 08:56:22 -> 09:00:09 UTC (227 s). One subagent probe returned no shell access and produced nothing.

ARTIFACTS: features p7d_m_ca2/features/{ca2_ki_v1.npz,library_v1.npz,ca2_ki_v1.json,library_v1.json}; metrics per model under p7d_m_ca2/models/<name>/; locked receipt evaluation/ca2_locked.json.

RISKS / LIMITATIONS: AUPRC and EF are inflated/insensitive at 92.7% positives; v2 features unusable through ml.train (tool limitation, would need stderr to diagnose); library scores saturate so top-100 internal order is arbitrary among ties; locked AUROC is from a single one-shot evaluation and cannot be repeated from this ticket.
