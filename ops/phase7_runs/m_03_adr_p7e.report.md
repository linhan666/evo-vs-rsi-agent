# M #3 adr

- task: `p7e_m_adr`
- ticket: `0006c9b6e11fb0973a9954c92c74ba16`
- state: ready
- wall: 175.9s, jobs 12 (failed 0), models 5
- best validation model (any split): runs/adr_ki_rf_v1 AUROC=0.934 AUPRC=0.9962 EF@1%=1.04
- best scaffold model: runs/adr_ki_rf_v1 AUROC=0.934 EF@1%=1.04
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

ADR (Ki) arm M complete: frozen split used (no data.split), RF selected on validation, one locked evaluation, 100k library ranked. All artifacts under the ticket workspace.

DATA/FEATURES
- dataset_p7b.csv: 2,870 molecules, 2,870 valid SMILES, 0 invalid; label column: 2,748 positives / 2,870 = 95.75% positive (122 negatives). Endpoint Ki, label_source=chembl_ki_adr_p7b.
- Frozen manifest .../ki/splits/frozen_adenosine_receptor_a.json used as --split-manifest: joined 2,870 -> train 2,454 / validation 287 / held-out test 129. No data.split call.
- Features: Morgan radius 2, 2048 bits + 7 RDKit 2D descriptors (desc_set v1), defaults kept so screening and the locked evaluator featurize identically.

MODEL CHOICE (validation on frozen scaffold split; AUROC / AUPRC / EF@1%)
- logreg 0.8814 / 0.9929 / 1.04
- RF 0.9340 / 0.9962 / 1.04  <- selected
- xgboost 0.8231 / 0.9893 / 1.04
- catboost 0.8518 / 0.9876 / 1.04
- RF on v2 descriptors 0.9153 / 0.9940 / 1.04, so v1 retained.
Why RF: best validation AUROC and AUPRC on identical features/split; selection used validation only, never the locked test. EF@1% is structurally capped at ~1.045 by the 95.75% positive rate (max = 1/prevalence), so it shows no enrichment and must not be read as one; AUPRC baseline is 0.957 for the same reason.

LOCKED EVALUATION (exactly one call; receipt evaluation/adr_locked.json)
- target ADR, endpoint Ki, desc_set v1, model runs/adr_ki_rf_v1/model.joblib -> receipt quote: AUROC 0.8072, AUPRC 0.9908, EF@1% 1.035, EF@5% 1.035.
- Note: locked test is small (~129 molecules, roughly 6 negatives at this prevalence), so the 0.8072 vs 0.9340 validation gap has wide uncertainty; no change was made after seeing it.

LIBRARY RANKING
- 100,000 / 100,000 compounds scored, 0 invalid. Top-100: /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/adenosine-p7e-m-0006c9b6e11f/ranking/adr_ki_top100.csv (workspace-relative ranking/adr_ki_top100.csv); full ranking ranking/adr_ki_ranked.csv; report ranking/adr_ki_report.json.
- Scores 0.995-1.0 with many ties at 1.0; order within ties is not meaningful. Library is unlabeled: no hit-rate or EF claim is made.

EXPERIENCE
- Store retrieved (target-filtered and unfiltered): only ids dataset_D2_001, model_D2_002, dataset_5HT_003, model_5HT_004 (D2/5HT; applicability scoped to ~6,811/~4,828-molecule Ki sets at ~0.96/0.98 positive rate, scaffold split). No ADR-specific record exists; ADR is 2,870 at 0.9575, outside that size scope, so model/feature choices were re-checked empirically on the ADR validation split. No ADR-specific experience fact was reused as authority.

COST
- 12 scientific jobs (3 experience.retrieve, 2 rdkit.featurize, 5 ml.train, 1 screening.rank, 1 evaluation.locked); 120.8 s end-to-end (09:25:51Z -> 09:27:51Z), ~39.2 s summed job wall time, CPU only, no GPU.

No human decision needed; all requested deliverables are produced.
