# R #7 kor

- task: `seq_r_kor`
- ticket: `794b4f2a413f636b30a09537af01a927`
- state: ready
- wall: 214.5s, jobs 12 (failed 0), models 4
- best validation model (any split): models/kor_xgboost AUROC=0.9431 AUPRC=0.9859 EF@1%=1.235
- best scaffold model: models/kor_xgboost AUROC=0.9431 EF@1%=1.235
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

KOR/OPRK1 Ki predictor completed through locked final test; 100k library ranked; no PR (deliverable is a report + artifacts). Workspace: /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/kor-seq-target7-794b4f2a413f

(a) DATA, SPLIT, CHOICES
- Labels: given dataset.csv (read-only), 1,899 molecules, 1,500 positives = 0.7899 positive rate, 0 invalid SMILES. Binary Ki labels used as provided (col `label`; id->molecule_chembl_id, smiles->canonical_smiles); no negatives invented, no Ki/IC50 mixing.
- Split: Bemis-Murcko scaffold, 30% test / 10% val, seed 17 -> train 1,141 / val 189 / test 569. Test accessed only via evaluation.locked.
- Features: Morgan r=2, 2048 bits + 7 RDKit 2D descriptors (v1), 2,055 features.
- Model selection on validation only (same manifest), four tool-supported families: logreg AUPRC 0.9606 / AUROC 0.8539; rf 0.9745 / 0.9039; xgboost 0.9859 / 0.9431; catboost 0.9695 / 0.8928. Selected xgboost (best on both). Final model: models/kor_xgboost/model.joblib.

(b) METRICS
- Validation (n=189, 153 pos): AUROC 0.9431, AUPRC 0.9859, EF@1% 1.235, EF@5% 1.235, accuracy 0.8995, F1 0.9373.
- Locked Ki test (receipt, n=569): AUROC 0.9100, AUPRC 0.9583, EF@1% 1.459, EF@5% 1.459.
- Honest caveats: 79% positive rate makes AUPRC optimistic and near-ceiling; validation EF@1% is based on top-2 of 189 molecules (coarse). Library is unlabeled, so no hit-rate/EF is defined for it; library scores are model probabilities only.

(c) TOP-100
- /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/kor-seq-target7-794b4f2a413f/screening/top100.csv (rank,id,smiles,score; 100 rows; scores 0.9711-0.9973; #1 zinc087407 0.997296).
- Full ranking: screening/ranked_100k.csv (100,000 rows, 0 invalid SMILES); report: screening/screening_report.json (sha256 19765c25...).

(d) COST
- 12 tool runs, ~58.4 s wall, ~646.7 CPU-s (~0.18 CPU-h), 0 GPU-s. Screening stage: 17.6 s for 100,000 molecules x 2,055 features. Cost is dominated by the catboost comparison run (~23 s wall / 625 CPU-s); the retained xgboost path itself is ~5 s train + ~18 s screen.

(e) EXPERIENCE REUSE
- Retrieved the given store path (/home/linhan_cluster/evo_vs_rsi/scientific/.artifacts/experience/experience.json): 12 records = 6 dataset + 6 model. KOR-specific retrieval returns 0 (new target), confirming the path works and target #1-#6 exist only as summaries.
- Profiles seen: D2 6811@0.9621, 5HT 4828@0.9803, ADR 3376@0.9588, DRD2 3293@0.6657, MOR 2790@0.7953, CBR 2309@0.9818 (all ChEMBL Ki binary, scaffold split).
- KOR (1,899 @ 0.7899) is closest to MOR -> primary reuse references dataset_MOR_009 / model_MOR_010; CBR is the next-closest rate. Reused verbatim: binary ChEMBL Ki framing, Bemis-Murcko scaffold 30/10 split seed 17, Morgan r=2/2048 + v1 descriptor featurization, probability-based ranking, threshold-free AUROC/AUPRC/EF reporting.
- Adapted: model family selected on validation (xgboost) rather than copied, because retrieval exposes only applicability summaries + payload sha256, not the stored model config; also re-checked the "much smaller dataset" applicability caveat since 1,899 is below the prior minimum of 2,309. No exotic representation, transfer or fusion was needed: prior experience covers this data profile.

KEY ARTIFACTS (relative to workspace): features/dataset.npz (090b9f7e...), features/dataset_report.json, splits/kor_scaffold.json (b4a2a897...), models/kor_xgboost/{model.joblib 4b928731..., predictions.csv, metrics.json a7c6f87b..., artifact_manifest.json}, models/kor_{logreg,rf,catboost}/ (comparison), screening/{ranked_100k.csv 6cb90f6b..., top100.csv 07b1c857..., screening_report.json}, eval/kor_ki_locked_receipt.json (1e9b055e...), experience/{exp_all.json,exp_kor.json,exp_models.json}. No blockers; no human decision needed.
