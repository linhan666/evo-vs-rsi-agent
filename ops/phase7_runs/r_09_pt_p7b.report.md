# R #9 pt

- task: `p7b_r_pt`
- ticket: `9ce42a9db97764e9a6bba7a55dfeb3da`
- state: ready
- wall: 227.6s, jobs 15 (failed 0), models 8
- best validation model (any split): runs/pt_rf_v1_s17 AUROC=0.9423 AUPRC=0.9754 EF@1%=1.437
- best scaffold model: runs/pt_rf_v1_s17 AUROC=0.9423 EF@1%=1.437
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

P7b PT (target 9/9) — deliverable report. All artifacts are in the ticket workspace; no GitHub PR (deliverable is the analysis, no code change).

DATASET / SPLIT
- dataset_p7b.csv (read-only): 2400 molecules, 1905 positives (79.4%), 0 invalid SMILES.
- Frozen split manifest passed verbatim as --split-manifest (data.split never called): train 2052 / validation 240 (167 pos, 69.6%). Locked test stays in the protected tree.

(a) CHOICES + RATIONALE
- Featurization: rdkit.featurize, Morgan r=2 / 2048 bits + 7 RDKit 2D descriptors, desc_set v1 (the locked channel is v1) and v2 (expanded descriptor vector) were both trialled.
- Model family compared on the frozen validation set: logreg, rf, xgboost, catboost (v1); rf and xgboost also on v2. Eight arms, seed 17 except rf seed checks.
- Selected: RandomForest (rf), desc_set v1, seed 17 — best validation AUROC and AUPRC; its seed-sensitivity was checked with seeds 42 and 7 (AUROC .9370/.9286, AUPRC .9716/.9679), so the choice is not an outlier.
- Models were fitted on train only; validation used for selection only (no test peeking). No negatives invented; labels are measured ChEMBL Ki binary labels from the provided file.

(b) FROZEN-SPLIT VALIDATION (n=240, 167 positives)
- Selected rf/v1/s17: AUROC 0.9423, AUPRC 0.9754, EF@1% 1.437 (EF@5% 1.437), accuracy 0.8542, F1 0.9020.

(c) LOCKED TEST — evaluation.locked called exactly once (receipt evaluation/pt_locked.json, sha256 4a505440…)
- "auroc": 0.9545 (verbatim). Also reported in the same receipt: auprc 0.9933, ef_at_1pct 1.134.

(d) TOP-100
- screening/pt_top100.csv (100 rows, rank,id,smiles,score; top scores 0.880–0.935). Full ranking: screening/pt_library_100k_ranked.csv (100000 molecules, 0 invalid). Library is unlabeled, so no hit-rate/EF claim is made for it.

(e) COST
- 15 scientific jobs, ~85 s total wall clock, CPU only (≤1 worker), max single job 27.8 s (catboost); screening 19.7 s; locked eval 2.3 s.

(f) EXPERIENCE STORE
- experience.retrieve on the given store for target PT returned count=0. Full store scan: 16 records (8 dataset + 8 model) for D2, 5HT, ADR, DRD2, MOR, CBR, KOR, CA2 — no PT record, and none covers PT's profile (different target class; different size/positive-rate range).
- Therefore no experience_id was used and nothing was reused verbatim; per the ticket's own rule, new configurations were explored only because prior experience does not cover this data profile. What was retained is the protocol pattern already fixed by the supplied manifest (binary ChEMBL Ki, scaffold frozen split, threshold-free AUROC/AUPRC/EF).

LIMITATIONS
- Validation has only 240 molecules, so EF@1% (~2.4 molecules at the cutoff) is coarse and was not used as the primary selection criterion; AUROC was .9286–.9423 across rf seeds.
- Locked receipt is summary-only by design; raw locked metrics are protected. Library scores are model votes from RF, not calibrated probabilities.

EVIDENCE
- runs/pt_rf_v1_s17/metrics.json (sha256 0f8c25ae…), model.joblib (a2b73478…)
- evaluation/pt_locked.json (4a505440…)
- screening/pt_screening_report.json (ad26bfb8…), ranked csv (8d526764…), top100 (30821dc2…)
- features/pt_dataset_p7b_v1.npz (d55558eb…), features/pt_dataset_p7b_v2.npz (bdd8bf81…)

