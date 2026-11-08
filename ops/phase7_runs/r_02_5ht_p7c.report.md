# R #2 5ht

- task: `p7c_r_5ht`
- ticket: `491db4fffb4242db7a283c055e450e14`
- state: ready
- wall: 310.6s, jobs 15 (failed 1), models 5
- best validation model (any split): models/rf_v2 AUROC=0.999 AUPRC=1.0 EF@1%=1.025
- best scaffold model: models/rf_v2 AUROC=0.999 EF@1%=1.025
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

P7c target 2/9 — 5HT (Ki): frozen split used, experience consulted, predictor selected on validation, one locked evaluation, 100k library ranked. All work done through the scientific tools; no data.split call.

## Deliverables (paths relative to the ticket workspace, DSH_SUPERAGENT_DIR)
- Locked receipt: `evaluation/5ht_locked.json` — AUROC **0.9665**, AUPRC 0.9997, EF@1% 1.008, EF@5% 1.008 (target 5HT, endpoint Ki, desc_set v1).
- Model: `models/rf_v1/model.joblib`; features `features_5ht_v1.npz`; validation metrics `models/rf_v1/metrics.json`.
- Full library ranking: `screening/library_100k_ranked.csv` (100,000 rows scored, 0 invalid SMILES).
- Top-100: `screening/top100_5ht.csv` (100 rows, rank 1–100).
- Screening report: `screening/5ht_rank_report.json`.
- Experience retrieval: `experience_5ht_retrieve.json`.

## Choices and why
- Split: passed `frozen_5-hydroxytryptamine_.json` to `ml.train --split-manifest`; trained on the manifest's train partition and reported metrics on its validation partition. `data.split` was not called (per instruction), so the frozen split/test is untouched. Counts from the tool: joined 4,104, train 3,509, validation 410. The remainder (4,104−3,509−410 = 185 molecules) is the frozen locked test; the receipt does not report its size.
- Labels: used the dataset's provided binary `label` column of `dataset_p7b.csv` as-is via `label_id_column=molecule_chembl_id`, `label_column=label`; `label_source=chembl_5HT_Ki_dataset_p7b`. No relabeling, no invented negatives. Dataset is 4,015/4,104 = 97.8 % positive.
- Features: Morgan radius 2, 2048 bits + 7 RDKit 2D descriptors (desc_set v1). desc_set v2 gave identical validation results, so v1 (smaller/cheaper) was kept.
- Model selection on the validation partition only: logreg 0.9693 / rf 0.9990 / xgboost 0.9918 / catboost 0.9953 AUROC. Random forest (rf_v1) had the best validation AUROC and AUPRC, so it was locked. One locked evaluation was spent, on rf/v1.

Validation metrics (all models; validation AUPRC baseline 0.9756, EF@1 % ceiling 1.025 because 400/410 validation molecules are positive):
| model | AUROC | AUPRC | EF@1% |
|---|---|---|---|
| logreg v1 | 0.9693 | 0.9991 | 1.025 |
| **rf v1 (locked)** | **0.9990** | **1.0000** | **1.025** |
| xgboost v1 | 0.9918 | 0.9998 | 1.025 |
| catboost v1 | 0.9953 | 0.9999 | 1.025 |
| rf v2 | 0.9990 | 1.0000 | 1.025 |

## Locked evaluation (quoted from the receipt)
`{"target":"5HT","endpoint":"Ki","desc_set":"v1","model":"model.joblib","metrics":{"auroc":0.9665,"auprc":0.9997,"ef_at_1pct":1.008,"ef_at_5pct":1.008}}` — receipt sha256 4fe940f3…cd3d365. The validation→locked-test AUROC drop (0.9990 → 0.9665) is a real distribution-shift/small-test signal and is reported, not hidden.

## Library ranking — material limitation
The RF scores saturate at the top of the library: the top 100 all score exactly 1.000000, so their rank order reflects only library file order, and the plateau is deep — diagnostic re-screens showed the top 1,000 all score 1.0 and the top 10,000 all ≥0.99. The 100k ranking is therefore usable as "all these are predicted maximal", but the top-100 order is not a meaningful priority order. The screening report states predictions only; no hit rate or EF is defined for the unlabeled library and none is claimed.

## Cost
15 scientific jobs in total (14 succeeded, 1 harmless failed path probe), summing 77 s of job wall time; session wall clock ~4 min (first job 21:05:47Z, last job 21:09:49Z). All jobs CPU-only.

## Experience store
`experience.retrieve` against `experience_r.json` returned `{"count": 0, "records": []}` (both for target 5HT and unfiltered), so **0 experience ids were reused**; no transferable facts were available for this target.

## Reproducibility anchors
features_5ht_v1.npz sha e5e9548d…14aba85; model.joblib sha 9248f7c5…08921b; full ranking sha 5cb335b7…2d6d2f3 (identical across top_k probes); top-100 sha 2fb5a8c0…38a847. Diagnostic probe artifacts `screening/probe_k1000_*` and `screening/probe_k10000_*` are kept as evidence of the tie depth.
