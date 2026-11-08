# M #7 kor

- task: `seq_m_kor`
- ticket: `cdaa20fe54f7a23026642a20e0a980ca`
- state: ready
- wall: 399.3s, jobs 23 (failed 0), models 9
- best validation model (any split): kor_xgboost_refit90 AUROC=0.9493 AUPRC=0.9853 EF@1%=1.267
- best scaffold model: kor_xgboost_scaffold_descv2_seed42 AUROC=0.8877 EF@1%=1.086
- refits excluded from ranking: []
- top-100 artifacts: 3

## agent report

KOR/OPRK1 Ki arm-7 complete. Delivered: xgboost Ki classifier, locked-test metrics, top-100 and full ranking of the 100k ZINC library. All artifacts are in the ticket workspace /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/kor-arm-m7-cdaa20fe54f7/.

(a) CHOICES AND RATIONALE
- Data: ChEMBL Ki binary labels @ .../chembl/oprk1/ki/dataset.csv; 1,899 rows, all 1,899 valid, 0 skipped; 1,500 positives = 0.790 positive rate (id/smiles auto-resolved to molecule_chembl_id / canonical_smiles). Ki only; no Kd/IC50 mixing.
- Experience match: retrieved with the required absolute store path (12 records). KOR profile (1,899 mols, 0.790) matches dataset_MOR_009 / model_MOR_010 (2,790 mols, 0.7953 positive rate) and is the same target class (opioid receptor); dataset_CBR_011 (2,309 @ 0.9818) is only near in size.
- Validation: Bemis-Murcko scaffold split, test 20% / val 10% / seed 17 (1,331 / 189 / 379). Random split was measured and rejected as optimistic (logreg AUROC 0.9338 random vs 0.6123 scaffold).
- Representation: Morgan radius 2, 2,048 bits + 7 RDKit 2D descriptors (desc_set v1). v1 is what screening.rank re-featurizes with, so training and library scoring use identical features.
- Family: compared logreg / rf / xgboost / catboost on the scaffold validation; xgboost had the best AUROC with near-best AUPRC, so xgboost was delivered.
- Final fit: xgboost refit on 90% of the development data (1,709 mols, seed 17); the remaining 10% exists only because ml.train requires a holdout and is not used for any reported claim.

(b) METRICS
- Selection metrics on scaffold validation (n=189, 174 positives; kor_xgboost_scaffold/metrics.json): xgboost AUROC 0.8805, AUPRC 0.9863, EF@1% 1.086. Caveat: EF@1% is saturated here (validation positive rate 0.921, maximum possible EF 1.086), so it is uninformative; the locked EF is the meaningful one.
- Official locked final test (protected, receipt kor_locked_eval_receipt.json, target KOR endpoint Ki desc v1): AUROC 0.9042, AUPRC 0.9531, EF@1% 1.459, EF@5% 1.459. Raw locked metrics are not readable from the ticket.
- The 100k ZINC set is unlabeled: no true EF@1%/hit rate is defined for it and none is claimed.
- Other families on the same scaffold validation: logreg 0.6123/0.9334, rf 0.8446/0.9817 (AUROC/AUPRC), catboost 0.8801/0.9868. desc v2 descriptors gave 0.8877/0.9870 but were not adopted (marginal, and screening.rank's fixed featurizer mirrors v1).

(c) ARTIFACTS
- Top-100: /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/kor-arm-m7-cdaa20fe54f7/kor_top100.csv (100 rows, verified; columns rank,id,smiles,score).
- Full ranking: /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/kor-arm-m7-cdaa20fe54f7/kor_library_ranked.csv (100,000/100,000 library rows scored, 0 invalid SMILES; kor_screening_report.json).
- Delivered model: kor_xgboost_refit90/model.joblib (sha256 1ae108d0...). Locked receipt: kor_locked_eval_receipt.json.

(d) COST
- CPU only, no GPU. Tool wall-clock ~93 s total (including one duplicated 12 s screening retry caused by a tool-output serialization failure; the ranking itself is 12.1 s for 100k molecules), ~13 CPU-minutes (CatBoost's 720 CPU-s multithreaded run dominates the family comparison), locked evaluation 2.7 s. Session wall ~6 minutes.

(e) REUSE
- Used: dataset_MOR_009, model_MOR_010 (and considered dataset_CBR_011).
- Reused verbatim: the recorded applicability regime for binary ChEMBL Ki, high positive rate (~0.79), and scaffold-split validation; Ki-only label channel preserved.
- Adapted: sample-size regime (1,899 vs 2,790) and the estimator. Important limitation: experience.retrieve surfaces only applicability text + payload_sha256; it does not expose the stored estimator/hyperparameters, so the model family was re-selected on KOR's own scaffold validation rather than copied. Fusion was tested as an option and not adopted: ml.fuse produces only a fused validation ordering (no fused metric and no model artifact the locked evaluator can consume).

Scientific-integrity notes: labels are binary Ki from a single endpoint; duplicates cannot cross splits because identical molecules share scaffolds in the scaffold split; all reported test numbers come from the locked evaluator receipt; no enrichment claim is made for the unlabeled library.
