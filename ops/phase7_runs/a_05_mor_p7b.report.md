# A #5 mor

- task: `p7b_a_mor`
- ticket: `e16601ac3b6e3280ab4a61581fd79016`
- state: ready
- wall: 309.3s, jobs 20 (failed 1), models 14
- best validation model (any split): .artifacts/state/work/mor-frozen-a-e16601ac3b6e/runs/rf_v2_s23 AUROC=0.9424 AUPRC=0.9715 EF@1%=1.416
- best scaffold model: .artifacts/state/work/mor-frozen-a-e16601ac3b6e/runs/rf_v2_s23 AUROC=0.9424 EF@1%=1.416
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

MOR Ki arm A complete: frozen-split predictor trained, one locked evaluation consumed, 100k ZINC library ranked. Receipt: locked AUROC 0.9425.

APPROACH (no experience store used; derived by validation comparison on the frozen manifest)
- Labels: scientific/.artifacts/chembl/oprm1/ki/dataset_p7b.csv, 2790 molecules (2219 pos / 571 neg, 79.5% pos), columns molecule_chembl_id/canonical_smiles/label.
- Frozen split passed as --split-manifest frozen_oprm1.json (scaffold-manifest): train 2385 / validation 279; data.split was never called.
- Features: rdkit.featurize Morgan radius 2, 2048 bits + 7 RDKit 2D descriptors. Compared desc_set v1 vs v2 (v2 npz is ~1.8x larger, richer fingerprint pack) at the same radius/bits so the locked evaluator's default featurization matches.
- Model search: 4 families x 2 desc sets, same frozen split/seed 17, plus 5 seed reruns. Validation:
  v1: logreg .8747/.9348; rf .9362/.9722; xgboost .9289/.9637; catboost .9128/.9565 (AUROC/AUPRC)
  v2: logreg .8781/.9374; rf .9410/.9738; xgboost .9277/.9621; catboost .9253/.9637
  RF v2 seed spread 17/23/42/101: AUROC .9410/.9424/.9422/.9357; AUPRC .9738/.9715/.9747/.9699 (mean .9403/.9725).
- Selected random forest on desc_set v2, seed 17 (default seed; not cherry-picked). Chosen on AUROC/AUPRC because EF@1% is saturated: validation prevalence .706 -> ceiling 1.416, and every model's top-3 validation molecules are all positives (EF@1% = 1.416). Validation EF@5% = 1.416 too.
- Final model is a deterministic re-run of that config: identical metrics and model sha as the trial run (sha256 9035b55d1cb64520d55d020ad615e4b725b4762bd8edd75416f212ba85df0777).

LOCKED EVALUATION (exactly one call; evaluation.locked --target MOR --endpoint Ki --desc-set v2 --receipt evaluation/mor_locked.json)
Receipt metrics: AUROC 0.9425, AUPRC 0.9745, EF@1% 1.379, EF@5% 1.379. Quote: "auroc": 0.9425, "auprc": 0.9745, "ef_at_1pct": 1.379. The raw locked file stays in the protected tree; receipt sha256 6ea308740a0590b0f22a7a0de4251ca068fc4eae9703d47ac6cd997c149adb8b. EF again non-discriminating (EF@1%=EF@5%), so AUROC/AUPRC carry the conclusion.

LIBRARY RANKING
- screening.rank with the same model and desc_set v2: 100000/100000 rows read and featurized, 0 invalid, 92.8 s, score range top 0.945 -> rank 100 0.8329.
- Full ranking: /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/mor-frozen-a-e16601ac3b6e/ranking/mor_ki_library_ranked.csv (sha256 87f4d24147f44ffda18d05b59a45021c8568daca71aeb342e6eced57118e1875)
- Top-100: /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/mor-frozen-a-e16601ac3b6e/ranking/mor_ki_top100.csv (sha256 9153155e8cedd6eb0ed94eab14763bd8d1ac39c77ff4ef7625d6f297a2b66ed5; 100 rows verified, best-first, top hit zinc025392 0.9450)
- Screening report: .../ranking/mor_ki_screening_report.json (sha256 2103b68b...); it states predictions only, no hit rate/enrichment is defined for an unlabeled library.

OTHER PATHS
- Features: .../features_p7b_v2.npz (sha256 cb5b54ba785ab2655f0f076c688cd6539efb91c694c4a5c2963936952bf29ad4)
- Final metrics: .../runs/mor_ki_rf_v2_final/metrics.json (auroc .9410, auprc .9738, ef@1% 1.416, counts 2385/279)
- Receipt: /home/linhan_cluster/evo_vs_rsi/evaluation/mor_locked.json

COST
- 20 scientific jobs total: 19 succeeded, 1 failed smoke run (relative input path unresolved; no data processed) — all CPU, no GPU.
- Tool wall time 165.8 s; end-to-end ~4.6 min (18:51:26Z -> ~18:56:00Z). Largest single job: library featurization+scoring 93.2 s.
- Experience ids reused: none. Arm A has no experience store and no experience.* calls were made.

INTEGRITY NOTES
- No data.split call; frozen scaffold manifest used for training and validation.
- No test-set error inspection; only the summary receipt was read.
- 100k library is unlabeled: top-100 is model-ranked only — no EF@1% or hit-rate claim is made for it.
