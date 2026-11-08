# M #6 cbr

- task: `seq_m_cbr`
- ticket: `6547209de52b996834eb60643debb96b`
- state: ready
- wall: 308.6s, jobs 14 (failed 3), models 4
- best validation model (any split): models/cbr_cat AUROC=0.8862 AUPRC=0.9971 EF@1%=1.022
- best scaffold model: models/cbr_cat AUROC=0.8862 EF@1%=1.022
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

Cannabinoid receptor (Ki) target #6 — analysis complete; deliverable is a trained model + ranked 100k library + report (no code PR).

WORKSPACE: /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/cannabinoid-arm-m6-6547209de52b (all paths below are relative to it).

(a) CHOICES AND RATIONALE
- Experience was retrieved first from the mandated absolute store path: /home/linhan_cluster/evo_vs_rsi/scientific/.artifacts/experience/experience.json (3 calls: all records, kind=model, target=MOR). The store held 10 records (5 dataset + 5 model: D2, 5HT, ADR, DRD2, MOR).
- Dataset profile: 2,309 molecules, 2,267 positives (98.18%), 42 negatives; columns molecule_chembl_id / canonical_smiles / precomputed binary label. Closest experience by positive rate: dataset_5HT_003 + model_5HT_004 (4,828 mol, 0.9803) and dataset_ADR_005 + model_ADR_006 (3,376 mol, 0.9588). dataset_MOR_009/model_MOR_010 (2,790 mol, 0.7953) is closest in size but outside its positive-rate applicability; DRD2 (0.6657) is not applicable.
- Reused from those records (protocol as documented): binary Ki labels exactly as provided (no Ki/Kd/IC50 mixing, no censoring transformation), Bemis–Murcko scaffold split, seed 17, scaffold-validation as the reporting channel, Morgan r=2 / 2048 bits + 7 RDKit 2D descriptors (v1).
- Adapted: model family. CB1 has 2,309 molecules, below every stored set (2,790–6,811), so the model records' applicability note ("re-check before applying to much smaller or balanced datasets") applies; I re-checked all four supported families on the identical split. CatBoost won clearly (val AUROC 0.8862 vs RF 0.6591, XGBoost 0.5778, logreg 0.3511; AUPRC 0.9971 vs 0.9882/0.9781/0.9705). Final model: CatBoost, seed 17, 1,618 training molecules, 2,055 features.
- Honest caveat: experience.retrieve emits record metadata + applicability + payload_sha256 only, not the payload body (payloads are content-addressed at .artifacts/experience/payloads/<sha256>.json; existence confirmed but no file-reading tool is available in this session), so prior hyperparameters could not be copied literally — family/parameter choice is the documented adaptation.

(b) METRICS (scaffold-validation: 230 molecules, 225 positives, 5 negatives; seed 17; train 1,618 / val 230 / test 461)
- CatBoost: AUROC 0.8862, AUPRC 0.9971, accuracy 0.9783, F1 0.9890, EF@1% 1.022, EF@5% 1.022.
- Interpretation limits: the always-positive AUPRC baseline is 0.982, and EF@1% has a structural ceiling of ~1.018 at a 98.18% positive rate, so AUPRC/EF are nearly uninformative; AUROC rests on only 5 validation negatives and is therefore noisy/provisional.
- The 461-molecule scaffold test partition was NOT scored: the locked evaluator (evaluation.locked) supports only MOR/KOR/DRD2, and no cannabinoid locked channel exists in this environment.

(c) OUTPUTS
- Top-100 ranking: rankings/cbr_top100.csv (columns rank,id,smiles,score; top score 0.999374 → rank-100 0.998648; #1 zinc000806, O=C(Nc1ccc(C2(C(=O)NC3CCCCC3)CC2)cc1)c1ccc(F)cc1).
- Full 100k ranking: rankings/cbr_full_ranking.csv (100,000 rows, 7.2 MB).
- Fitted model: models/cbr_cat/model.joblib (sha256 176526ca9b563cfbaedc447aa4dadcd76ffa7d2276e7d85a6f264344ab594748).
- Metrics: models/cbr_cat/metrics.json; predictions: models/cbr_cat/predictions.csv.
- Split manifest: splits/cbr_split.json (sha256 f21d5d3683b86057157bf4c00c6b849a1a06f4127367546b2aebe3ab9ae76c30).
- Features: features/cbr_dataset.npz + features/cbr_dataset_report.json (2,309 rows, 0 invalid).
- Screening report: reports/cbr_screening.json (100,000 read, 100,000 featurized, 0 invalid, 13 s).
- Experience retrieval log: reports/experience_all.json.

(d) COST
- Final path: CatBoost train 23.0 s wall / 601.3 s CPU, 100k screening 13.7 s wall / 13.9 s CPU.
- All work: ~50.5 s wall, ~627 s CPU (~10.5 CPU-min), 0 GPU; peak wall for any single job 23.0 s. Model-family comparison added only ~11 s wall.

(e) EXPERIENCE IDS USED
- Used: dataset_5HT_003, model_5HT_004, dataset_ADR_005, model_ADR_006 (positive-rate match), with dataset_MOR_009/model_MOR_010 reviewed but treated as out of applicability (positive rate 0.7953).
- Reused verbatim: the documented binary-Ki + Bemis–Murcko scaffold-split evaluation protocol (seed 17, scaffold-validation reporting).
- Adapted: model family/parameters re-selected on validation because the CB1 set is smaller than every stored dataset; featurization kept at the same Morgan r=2/2048 + v1 descriptor recipe.

LIMITATIONS / RISKS
- 100k library is unlabeled: the ranking is prediction-only; no hit rate, EF, or enrichment is claimed for it (AGENTS.md red line respected).
- Metrics are scaffold-validation, not a locked final test; they are not comparable to locked-test numbers for the three evaluator-supported targets.
- With 42 negatives overall, model ranking and AUROC uncertainty is large; treat CatBoost-vs-others as provisional.

No human action required.
