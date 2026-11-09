# M #8 ca2

- task: `p7e_m_ca2`
- ticket: `b868f6845868927db74ee5073afeb5c4`
- state: ready
- wall: 229.3s, jobs 14 (failed 3), models 4
- best validation model (any split): ca2/train_v1_rf AUROC=0.9838 AUPRC=0.9991 EF@1%=1.056
- best scaffold model: ca2/train_v1_rf AUROC=0.9838 EF@1%=1.056
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

CA2 (Ki) run complete — no code change, so no PR; deliverable is the locked receipt plus ranked library artifacts. All work via the science toolkit in the ticket workspace; paths below are workspace-relative as the toolkit reports them.

CHOICES
- Split: passed the frozen manifest .../ki/splits/frozen_carbonic_anhydrase_2.json as --split-manifest to ml.train (data.split never called). ml.train counts: joined 6206, train 5306, validation 621 → 279 implied held-out (test), scaffold-manifest strategy.
- Labels: the provided binary Ki column of dataset_p7b.csv used unchanged (label_column=label, label_source=chembl_ki_binary); no re-thresholding, no label edits. Overall positive rate 5751/6206 = 0.927.
- Features: Morgan r=2, 2048 bits + 7 RDKit descriptors = desc_set v1; dataset featurized 6206/6206 valid, 0 invalid, id→molecule_chembl_id, smiles→canonical_smiles (ca2/featurize_p7b_v1.json). desc_set v2 was also featurized (6206/6206 valid) but ml.train rejected it for both logreg and rf (exit 1, tool exposes no stderr), so v2 is unusable for training as delivered; all training used v1.
- Model selection on scaffold-validation only, 4 families (all with the frozen manifest, seed 17):
  | model | AUROC | AUPRC | EF@1% |
  | logreg | 0.9156 | 0.9936 | 1.056 |
  | rf | 0.9838 | 0.9991 | 1.056 |
  | xgboost | 0.9716 | 0.9983 | 1.056 |
  | catboost | 0.9675 | 0.9981 | 1.056 |
  RF chosen: best validation AUROC and AUPRC. EF@1% is identical for every model and equals its mathematical ceiling (1/0.9469 validation positive rate; all 6 of the top 6 are positive), so EF@1% did not discriminate — AUROC/AUPRC drove the choice.
- Locked: exactly one evaluation.locked call — target CA2, endpoint Ki, desc_set v1, model ca2/train_v1_rf/model.joblib → receipt evaluation/ca2_locked.json. Receipt metrics: AUROC 0.9687, AUPRC 0.9969, EF@1% 1.063 (EF@5% 1.063). Raw locked file stayed in the protected tree; only the receipt was read.
- Screening: rf/v1 model scored /home/linhan_cluster/evo_vs_rsi/scientific/.artifacts/zinc/library_100k.smi — 100000/100000 featurized, 0 invalid, 0 duplicates removed (library scored as provided). Outputs: ca2/library_ranked.csv (full 100k ranking), ca2/top100.csv (top-100), ca2/screening_report.json. Top-100 path: ca2/top100.csv (scores 0.985–1.000; top ranks dominated by primary aryl-sulfonamides, the known CA2 zinc-binding motif — plausibility check only, not a measured hit rate).

EVIDENCE/CHECKS
- Preprocessing: ca2/features_p7b_v1.npz sha 672d83…; ca2/train_v1_rf/artifact_manifest.json ties that sha and dataset sha d04d4b… to the fitted model.joblib sha 70b7b0…; screening report's model_sha256 matches 70b7b0…; receipt sha 008be1….
- Metrics rechecked against the JSON artifacts, not the transcript summary.
- Provenance gap: ml.train's artifact_manifest lists features+labels but not the split-manifest hash; the manifest path is in the recorded argv and the metrics record split_strategy=scaffold-manifest.

COST
- 14 toolkit jobs (11 succeeded, 3 failed: one input-probe featurize, v2 logreg, v2 rf); total job wall time 47.0 s. Breakdown: screening 17.1 s; featurizations 1.1 s + 6.7 s; five successful trainings 3.0–5.3 s each; locked eval 2.6 s; experience reads 0.3 s. Ticket wall clock ~4 min. No GPU used, no server-side interference.

EXPERIENCE
- experience_m_rep3.json (ca2/exp_store_all.json): 14 records for D2, 5HT, ADR, DRD2, MOR, CBR, KOR; 0 records for CA2. None reused — the applicability notes bind each record to its own target/size/positive-rate, so all are context only. Ids inspected: dataset_KOR_013/model_KOR_014 (most recent) and the dataset/model pairs for the other six targets.

LIMITATIONS
- Labels are binary, so scores are activity-class probabilities, not potency: the ranking must not be read as predicted pKi ordering.
- 92.7% positive rate makes AUPRC's no-skill baseline 0.927 and saturates EF@1%; AUROC/AUPRC carry the signal.
- Validation→locked AUROC drop 0.0151, with an implied 279 locked-test molecules (~17 negatives) — the locked AUROC has a wide CI.
- The 100k library is unlabeled: no hit rate or EF@1% is defined for it (screening report states this explicitly).
- desc_set v2 not trainable through ml.train as delivered (documented above); an upstream tool limitation, not a modelling choice.
