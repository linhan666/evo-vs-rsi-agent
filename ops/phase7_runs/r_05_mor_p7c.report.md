# R #5 mor

- task: `p7c_r_mor`
- ticket: `cf993cda4fe6ef428b06ef08064cffea`
- state: ready
- wall: 222.7s, jobs 15 (failed 0), models 9
- best validation model (any split): models/mor_ki_v2_rf_seed7 AUROC=0.9427 AUPRC=0.9744 EF@1%=1.416
- best scaffold model: models/mor_ki_v2_rf_seed7 AUROC=0.9427 EF@1%=1.416
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

P7c MOR (Ki) target 5 completed in the ticket workspace. Deliverables are artifacts, not code: no GitHub PR (pr_number null). 15/15 scientific jobs succeeded; 2 min 46 s wall from first to last job (115 s summed tool wall, screening dominates at 78 s).

DECISIONS / WHY
1) Split: passed the frozen manifest .../chembl/oprm1/ki/splits/frozen_oprm1.json to ml.train as --split-manifest; did NOT call data.split. Manifest split used: train 2385, validation 279 (197 positives, 70.6%); locked test portion never touched before the single locked evaluation.
2) Features: desc_set v2 = Morgan r2 2048 bits + 7 RDKit 2D descriptors (MW, logP, HBD, HBA, TPSA, rotatable bonds, rings). v2 beat v1 at equal model (RF 0.9410/0.9738 vs 0.9362/0.9722 AUROC/AUPRC). 2790/2790 dataset SMILES featurized, 0 invalid.
3) Model: RandomForest on v2, chosen over logreg/xgboost/catboost (validation AUROC/AUPRC): logreg 0.8781/0.9374; xgboost 0.9277/0.9621; catboost 0.9253/0.9637; RF 0.9410/0.9738 (seed17), 0.9422/0.9747 (seed42), 0.9427/0.9744 (seed7). Seed spread <=0.002 AUROC, RF dominance is not a seed artifact. Chosen model: models/mor_ki_v2_rf_seed7 (seed 7; AUROC best, AUPRC within 0.0003 of seed 42).

METRICS (chosen model, frozen scaffold validation, 279 molecules)
AUROC 0.9427 | AUPRC 0.9744 | EF@1% 1.416 (top 3 of 279 all positives; EF@5% 1.416). All sweep models had EF@1% 1.416, so AUPRC/AUROC disambiguate.
LOCKED (one call, evaluation/mor_locked.json; target MOR, endpoint Ki, desc_set v2, model models/mor_ki_v2_rf_seed7/model.joblib): AUROC 0.9435, AUPRC 0.9759, EF@1% 1.379. Locked AUROC is consistent with validation (+0.0008), i.e. no leakage/tuning-through-test signature.

LIBRARY RANKING (screening.rank, same model sha b87b4d0cf5c1738b2c48af7f1630c9f96ee287435ebfa4047cb23af0df742565)
100,000/100,000 library SMILES featurized, 0 invalid, 77.6 s. Top-100: ranking/mor_ki_v2_rf_top100.csv (sha256 77b05cdc51aa3832e07d8352948e504753672e6ab96a316109fed37d33035d1e; score range 0.945 -> 0.8252). Full ranking: ranking/mor_ki_v2_rf_library_ranked.csv (sha256 92a50236211f35f961d826b277d7d15ffb374745519289bf6254b076edf604fc). Top-3: zinc025392, zinc050152, zinc076299. Screening report: ranking/mor_ki_v2_rf_screening.json. These are unlabeled model scores only: no hit rate/EF claim is possible for the 100k library.

EXPERIENCE: experience.retrieve on .../experience/experience_r.json returned count 0 both for target MOR and unfiltered (identical output sha b8dbaa59...; experience/mor_retrieve.json). 0 experience ids reused; store is empty.

LIMITATIONS: class prevalence is high (79.5% positives), so AUPRC is optimistic in absolute terms; EF@1% is ceiling-limited on both validation (3-molecule top 1%) and locked test and is reported as-is. Library was scored as provided (report states dedup is caller preprocessing, so duplicates were not removed). Raw locked metrics stay in the protected tree; only the receipt summary was read.

EVIDENCE: evaluation/mor_locked.json (receipt), models/mor_ki_v2_rf_seed7/{model.joblib,metrics.json,predictions.csv,artifact_manifest.json}, features/mor_ki_v{1,2}{,_report}.json, ranking/*.
