# M #4 drd2

- task: `p7b_m_drd2`
- ticket: `81b6a3421515a8edf8b942fb9ae1d390`
- state: ready
- wall: 290.0s, jobs 13 (failed 0), models 6
- best validation model (any split): p7b_drd2_m/v2_rf AUROC=0.9544 AUPRC=0.9678 EF@1%=1.705
- best scaffold model: p7b_drd2_m/v2_rf AUROC=0.9544 EF@1%=1.705
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

DRD2 (Ki) P7b arm M completed end-to-end with the scientific toolchain; 13 jobs, all SUCCEEDED, 225 s wall-clock span (3m45s; summed job time 157 s), 0 retried/failed jobs.

DATA & SPLIT: dataset_p7b.csv = 3293 molecules, 0 invalid; frozen scaffold manifest used directly (no data.split call): train 2816 / validation 329 / locked test 148. Label source declared "chembl_drd2_ki_binary_p7b"; overall positives 2192 (66.6%), validation positives 193 (58.7%). Features: Morgan ECFP r=2, 2048 bits + 7 RDKit 2D descriptors; desc_set v1 and v2 both featurized and compared.

MODEL SELECTION (validation only, before any locked access) — AUROC / AUPRC / EF@1%:
logreg v1 0.8764 / 0.8971 / 1.705
rf v1 0.9481 / 0.9640 / 1.705
xgboost v1 0.9423 / 0.9608 / 1.705
catboost v1 0.9444 / 0.9595 / 1.705
rf v2 0.9544 / 0.9678 / 1.705  <-- selected at p7b_drd2_m/v2_rf/model.joblib (sha256 c339b866...)
xgboost v2 0.9440 / 0.9612 / 1.705
EF@1% is saturated at its ceiling on validation (top 3 of 329 all positive => 1.0 precision / 0.5866 prevalence = 1.705), so AUROC/AUPRC were the discriminating criteria. RF chosen for best validation AUROC+AUPRC and robustness; catboost was the costliest (28.4 s wall, 768 CPU-s) and did not win.

LOCKED EVALUATION (exactly one, evaluation.locked --target DRD2 --endpoint Ki --desc-set v2 --receipt evaluation/drd2_locked.json): AUROC 0.9215, AUPRC 0.9411, EF@1% 1.824, EF@5% 1.824 (EF again at ceiling: k=1 on 148 test molecules, so top-1 hit gives 1.824 = 1/prevalence; AUROC/AUPRC are the informative numbers). Raw protected metrics (protected/chembl37_ki_drd2/metrics_test_locked_agent_Ki_v2_._DRD2.json) are not readable from the ticket; only the receipt summary is available.

RANKING: screening.rank featurized 100000/100000 library molecules, 0 invalid, scored with the same rf/v2 pipeline; full ranking p7b_drd2_m/ranked_library.csv (100000 rows, best first), top-100 p7b_drd2_m/top100.csv (rank,id,smiles,score; #1 zinc046207 score 0.910; 100th ~0.76). Screening report explicitly states no hit-rate/enrichment is defined for the unlabeled library and none was claimed.

EXPERIENCE: experience.retrieve on experience_m.json returned 6 records (dataset_D2_001, model_D2_002, dataset_5HT_003, model_5HT_004, dataset_ADR_005, model_ADR_006) and 0 DRD2 records (target filters "DRD2" and "DRD2 (Ki)" both returned count 0). None were reused: each applicability note is scoped to another target's ChEMBL Ki binary set (~6811, ~4828, ~3376 molecules at ~0.96 positive rate, scaffold split) and DRD2 here is 3293 molecules at 0.666 positive rate, so reusing them would violate their stated limits. Ids reviewed but not applied: the six above.

INTEGRITY/LIMITS: frozen split untouched, Ki endpoint only, no test-set peeking outside the locked evaluator, one locked evaluation consumed, no EF@1% claim on the unlabeled library. Evidence artifacts: p7b_drd2_m/features_v1_report.json, features_v2_report.json, v2_rf/{metrics.json,predictions.csv,model.joblib,artifact_manifest.json}, screening_report.json, ranked_library.csv, top100.csv, evaluation/drd2_locked.json. Locked AUROC (0.9215) trails validation (0.9544) by 0.033, a normal scaffold-split generalisation gap; no claim beyond the receipt.

Paths are workspace-relative (ticket workspace = this ticket's directory). No code/PR was needed for this ticket.
