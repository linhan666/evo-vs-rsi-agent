# R #1 d2

- task: `seq_r_d2_coldstart2`
- ticket: `aadd34901c2f0f31e09575718460ad0f`
- state: ready
- wall: 406.3s, jobs 16 (failed 0), models 7
- best validation model (any split): models/cat_r3_4096 AUROC=0.9597 AUPRC=0.9991 EF@1%=1.019
- best scaffold model: models/cat_r3_4096 AUROC=0.9597 EF@1%=1.019
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

D2 Ki cold-start replay #2 complete. All work is in the ticket workspace /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/dopamine-coldstart2-aadd34901c2f (no repo code changed, no GitHub PR needed: the deliverable is a report + scored artifacts).

(a) Choices and rationale
1. Experience: executed exactly one experience.retrieve against the mandated store /home/linhan_cluster/evo_vs_rsi/scientific/.artifacts/experience/replay_coldstart.json -> {"count": 0, "records": []} (exp/retrieve_coldstart2.json). No other path probed, as instructed. No experience_id exists for this profile, so nothing was reused verbatim or adapted; every choice below is de novo.
2. Labels: read-only dataset.csv used exactly as delivered: 6,811 molecules, all SMILES valid, pre-binarized `label` column with 6,553 positives (96.2%). No re-thresholding and no mixing of Ki/Kd/IC50; relation semantics left untouched.
3. Split: data.split Bemis-Murcko scaffold, seed 17 -> train 4,087 / val 681 / manifest held-out test 2,043. ml.train fitted on train only; the 2,043 manifest test was never read by training, and the locked evaluator uses its own protected test set, so no leakage. A random split (same seed) was run only as an optimistic diagnostic.
4. Representation: Morgan FP radius 2, 2,048 bits + 7 RDKit 2D descriptors (desc_set v1). I also tried radius 3 / 4,096 bits (scaffold-val AUROC 0.9597), but evaluation.locked and screening.rank featurize at the fixed r2/2048+v1 profile, so a 4,096-bit model cannot be scored end-to-end; the deployed config is r2/2048+v1.
5. Model: CatBoost (seed 17) chosen on scaffold-val AUROC/AUPRC over the alternatives: CatBoost 0.9481 / 0.9988; XGBoost 0.9310 / 0.9985; logistic regression 0.9231 / 0.9982; random forest 0.9161 / 0.9972. desc_set v2 was worse (AUROC 0.9232).
6. No fusion: the screening tool writes the ranked library/top-100 from a single fitted model; fusing two models would break that path, and the val AUPRC spread is inside noise at 98% prevalence.
7. Locked evaluation: evaluation.locked target DRD2, endpoint Ki, desc_set v1, on models/cat_scaffold/model.joblib. The screener report confirms the same model SHA-256 (617987b8...) was used for the library.

(b) Metrics
- Locked final test (protected; receipt locked/d2_ki_cat_r2_receipt.json): AUROC 0.7847, AUPRC 0.7723, EF@1% 1.824, EF@5% 1.635.
- Scaffold validation: AUROC 0.9481, AUPRC 0.9988, EF@1% 1.019, EF@5% 1.019. Honest caveat: val prevalence is 0.981, so EF@1% is pinned at its ceiling 1/0.981 = 1.019 and is non-informative on val; the locked test is the only trustworthy generalisation number.
- Random-split diagnostic: AUROC 0.9122, AUPRC 0.9953, EF@1% 1.038. (metrics.json hardcodes split_strategy "scaffold-manifest"; the manifest actually passed was split/d2_random.json.)
- The large scaffold-val vs locked-test gap is a real distribution shift and is reported as such, not smoothed over.

(c) Top-100
- screen/d2_ki_top100.csv: 100 rows (rank,id,smiles,score), top score 0.998608, 100th 0.996096.
- screen/d2_ki_ranked.csv: 100,000/100,000 library molecules featurized, 0 invalid, ranked best-first (7.2 MB).
- The library is unlabeled, so these are predictions only; no hit rate or EF claim is made for it.

(d) Cost
16 tool jobs, 221.96 s wall, ~4,452 CPU-s (~74 CPU-min), 0 GPU (CPU-only; gpu_seconds null for every job). Largest single items: CatBoost fits (32-50 s wall, ~900-1,350 CPU-s each); screening 16.2 s; locked evaluation 2.25 s.

(e) Experience reuse
0 experience_ids, 0 reused verbatim, 0 adapted (empty store by design).

Artifacts in the ticket workspace: exp/retrieve_coldstart2.json; split/d2_scaffold.json and split/d2_random.json; feat/d2_ki_r2_2048.npz (+report), feat/d2_ki_r3_4096.npz, feat/d2_ki_r2_2048_v2.npz; models/{logreg_scaffold,rf_scaffold,xgb_scaffold,cat_scaffold,cat_r3_4096,cat_r2_v2,cat_r3_4096_random}/; screen/d2_ki_ranked.csv, screen/d2_ki_top100.csv, screen/d2_ki_rank_report.json; locked/d2_ki_cat_r2_receipt.json. Verification done: store returned 0 records; 100,000/100,000 library rows valid; screening model SHA-256 equals the evaluated model SHA-256; locked receipt read successfully.
