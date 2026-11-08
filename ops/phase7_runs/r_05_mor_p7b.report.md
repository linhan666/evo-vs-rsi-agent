# R #5 mor

- task: `p7b_r_mor`
- ticket: `dec8efdcd715f17c4b0433cfe2956626`
- state: ready
- wall: 406.3s, jobs 20 (failed 1), models 12
- best validation model (any split): mor_frozen/seedcheck_rf_v2_s7 AUROC=0.9427 AUPRC=0.9744 EF@1%=1.416
- best scaffold model: None AUROC=None EF@1%=None
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

DONE — MOR (target #5) final model trained on the frozen split, locked once, 100k library ranked.

FINAL ARTIFACTS (ticket workspace, relative paths; same workspace the scientific tools ran in)
- Locked receipt: evaluation/mor_locked.json
- Full ranking (100,000 rows): mor_frozen/library_ranking_rf_v2.csv
- TOP-100: mor_frozen/top100_rf_v2.csv (100 rows, unique ids, score 0.9450 → 0.832917)
- Screening report: mor_frozen/screening_report_rf_v2.json
- Final fitted model: mor_frozen/model_rf_v2/model.joblib (sha256 9035b55d…)
- Evidence: mor_frozen/{feat_v1_report.json,feat_v2_report.json,model_*/metrics.json,screening_report_rf_v2.json}, mor_frozen/experience_retrieved.json, mor_frozen/exp_model_drd2.json

DATASET/SPLIT (frozen manifest used exactly as given, no data.split call)
dataset_p7b.csv: 2,790 labeled molecules, 0 invalid SMILES, positive rate 0.795 (2,219 pos). Manifest gives train=2,385 (2,022 pos), validation=279 (197 pos; 0.706). The remaining 126 labeled molecules are not in the manifest's train/validation partitions and were not used for fitting or selection. split_strategy recorded as "scaffold-manifest"; no test labels seen; locked test accessed only through evaluation.locked.

EXPERIENCE STORE
Target-filtered query (target=MOR) returned 0 records; unfiltered store has 8 records (D2, 5HT, ADR, DRD2 × dataset/model). Closest profile: dataset_DRD2_007 / model_DRD2_008 (ChEMBL Ki binary, 3,293 mols, 0.666 pos, scaffold split); also consulted dataset_ADR_005, dataset_5HT_003, dataset_D2_001 and their model records. Their applicability notes explicitly say "re-check before applying to much smaller or balanced datasets", and MOR (2,790 mols, 0.795 pos) is smaller/less extreme than every stored record. The retrieve tool exposes only experience_id/applicability/payload_sha256 (not the stored hyperparameters), so what was reused VERBATIM is the protocol frame: one frozen scaffold manifest shared by every arm, validation-only model selection, report AUROC/AUPRC/EF@1% plus calibrated scores, high-positive-rate ChEMBL Ki framing. Feature set, model family and seed grid were re-derived for MOR's profile (i.e., not transplanted). No experience configuration was copied at hyperparameter level because none was exposed by the store tool.

MODEL SELECTION (frozen-split validation only; 8 arms, seed 17)
desc_set v1 (Morgan r2/2048 + 7 RDKit 2D descriptors): logreg 0.8747/0.9348; rf 0.9362/0.9722; xgboost 0.9289/0.9637; catboost 0.9128/0.9565  (AUROC/AUPRC)
desc_set v2: logreg 0.8781/0.9374; rf 0.9410/0.9738; xgboost 0.9277/0.9621; catboost 0.9253/0.9637
Seed stability of the winner (RandomForest, desc_set v2): AUROC 0.9410/0.9427/0.9422 for seeds 17/7/42; v1 RF: 0.9362/0.9352/0.9316 → RF+v2 consistently best, margin ~0.008 AUROC.
CHOSEN: RandomForest, desc_set v2 (radius 2, 2048 bits), seed 17.
Frozen-split validation of chosen model: AUROC 0.9410, AUPRC 0.9738, EF@1% 1.416, EF@5% 1.416 (accuracy 0.8674, F1 0.9086).

LOCKED TEST (called exactly once) — evaluation/mor_locked.json, quoted verbatim:
{"target":"MOR","endpoint":"Ki","desc_set":"v2","model":"model.joblib","metrics":{"auroc":0.9425,"auprc":0.9745,"ef_at_1pct":1.379,"ef_at_5pct":1.379},"note":"summary only; the raw locked metrics file is not readable from the ticket"}
→ locked AUROC 0.9425 (AUPRC 0.9745, EF@1% 1.379), consistent with validation (0.9410), so the model does not appear to be validation-overfit.

TOP-100
screening.rank with the locked model on library_100k.smi using desc_set v2: 100,000/100,000 rows featurized, 0 invalid, elapsed 83.3 s. Top: rank1 zinc025392 score 0.945; rank100 zinc097917 score 0.832917. Path: mor_frozen/top100_rf_v2.csv. The library is unlabeled, so no hit-rate or EF claim is made for it (predictions only; library scored as provided, no dedup by the tool).

COST
20 tool jobs (19 successful + 1 deliberate failed probe of a bad store path); summed tool wall ≈199 s (3.3 min); end-to-end session 14:16:00–14:22:20 UTC ≈ 6.3 min. Dominant costs: library screening 83.8 s; catboost arms 57.6 s combined; featurization 6.5 s; all locked/validation runs <8 s. One CPU node, no GPU used.

LIMITATIONS / CAVEATS
- EF@1%/EF@5% saturate at this positive rate (1% of 279 = ~3 molecules) and are not informative; AUROC/AUPRC are the discriminative evidence.
- Locked metrics are a summary receipt only; per-sample locked errors were not accessed.
- 126 labeled molecules outside the manifest partitions were left unused; this is a property of the frozen split, not a filtering choice.
- Experience payloads (hyperparameters) were not retrievable from the store tool; reuse is protocol-level as stated.
No human decision or permission is required.
