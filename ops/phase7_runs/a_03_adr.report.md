# A #3 adr

- task: `seq_a_adr`
- ticket: `90b802f1c51bffc8d2a92d86a583d72f`
- state: ready
- wall: 1096.2s, jobs 86 (failed 11), models 50
- best validation model (any split): work_adr/rf_v2 AUROC=0.9506 AUPRC=0.9975 EF@1%=1.04
- best scaffold model: work_adr/rf_v2 AUROC=0.9506 EF@1%=1.04
- refits excluded from ranking: []
- top-100 artifacts: 4

## agent report

ADORA1 (adenosine receptor A, ChEMBL Ki) predictor + 100k-library ranking complete. No experience store / cross-target memory used; all choices derived from this dataset.

Deliverables (paths relative to the ticket workspace; absolute root /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/adenosine-arm-a3-90b802f1c51b):
- TOP-100: `work_adr/top100_final.csv` (100 rows: rank,id,smiles,score; all 100 SMILES valid)
- Full 100k ranking: `work_adr/ranking_final.csv`
- Screening report: `work_adr/screen_final.json`
- Delivered model: `work_adr/xgb_4096_v1_deploy/model.joblib`
- Selection metrics: `work_adr/xgb_4096_v1_{val30,val30_s23,val30_s42,val30_s101,default,random}/metrics.json`

(a) CHOICES
- Data: 3,376 ChEMBL Ki records; 3,237 positives / 139 negatives (95.9% positive); all 3,376 SMILES valid. Used the supplied binary `label` unchanged; Ki endpoint only; no negatives invented. Raw Ki/relation columns are not exposed by this tool API, so the binarisation threshold/censoring could not be re-derived (limitation).
- Prevalence (~96%) makes this a weak-binder-deprioritisation / ranking task: AUPRC baseline is ~0.97 and EF@1% is structurally ~1, so AUROC carries the signal.
- Features: Morgan FP radius 2, 4096 bits + 7 RDKit descriptors (desc_set v1). This is exactly what the screening tool's library featuriser reproduces.
- Model: XGBoost. It beat logistic regression (AUROC 0.688), CatBoost (0.730) and r3 fingerprints (0.716) on the hard scaffold holdout; RF was close on AUROC (0.772) but lower AUPRC (0.985 vs 0.990).
- Validation: Bemis-Murcko scaffold, 30% validation (1,012 molecules; 982 pos / 30 neg) over three seeds (17/23/42) plus a fresh seed 101. A 10% scaffold val slice (13 negatives) is over-optimistic: the identical model (same train, same sha256) gives AUROC 0.911 on the 10% slice vs 0.755 on the 30% slice.
- Deploy: retrained on 90% (3,040 train; 5% val / 5% held out) and screened the library.
- Fusion rejected: ml.fuse produced no validated fused metric and the weaker component was consistently worse.

(b) METRICS (scaffold validation unless stated)
- XGB r2/4096/v1, 30% val, 3 seeds: AUROC 0.770 ± 0.014; AUPRC 0.990 ± 0.001; EF@1% 1.031.
- Fresh seed 101 (never used for selection): AUROC 0.751; AUPRC 0.988; EF@1% 1.031.
- Random split (optimistic): AUROC 0.905; AUPRC 0.990; EF@1% 1.073.
- 10% scaffold slice vs 30% slice, identical model: 0.911/0.994/1.040 vs 0.755/0.988/1.031.
- Deploy model's own 5% val (168 molecules, 3 negatives): 0.705/0.992/1.018 — too few negatives to interpret; not used as the estimate.
- Ablations (30% val): XGB r2/2048/v1 0.767/0.989; RF r2/4096/v1 0.772/0.985; RF r2/2048/v1 0.747/0.985.
- v2 descriptor block (rejected for deployment): XGB r2/2048/v2 0.810 ± 0.022; r2/4096/v2 0.809 ± 0.010; r2/1024/v2 0.807.
Interpretation: the honest scaffold-generalisation estimate is AUROC ~0.75-0.77. AUPRC/EF@1% are near their trivial maxima (97% prevalence in this val slice; 1% ≈ 10 molecules, all/nearly all positive) and are not evidence of top-1% enrichment.

(c) TOP-100
`work_adr/top100_final.csv` — ranks 1-100, ids zinc021605 (rank 1), zinc068728, zinc080052, zinc076343, zinc024735, ... Ranked by the delivered XGBoost r2/4096/v1 model trained on 90% of the Ki data. Library: 100,000/100,000 SMILES featurised, 0 invalid, scored as provided (no dedup — tool policy). No hit rate or enrichment is claimed for the unlabelled library. Scores are saturated (0.999878-0.999988), so the top-100 order within the shortlist is fragile. Chemical sanity: top ranks are dominated by xanthine-dione and aminopyrimidine/adenine-like scaffolds, consistent with known A1 chemotypes.

(d) COST
~17.5 min wall clock; ~6.5 min aggregate job wall time (jobs ran in parallel); ~29 CPU-min, of which two CatBoost trials alone used ~24 CPU-min; 0 GPU; 0 external API calls; ~90 MB artifacts (two 7.2 MB full rankings; RF/XGB model files dominate).

(e) WHAT I WOULD REUSE ON ANOTHER TARGET OF THIS KIND
- Start with the label prevalence. If positives are >90%, treat it as a potency-ranking problem, report AUROC, and do not present AUPRC/EF@1% as enrichment.
- Featuriser must match the screening featuriser exactly. Here that is Morgan r2/4096 + 7 descriptors; the richer descriptor block (v2) is materially better (+0.04 AUROC) but screening.rank has no desc_set parameter and cannot score v2 models, so it was unusable. Extending the screener to accept desc_set is the first upgrade I would make.
- Validate on Bemis-Murcko scaffold splits with a large validation slice (≥30%, ≥3 seeds); a 10% val slice with ~13 negatives misleads by ~0.16 AUROC.
- XGBoost is a good default; RF is an equally good, more stable fallback (AUROC 0.772 ± 0.009); logistic regression is not competitive here (0.688).
- Retrain on ~90% after selection, then screen; keep the selection-phase metrics as the honest estimate.

LIMITATIONS
- No locked external test exists for ADORA1 in this arm (evaluation.locked covers MOR/KOR/DRD2); the 30%/10% scaffold slices served as validation, so no fully untouched test metric is available.
- The supplied binary label was used as given; the raw Ki values/relation symbols were not accessible through the tool API, so threshold and censoring handling could not be audited.
- 96% label prevalence and saturated probabilities limit the usefulness of AUPRC/EF@1% and of fine ordering inside the top-100.
- The library was scored as provided; duplicates were not removed.
- No PR: this ticket's deliverable is the scientific report/model/ranking, not a repository code change.
