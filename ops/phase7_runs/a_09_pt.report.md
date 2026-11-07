# A #9 pt

- task: `seq_a_pt`
- ticket: `e80a4cc5b7a02919ede84c3e10fee2a4`
- state: ready
- wall: 1103.0s, jobs 71 (failed 0), models 46
- best validation model (any split): runs/v25_rf AUROC=0.9576 AUPRC=0.9856 EF@1%=1.047
- best scaffold model: runs/v25_rf AUROC=0.9576 EF@1%=1.047
- refits excluded from ranking: ['runs/final_cat11_t95', 'runs/final_rf11', 'runs/final_rf11_t95']
- top-100 artifacts: 5

## agent report

COMPLETED — Prothrombin (F2) Ki predictor + top-100 of the 100k library. Deliverable is analysis artifacts in the ticket workspace (no code PR; pr_number null).

HEADLINE
- Model: Random Forest on Morgan r=2/2048 bits + 7 RDKit descriptors (desc_set v1), fitted via ml.train.
- Generalisation (5 Bemis–Murcko scaffold partitions, val 564–988): AUROC 0.948 ± 0.006, AUPRC 0.986 ± 0.001, EF@1% 1.05–1.21.
- Label prevalence is 80.7% positive (2,279/2,824), so the AUPRC no-skill baseline is 0.807 and the EF@1% ceiling is ≈1.24; AUROC is the discriminating metric, EF@1% cannot separate models here.
- Final predictor refit on 2,682/2,824 labels (95%); all 100,000 ZINC molecules scored, 0 invalid, in 20.4 s.
- Top-100 file: screen/primary_top100.csv (columns rank,id,smiles,score; 100 rows). Full ranking: screen/primary_ranked.csv. Model: runs/final_rf11_t95/model.joblib (sha256 31ba1009…). Workspace-absolute prefix: /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/prothrombin-arm-a9-e80a4cc5b7a0/

(a) CHOICES
- Data: 2,824 rows, binary `label` used as provided (1=active); no unmeasured pairs were turned into negatives. Continuous Ki/units/relations were not re-derived (arm exposes only the prepared binary label; documented limitation).
- Representation: compared r2/2048+desc-v1 vs r3/4096+desc-v1 vs r2/2048+desc-v2; differences ≤0.005 AUROC (within noise); kept r2/2048+v1.
- Models: logreg / RF / XGBoost / CatBoost (ml.train defaults, seed varied).
- Validation: scaffold split. IMPORTANT: data.split's scaffold partition is seed-inert (seeds 7,101–105 gave byte-identical deterministic logreg models), so repeats were built by varying train/val/test fractions, plus 5 model-seed replicates on one partition. Random split reported only as optimism diagnostic (logreg 0.947 random vs 0.856 scaffold).
- RF beat CatBoost on AUROC in all 5 partitions (0.9478 vs 0.9405); XGBoost 0.9380; logreg 0.856. RF chosen.
- Rank-average RF+CatBoost fusion produced as secondary consensus (screen/fused_ranked.csv, ids only); not primary because fused-score metrics cannot be computed in this arm and its output lacks SMILES.

(b) METRICS (RF, scaffold)
v25 (train 1977/val 706): AUROC .9576 AUPRC .9856 EF1 1.047
v30 (1836/847, 5 seeds): .9478±.0026 / .9854 / 1.212
v35 (1695/988): .9408 / .9863 / 1.192
t15 (1554/847): .9473 / .9882 / 1.165
t25v2 (1554/564): .9457 / .9863 / 1.175
Mean .9478±.0061 / .9864±.0011. CatBoost mean .9405±.0105/.9853; XGB .9380/.9835; logreg .8564/.9488.

(c) TOP-100 PATH + screening: screen/primary_top100.csv; screen/primary_report.json (100,000 rows read/featurized, 0 invalid, library sha256 09446ea1…, top_score_range 0.88–0.94). No hit-rate/enrichment claim for the unlabeled library. No locked evaluator exists for prothrombin (evaluation.locked supports MOR/KOR/DRD2 only), so the 5% scaffold test partitions were reserved but unscored.

(d) COST: 70 scientific tool jobs; ≈620 s wall (≈10 min); ≈9,860 CPU-s (≈2.7 CPU-h), 98% in 13 CatBoost fits; 0 GPU. 2,824 labelled + 100,000 library molecules.

(e) REUSABLE: featurize r2/2048+v1 → ≥4 distinct scaffold partitions (vary fractions, not seed) → RF first, CatBoost second → AUROC primary when prevalence >50%, AUPRC vs prevalence, EF@1% only at low prevalence → refit on 95% → screening.rank to score/deliver top-K. Fully target-agnostic; only the label file changes.

LIMITATIONS: labels taken as provided (no re-derivation of Ki censoring); no locked test for prothrombin; partition set is nested so its ± is a lower bound; fused ranking unvalidated and id-only; library scored as provided (no dedup by this arm).
