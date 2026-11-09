# M #2 5ht

- task: `p7e_m_5ht`
- ticket: `101578d0b22c5828a1b5c9afd38d07eb`
- state: ready
- wall: 630.9s, jobs 24 (failed 4), models 8
- best validation model (any split): .artifacts/models/5ht/v2_rf_seed7 AUROC=0.9992 AUPRC=1.0 EF@1%=1.025
- best scaffold model: .artifacts/models/5ht/v2_rf_seed7 AUROC=0.9992 EF@1%=1.025
- refits excluded from ranking: []
- top-100 artifacts: 2

## agent report

COMPLETED. 5HT/Ki predictor trained on the frozen split, one locked evaluation run, the 100k ZINC library ranked. No code change and no PR: the deliverables are scientific artifacts. They were written into the ticket workspace /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/ht-p7e-m-101578d0b22c (the scientific tools' cwd); all paths below are relative to it.

DATA + SPLIT (no data.split)
- Labels: /home/linhan_cluster/evo_vs_rsi/scientific/.artifacts/chembl/5-hydroxytryptamine_/ki/dataset_p7b.csv — 4104 rows, all 4104 featurizable (0 invalid), 4015 positives (97.8%).
- Frozen manifest: .../ki/splits/frozen_5-hydroxytryptamine_.json, passed as --split-manifest to every fit. Manifest split: train 3509, validation 410 (400 pos / 10 neg); the remaining 185 molecules are not used by ml.train. data.split was never called.
- Featurization: Morgan r=2 / 2048 bits + 7 physchem descriptors (desc_set v2); a Morgan-only v1 set was kept as comparator. Files: .artifacts/chembl/5-hydroxytryptamine_/ki/features_5ht_v1.npz, features_5ht_v2.npz.

EXPERIENCE (store read)
- experience.retrieve on /home/linhan_cluster/evo_vs_rsi/scientific/.artifacts/experience/experience_m_rep3.json: 5HT has 0 records; the store contains only dataset_D2_001 and model_D2_002 (D2; ~6811 molecules, 0.9621 positive rate, scaffold split). Applicability audit: this 5HT set is 4104 molecules at 0.978 positive, so the D2 facts were not applied.
- Experience IDs reused: none (0). Retrieval outputs: .artifacts/experience/retrieve_*.json.

MODEL SELECTION (validation only; no test peeking)
Validation AUROC / AUPRC / EF@1%:
- v1 logreg 0.9693 / 0.9991 / 1.025
- v1 RF 0.9990 / 1.0000 / 1.025
- v1 XGBoost 0.9918 / 0.9998 / 1.025
- v2 RF 0.9990 / 1.0000 / 1.025  ← chosen
- v2 XGBoost 0.9938 / 0.9998 / 1.025
- v2 CatBoost 0.9895 / 0.9997 / 1.025
- v2 logreg failed (exit 1, no stderr exposed); v1 logreg succeeded, so the failure is descriptor-set specific, not data.
Chosen: RandomForest, seed 17, desc_set v2 (model .artifacts/models/5ht/v2_rf/model.joblib, sha256 8fca4e966ea0f4b5a65d343eace1aed96781b795c5a129c37a787b4bbe92cb7b). Why: best validation AUROC/AUPRC, seed-robust (seeds 7/42 give 0.9992 / 1.0000), and a tree ensemble is scale-free on binary fingerprints + descriptors. v2 matched v1 on validation while adding 7 interpretable 2D descriptors, so the richer set was kept.

LOCKED EVALUATION (exactly one call)
evaluation.locked --target 5HT --endpoint Ki --desc-set v2 --model .artifacts/models/5ht/v2_rf/model.joblib --receipt evaluation/5ht_locked.json
Receipt (sha256 a2bfb74dcebc50fbcb5d656cc1256be2f7cd4557971e13e0810307e95687186f): locked AUROC 0.9653, AUPRC 0.9997, EF@1% 1.008, EF@5% 1.008. Raw test metrics stayed protected at /home/linhan_cluster/evo_vs_rsi/protected/chembl37_ki_5ht/metrics_test_locked_agent_Ki_v2_._5HT.json; the receipt is summary-only, and the protected test's size/class balance is not exposed.

LIBRARY RANKING
- screening.rank with the same RF v2 model: 100000 library rows read and featurized, 0 invalid, 81.7 s; model sha256 matches the fitted model above.
- Full ranking: .artifacts/screening/5ht/ranking.csv (sha256 fcf2f357…, 7,220,835 B). Top-100: .artifacts/screening/5ht/top100.csv (sha256 03108734…, 100 rows).
- Material limitation: all 100 top scores are exactly 1.000000 (report top_score_range [1.0, 1.0]), so the RF top-100 is its highest-confidence band and its internal order is not resolved by the model. An auxiliary XGBoost ranking of the same library is at .artifacts/screening/5ht/top100_xgb.csv (top scores 0.99995–0.99999, graded ordering) but that model was not the locked-evaluated one — treat it only as a tie-break cross-check. The library is unlabeled, so no hit-rate or true EF@1% claim is made.

COST
- 24 tool jobs (20 succeeded, 4 failed: 1 v2-logreg fit + 3 workspace-path diagnostics). Cumulative job runtime 207.6 s; ticket wall 2026-11-09T09:14:25Z → 09:24:03Z ≈ 9m38s; CPU only, no GPU. Two 100k screenings account for 166 s; the 8 successful model fits ≈ 30 s.

INTEGRITY NOTES
- Single endpoint (Ki), no Kd/IC50 mixing; unmeasured pairs were never treated as negatives; the test channel was touched only through evaluation.locked, with no per-sample errors exposed.
- Validation is saturated: 97.6% positive, AUPRC 1.000 against a 0.9756 prevalence, EF@1% capped at 1.025. Locked AUROC 0.9653 is the honest discrimination result; the gap from 0.999 validation reflects the tiny negative count (10 val vs a protected test with few negatives).

EVIDENCE HASHES
- features v1 e5e9548d…; v2 ecb6749c…; v2_rf metrics 7fda0b5b…; model 8fca4e96…; screening report 64dbcc90…; top-100 03108734…; receipt a2bfb74d….

No PR was opened because this ticket's deliverable is the fitted model, the locked receipt and the ranked library, and repo rules forbid committing data/models.
