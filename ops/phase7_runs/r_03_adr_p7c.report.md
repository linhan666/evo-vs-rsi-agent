# R #3 adr

- task: `p7c_r_adr`
- ticket: `44a297905ae8432129ad3d39df11f761`
- state: ready
- wall: 254.9s, jobs 19 (failed 1), models 9
- best validation model (any split): models/rf_v1_r2_4096 AUROC=0.9457 AUPRC=0.9972 EF@1%=1.04
- best scaffold model: models/rf_v1_r2_4096 AUROC=0.9457 EF@1%=1.04
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

ADR (Ki) target 3 completed end-to-end in workspace `/home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/adenosine-p7c-r-44a297905ae8` (all artifact paths below are relative to it).

## Choices and why
- **Frozen split only**: passed `.../ki/splits/frozen_adenosine_receptor_a.json` as `--split-manifest` to every `ml.train` run; never called `data.split`. Runs report `scaffold-manifest`: 2870 joined, 2454 train, 287 validation (276 positives); the 129 held-out test molecules were touched only by `evaluation.locked`.
- **Experience**: `experience.retrieve` on `.../experience/experience_r.json` (no target/kind filter) returned `{"count":0,"records":[]}` — store empty. **Experience ids reused: none.**
- **Features/labels**: labels `dataset_p7b.csv` as provided (Ki, ChEMBL ADR P7b; no new negatives, no label mixing; `<`/`>` untouched). `rdkit.featurize` Morgan r=2/2048 bits + 7 `v1` 2D descriptors; also probed `v2` and 4096-bit variants.
- **Model sweep (validation AUROC / AUPRC / EF@1%)**, all same frozen manifest:
  - v1 r2/2048: logreg 0.8814/0.9929/1.04 · RF **0.9340/0.9962/1.04** · XGBoost 0.8231/0.9893/1.04 · CatBoost 0.8518/0.9876/1.04
  - v2: RF 0.9153/0.9940 · XGBoost 0.7441/0.9851 · CatBoost 0.8165/0.9883 · logreg failed (exit 1, no stderr emitted)
  - v1 RF r2/4096 0.9457/0.9972 · v1 RF r3/4096 0.8674/0.9919
- **Selected model**: RandomForest on v1 r2/2048 bits (`models/rf_v1/model.joblib`) — best lock-compatible validation AUROC and AUPRC. The 4096-bit RF scored marginally higher but was rejected because `evaluation.locked` exposes only `desc_set` (canonical 2048-bit featurization); spending the single locked evaluation on an unverifiable feature width was unacceptable, and the 0.9340→0.9457 gap is within noise on 11 validation negatives.

## Locked evaluation (exactly one call)
`evaluation.locked --target ADR --endpoint Ki --desc-set v1 --model models/rf_v1/model.joblib --receipt evaluation/adr_locked.json`
Receipt (`evaluation/adr_locked.json`): **AUROC 0.8072**, AUPRC 0.9908, EF@1% 1.035. Raw protected output path is named in the receipt and was not read.

## Ranking of the 100k library
`screening.rank` with the locked model: 100000 rows read/featurized, 0 invalid, 14.2 s; no hit-rate/EF is defined for an unlabeled library.
- Full ranking: `rankings/library_100k_ranked.csv` (100000 rows)
- **Top-100: `rankings/top100.csv`** (100 rows; rank 1 `zinc057910`, score 1.0)
- Tie caveat: **76 of the top 100 have score exactly 1.000000** (RF vote saturation), ordered by library input order; only ranks 77-100 carry finer scores (0.99875/0.9975/0.99625/0.995). Within the tied head the order is arbitrary.

## Cost
19 scientific tool jobs (18 succeeded, 1 failed: logreg on v2), summed tool wall **57 s**, end-to-end ~3 min; CPU-only, no GPU; 1 of 1 locked evaluations used.

## Limitations (honest)
- Label prevalence 2748/2870 positives (95.7%): AUPRC baseline 0.957 and EF@1% ceiling ≈1.04, so AUPRC/EF are near-saturated and weak evidence of enrichment.
- Scaffold validation→locked-test AUROC drops 0.9340→0.8072; expect degraded generalisation on novel chemotypes.
- RF probability ties cap top-K granularity (see above); the 100k library is unlabeled so rankings are model scores only.

## Key artifacts
`models/rf_v1/{model.joblib,metrics.json}`, `evaluation/adr_locked.json`, `rankings/{top100.csv,library_100k_ranked.csv,screening.json}`, `features/labels_v1.*`, `experience_all.json`; candidate models under `models/*`.
