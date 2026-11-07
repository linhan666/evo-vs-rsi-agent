# R #4 drd2

- task: `seq_r_drd2`
- ticket: `8377ac141ca66518c081158aa512b2a2`
- state: ready
- wall: 470.8s, jobs 31 (failed 0), models 16
- best validation model (any split): train_catboost_v2 AUROC=0.8649 AUPRC=0.9258 EF@1%=1.509
- best scaffold model: train_catboost_v2 AUROC=0.8649 EF@1%=1.509
- refits excluded from ranking: []
- top-100 artifacts: 2

## agent report

DRD2 (sequence target 4/9) complete — report-only deliverable, no code change/PR. All numbers below are from executed scientific-tool jobs whose artifacts remain in the ticket workspace /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/chembl-drd2-seq4-8377ac141ca6.

(a) Choices and rationale
- Data/labels: ChEMBL DRD2 Ki binary set, dataset.csv, 3293 molecules, 2192 positives (66.6% positive; val 218/329 = 66.3%). Label source recorded as chembl_drd2_ki; labels used as provided, no Ki/Kd/IC50 mixing, no invented negatives.
- Experience: called experience.retrieve with the exact absolute store path; store returned 6 records: dataset_D2_001, model_D2_002 (6811 mol @ 0.9621 pos), dataset_5HT_003, model_5HT_004 (4828 @ 0.9803), dataset_ADR_005, model_ADR_006 (3376 @ 0.9588). Reused verbatim: ChEMBL Ki binary treatment and the Bemis-Murcko scaffold-split protocol (that is what the records certify; their applicability text explicitly warns the recipe is only certified for ~96-98% positive, 3376-6811-molecule sets). Adapted/re-checked: because DRD2 is 66.6% positive and 3293 molecules, I re-selected representation and model family on DRD2's own scaffold validation instead of copying the prior model blindly. Honest limitation: the retrieve surface exposes applicability + payload hashes, not hyperparameters, so verbatim hyperparameter copying was not possible and is not claimed.
- Split: scaffold (Bemis-Murcko), seed 17, train 2306 / val 329 / local-test 658. The local 658 were not used for fitting or reporting (avoids leakage); final judge is the hidden locked test.
- Representation: Morgan radius 2, 2048 bits + 7 RDKit 2D descriptors (desc_set v1). Alternatives tested on the same split: radius 3 (AUPRC 0.9215), 4096 bits (0.9302), desc_set v2 (rf 0.9290), all worse than 2048/v1 (0.9328).
- Model: RandomForest. Val comparison: logreg 0.8396 AUPRC / 0.7532 AUROC; xgboost 0.9014/0.8250; catboost 0.9243/0.8524; rf 0.9328/0.8648. Model-seed stability: rf AUPRC 0.9246-0.9328 over seeds 7/17/42/2024 (declared seed 17 kept, not cherry-picked).
- Fusion: rf+catboost rank fusion was considered but rejected: ml.fuse returns only a fused ranking with null AUPRC and cannot be validated or submitted to the locked evaluator, so a single validated rf is the more reliable choice.
- EF@1% caveat: val positive rate 0.663 caps EF@1% at 1.509; the model hits the ceiling (1.509). Locked test caps at 1.824 and the model hits 1.824. So EF@1% is saturated on both sets and not discriminative here; AUPRC/AUROC are the evidence.

(b) Metrics
Scaffold validation (n=329, positives=218): AUROC 0.8648, AUPRC 0.9328 (no-skill baseline 0.6626), EF@1% 1.509 (ceiling), EF@5% 1.509, accuracy 0.7751, F1 0.8186.
Locked final test (protected, receipt locked_drd2_ki_receipt.json): AUROC 0.9327, AUPRC 0.9512, EF@1% 1.824 (ceiling), EF@5% 1.824.

(c) Top-100 path: /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/chembl-drd2-seq4-8377ac141ca6/drd2_top100.csv (rank,id,smiles,score). Full 100k ranking: drd2_library_ranked.csv; screening report drd2_screening_report.json (100000 rows read/featurized, 0 invalid, model sha256 e799389c... = train_rf_v1/model.joblib). Top chemotypes are D2-like arylpiperazines / o-methoxyphenylpiperazines and benzisothiazole-piperidines, a sanity check on plausibility. Top-100 score range 0.672-0.865; these are predictions only - no hit rate or true EF can be claimed for an unlabeled library.

(d) Cost: ~239 s total wall (31 tool invocations, 0 GPU; includes exploration and 2 redundant screening attempts (~41 s) caused by a tool-response serialization glitch whose artifacts were still recorded). Final deliverable path alone ~31 s (retrieve 0.1 + featurize 1.0 + split 2.3 + train 4.4 + screen 20.5 + locked eval 2.7). CPU-heavy: catboost fits ~4.4k CPU-s total. No paid/account resources.

(e) Reuse: experience ids used as reference: dataset_D2_001, model_D2_002, dataset_5HT_003, model_5HT_004, dataset_ADR_005, model_ADR_006 (D2 pair for target-class match, ADR pair for size match). Reused verbatim: scaffold-split protocol and Ki binary treatment. Adapted: ML family, fingerprint/descriptor configuration, and class-balance handling were re-validated on DRD2 because applicability conditions (96-98% positive) do not hold.

Artifacts: model train_rf_v1/model.joblib, metrics train_rf_v1/metrics.json, receipt locked_drd2_ki_receipt.json, top-100 drd2_top100.csv. No PR (report-only deliverable).
