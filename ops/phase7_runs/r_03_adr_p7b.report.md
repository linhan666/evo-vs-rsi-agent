# R #3 adr

- task: `p7b_r_adr`
- ticket: `13b01a41fb49ea0894f454e82736f48f`
- state: ready
- wall: 484.9s, jobs 31 (failed 2), models 18
- best validation model (any split): models/rf_r2_b4096 AUROC=0.9457 AUPRC=0.9972 EF@1%=1.04
- best scaffold model: None AUROC=None EF@1%=None
- refits excluded from ranking: []
- top-100 artifacts: 2

## agent report

ADR (adenosine receptor A) P7b target #3 — COMPLETE. No GitHub PR (local scientific ticket); all artifacts are in the ticket workspace.

## Data & protocol (no data.split used)
- Labels: `/home/linhan_cluster/evo_vs_rsi/scientific/.artifacts/chembl/adenosine_receptor_a/ki/dataset_p7b.csv` — 2,870 molecules, 2,870 featurized, 0 invalid; 2,748 positives (95.75%).
- Frozen split passed verbatim: `/home/linhan_cluster/evo_vs_rsi/scientific/.artifacts/chembl/adenosine_receptor_a/ki/splits/frozen_adenosine_receptor_a.json`; ml.train reports `split_strategy=scaffold-manifest`, train 2,454 / validation 287 (276 positives). No self-made fractions.
- Endpoint: Ki only; labels consumed as the provided binary Ki labels (`label_source=chembl_ki_binary`); no Kd/IC50/EC50 mixing, no synthetic negatives, no negatives invented for the 100k library.

## (a) Choices and rationale
Final model: sklearn RandomForest (`rf`), seed 17, on desc_set `v1` = Morgan fingerprint radius 2 / 2048 bits + 7 RDKit 2D descriptors (MW, logP, HBD, HBA, TPSA, rotatable bonds, rings; RDKit 2024.09.5). Model file `models/rf_v1/model.joblib` (sha256 56785e39…, 4.17 MB); metrics `models/rf_v1/metrics.json`.
Rationale: small (n=2,870), highly imbalanced (95.75% positive) ChEMBL Ki set; compact fingerprint+descriptor representation; RF is robust at this n without scaling and gave the best frozen-split AUROC among the four model families tested. Family/representation comparison on the same manifest (validation AUROC / AUPRC):
- RF, v1 2048, seed 17: **0.934 / 0.9962** (final)
- RF, v1 4096, seed 17: 0.9457 / 0.9972 (exploratory best; not usable for the locked evaluator — see limits)
- RF, v2 2048: 0.9153 / 0.9940
- LogReg, v1 2048: 0.8814 / 0.9929
- XGBoost, v1 2048: 0.8231 / 0.9893
- CatBoost, v1 2048: 0.8518 / 0.9876
- RF, radius 3 / 4096: 0.8674 / 0.9919
Seed-sensitivity check on the chosen 2048-bit RF: seeds 17/42/13/2024 gave 0.934/0.9338/0.9226/0.9109 (mean 0.925); the 4096-bit variant gave 0.9004–0.9457 (mean 0.932). Validation n is only 287, so differences below ~0.02 are noise.

## (b) Frozen-split validation (final model)
AUROC **0.934**, AUPRC **0.9962**, EF@1% **1.04** (EF@5% 1.04), accuracy 0.9686, F1 0.984. EF@1% is saturated: 1% of 287 = 3 molecules, all 3 positive, and the maximum attainable EF given the 96.2% validation positive rate is ≈1.04 — treat EF as uninformative here.

## (c) Locked-test AUROC (verbatim from receipt)
`evaluation/adr_locked.json`: `"auroc": 0.8072`, `"auprc": 0.9908`, `"ef_at_1pct": 1.035`, `"ef_at_5pct": 1.035`, target ADR, endpoint Ki, desc_set v1. Raw per-sample metrics stay in the protected tree (`/home/linhan_cluster/evo_vs_rsi/protected/chembl37_ki_adr/…`), not read.
The locked AUROC is 0.8072 vs 0.934 scaffold-manifest validation — a real scaffold-shift/selection-optimism gap; 0.8072 is the number that counts and is reported without adjustment.

## (d) Deliverables
- Top-100: `screening/adr_top100.csv` (absolute: `/home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/adenosine-frozen-r-13b01a41fb49/screening/adr_top100.csv`) — 100 rows, ranks 1–100, scores 0.995–1.0. 76 of the top 100 are tied at exactly 1.000000; order within those ties is arbitrary.
- Full 100k ranking: `screening/adr_library_100k_ranked.csv`; screening report `screening/adr_screening_report.json` (100,000 read, 100,000 featurized, 0 invalid; model sha matches the receipt model; 18.3 s). Predictions only — no hit rate or EF can be defined for an unlabeled library.
- Receipt: `evaluation/adr_locked.json` (sha256 03f1c44c…); model: `models/rf_v1/model.joblib`.

## (e) Cost
31 tool jobs (29 successful; 1 logreg/v2 training failed with exit 1 and was abandoned; 1 first locked call with the 4096-bit variant failed with exit 1 and produced no receipt). ~3.3 min summed tool wall time, ~6.2 min end-to-end (13:59:45–14:05:55), CPU only, no GPU. No human intervention.

## (f) Experience store
`experience.retrieve` with `store=/home/linhan_cluster/evo_vs_rsi/scientific/.artifacts/experience/experience_r.json`:
- `target=ADR`: **0 records** (store is readable — unfiltered retrieval returns 4 records, so this is absence, not a bad path).
- Available: `dataset_D2_001`, `model_D2_002` (D2, ~6,811 mol @0.9621 positive, scaffold), `dataset_5HT_003`, `model_5HT_004` (5HT, ~4,828 mol @0.9803 positive, scaffold). No ADR record exists; nearest is model_5HT_004.
- No experience was reused verbatim. I adapted the protocol-level facts from `model_5HT_004` / `model_D2_002` (ChEMBL Ki binary classification, scaffold split, high positive prevalence, tree-ensemble candidate) to the smaller 2,870-molecule ADR set; model family/representation were then selected by the frozen-split comparison above. `experience.retrieve` exposes only `payload_sha256`, not the payload configuration, so no hyperparameters could be copied from those records.

## Limits / notes
- First locked attempt used the 4096-bit RF and failed in 2.37 s (exit 1, no receipt); the locked v1 evaluator's fixed 2048-bit featurization matched only the canonical v1 model, so the final receipt is for `models/rf_v1` (2048 bits). Exactly one receipt exists.
- Validation is small (287) and positive-heavy; EF@1% saturated; locked AUROC is the honest generalisation estimate.
- Top-100 inherits RF score saturation (76 ties at 1.0) and no library deduplication was performed (screening tool scores the library as provided).
