# M #9 pt

- task: `seq_m_pt`
- ticket: `e33dfdfd3c5ca45e4fdb186ecb54cb7f`
- state: ready
- wall: 483.3s, jobs 37 (failed 0), models 21
- best validation model (any split): probe_train AUROC=0.9469 AUPRC=0.9828 EF@1%=1.24
- best scaffold model: b_rf_r2_2048 AUROC=0.9457 EF@1%=1.175
- refits excluded from ranking: ['final_rf_r2_2048_rand10']
- top-100 artifacts: 3

## agent report

Prothrombin (target 9/9, Ki) — model built, validated, 100k library ranked. Deliverable ready for review.

## (a) Choices and rationale
- **Data**: 2824 ChEMBL molecules (`molecule_chembl_id`, `canonical_smiles`, binary `label`), 0 invalid SMILES, 2279 positives (positive rate **0.8070**). Endpoint-specific Ki path; labels are the upstream-supplied binary column — not re-derived, no IC50/Kd mixing, untested molecule–target pairs are never treated as negatives (the library is only scored, never labelled).
- **Validation (primary, honest generalisation)**: Bemis–Murcko scaffold split. Partition A: test 30% / val 15% → train 1554, val 423 (369 pos, 54 neg), test 847 untouched. Partition B: test 25% / val 20% → train 1554, val 564 (480/84), test 706. Note: `data.split` seed 17 vs 23 produced an **identical** scaffold partition (identical val predictions/model hashes), so split variance was probed by changing fractions, not seed.
- **Representation**: Morgan r=2, 2048 bits + 7 RDKit 2D descriptors; compared with r=3/4096 and desc_set v2.
- **Models**: logreg, RandomForest, XGBoost, CatBoost.
- **Selection rule**: candidate model family/representation chosen on scaffold-validation only (test never touched). AUROC was the discriminating metric because AUPRC is near-saturated by the 0.87 validation prevalence.

## (b) Metrics (scaffold-held-out; no locked test available for prothrombin)
Partition A (423 held-out, 54 negatives):

| model | features | AUROC | AUPRC | EF@1% |
|---|---|---|---|---|
| **rf** | **r2/2048+v1** | **0.9410** | **0.9898** | 1.146 |
| rf | r3/4096 | 0.9396 | 0.9898 | 1.146 |
| rf | r2/2048+v2 | 0.9372 | 0.9889 | 1.146 |
| xgboost | r2/2048 | 0.9182 | 0.9841 | 1.146 |
| catboost | r2/2048 | 0.9147 | 0.9868 | 1.146 |
| logreg | r2/2048 | 0.8705 | 0.9729 | 1.146 |

Partition B (564 held-out): rf 0.9457 / 0.9863 / 1.175; xgboost 0.9278 / 0.9830; logreg 0.8677 / 0.9648. RF seed sensitivity on A (seeds 7/17/101): AUROC 0.9361–0.9410, AUPRC 0.9879–0.9898.

**Selected pipeline**: RandomForest on Morgan r=2, 2048 bits + MW/logP/HBD/HBA/TPSA/rotB/rings. Headline: **AUROC 0.941, AUPRC 0.990, EF@1% 1.146** (partition A) and **AUROC 0.946, AUPRC 0.986, EF@1% 1.175** (partition B).

Caveats: EF@1% is **ceiling-limited**, not evidence — validation prevalence is 0.872 (A) / 0.851 (B), so maximum attainable EF is 1.146 / 1.175; all 4 top-1% and all 21 top-5% validation molecules are positive for every model, making EF non-discriminating here. Validation has only 54–84 negatives → AUROC uncertainty ≈ ±0.01. **No independent locked test exists for prothrombin** (`evaluation.locked` serves MOR/KOR/DRD2 only), so these are scaffold-split CV metrics, not a locked final-test score.

**Deployed model for screening**: same pipeline refit on 2542 molecules (90%, random 10% holdout). Its random-split diagnostic AUROC 0.9577 / AUPRC 0.9859 / EF 1.237 is optimistic and is **not** used for any quality claim; the scaffold numbers above are the reported quality.

## (c) Top-100
- Top-100: `/home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/prothrombin-arm-m9-e33dfdfd3c5c/top100_prothrombin.csv`
- Full ranking (100k): `.../rank_prothrombin_100k.csv` (7.2 MB), report `.../rank_prothrombin_100k.report.json`
- Model: `.../final_rf_r2_2048_rand10/model.joblib`; headline metrics files `.../v15_rf_r2_2048/metrics.json`, `.../b_rf_r2_2048/metrics.json`; splits `.../split_scaffold_v15.json`, `.../split_scaffold_b.json`.

Library: 100000 rows read, 100000 featurized, 0 invalid, 21.5 s. Scores 0.945 (rank 1) → 0.880 (rank 100). Top 5: zinc031124 (0.945), zinc026344 (0.945), zinc058631 (0.945), zinc062141 (0.9367), zinc034201 (0.935). All 100 ids distinct; sulfonamide/amide-rich chemistry consistent with a serine-protease target.

Ranking caveats: (i) heavy score ties (three molecules at 0.945; 13 at 0.880 in ranks 85–100; dense 0.885/0.890/0.895 bands), so order **within** tied scores is arbitrary; (ii) the default Morgan fingerprint encodes no stereochemistry, so stereoisomers tie exactly — e.g. ranks 23 and 25 are cis/trans stereoisomers both at 0.905; (iii) the library was scored as provided, no deduplication; (iv) no EF/hit-rate is defined or claimed for the unlabelled library.

## (d) Cost
≈183 s wall, ≈1587 CPU-s (≈26 CPU-min), 0 GPU-s, 35 recorded tool invocations. Breakdown: screening 22 s; model training 130 s wall (CatBoost accounts for 1491 of the 1587 CPU-s for zero AUROC gain — the main avoidable cost); featurization 11 s; splitting 10 s. Two extra `screening.rank` calls returned a tool-serialization error and left no job record, so they are excluded from the tally and their artifacts are unreachable.

## (e) Experience reuse
Retrieved with the absolute store path 4×: `target=prothrombin` → 0 records, `target=MOR` → 2, `kind=model` → 8, unfiltered → 16 (8 dataset + 8 model for D2, 5HT, ADR, DRD2, MOR, CBR, KOR, CA2).
- **Used**: `dataset_MOR_009` / `model_MOR_010` — applicability "~2790 molecules at 0.7953 positive rate, scaffold split", the closest profile to prothrombin (2824 at 0.8070); the other 14 records confirm the same regime (0.6657–0.9818 positive rate, all ChEMBL Ki binary, all scaffold split).
- **Reused verbatim**: the protocol declared in those applicability notes — scaffold-split validation, ChEMBL Ki binary labels, and the expectation of a positive-rate-dominated, AUPRC-saturated regime (which is why AUROC, not AUPRC/EF, drove selection).
- **Could not reuse**: hyperparameters. `experience.retrieve` returns only target, kind, applicability text and `payload_sha256`; payload bodies are not exposed by the tool, so no configuration could be copied byte-for-byte.
- **Adapted/re-derived**: representation (r2/2048 vs r3/4096 vs desc v2), model family (rf vs xgboost vs catboost vs logreg) and the refit-on-90% step for library screening. Fusion was considered and rejected: `ml.fuse` provides no validation-scored metric, so a fused model could not be shown to beat the single RF, and fusing a weaker correlated model would be unvalidated complexity.
- **Record for the store**: dataset {n=2824, positive rate 0.8070, scaffold split, Ki binary}; model {RandomForest, Morgan r=2/2048 + 7 RDKit 2D descriptors, AUROC 0.941 (A) / 0.946 (B), AUPRC 0.990 / 0.986}.

## Risks / limitations
No locked final test for this target; small negative class in validation; EF saturated; no measured stability of the top-100 between the scaffold-trained and refit models (the tooling recorded only one screening job); unlabelled library has no ground truth, so no enrichment claim is made. No code or repository changes were needed for this analysis.
