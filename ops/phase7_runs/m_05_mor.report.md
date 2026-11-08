# M #5 mor

- task: `seq_m_mor`
- ticket: `24fee0f1c8454fbfcdd7e7fe242975e4`
- state: ready
- wall: 343.5s, jobs 20 (failed 0), models 9
- best validation model (any split): train_random_rf AUROC=0.9576 AUPRC=0.9843 EF@1%=1.281
- best scaffold model: train_scaffold_s23_rf AUROC=0.9089 EF@1%=1.229
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

MOR (OPRM1) Ki binding-activity predictor — sequence arm target 5 — COMPLETE. No code change/PR (deliverable is the report + ranked library, per the assignment).

(a) Choices and rationale
- Data: read-only ChEMBL OPRM1 Ki dataset. 2,790 molecules, 2,790 valid SMILES; the dataset's provided binary `label` column used verbatim (no re-thresholding): 2,219 positives (79.53%). Scaffold (Bemis–Murcko) split via data.split, seed 17: train 1,674 / val 279 / test 837 (sums to 2,790). The split's test rows were never scored or inspected; the final estimate comes only from the independent locked evaluator.
- Representation: Morgan fingerprint radius 2 / 2048 bits + 7 RDKit 2D descriptors (desc_set v1).
- Model: Random Forest (ml.train rf, seed 17).
- Validation strategy: scaffold split is primary; random split run only as an optimistic diagnostic.
- Selection on scaffold-validation AUROC/AUPRC: RF 0.9089/0.9751 (chosen) > XGBoost 0.9016/0.9746 > logreg 0.8911/0.9615 > CatBoost 0.8821/0.9683; feature variants RF r=3 0.8830/0.9603 and RF desc_set v2 0.8789/0.9680 were worse. EF@1% saturates at 1.229 for every family (81.4% validation prevalence), so AUROC/AUPRC drove selection.
- Fusion rejected: the RF+XGB rank-fusion tool reports no fused performance metric and the two base AUPRCs differ by 0.0005 (within noise); a fused ranker also has no single fitted artifact the locked evaluator can score. Keeping one RF keeps the delivered top-100 and the locked metrics aligned.
- Scaffold split proved seed-invariant (seed 17 vs 23 gave identical assignments), so no second independent-split estimate exists; the locked test is the independent estimate.

(b) Metrics
- Scaffold validation (279 molecules, 227 positives): AUROC 0.9089, AUPRC 0.9751, EF@1% 1.229 (the 1/prevalence ceiling), EF@5% 1.229, accuracy 0.8602, F1 0.9199.
- Locked MOR/Ki test (independent evaluator, desc_set v1, one call): AUROC 0.9386, AUPRC 0.9740, EF@1% 1.379, EF@5% 1.379.
- Random-split RF diagnostic: AUROC 0.9576, AUPRC 0.9843 (optimistic; not the headline).

(c) Top-100 path
/home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/mor-arm-m5-24fee0f1c845/top100_mor_rf.csv (columns rank,id,smiles,score; 100 rows; scores 0.82–0.9025; top-5 ids zinc093549, zinc025392, zinc090159, zinc050992, zinc058304). Full 100k ranking: .../ranking_mor_rf.csv; screening report: .../screening_mor_rf.json. 100,000/100,000 library rows featurized, 0 invalid. Library was scored as provided (no caller dedup applied; the tool notes dedup is the caller's preprocessing step). No hit-rate/enrichment is claimed for the unlabeled library.

(d) Cost
20 tool jobs total: 84.5 s wall, 707.9 s CPU, 0 GPU (CPU-only). CatBoost exploration alone used 666.8 CPU s. The chosen path (retrieve → featurize → split → RF train → 100k screen → locked eval) cost about 26 s wall / 16 s CPU; the 100k screening was 17.4 s wall / 10.0 s CPU.

(e) Experience reuse
Retrieved the store from the exact absolute path; count=8 confirms the path is valid (a wrong/missing path returns 0). Records: dataset_D2_001/model_D2_002 (~6,811 @ 0.9621), dataset_5HT_003/model_5HT_004 (~4,828 @ 0.9803), dataset_ADR_005/model_ADR_006 (~3,376 @ 0.9588), dataset_DRD2_007/model_DRD2_008 (~3,293 @ 0.6657); every applicability note says "ChEMBL Ki binary, scaffold split; re-check before applying to much smaller or balanced datasets".
- MOR's profile (2,790 @ 0.7953) is smaller than every stored set, with prevalence between DRD2 and the high-prevalence sets. Nearest profile: dataset_DRD2_007/model_DRD2_008.
- Reused verbatim/protocol-level: ChEMBL Ki binary framing; scaffold-split protocol; standard Morgan r=2/2048 + 7 descriptors; label column used as provided.
- Adapted: model family re-selected on MOR's own scaffold validation (RF), as the store's applicability caveat requires for a smaller/less-imbalanced set; bounded feature checks (r=3, desc v2) were run only because no stored profile covers this data profile.
- Limitation: the retrieve interface returns record applicability metadata (id/kind/target/applicability/payload sha), not stored payload contents, so reuse is protocol/profile-level, not a copied hyperparameter set.

Integrity notes: read-only labels/library/store; no label re-derivation (censoring handling inherited from the curated label column); no test leakage; no EF claimed on the 100k library; no GitHub/code changes. Artifacts: model .../train_scaffold_rf/model.joblib, val metrics .../train_scaffold_rf/metrics.json, locked receipt .../receipt_mor_ki.json.
