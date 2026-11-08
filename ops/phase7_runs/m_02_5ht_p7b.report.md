# M #2 5ht

- task: `p7b_m_5ht`
- ticket: `ccd60a43be74e3683ebcb4f100350606`
- state: ready
- wall: 278.0s, jobs 15 (failed 1), models 8
- best validation model (any split): models/rf_v1_s7 AUROC=0.9992 AUPRC=1.0 EF@1%=1.025
- best scaffold model: models/rf_v1_s7 AUROC=0.9992 EF@1%=1.025
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

P7b 5-HT (Ki) arm M complete. Frozen split used end-to-end; no data.split call; exactly one locked evaluation.

## Deliverables (ticket workspace relative)
- Ranked library: screening/5ht_ranked.csv (100,000 rows)
- Top-100: screening/5ht_top100.csv
- Screening report: screening/5ht_rank_report.json (100000 read, 100000 featurized, 0 invalid; sha256 ffde27d8…)
- Chosen model: models/rf_v1/model.joblib (RF, seed 17, desc_set v1; model sha256 bb831039…), metrics: models/rf_v1/metrics.json
- Locked receipt: evaluation/5ht_locked.json (sha256 4fe940f3…, size 413)

## Choices and why
- Split: passed the frozen manifest /home/linhan_cluster/evo_vs_rsi/scientific/.artifacts/chembl/5-hydroxytryptamine_/ki/splits/frozen_5-hydroxytryptamine_.json to ml.train --split-manifest. Train 3509 / validation 410 / protected test 185 (4104 joined).
- Features: desc_set v1 = Morgan r=2, 2048 bits + 7 2D descriptors (MW, logP, HBD, HBA, TPSA, rotB, rings). Featurization on the labels CSV resolved id→molecule_chembl_id, smiles→canonical_smiles; 4104/4104 valid.
- Model sweep on validation only (AUROC / AUPRC / EF@1%):
  * logreg v1: 0.9693 / 0.9991 / 1.025
  * xgboost v1 seed17: 0.9918 / 0.9998 / 1.025; seed7: 0.9900 / 0.9997 / 1.025
  * catboost v1: 0.9953 / 0.9999 / 1.025
  * rf v1 seed17: 0.9990 / 1.0000 / 1.025; seed7: 0.9992 / 1.0000 / 1.025
  * rf v2: 0.9990 / 1.0000 / 1.025; xgboost v2: 0.9938 / 0.9998
  Chose RF v1 seed17: best and stable validation AUROC/AUPRC across two seeds and both descriptor sets; v1 preferred over v2 for the simpler, smaller feature block with identical RF performance.
- Locked evaluation run once on the chosen model: target 5HT, endpoint Ki, desc_set v1, receipt evaluation/5ht_locked.json.

## Metrics
- Validation (RF v1 seed17; 410 val mols, 400 positives): AUROC 0.9990, AUPRC 1.0000, EF@1% 1.025, EF@5% 1.025, accuracy 0.9927, F1 0.9963.
- Locked test (quoted from receipt): AUROC 0.9665, AUPRC 0.9997, EF@1% 1.008, EF@5% 1.008.

## Cost
- 15 scientific jobs total (14 SUCCEEDED, 1 FAILED: logreg on v2 exited 1, no artifacts, unused/not needed). ml.train + screening + evaluation all CPU.
- Wall clock: first job 17:44:33Z → last job 17:48:07Z = 214 s (3 m 34 s); sum of individual job wall times ≈ 134 s. Ticket-level elapsed ≈ 4 min including setup.

## Experience reused
- Consulted store experience_m.json via experience.retrieve; 2 records returned: dataset_D2_001 and model_D2_002 (both D2). Their applicability note (ChEMBL Ki binary, ~6811 mols, 0.9621 positive, scaffold split; re-check before applying to much smaller/balanced sets) was re-checked against 5-HT: 4104 mols, overall positive rate 4015/4104 = 0.9783, scaffold split — same regime, smaller N, so used only as a weak prior favouring tree-ensemble recipes; the model choice was then settled empirically on validation, not taken from the store. Payloads are not exposed by experience.retrieve (only applicability + payload sha), so no record payload was copied.

## Material limitations (reported honestly)
1. Class imbalance: 97.8% positives makes AUPRC≈1 and EF@1%/5% ceiling-capped at ~1.025 on validation (only ~4 molecules in top 1%); those validation enrichment numbers are not informative. Locked EF@1% 1.008 reflects the same near-ceiling base rate.
2. Validation 0.999 vs locked 0.9665 gap: validation has only 410 mols / 10 negatives, so it was optimistic; the locked AUROC is the unbiased estimate of record.
3. RF tie saturation: RF probabilities come from a 100-tree vote fraction, and every molecule in the top-100 scores exactly 1.000000. The top-100 set is therefore a high-confidence set whose internal order is a deterministic tie-break, not a meaningful 1→100 ranking. The full ranked CSV is still best-first by score, but in-tie ordering should not be over-interpreted. This is a genuine limitation of using this RF for screening; the alternative (xgboost) had slightly lower validation AUROC and could not be substituted for the already-consumed locked evaluation.
4. No true EF@1% or hit rate is defined or claimed for the unlabeled 100k library (100k labels do not exist).

## Repo hygiene
- No repository code changes were made (scientific-tool artifacts only), so no PR is opened; the request is a scientific deliverable, not a code change. Labels kept strictly Ki (no Ki/Kd/IC50/EC50 mixing); measured-activity label_source recorded as chembl_ki_5ht_p7b.
