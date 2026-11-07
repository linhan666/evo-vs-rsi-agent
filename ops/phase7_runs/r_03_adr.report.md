# R #3 adr

- task: `seq_r_adr`
- ticket: `4a9b986a1b1d8d1829b46e8dcd2555fc`
- state: ready
- wall: 566.1s, jobs 24 (failed 0), models 9
- best validation model (any split): models/seed42_rf AUROC=0.938 AUPRC=0.9965 EF@1%=1.04
- best scaffold model: models/seed42_rf AUROC=0.938 EF@1%=1.04
- refits excluded from ranking: ['models/final_rf_trainval', 'models/final_xgb_trainval']
- top-100 artifacts: 6

## agent report

ADORA1 (adenosine receptor A) Ki predictor — completed. All artifacts are under /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/adenosine-seq-4a9b986a1b1d/.

DATA & SPLIT
- Labels: /home/linhan_cluster/evo_vs_rsi/scientific/.artifacts/chembl/adenosine_receptor_a/ki/dataset.csv — 3,376 molecules, id=molecule_chembl_id, SMILES=canonical_smiles, binary label column; 3,237 positives / 139 negatives (positive rate 0.9589); 0 invalid rows. Ki endpoint only (path ki/, label_source chembl_ki_binary); no Ki/Kd/IC50 mixing or label re-derivation was done in this ticket — the provided binary `label` column was consumed as-is.
- Library: /home/linhan_cluster/evo_vs_rsi/scientific/.artifacts/zinc/library_100k.smi — 100,000 rows, 100,000 featurized, 0 invalid.
- Split: deterministic Bemis–Murcko scaffold split, seed 17, 60/10/30 → train 2,027 / val 337 (324 pos, 13 neg) / test 1,012. Test partition left untouched. A seed-42 repeat produced the identical scaffold partition, so scaffold assignment is deterministic.

EXPERIENCE REUSE
- Retrieved with the exact store path /home/linhan_cluster/evo_vs_rsi/scientific/.artifacts/experience/experience.json (non-empty: 4 records) into retrieval/exp_adenosine.json.
- Experience IDs used: dataset_D2_001, model_D2_002, dataset_5HT_003, model_5HT_004. No ADORA1-specific record exists yet.
- Applicability matched: ChEMBL Ki binary, ~0.96 positive rate, scaffold split. Our 3,376 @ 0.9589 sits inside the stored 4,828 @ 0.9803 and 6,811 @ 0.9621 range (same target class; not a small/balanced set).
- Reused verbatim: the scaffold-split generalisation protocol, binary Ki label handling, high-positive-rate treatment, and the toolchain-standard Morgan radius-2 / 2048-bit + 7 v1-descriptor featurization. Adapted: classifier family re-selected on this target's scaffold validation, then refit on train+val. Limitation: experience.retrieve exposes applicability text + payload_sha256, not the stored hyperparameters, so the stored classifier family could not be copied field-by-field; no feature or hyperparameter search beyond toolchain defaults was run.

(a) CHOICES
- Representation: Morgan radius 2, 2048 bits + 7 RDKit v1 descriptors (MW, logP, HBD, HBA, TPSA, rotatable bonds, rings).
- Validation: scaffold split as the primary generalisation check (random split is optimistic and was not used for selection).
- Models compared on scaffold val: logreg, random forest, XGBoost, CatBoost.

(b) METRICS (scaffold validation, n=337: 324 pos / 13 neg)
| model    | AUROC  | AUPRC  | acc    | F1     | EF@1% | EF@5% |
| logreg   | 0.8882 | 0.9893 | 0.9555 | 0.9765 | 1.04  | 1.04  |
| RF       | 0.9380 | 0.9965 | 0.9792 | 0.9893 | 1.04  | 1.04  |
| XGBoost  | 0.9214 | 0.9955 | 0.9763 | 0.9877 | 1.04  | 1.04  |
| CatBoost | 0.9145 | 0.9948 | 0.9703 | 0.9846 | 1.04  | 1.04  |
Random-split diagnostic (logreg, optimistic): AUROC 0.8694, AUPRC 0.9899.
Caveats: EF@1% and EF@5% saturate at 1/0.9589 ≈ 1.04 because 95.9% of labels are positive (enrichment cannot exceed ~1.04), so EF is not discriminative here; AUPRC is dominated by the base rate. With only 13 negatives, the RF–XGB AUROC gap (0.0166) is within sampling noise.

Shipped model: XGBoost, refit on train+val (2,363 molecules), models/final_xgb_trainval/model.joblib (sha256 2bf486b8…). Rationale: RF had the best val AUROC, but its probabilities saturate — 67/100 of its top-100 are exactly 1.000000 and 31 more are 0.995 (98/100 tied), so the top-100 order is not identifiable. XGBoost's top-100 is fully resolved (all 100 scores distinct, range 0.999901–0.999987) at statistically indistinguishable validation performance, so it is the better ranking deliverable. RF ranking retained at ranking/ for comparison.

(c) TOP-100
- Primary: /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/adenosine-seq-4a9b986a1b1d/ranking_final/top100.csv (rank,id,smiles,score; exactly 100 rows, unique ids; sha256 4fbaa199…).
- Full 100k ranking: ranking_final/lib_ranked.csv (sha256 554c6901…).
- Screening report: ranking_final/lib_report.json — 100,000 read/featurized, 0 invalid, model sha256 2bf486b8…, top score range [0.9999009, 0.9999865].
- Top-5: zinc080052, zinc076343, zinc004260, zinc097814, zinc005626.

(d) COST
- CPU-only on one node: 185.4 s wall / 776.5 s CPU / 0 GPU during the whole ticket (max RSS not reported by the runner).
- Production path (featurize + scaffold split + final XGBoost train + 100k ranking) = 24.8 s wall / 13.9 s CPU.
- The CatBoost comparison alone used 680.3 CPU-s (88% of CPU); logreg/RF/XGB comparisons were each under 10 CPU-s. No paid cloud resources.

(e) EXPERIENCE IDS
dataset_D2_001, model_D2_002, dataset_5HT_003, model_5HT_004. Protocol/a applicability reused verbatim as described above; classifier family adapted on this target; final refit on train+val.

INTEGRITY / LIMITATIONS
- The 100k library is unlabeled: no hit rate, EF or enrichment is claimed for it (the screening report states predictions are model scores only).
- No locked ADR evaluator exists in this installation (evaluation.locked accepts only MOR/KOR/DRD2; ADR was rejected), so expected generalisation is the scaffold-validation estimate, which is noisy (13 val negatives; 139 negatives total). The 1,012-molecule scaffold test partition remains untouched.
- Scores are model probabilities, not calibrated pKi; the 96% positive rate limits discrimination metrics. Untested molecules are not treated as negatives.

No blockers; deliverable complete (model, full ranking, top-100, metrics, cost, experience accounting).
