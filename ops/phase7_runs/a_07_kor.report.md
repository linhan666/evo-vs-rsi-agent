# A #7 kor

- task: `seq_a_kor`
- ticket: `053e7e0a5b494a8cb61425c4e53cfc2e`
- state: ready
- wall: 266.6s, jobs 24 (failed 1), models 13
- best validation model (any split): models/xgb_r2_randomsplit AUROC=0.9583 AUPRC=0.9879 EF@1%=1.284
- best scaffold model: models/xgb_r2_s4 AUROC=0.9456 EF@1%=1.235
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

KOR (OPRK1) Ki predictor + 100k library ranking are complete and validated; no code change/PR (analysis deliverable). All artifacts are under the ticket workspace /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/kor-arm-a7-053e7e0a5b49.

DATA. 1,899 ChEMBL OPRK1 molecules with a provided binary Ki-derived label column "label" (1,500 positives = 79.0%); 1,899/1,899 SMILES parsed. Labels used as provided: no invented negatives, no endpoint mixing. The tools expose only the binarized label, so the exact Ki cut-off and censoring handling are not visible (upstream).

(a) CHOICES. Representation: Morgan r=2, 2048 bit + 7 RDKit 2D descriptors (desc_set v1). Tried r=3/2048 (val AUPRC 0.9840) and r=2 + desc_set v2 (0.9766) — both below v1. Models on identical features/split: logreg, RF, XGBoost, CatBoost. Validation: Bemis-Murcko scaffold split, seed 17 (train 1,141 / val 189 / held-out test 569), plus a random-split diagnostic; model selection used only the scaffold validation. Split seeds 17/42/123 produced identical validation assignments and metrics, so the scaffold partition is effectively seed-invariant here. XGB seed check (4 seeds): AUPRC 0.9794-0.9863, AUROC 0.9193-0.9456.

(b) METRICS. Scaffold validation (n=189, 153 positives; AUPRC baseline 0.806), AUPRC / AUROC: logreg 0.9606/0.8539; RF 0.9745/0.9039; CatBoost 0.9695/0.8928; XGBoost 0.9859/0.9431 (chosen); EF@1% 1.235. Random-split diagnostic (XGB): AUPRC 0.9879, AUROC 0.9583 — the usual optimism gap vs scaffold. Locked protected test (one-shot, receipt receipts/kor_ki_xgb_r2.json): AUROC 0.910, AUPRC 0.9583, EF@1% 1.459. EF caveat: validation top-1% is ~2 molecules and the tool reports EF@5% identical to EF@1%, so only EF@1% should be read as evaluated; the locked-test EF@1% is the meaningful one.

(c) TOP-100 PATH. Top-100: screen/top100_xgb_r2.csv (columns rank,id,smiles,score; ranks 1-100, scores 0.9711-0.9973). Full 100k ranking: screen/ranked_xgb_r2.csv. Screening report: screen/report_xgb_r2.json (100,000/100,000 featurized, 0 invalid, 17.7 s). Fitted model: models/xgb_r2/model.joblib. Model scores only; no hit rate, enrichment or EF on the unlabeled library is defined or claimed. Chemistry sanity: top hits are drug-like amides/sulfonamides/basic amines consistent with opioid-receptor ligands, but the top-100 has close analog redundancy (e.g., zinc058578/zinc007074 are stereoisomers with identical score), so real chemotype diversity is <100.

(d) COST. 24 tool invocations, 108 s wall total, 657 CPU-seconds (~11 CPU-min), no GPU. CatBoost alone used 594 CPU-s; excluding it the whole pipeline is ~63 CPU-s (~1 min), and screening 100k molecules costs 17.7 s wall / 7.4 CPU-s. Locked evaluation 3.5 s.

(e) REUSE FOR ANOTHER TARGET. Recipe: inspect n, positive rate and scaffold diversity first; choose scaffold split as the primary generalisation check and always report the base-rate-aware AUPRC; Morgan r=2/2048 + 2D descriptors with XGBoost is a strong cheap default; run seed and split stability checks; keep EF@1% claims only when the top-1% bucket contains enough molecules; use the one-shot locked test for the final number; escalate to pKi regression only when the relationship symbols (<, >) are preserved.

LIMITATIONS. Label threshold upstream and not inspectable; no applicability-domain/Tanimoto check against training chemotypes was possible with the available tools; library was scored as provided (no dedup).
