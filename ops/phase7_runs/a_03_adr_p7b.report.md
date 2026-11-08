# A #3 adr

- task: `p7b_a_adr`
- ticket: `969017b5fcd3fae052ca45e8614f2d8a`
- state: ready
- wall: 258.6s, jobs 20 (failed 2), models 12
- best validation model (any split): models/rf_v1_4k AUROC=0.9457 AUPRC=0.9972 EF@1%=1.04
- best scaffold model: models/rf_v1_4k AUROC=0.9457 EF@1%=1.04
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

ADR (Ki) predictor built on the frozen split, locked-evaluated once, and used to rank the 100k ZINC library.

APPROACH / CHOICES (selected on the frozen scaffold-validation split only; no use of the protected test set, no data.split call, no experience store):
1) Feature set: desc_set=v1 (Morgan r2, 2048 bits + 7 descriptors) beat v2 for RF (AUROC 0.9340 vs 0.9153). 4096 bits gave higher single-seed AUROC (0.9457) but lower seed stability (seeds 7/42/17: 0.9368/0.9004/0.9457, mean 0.9276, sd 0.024) than 2048 (0.9219/0.9338/0.9340, mean 0.9299, sd 0.0068), so 2048 was kept. Radius 3 was worse (0.8877).
2) Model family (v1 features, seed 17): rf 0.9340 AUROC / 0.9962 AUPRC > catboost 0.8518/0.9876 > xgboost 0.8231/0.9893. logreg cannot run: ml.train exits 1 with zero stdout/stderr, twice, same args (tool-side defect, reproducible; no shell in this session to diagnose). Not needed since RF won.
3) Seed: kept default 17 rather than cherry-picking a seed; seeds 7/42 gave 0.9219/0.9338 AUROC.
4) Fusion (ml.fuse) considered and rejected: the locked channel consumes one fitted pipeline, so a fused ranking could not be the evaluated model.

VALIDATION (frozen scaffold-validation, 287 molecules, 276 positives; train 2454; 129 protected rows untouched): AUROC 0.9340, AUPRC 0.9962, EF@1% 1.04. EF is at its ceiling here: 1% of 287 = 2.87 -> 3 slots, max EF = 287/276 = 1.04; prevalence 96.2% makes EF uninformative and AUPRC optimistic-baselined (0.96). AUROC is the discriminating statistic.

LOCKED EVALUATION (exactly one call, receipt evaluation/adr_locked.json, sha256 03f1c44cd61f4badb0dd819a876a4afc0d2002e56ff5f12dc40dff1272ed9101, 413 B): target ADR endpoint Ki desc_set v1, model models/rf_v1/model.joblib. Locked AUROC 0.8072, AUPRC 0.9908, EF@1% 1.035 (EF@5% 1.035). Generalization drop from validation is expected for a scaffold split. Raw test file stays in the protected tree.

ARTIFACTS: models/rf_v1/model.joblib (sha256 56785e3902cd9610b424b28a9ce564494e6e22bc8da619bbeb7c3322bd247b4a, 4.17 MB); ranking/adr_ranked.csv (100,000/100,000 featurized, 0 invalid, 7,220,835 B); ranking/adr_top100.csv (7,213 B); ranking/adr_rank_report.json (model_sha256 == evaluated model; library_sha256 09446ea1…; elapsed 37.2 s). Top-100 path: ranking/adr_top100.csv; first hit zinc057910, score 1.000000.

MATERIAL LIMITATION for downstream use: RF probabilities saturate — ranks 1-76 are all exactly 1.000000 and only from rank 77 do scores fall (0.998750 … 0.995000 by rank 100). Membership of the top set is model-driven, but ordering among the 76 tied molecules follows library input order, i.e. intra-tie order is arbitrary. ZINC was scored as provided (no dedup; tool leaves dedup to the caller). No hit rate or EF is defined for the unlabeled library.

COST: 20 jobs submitted (18 succeeded, 2 failed = the two logreg attempts), 117.0 s total job wall time, 3 min 08 s session elapsed, CPU-only, no GPU, no paid/network services. Experience ids reused: none (0) — arm A has no experience store.
