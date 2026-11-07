# R #1 d2

- task: `seq_r_d2_coldstart`
- ticket: `4f74e0895047477d2fe876c1ad35640f`
- state: ready
- wall: 1147.2s, jobs 64 (failed 7), models 34
- best validation model (any split): artifacts/train_rf_r4v1_scaffold AUROC=0.9218 AUPRC=0.9981 EF@1%=1.019
- best scaffold model: artifacts/train_rf_r4v1_scaffold AUROC=0.9218 EF@1%=1.019
- refits excluded from ranking: ['artifacts/final_rf_r4v1_90', 'artifacts/final_xgb_r4v1_90', 'artifacts/final_xgb_v1_90']
- top-100 artifacts: 8

## agent report

DELIVERY SUMMARY (human-facing): Cold-start DRD2 replay complete. The experience store returned 0 records, so nothing was reused. Final model: XGBoost on Morgan r2/2048 + 7 RDKit descriptors, trained on 6,130 molecules. Locked test AUROC 0.8028, AUPRC 0.7699, EF@1% 1.52. Scaffold-validation AUROC 0.8683 (AUPRC 0.9969; EF@1% 1.019, saturated). All 100,000 library molecules are ranked; top-100 at /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/dopamine-coldstart-4f74e0895047/artifacts/top100_drd2_ki.csv. Cost ~11 min wall / ~1.6 CPU-hours, no GPU. Limitations below.

=== FULL REPORT ===

(a) CHOICES AND RATIONALE
- Experience retrieval (run first, as instructed): store=/home/linhan_cluster/evo_vs_rsi/scientific/.artifacts/experience/replay_coldstart.json -> {"count": 0, "records": []} (artifacts/experience_retrieve.json). Zero experience_ids used; nothing reused verbatim, nothing adapted. Cold start, so all choices were derived from the data profile.
- Data profile: 6,811 rows, all featurizable (0 invalid); columns molecule_chembl_id / canonical_smiles / label; DRD2 Ki binary labels; 6,553 positives / 258 negatives = 96.2% positive. This explains saturated AUPRC/EF in internal validation and was the key modelling constraint.
- Validation: scaffold (Bemis-Murcko) split, seed 17, 32% test / 12% val -> train 3,815 / val 817 (802 pos, 15 neg) / test 2,179. Seeds 17/23/42 produced identical assignments (identical validation predictions), so split-seed variance could not be estimated; model-seed variance was used instead.
- Representations/models screened on scaffold validation (AUROC; AUPRC): logreg r2/2048 v1 0.8031 (0.9925); RF r2/2048 v1 0.8632 (0.9962); XGB r2/2048 v1 0.8683 (0.9969); CatBoost r2/2048 v1 0.8390 (0.9956); RF r3/4096 v2 0.8707; XGB r3/4096 v2 0.8776; CatBoost r3/4096 v2 0.8661; RF r4/4096 v2 0.8901; XGB r4/4096 v2 0.9077; CatBoost r4/4096 v2 0.8869; XGB r4/4096 v1 0.8683; RF r4/4096 v1 0.9218 (seed 17) but 0.8888 (seed 42) and 0.8759 (seed 7), showing +/-0.02 seed noise on only 15 validation negatives.
- Deployability constraint discovered by direct test: the locked evaluator and screening tool featurize with radius 2 / 2048 bits and desc_set v1 (screening has no desc_set override). A locked-evaluation attempt with the r4/4096 model failed; the r2/2048 v1 model succeeded. Screening with r4 features likewise produced no outputs when r2 arguments were supplied. Therefore, although r4/4096 + desc_set v2 had the best scaffold AUROC (0.9077), it cannot be evaluated or used to rank the library with the provided deployment tools.
- Selected final model: XGBoost, Morgan r2/2048 + 7 RDKit 2D descriptors (desc_set v1), seed 17. Among deployable configurations it had the best mean scaffold AUROC (0.8683 seed 17; 0.8569 seed 42; 0.8521 seed 7; mean 0.859) versus RF (0.833) and CatBoost (0.839). Final refit on 6,130 molecules (90% internal-random split, seed 17), model artifacts/final_xgb_v1_90/model.joblib. A single model was chosen rather than a fusion because the fusion tool does not produce a model for library screening and no metric tool exists for fused validation predictions.
- Scientific integrity: only Ki labels used, no Ki/Kd/IC50 mixing; no negatives invented; the 100k library is unlabeled and no EF is claimed for it. I did not independently re-verify duplicate-molecule confinement across splits beyond the harness scaffold splitter.

(b) METRICS
- Scaffold-manifest validation (817 molecules, 15 negatives; selected config): AUROC 0.8683, AUPRC 0.9969, EF@1% 1.019, EF@5% 1.019. Baseline AUPRC = 802/817 = 0.9816; top 1% is only 8 molecules, so EF@1% is mathematically saturated and shows no enrichment.
- Final model, internal random 10% diagnostic (681 molecules, 26 negatives): AUROC 0.9613, AUPRC 0.9983, EF@1% 1.04 (optimistic because random-split near-duplicates remain).
- LOCKED TEST (protected chembl37_ki_drd2, one permitted evaluation; receipt artifacts/locked_receipt.json): AUROC 0.8028, AUPRC 0.7699, EF@1% 1.52, EF@5% 1.258. This is the official held-out result. The locked positive rate is not disclosed, so AUPRC/EF baselines cannot be computed for it.

(c) TOP-100 PATH
- Top-100: /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/dopamine-coldstart-4f74e0895047/artifacts/top100_drd2_ki.csv (columns rank,id,smiles,score; 100 rows, all valid, 100 distinct ZINC ids, scores descending 0.999971 to >=0.99983).
- Full ranking: artifacts/rank_drd2_ki_100k.csv (100,000 rows, all valid). Verified 100,000 and 100 rows respectively by independent featurization; top-30 SMILES extracted and inspected.
- Honest reading: scores are extremely compressed (0.9998-0.99997) because of the 96% positive prior, and the top-30 span heterogeneous scaffolds (sulfonamides, benzoxazinones, indoles, fluorinated aromatics) rather than a single canonical D2 motif. With locked AUROC 0.803 the top-100 should be treated as triage/prioritization, not structurally validated D2 hits.

(d) COST
- ~11 minutes wall clock, ~5,640 CPU-seconds (~1.6 CPU-hours), 0 GPU-seconds, no external API spend.
- 62 scientific tool invocations: 32 model fits (5 CatBoost fits alone = 5,341 CPU-s, ~95% of CPU), 14 featurizations, 5 splits, 6 screening runs, 2 locked-evaluation attempts (1 failed on r4 feature mismatch, 1 succeeded), 2 fusion checks (assessed, not used), 1 experience retrieval.

(e) EXPERIENCE
- Used experience_ids: none (store returned count 0 / records []).
- Reused verbatim: nothing. Adapted: nothing. All configurations were derived locally from dataset characteristics.
- Facts that would be written to a future store (store is read-only here): DRD2 Ki ChEMBL dataset is 6,811 molecules with 96.2% positives -> AUPRC/EF on internal splits are saturated and AUROC is the usable selection metric; the deployable feature pipeline for this harness is Morgan r2/2048 + desc_set v1; richer r3/r4 and desc_set v2 features score better on validation but are not accepted by the locked evaluator/screening tool.

LIMITATIONS / RISKS
1. 96.2% positive rate makes internal AUPRC/EF uninformative; only the locked AUROC (0.8028) and EF@1% (1.52) are meaningful.
2. Scaffold validation has 15 negatives, so config selection differences (~0.02-0.04 AUROC) are near noise; seed 17 was the best draw.
3. The single allowed locked evaluation is consumed; no further model revision can be re-evaluated within this ticket.
4. Library scored as provided, no deduplication; screening report notes the caller owns that step.
5. No GitHub PR/code change was part of this deliverable (data-science replay only).

Key artifacts: artifacts/experience_retrieve.json, artifacts/feat_v1.npz, artifacts/split_scaffold.json, artifacts/final_xgb_v1_90/{model.joblib,metrics.json}, artifacts/locked_receipt.json, artifacts/rank_drd2_ki_100k.csv, artifacts/top100_drd2_ki.csv.
