# R #7 kor

- task: `p7b_r_kor`
- ticket: `e779b451058809a30ef2398bc6473301`
- state: ready
- wall: 333.3s, jobs 23 (failed 2), models 11
- best validation model (any split): kor_r3/train_rf AUROC=0.985 AUPRC=0.9938 EF@1%=1.387
- best scaffold model: kor_r3/train_rf AUROC=0.985 EF@1%=1.387
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

KOR (OPRK1) Ki predictor and top-100 library ranking complete, with the one allowed locked evaluation run and receipt quoted.

DELIVERABLES (ticket workspace = /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/kor-frozen-r-e779b4510588):
- top-100: kor_v1/top100.csv (abs: .../kor_v1/top100.csv), 100 rows, rank,id,smiles,score, best-first, score range 0.830-0.904
- full ranking: kor_v1/rank_100k.csv (100,000/100,000 library rows featurized, 0 invalid)
- fitted model: kor_v1/train_rf/model.joblib (sha256 4f035d8d16308caaa809653ba44397b5d7343c8372c1acb6c2d9baec05fe4d97)
- locked receipt: evaluation/kor_locked.json (sha256 ef187309ffcd9124529349476c134c9c0b9327c2bee992d46bd2ecabe415a03c)
- no PR: assignment explicitly requests a report, not code.

(a) CHOICES AND RATIONALE
- Data: dataset_p7b.csv has 1,899 valid molecules, binary label column already derived from ChEMBL Ki (1,500 positives, 79.0%); frozen manifest used verbatim (--split-manifest .../splits/frozen_oprk1.json): train 1,624, validation 190 (137 positives).
- Representation: Morgan radius 2, 2048 bits + 7 physchem descriptors (desc_set v1); model: scikit-learn RandomForest (ml.train "rf"), seed 17.
- Rationale: prior experience records (see f) are high-positive-rate scaffold-split ChEMBL Ki binary sets; no KOR record existed. I screened a declared grid (desc_set v1/v2 x logreg/rf/xgboost/catboost) on the frozen validation split and picked the best validation AUROC/AUPRC arm. RF-v1 was best; v2 features and fp variants were not better. I deliberately locked the canonical radius-2/2048 v1 model because evaluation.locked accepts only --desc-set (no radius/bits), so this guarantees train/inference featurization agreement; the radius-3 variant (0.9850 AUROC) differed from radius-2 (0.9843) by noise only.

(b) FROZEN-SPLIT VALIDATION (seed 17; 190 molecules, 137 positives)
chosen RF-v1-r2-2048: AUROC 0.9843, AUPRC 0.9935, EF@1% 1.387, EF@5% 1.387 (accuracy 0.9368, F1 0.9580).
Grid AUROC/AUPRC: logreg v1 0.9464/0.9762; xgb v1 0.9757/0.9905; cat v1 0.9787/0.9916; rf v2 0.9738/0.9882; xgb v2 0.9747/0.9898; cat v2 0.9772/0.9913; rf v1-r3 0.9850/0.9938; rf v1-4096 0.9774/0.9894. EF@1% is saturated at 1.387 for every arm (only ~2 molecules in the 1% slice; 79% positives), so it does not discriminate arms. Seed stability of the chosen arm: 0.9847 (seed 7), 0.9843 (17), 0.9807 (42); mean 0.9832, sd ~0.0022.
(v2+logreg run failed exit 1; RF/XGB/CatBoost trained on v2, consistent with non-finite descriptors. Not selected.)

(c) LOCKED-TEST RECEIPT (evaluation.locked, target KOR, endpoint Ki, desc_set v1, called once)
evaluation/kor_locked.json metrics verbatim: auROC 0.9129, auprc 0.9576, ef_at_1pct 1.459, ef_at_5pct 1.459.
Raw locked file is in the protected tree and not readable from the ticket; only this summary receipt is available. Locked AUROC is 0.071 below validation — an honest generalisation gap on novel scaffolds; validation selection optimism cannot be excluded.

(d) TOP-100: kor_v1/top100.csv (absolute path .../.artifacts/state/work/kor-frozen-r-e779b4510588/kor_v1/top100.csv). Library is unlabeled: these are model scores/ranks, no hit rate or EF claim is made.

(e) COST: wall clock 14:32:33Z -> 14:37:44Z (~5.2 min); 23 scientific jobs (21 succeeded, 2 failed probes: 5-row probe with wrong label column; v2 logreg) + 1 subagent capability probe; total measured job compute 128.8 s CPU wall (~2.1 min), dominated by catboost (56 s) and library screening (23.7 s). Single CPU node, no GPU.

(f) EXPERIENCE: retrieve against the exact store path returned 0 KOR-target records and 12 store records overall (D2, 5HT, ADR, DRD2, MOR, CBR). Closest profile used: dataset_MOR_009 (opioid, 2,790 molecules, 0.7953 positive rate vs KOR 1,899/0.7899) and model_MOR_010 as the nearest modelling precedent, plus dataset_CBR_011 for the smaller-n regime. Reused verbatim: the scaffold-manifest ChEMBL-Ki-binary protocol and pipeline shape only; the retrieved records expose applicability summaries + payload_sha256 but NOT the payload configuration, so no model hyperparameters could be copied verbatim. Adaptations: model family and feature set were chosen on this dataset's local validation; nothing was tuned on the locked test.

RISKS/LIMITS: validation n=190 makes EF@1% and small AUROC gaps noisy; only one seed was used for the locked model (seed stability reported); locked AUROC 0.9129 is well below validation, so the ranking should be treated as a prioritisation aid, not a validated hit list.
