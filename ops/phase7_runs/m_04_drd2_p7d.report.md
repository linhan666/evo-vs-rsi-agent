# M #4 drd2

- task: `p7d_m_drd2`
- ticket: `96ed1c2b7f13161f3719a587e48f93c8`
- state: ready
- wall: 330.6s, jobs 16 (failed 0), models 8
- best validation model (any split): .artifacts/chembl/drd2/ki/p7d_m/train_v2_rf AUROC=0.9544 AUPRC=0.9678 EF@1%=1.705
- best scaffold model: .artifacts/chembl/drd2/ki/p7d_m/train_v2_rf AUROC=0.9544 EF@1%=1.705
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

P7d DRD2 (Ki) arm M complete. Frozen split used directly (no data.split call); one locked evaluation consumed. All artifacts under scientific/.artifacts/chembl/drd2/ki/p7d_m/ plus receipt scientific/evaluation/drd2_locked.json.

DATA/SPLIT: dataset_p7b.csv featurized 3,293 molecules, 0 invalid (id=molecule_chembl_id, smiles=canonical_smiles, label=label, label_source=chembl_ki). Frozen manifest gave 2,816 train / 329 validation / 148 held-out test; worker never read test labels or per-sample test errors.

CHOICE AND WHY: compared logreg / rf / xgboost / catboost × desc_set v1/v2 (Morgan r=2, 2048 bits, + descriptors), seed 17, selection on validation only.
Validation AUROC / AUPRC (EF@1% all 1.705):
 v1 logreg 0.8764/0.8971; v1 rf 0.9481/0.9640; v1 xgb 0.9423/0.9608; v1 cat 0.9444/0.9595
 v2 logreg 0.8833/0.9038; v2 rf 0.9544/0.9678; v2 xgb 0.9440/0.9612; v2 cat 0.9457/0.9626
Picked RandomForest + desc_set v2 (best AUROC and AUPRC). Note: validation prevalence 193/329=0.5866, so EF@1% is capped at 1/prevalence=1.705; top 1% and 5% were all positives for every candidate, so EF@1% did not discriminate — AUROC/AUPRC did. Model: train_v2_rf/model.joblib (sha256 b5a03ccb…).

LOCKED RECEIPT (scientific/evaluation/drd2_locked.json, desc_set v2): AUROC 0.9215 (quoted from receipt), AUPRC 0.9411, EF@1% 1.824, EF@5% 1.824. Raw test metrics remain protected.

RANKING: screening.rank with the chosen model; 100,000/100,000 library molecules featurized, 0 invalid. Top-100: /home/linhan_cluster/evo_vs_rsi/scientific/.artifacts/chembl/drd2/ki/p7d_m/top100.csv (scores 0.76–0.91); full ranking ranked_100k.csv; screening_report.json records no hit rate/EF is defined for an unlabeled library.

COST: 16 scientific jobs (4 experience retrievals, 2 featurize, 8 training, 1 screening, 1 locked eval), CPU-only (no GPU). Aggregate tool wall 139.5 s; end-to-end 08:36:10–08:40:59 UTC ≈ 289 s (core featurize→receipt 194 s); screening dominates (89.2 s).

EXPERIENCE: experience_m_rep2.json retrieved (target DRD2 filter = 0 records; D2-family records dataset_D2_001 and model_D2_002 consulted). Their applicability note covers ~6,811-molecule, 96.21%-positive Ki sets and explicitly says re-check for much smaller/balanced sets; our 3,293-molecule, 66.57%-positive set violates that, so no model/hyperparameter was transferred. 5HT/ADR records not applicable. Reused for configuration: none; IDs consulted: dataset_D2_001, model_D2_002.

CAVEATS: validation n=329 and locked test n=148 → wide uncertainty; single seed 17; model selection exhausted before the one-shot evaluation; no GPU. No repo code changes, so no PR.
