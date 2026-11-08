# R #2 5ht

- task: `p7b_r_5ht`
- ticket: `e3be5f2c4f30700c882db3776d6cef3d`
- state: ready
- wall: 536.1s, jobs 23 (failed 6), models 7
- best validation model (any split): experiments/rf_v2 AUROC=0.999 AUPRC=1.0 EF@1%=1.025
- best scaffold model: experiments/rf_v2 AUROC=0.999 EF@1%=1.025
- refits excluded from ranking: []
- top-100 artifacts: 3

## agent report

# P7b 5-HT (target 2) — final report

All work is done. No code/repo changes were made; all artifacts are in the ticket workspace `/home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/ht-frozen-r-e3be5f2c4f30`. No PR applies (deliverable is a scientific report/artifacts, not a code change).

## (a) Choices and rationale
- Labels: ChEMBL 5-HT **Ki** binary labels, `dataset_p7b.csv` (read-only) — `molecule_chembl_id`, `canonical_smiles`, `label`. 4104 valid molecules, 4015 positives (0.9783). Only Ki used; no Ki/IC50 mixing.
- Split: passed `frozen_5-hydroxytryptamine_.json` **verbatim** as `--split-manifest` to `ml.train`; `data.split` was never called and no fractions chosen. Manifest: train 3509 / validation 410 (400 validation positives). Of 4104 joined molecules, 3509+410 are used; the remaining 185 are outside the train/validation sections of the frozen manifest and were neither fitted nor scored.
- Representation: Morgan FP radius 2, 2048 bits + 7 RDKit 2D descriptors, **desc_set v1** (`features/5ht_all_v1.npz`, sha256 e5e9548d…, 4104 rows, 0 invalid). v2 was tested (identical descriptor names) and gave no validation advantage.
- Model: **RandomForest (`rf`), seed 17** (`experiments/rf_v1/model.joblib`, sha256 bb831039…). Frozen-split comparison of the supported families (same features/manifest): rf 0.9990 AUROC, catboost 0.9953, xgboost 0.9918, logreg 0.9693. Seed-23 replication of rf: 0.9986 AUROC.
- No fusion: `evaluation.locked` accepts one fitted pipeline, and validation AUPRC is saturated (both models ≈1.0), so no principled fusion weight could be justified. Fusion was therefore not used.

## (b) Frozen-split validation (410 molecules, 400 positives)
`experiments/rf_v1/metrics.json`: **AUROC 0.9990, AUPRC 1.0000, accuracy 0.9927, F1 0.9963, EF@1% 1.025, EF@5% 1.025**.
- Seed-23 rf: AUROC 0.9986, AUPRC 1.0000. rf on v2: AUROC 0.9990, AUPRC 1.0000.
- Caveat: AUPRC baseline is 0.9756 and EF@1% ceiling ≈1.025 at a 97.6% positive rate, so AUPRC/EF are not discriminative on this validation set; AUROC is the informative frozen-split metric.

## (c) Locked test (the number that counts)
`evaluation.locked` was called **exactly once**: target 5HT, endpoint Ki, desc_set v1, model `experiments/rf_v1/model.joblib`; receipt `evaluation/5ht_locked.json` (sha256 4fe940f3…). Verbatim from the receipt:
- **"auroc": 0.9665**, "auprc": 0.9997, "ef_at_1pct": 1.008, "ef_at_5pct": 1.008.
- Raw locked metrics stay protected at `protected/chembl37_ki_5ht/metrics_test_locked_agent_Ki_v1_._5HT.json` (not readable from the ticket).
- The locked AUROC (0.9665) is the reported headline; the frozen-split 0.9990 is optimistic for the locked set, as expected.

## (d) Top-100
- Deliverable top-100: **`screening/top100_rf_v1.csv`** (sha256 2fb5a8c0…, 100 rows, `rank,id,smiles,score`, rf_v1 scores).
- Full 100k ranking: `screening/library_100k_rf_v1_ranked.csv` (100000/100000 featurized, 0 invalid); report `screening/report_rf_v1.json` (library sha256 09446ea1…, model sha256 bb831039…).
- Limitation: all top-100 scores are exactly 1.000000 (`top_score_range: [1.0, 1.0]`), because RF probabilities saturate on the library. The top-100 **set** is the model's tied maximal block; the order inside it is arbitrary (library order), not a resolved ranking. If a graded order matters, `screening/top100_cat_v1.csv` (CatBoost, scores 0.99921–0.99977, frozen-split AUROC 0.9953) is provided as a tie-broken alternative.
- No hit rate, enrichment or EF is claimed for the unlabeled 100k library; predictions only.

## (e) Cost
- 23 scientific tool jobs submitted: 16 result-producing (3 `experience.retrieve`, 2 `rdkit.featurize`, 7 `ml.train`, 3 `screening.rank`, 1 `evaluation.locked`) + 7 read-only probes (6 failed harmlessly while recovering the experience payload/formats, 1 empty retrieval).
- Tool wall time ≈138 s summed across jobs (max single job 29.9 s, CatBoost); session wall clock ≈8 min including reasoning. CPU only; no GPU, no /tmp, no background jobs left running.

## (f) Experience used
- Retrieved from `experience_r.json`: **dataset_D2_001** and **model_D2_002** (target D2, GPCR, ChEMBL Ki binary, 6811 molecules / 6553 positives / 0.9621 positive rate, scaffold split). The 5HT profile (4104, 0.9783, same endpoint and target class) falls inside that applicability note ("re-check before applying to much smaller or balanced datasets" — this is neither).
- From model_D2_002 `best_configuration` (payload_sha256 52ea51f6…): **reused verbatim** model=`rf`, radius=2, n_bits=2048, desc_set=`v1`, split_strategy=`scaffold-manifest`. **Adapted**: seed 17 (tool default) instead of recorded 23, after verifying seed 23 gives 0.9986 vs 0.9990 frozen-split AUROC (immaterial); the 5HT label file and frozen manifest are necessarily 5HT-specific. D2's recorded metrics (0.9801 AUROC / 0.9983 AUPRC / 1.064 EF@1%) are context only.

## Compliance notes
One GPU rule irrelevant (CPU jobs); no data written outside the project; no data/model/log commits; no split re-definition; no unlabeled-library enrichment claim; locked evaluation used once.

