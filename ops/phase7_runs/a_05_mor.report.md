# A #5 mor

- task: `seq_a_mor`
- ticket: `afc7d7769fdfd99a343116ba3d664ea6`
- state: ready
- wall: 236.4s, jobs 14 (failed 0), models 8
- best validation model (any split): artifacts/train_rf AUROC=0.9089 AUPRC=0.9751 EF@1%=1.229
- best scaffold model: artifacts/train_rf AUROC=0.9089 EF@1%=1.229
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

MOR/OPRM1 Ki predictor complete: model selected on scaffold validation, one-shot locked test evaluated, 100k library ranked, top-100 written. No experience store used; all choices derived from the local data. No PR: the assignment's deliverable is the analysis + artifacts below, not a code change.

DATA (read-only, as shipped)
- Labels: ChEMBL OPRM1 Ki dataset, 2,790 molecules, 2,790 valid SMILES (0 invalid), 2,219 positives (79.5%). The binary `label` column was used exactly as shipped; I did not re-threshold or mix Ki with any other endpoint. No shell was available in this session, so the exact Ki cutoff/censoring rule encoded in that label was not re-derived by me.
- Scaffold split (Bemis-Murcko, seed 17, 60/10/30): train 1,674 / val 279 / test 837. Same scaffold never crosses splits; val used only for model selection; test only via the locked evaluator.

(a) CHOICES + RATIONALE
- Representation: Morgan fingerprint radius 2, 2048 bits, + 7 RDKit 2D descriptors (v1). Compact, fast, standard for ligand-based screening; descriptors add global physicochemical context.
- Model: RandomForest (sklearn RF, seed 17). Compared 4 families and 3 representations on the scaffold-val split:
  logreg 0.8911/0.9615; RF 0.9089/0.9751; XGBoost 0.9016/0.9746; CatBoost 0.8821/0.9683 (AUROC/AUPRC).
  RF on radius-3/2048: 0.8830/0.9603; RF with v2 descriptors: 0.8789/0.9680; logreg radius-3: 0.8729/0.9610; XGBoost v2: 0.8947/0.9739.
  RF on radius-2/2048+v1 won on both AUROC and AUPRC. Differences RF vs XGBoost are within noise on a 279-molecule val set, so the simpler/most stable model was kept. No fusion: the screening tool consumes one fitted pipeline, and RF/XGB validation AUPRCs differ by 0.0005, so a fused score could not be justified or applied to the library through this toolchain.

(b) METRICS (AUROC / AUPRC / EF@1% / EF@5%)
- Scaffold validation (279 mol, 227 pos = 81.4%; EF ceiling = 1/0.8136 = 1.229): 0.9089 / 0.9751 / 1.229 / 1.229.
- Locked held-out test (837 mol, evaluated once): AUROC 0.9386, AUPRC 0.9740, EF@1% 1.379, EF@5% 1.379.
- Honest reading: AUPRC baselines are the prevalences (0.814 val, ~0.725 test); the model adds +0.162 / +0.249 AUPRC over random. EF@1% is at its attainable ceiling on both splits (1.379 = 1/0.725), i.e. every molecule in the top 1% (and top 5%) was a positive, so EF is saturated and cannot discriminate further; AUROC/AUPRC carry the signal. EF is reported, not claimed as a large enrichment.
- Locked receipt: artifacts/locked_eval_receipt_mor.json (protected raw output not readable: .../protected/chembl37_ki/metrics_test_locked_agent_Ki_v1_._MOR.json).

(c) TOP-100 PATHS (workspace /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/mor-arm-a5-afc7d7769fdf)
- Top-100: artifacts/library_top100_rf.csv (rank,id,smiles,score; 100 rows).
- Full 100k ranking: artifacts/library_ranked_rf.csv.
- Top score 0.9025 (zinc093549), rank-100 score 0.8200. Library: 100,000/100,000 SMILES valid and scored; no invalid molecules. Unlabeled library => no hit-rate/EF claim is made; scores are model probabilities only.
- Fitted model: artifacts/train_rf/model.joblib (sha256 3a71785d...); top-100 sha256 15bdde55...; full ranking sha256 a7860301...

(d) COST
- 14 CPU jobs, no GPU: 88.1 s wall total, 765.2 s CPU total (12.75 CPU-min). Dominated by CatBoost (722.7 CPU-s for the worst AUPRC); RF training 3.8 s wall/3.5 CPU-s, 100k screening 20.3 s, locked eval 2.9 s. Artifacts: model 6.7 MB, full ranking 7.2 MB, top-100 7.5 KB. A repeat of the selected pipeline (featurize + split + RF + screen + locked test) is ~30 s wall on this host.

(e) REUSE FOR ANOTHER TARGET OF THIS KIND
- Reuse the protocol, not assumptions: (1) profile size/prevalence first — at 79.5% positive, AUPRC's floor is 0.795 and EF@1% is capped near 1.23, so select by AUPRC/AUROC and always state prevalence; (2) scaffold split for an honest generalisation read, random split only as a diagnostic; (3) Morgan r2/2048 + 7 v1 descriptors and RF as the cheap strong baseline; (4) sweep logreg/RF/XGBoost on that representation, skip CatBoost unless it wins (it cost 95% of the CPU here for the worst AUPRC); (5) finer radius or v2 descriptor sets did not help — test, don't assume; (6) lock the final test and evaluate the exact artifact that also screens the library.

LIMITATIONS
- No shell in this session: dataset schema was resolved by the featurizer (id=molecule_chembl_id, smiles=canonical_smiles); label threshold/censoring details could not be independently inspected. The model therefore predicts the shipped binary label, not a Ki value.
- Top-1% enrichment is saturated; no per-molecule locked-test errors are accessible, so no finer error analysis.
- Library was scored as provided (tool notes deduplication is the caller's step); no applicability-domain/novelty analysis was possible with the available tools. These do not affect the delivered ranking's validity as a model-score ranking.
