# R #8 ca2

- task: `p7b_r_ca2`
- ticket: `e412acda8b8d504e228df450fb6d2dd0`
- state: ready
- wall: 2064.5s, jobs 18 (failed 4), models 5
- best validation model (any split): models/ca2_rf_v1_s42 AUROC=0.9852 AUPRC=0.9992 EF@1%=1.056
- best scaffold model: models/ca2_rf_v1_s42 AUROC=0.9852 EF@1%=1.056
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

CA2 Ki P7b report-only deliverable (no code change, no PR; all artifacts under /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/anhydrase-frozen-r-e412acda8b8d/).

PROTOCOL (no data.split called; no fractions chosen)
- Labels: scientific/.artifacts/chembl/carbonic_anhydrase_2/ki/dataset_p7b.csv, 6,206 molecules, 5,751 positives (92.67%); rdkit.featurize rows_valid=6206/6206, 0 invalid.
- Frozen manifest passed verbatim as --split-manifest .../ki/splits/frozen_carbonic_anhydrase_2.json; ml.train reports 5,306 train / 621 validation; the remaining 279 molecules were never loaded (locked test).

(a) CHOICES AND RATIONALE
- Representation: desc_set v1 (Morgan radius 2, 2048 bits + 7 RDKit 2D descriptors). v2 was featurized (6206 rows) but ml.train rejected it for logreg, rf and xgboost alike (exit 1, no diagnostics), so v1 is the trained and evaluated descriptor set.
- Model comparison on the frozen validation split (AUROC / AUPRC): logreg v1 0.9156 / 0.9936; xgboost v1 0.9716 / 0.9983; rf v1 seeds 7/17/42 = 0.9830/0.9838/0.9852 / 0.9990/0.9991/0.9992. RF is both best and stable (range 0.0022 across seeds); selected rf v1 seed 42 (best validation AUROC).
- CatBoost was not evaluated: it hit the 1800 s wall limit and produced no artifact; excluded on cost.
- Why AUROC is primary: at 92.7% positives AUPRC saturates, and EF@1% is at its ceiling on this split (top 1% = 6 validation molecules, all positive, EF 1.056 = 1/0.9469). EF therefore adds no discrimination here; AUROC is reported as the selection metric.

(b) FROZEN-SPLIT VALIDATION — final model models/ca2_rf_v1_s42/model.joblib
AUROC 0.9852, AUPRC 0.9992, EF@1% 1.056 (ceiling), EF@5% 1.056 (ceiling), accuracy 0.9565, F1 0.9775. Counts: 5,306 train / 621 val (588 positive, 33 negative, 94.7% positive). The 33-negative validation makes AUROC granular/noisy (~0.001 per pair), and seed spread was only 0.0022.

(c) LOCKED TEST — called exactly once (evaluation.locked, target CA2, endpoint Ki, desc_set v1, receipt evaluation/ca2_locked.json), quoted verbatim from the receipt:
"auroc": 0.9683, "auprc": 0.9969, "ef_at_1pct": 1.063, "ef_at_5pct": 1.044.
Receipt sha256 609b1e2892021a4f092003a6dd54fa43c7f62ce78d900f13cfd4a7cdbb0f6110. The receipt exposes no counts; test size is inferred as 279 from the manifest join (6206-5306-621) and is not stated by the tool. Locked AUROC is ~0.017 below validation, an expected scaffold-shift drop.

(d) TOP-100 RANKING — screen 100k with the evaluated model
- rankings/ca2_rf_v1_s42_top100.csv (100 rows + header; sha256 a130062c87f3b7430350abfb89be366a5f1175632fba86ee15cef17d9ee3ddda).
- Full ranking: rankings/ca2_rf_v1_s42_ranked.csv; screening report: rankings/ca2_rf_v1_s42_screening_report.json (100,000 rows read, 100,000 featurized, 0 invalid; top_score_range 0.99-1.0).
- Ties: 42 molecules at score 1.000, 31 at 0.995, 27 at 0.990; rank order within a band is arbitrary and only membership in the top-100 is stable.
- Chemical sanity check: all 100 carry a primary sulfonamide (S(N)(=O)=O / NS(=O)(=O)), the known CA2 zinc-binding motif — descriptive only, not evidence of measured activity.
- The library is unlabeled; no hit rate, EF or enrichment is defined or claimed for it.

(e) COST
18 scientific jobs, one tool slot (parallel dispatches serialized). Sum of reported wall times 1,871.6 s ≈ 31.2 min, of which 1,800 s (30.0 min) is the single timed-out CatBoost run; all other jobs together ≈ 71.6 s. No GPU used, no data mutated, no repo code changed. Extra 3 jobs were 0.09 s experience-store probes.

(f) EXPERIENCE USED
- Retrieved scientific/.artifacts/experience/experience_r.json with experience.retrieve: target=CA2 returned 0 records. The all-model retrieval returned 7: model_D2_002 (~6,811 mol, 0.9621 pos), model_5HT_004 (~4,828, 0.9803), model_ADR_006 (~3,376, 0.9588), model_DRD2_008 (~3,293, 0.6657), model_MOR_010 (~2,790, 0.7953), model_CBR_012 (~2,309, 0.9818), model_KOR_014 (~1,899, 0.7899) — all "ChEMBL Ki binary, scaffold split".
- Nearest profile to CA2 (6,206 mol, 0.9267 pos): model_D2_002 by size/rate, then 5HT_004/ADR_006.
- Reused verbatim: the applicability-derived protocol regime (ChEMBL Ki binary labels, scaffold-manifest split, high-positive-rate applicability) and the standard tool chain featurize -> ml.train(frozen manifest) -> screening.rank -> evaluation.locked.
- Adapted: representation/model/seed chosen by local frozen-validation comparison (v1 + RF seed 42). Honest limitation: experience.retrieve surfaces only applicability text + payload_sha256, not the stored config payload, so NO stored hyperparameters could be copied verbatim; all modelling choices were made and validated on this dataset. (I also probed guessed payload/record paths; retrieve returned 0 records, no payload access.)

RISKS / LIMITATIONS
- Locked AUROC 0.9683 rests on a small negative class (test is ~94% positive, counts not exposed), so treat it as coarse (±~0.01).
- v2 descriptor set is unusable through ml.train (silent exit 1) and is unexplored; CatBoost is untested due to the 30-min timeout.
- EF@1% is at the base-rate ceiling for both splits and must not be read as strong enrichment.
- Report-only task: nothing committed, no PR opened.
