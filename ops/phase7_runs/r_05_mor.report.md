# R #5 mor

- task: `seq_r_mor`
- ticket: `fbc189d9e56a78a5f02381efab02dc6c`
- state: ready
- wall: 405.9s, jobs 27 (failed 1), models 15
- best validation model (any split): probe_labels AUROC=0.9231 AUPRC=0.967 EF@1%=1.1
- best scaffold model: models_scaffold/rf_v2 AUROC=0.9196 EF@1%=1.341
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

MOR/OPRM1 (sequence target #5) predictor, 100k ranking and report complete. No code change / no PR; all artifacts are in the ticket workspace /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/mor-seq-target5-fbc189d9e56a/.

DATA & PROTOCOL
- Labels: /home/linhan_cluster/evo_vs_rsi/scientific/.artifacts/chembl/oprm1/ki/dataset.csv, 2790 valid molecules (id/smiles resolved to molecule_chembl_id/canonical_smiles; provided binary Ki label, 2219 positives = 79.5%). Label used unchanged, no invented negatives.
- Split: Bemis-Murcko scaffold, seed 17 -> 1953 train / 279 validation / 558 untouched test; the 100k library is unlabeled, so no hit-rate/EF claim is made for it.
- Features: Morgan radius 2, 2048 bits + v1 2D descriptors. Model: sklearn RandomForest via ml.train, seed 17.

CHOICES / RATIONALE (bounded comparison on the scaffold validation set, r2/2048 v1)
- rf 0.9036 AUROC / 0.9626 AUPRC (chosen); catboost 0.8982/0.9609; xgboost 0.8817/0.9512; logreg 0.8537/0.9413.
- v2 descriptors improved rf (0.9196/0.9698) and were rejected for deployment because screening.rank exposes no desc_set parameter and always featurizes with v1, so a v2 model cannot rank the library. Radius-3 (0.8775/0.9498) and 4096-bit (0.8975/0.9606) variants were worse.
- Seed robustness rf-v1: AUROC 0.9036/0.8967/0.9038 (seeds 17/42/7, mean 0.9014); AUPRC 0.9626/0.9600/0.9619 (mean 0.9615).

METRICS
- Scaffold validation (279, prevalence 0.745): AUROC 0.9036, AUPRC 0.9626, EF@1% 1.341 (EF@5% 1.341; EF@1% identical for all four v1 model families on this small validation set, so treat it as low-resolution).
- Locked final test via the independent evaluator (single permitted evaluation, summary receipt only): AUROC 0.9375, AUPRC 0.9741, EF@1% 1.379 (EF@5% 1.379). Test prevalence and raw per-sample results are protected and not exposed; AUPRC must be read against the 0.795/0.745 prevalence baselines, not against 0.5.

DELIVERABLES (all absolute under the ticket workspace)
- Top-100: /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/mor-seq-target5-fbc189d9e56a/mor_top100_rf_v1.csv (100 rows; columns rank,id,smiles,score; scores 0.930-0.835; MOR-typical carboxamide/urea/piperidine chemotypes).
- Full ranking: /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/mor-seq-target5-fbc189d9e56a/mor_library_ranked_rf_v1.csv (100000/100000 featurized, 0 invalid).
- Model: /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/mor-seq-target5-fbc189d9e56a/models_scaffold/rf/model.joblib (sha256 cded76ce2dde244a43210d55dbd40a43d5fe4d3208a81298347a83e15604c67e - same file scored by screening and evaluated locked).
- Screening report /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/mor-seq-target5-fbc189d9e56a/mor_library_ranked_rf_v1_report.json; locked receipt /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/mor-seq-target5-fbc189d9e56a/mor_locked_receipt.json; validation metrics /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/mor-seq-target5-fbc189d9e56a/models_scaffold/rf/metrics.json.

COST
- Whole ticket: 154.5 s wall, ~1462 s CPU, 0 GPU (all CPU tools; GPU never used).
- Chosen final pipeline (featurize + scaffold split + rf train + 100k screening + locked evaluation): 30.0 s wall / 19.3 s CPU.

EXPERIENCE REUSE (store read with the exact absolute path; target=MOR filter returns 0 because MOR is not yet completed, so I read all records)
- 8 records retrieved: dataset_D2_001 + model_D2_002 (~6811 mols, 0.9621 positive, scaffold), dataset_5HT_003 + model_5HT_004 (~4828, 0.9803), dataset_ADR_005 + model_ADR_006 (~3376, 0.9588), dataset_DRD2_007 + model_DRD2_008 (~3293, 0.6657).
- Reused verbatim: the pipeline protocol those records document - ChEMBL Ki binary labelling of the provided labels, Bemis-Murcko scaffold split with validation-based model selection, and independent locked-test reporting.
- Adapted: model family and feature set were re-selected because the MOR profile (2790 molecules, 0.795 positive) lies outside every stored profile (3293-6811 molecules, 0.666-0.980 positive); rf-v1 was chosen on scaffold validation rather than copied from a stored record.
- Limitation to flag: experience.retrieve exposes only record metadata, applicability text and payload_sha256 - the stored payloads (exact model hyperparameters/config) were not readable through the tool, so no literal configuration copy was possible. The reuse is therefore protocol-level, documented honestly rather than overstated.

OTHER LIMITATIONS
- Final model is fit on the 70% scaffold-train split (1953 molecules); the available toolchain has no refit-on-train+val path, so the same model is used for both the reported metrics and the library ranking.
- The v2-descriptor gain (+0.016 AUROC) could not be deployed end-to-end because screening.rank cannot featurize the library with desc_set v2 (schema omits the argument; v2 screening fails, v1 succeeds).
- Raw locked per-sample metrics stay in the protected tree; only the summary receipt is available.
