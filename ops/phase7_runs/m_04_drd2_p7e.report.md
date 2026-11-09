# M #4 drd2

- task: `p7e_m_drd2`
- ticket: `be53a783eb12c20952bb2a31281fc125`
- state: ready
- wall: 223.2s, jobs 18 (failed 1), models 7
- best validation model (any split): work/p7e_m_drd2/model_rf_v2 AUROC=0.9544 AUPRC=0.9678 EF@1%=1.705
- best scaffold model: work/p7e_m_drd2/model_rf_v2 AUROC=0.9544 EF@1%=1.705
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

DRD2 (Ki) arm-M run complete; no PR (experiment ticket, artifacts under scientific/).

SETUP
- Labels: .artifacts/chembl/drd2/ki/dataset_p7b.csv (3293 rows, 3293 valid, 0 invalid; id=molecule_chembl_id, smiles=canonical_smiles, label=label). label_source recorded as "chembl_drd2_ki_dataset_p7b".
- Split: passed .artifacts/chembl/drd2/ki/splits/frozen_drd2.json as --split-manifest to ml.train; data.split was NOT called. Counts: train 2816 / validation 329 (193 val positives) / held-out 148.
- Experience store .artifacts/experience/experience_m_rep3.json queried via experience.retrieve for target DRD2 with kinds model/screening/dataset/transfer/harness (and "D2"): every query returned count 0 — no DRD2 records in this store, so zero experience ids reused (worked from first principles/frozen split only).

CHOICES AND WHY
- Featurization: rdkit.featurize Morgan r=2, 2048 bits + 7 RDKit descriptors; compared desc_set v1 vs v2. Radius/bit defaults kept because evaluation.locked has no radius/n_bits knobs — using non-default fingerprint params would break train/eval consistency.
- Model search under the frozen split: logreg, rf, xgboost, catboost × desc_set {v1,v2}, seed 17. Selected random forest on desc_set v2 (best validation AUPRC): AUROC 0.9544, AUPRC 0.9678, EF@1% 1.705, accuracy 0.8419, F1 0.8791 (val n=329, 193 positives). Runners-up: xgboost v2 0.9440/0.9612/1.705; catboost v2 0.9457/0.9626/1.705; rf v1 0.9481/0.9640/1.705; logreg v1 0.8764/0.8971/1.705. Model file: work/p7e_m_drd2/model_rf_v2/model.joblib (sha256 b5a03ccb…).
- No fusion/ensemble: ml.fuse emits predictions-only, not a fitted pipeline that screening.rank can serve; kept a single auditable model.

LOCKED EVALUATION (one call, 2026-11-09T09:32:15Z)
- evaluation.locked --target DRD2 --endpoint Ki --desc-set v2 --model work/p7e_m_drd2/model_rf_v2/model.joblib --receipt evaluation/drd2_locked.json (sha256 be6030dc…).
- Receipt metrics: locked AUROC 0.9215, AUPRC 0.9411, EF@1% 1.824 (EF@5% 1.824). Raw per-sample metrics remain in the protected tree (protected/chembl37_ki_drd2/metrics_test_locked_agent_Ki_v2_._DRD2.json), unreadable from this ticket.

LIBRARY RANKING
- screening.rank with the rf_v2 model, desc_set v2, Morgan r2/2048: library_100k.smi 100000 rows read, 100000 featurized, 0 invalid, 79.1 s; predictions only (no hit rate/EF claimed for the unlabeled library). Score range top-100 0.76–0.91.
- Full ranking: /home/linhan_cluster/evo_vs_rsi/scientific/work/p7e_m_drd2/ranking_drd2.csv (sha256 8fa0cef2…); screening report: work/p7e_m_drd2/screening_drd2.json.
- TOP-100 PATH: /home/linhan_cluster/evo_vs_rsi/scientific/work/p7e_m_drd2/top100_drd2.csv (sha256 66330d34…; rank,id,smiles,score; e.g. rank 1 zinc046207 score 0.910).

COST
- Wall clock ~3.3 min end-to-end (first job 09:29:13Z, last 09:32:32Z). 18 tool runs: 17 succeeded, 1 failed (rdkit.featurize rejected a workspace-relative input path; retried with the absolute data-root path), 0 GPU. Screening dominated at 79.6 s; all trains ≤5 s.

LIMITATIONS
- Validation is small (329 molecules; EF@1% = top 3 molecules), so EF is noisy; the locked AUROC (0.9215) is the headline held-out number and is lower than validation (0.9544), as expected for a scaffold split.
- 100k library is unlabeled: no true EF@1% or hit rate can be computed for it; only model scores are reported.
