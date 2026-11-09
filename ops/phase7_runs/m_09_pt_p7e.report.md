# M #9 pt

- task: `p7e_m_pt`
- ticket: `41d689fc1b7d46535e58720cc6563cb2`
- state: ready
- wall: 216.5s, jobs 16 (failed 1), models 9
- best validation model (any split): p7e_m_pt_v1_rf_s43 AUROC=0.9432 AUPRC=0.9751 EF@1%=1.437
- best scaffold model: p7e_m_pt_v1_rf_s43 AUROC=0.9432 EF@1%=1.437
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

P7e PT (Ki) target 9/9, arm M — complete. Frozen split honored, no data.split call, exactly one locked evaluation.

DATA / SETUP
- Labels: scientific/.artifacts/chembl/prothrombin/ki/dataset_p7b.csv (resolved columns id=molecule_chembl_id, smiles=canonical_smiles, label). Featurization: 2400 rows, 2400 valid, 0 invalid; 1905 positives (79.4%).
- Split: frozen_prothrombin.json passed as --split-manifest to ml.train; strategy recorded by tool as "scaffold-manifest"; counts train 2052 / validation 240 / locked test 108. Test never touched except by evaluation.locked.

CHOICES AND WHY
- Features: desc_set v1 (Morgan r=2, 2048 bits + 7 RDKit 2D descriptors). v2 was trained too but gave slightly lower RF validation AUROC (0.9404 vs 0.9423) and AUPRC (0.9732 vs 0.9754), so v1 was kept (simpler, same descriptor list, marginally better).
- Model: RandomForest. Head-to-head under the same frozen split (seed 17, v1): RF AUROC 0.9423 / AUPRC 0.9754; CatBoost 0.9132/0.9581; XGBoost 0.9039/0.9522; LogReg 0.8197/0.8996. RF won on both ranking metrics.
- Seed robustness (RF v1): seeds 17/43/101 gave AUROC 0.9423/0.9432/0.9311 (mean 0.9389, sd ~0.005) and AUPRC 0.9754/0.9751/0.9679. Seed 17 (pre-declared) was locked, not the best-seed cherry-pick.
- No fusion: evaluation.locked accepts a single ml.train pipeline, so a fused ranking could not be locked; the selected RF pipeline was used consistently for screening and locking.
- Train-only fit: the frozen manifest's train split (2052) was used for fitting; validation was only for model selection, so the locked test remained untouched and there is no val/test leakage.

VALIDATION (frozen scaffold-manifest validation, n=240, 167 positives)
- AUROC 0.9423, AUPRC 0.9754, EF@1% 1.437, EF@5% 1.437, accuracy 0.8542, F1 0.902.
- EF caveat: 1% of 240 is k=2 and both top-2 are positives, so 1.437 is the ceiling (1/0.6958) and not a discriminating number; RF's top-5% (k=12) were also all positive.

LOCKED TEST (single call; receipt evaluation/pt_locked.json, sha256 4a505440…)
- AUROC 0.9545, AUPRC 0.9933, EF@1% 1.134, EF@5% 1.134.
- desc_set v1, model p7e_m_pt_v1_rf/model.joblib (sha256 583bccc9…), endpoint Ki, target PT.
- Raw metrics stay protected: /home/linhan_cluster/evo_vs_rsi/protected/chembl37_ki_pt/metrics_test_locked_agent_Ki_v1_._PT.json (not readable from the ticket).

100k LIBRARY SCREENING
- Library 100000 rows, 100000 featurized, 0 invalid, 13.7s; scored with the same fitted pipeline (model sha256 583bccc9… matches ml.train artifact; library sha256 09446ea1…).
- Top-100: screening/pt_m_top100.csv (rank,id,smiles,score; top-100 score range 0.880–0.935).
- Full ranking: screening/pt_m_ranked.csv; report: screening/pt_m_report.json.
- Output paths are workspace-relative (same workspace that produced evaluation/pt_locked.json).
- Integrity: the library is unlabeled, so no hit rate, EF, or enrichment claim is made; the report states predictions only. No dedup was applied (tool records that as caller preprocessing).

EXPERIENCE STORE
- Store queried twice: target=PT returned 0 records; unfiltered returned 16 records covering D2, 5HT, ADR, DRD2, MOR, CBR, KOR, CA2. None is applicability-matched to PT (their notes are tied to other ChEMBL Ki sets/positive rates), so 0 experience ids were reused.

COST
- 16 registered tool jobs: 15 succeeded, 1 intentionally failed read-only probe (attempt to reveal the absolute workspace root; it produced no artifacts). Successful-job wall time 47.0s total (screening 14.2s dominates; training 1.9–4.7s per model; locked eval 1.8s); 16-job total 47.3s; end-to-end tool span ~113s (~2.3 min including analysis). CPU only, no GPU, one process at a time.

EVIDENCE FILES (workspace-relative)
- p7e_m_pt_labels_v1.npz + p7e_m_pt_labels_v1_report.json (2400/2400 valid)
- p7e_m_pt_v1_rf/{metrics.json,predictions.csv,model.joblib,artifact_manifest.json}
- screening/{pt_m_ranked.csv,pt_m_top100.csv,pt_m_report.json}
- evaluation/pt_locked.json
- Comparison runs retained for audit: p7e_m_pt_v{1,2}_{logreg,rf,xgb,cat}, plus RF seed reruns.

No blockers; no PR needed (scientific run, no code change requested).
