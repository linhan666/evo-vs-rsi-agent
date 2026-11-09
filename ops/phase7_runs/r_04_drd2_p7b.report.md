# R #4 drd2

- task: `p7b_r_drd2`
- ticket: `f9431dceb9c14e0231f7316bc772b89a`
- state: ready
- wall: 467.5s, jobs 24 (failed 0), models 11
- best validation model (any split): runs/rf_v2_seed97 AUROC=0.9555 AUPRC=0.9697 EF@1%=1.705
- best scaffold model: runs/rf_v2_seed97 AUROC=0.9555 EF@1%=1.705
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

P7b DRD2 Ki (target 4/9) complete. Final model: RandomForest on rdkit.featurize desc_set=v2 (Morgan r=2, 2048 bits + 7 RDKit 2D descriptors), frozen split, one locked evaluation used. Locked-test AUROC = 0.9215.

(a) Choices and rationale
- Frozen split respected: /home/linhan_cluster/evo_vs_rsi/scientific/.artifacts/chembl/drd2/ki/splits/frozen_drd2.json passed as split_manifest to ml.train; data.split never called; no self-chosen fractions.
- Labels: dataset_p7b.csv, label column "label", id molecule_chembl_id, label_source chembl_ki. 3293 rows, 2192 positives (0.6657). ml.train joined 3293, fitted on 2816 train and scored 329 validation; the other 148 joined rows are outside the manifest train/validation blocks this tool consumes (they cannot be the locked set, which was removed from the CSV) and were left untouched.
- Representation: desc_set v2 beat v1 for every family, so v2 was used (v1-vs-v2 AUROC/AUPRC: logreg 0.8764/0.8971 vs 0.8833/0.9038; rf 0.9481/0.9640 vs 0.9544/0.9678; xgboost 0.9423/0.9608 vs 0.9440/0.9612; catboost 0.9444/0.9595 vs 0.9457/0.9626).
- Model: ml.train rf, seed 17, default hyperparameters, chosen by validation AUPRC then AUROC. Radius 3 on v2 was tested and rejected (0.9439/0.9611). Seed stability at seeds 43/97: AUROC 0.9541/0.9555, AUPRC 0.9679/0.9697 (chosen seed was not cherry-picked; seed 17 is the default and its 0.9544/0.9678 sits inside that range).
- No model fusion: ml.fuse emits no validation metric, so an RF+XGB fused scorer could not have its weight justified by validation AUPRC, and only one locked evaluation exists per ticket/endpoint. The single locked-evaluated model was used for ranking.
- 3293/3293 dataset and 100000/100000 library SMILES featurized, 0 invalid.

(b) Frozen-split validation (329 molecules, 193 positive, scaffold-manifest)
AUROC 0.9544, AUPRC 0.9678, EF@1% 1.705, EF@5% 1.705, accuracy 0.8419, F1 0.8791.
Caveat: EF@1% is saturated here (top 1% = 4 molecules, all 4 positive, theoretical max 1/0.5866 = 1.7046), and every model tested scored exactly 1.705, so EF@1% did not discriminate; selection used AUPRC/AUROC.

(c) Locked test, quoted verbatim from evaluation/drd2_locked.json (sha256 be6030dcb9d64c61b1c540c316598d0739b12c9babaeca578d30ae7b422bee8b): target DRD2, endpoint Ki, desc_set v2; "auroc": 0.9215, "auprc": 0.9411, "ef_at_1pct": 1.824, "ef_at_5pct": 1.824. Locked-test AUROC = 0.9215. Exactly one locked evaluation was made (job eb9522e9ca4c); the protected raw metrics file was not read.

(d) Top-100: predictions/top100_rf_v2.csv (sha256 d8c1228082eb40d4fa1535af6b27b79e24f46ed30d5c9f379d66037911704188); full 100k ranking predictions/library_rf_v2_ranked.csv (sha256 8d9422e2df6d12ffce942465b5ed5cd63f2df65a8ed8cc9db082399937d60139). Top scores span 0.76-0.91. These are model scores on an unlabeled library only; no hit rate/EF is claimed for the library.

(e) Cost: 24 scientific tool jobs, all SUCCEEDED (no GPU; CPU only); summed tool wall time ~239 s (~4.0 min); end-to-end ~6.9 min. Dominant costs: library featurization 13.9 s, library screening 96.4 s (100k molecules), locked evaluation 5.9 s, catboost runs 31.3/33.7 s; all other jobs under 8 s.

(f) Experience: retrieved all 6 records in experience_r.json - dataset_D2_001/model_D2_002, dataset_5HT_003/model_5HT_004, dataset_ADR_005/model_ADR_006. Their applicability is limited to ChEMBL Ki binary sets of ~6811@0.9621, ~4828@0.9803 and ~3376@0.9588 positive rate, scaffold split, explicitly "re-check before applying to much smaller or balanced datasets". This DRD2 set (3293 at 0.6657) is both smaller and far more balanced than every record, so none fits and nothing was reused verbatim or adapted; the retrieval served only as a documented applicability check (no DRD2 prior existed). Limitation: the retrieval interface exposes only applicability plus payload_sha256, not the stored configurations; I did not guess or reverse them.

Other evidence: dataset CSV sha256 928f3de277bf452b71b33e5ac106199a90a92e0bade03d739ad4c29b4604126c; dataset v2 features sha256 5f3b1a7552bfecc63cd2b0bc4b5203e3547a1d8bbf25df5a2f86277d6d8c3be2; model sha256 c339b8662ddbcfc92b09db0be82136d0b8e68b274258bdb2869e5591cdfd845e; metrics runs/rf_v2/metrics.json. All paths are workspace-relative to the ticket workspace /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/chembl-drd2-frozen-f9431dceb9c1. No repository code was changed and no PR was opened; the requested deliverable is this report plus the artifacts.
