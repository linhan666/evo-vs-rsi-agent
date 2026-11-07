# A #4 drd2

- task: `seq_a_drd2`
- ticket: `89e6ce69b3e6462be15d18a51a35e146`
- state: ready
- wall: 648.1s, jobs 32 (failed 0), models 18
- best validation model (any split): drd2/m_r2_xgb_s23 AUROC=0.9452 AUPRC=0.9686 EF@1%=1.645
- best scaffold model: drd2/m_r2_xgb_s23 AUROC=0.9452 EF@1%=1.645
- refits excluded from ranking: ['drd2/final_cat_r2_2048']
- top-100 artifacts: 2

## agent report

DRD2 Ki virtual screening — COMPLETE (scientific deliverable: model, metrics, 100k ranking, top-100, locked-test receipt; no repo code change, no PR).

ENVIRONMENT / DATA
- Work done through the scientific tool layer only (rdkit.featurize, data.split, ml.train, ml.fuse, screening.rank, evaluation.locked). 32 tool invocations; all CPU, zero GPU.
- Labels (read-only): scientific/.artifacts/chembl/drd2/ki/dataset.csv — 3,293 molecules, 0 invalid SMILES, columns molecule_chembl_id/canonical_smiles; provided binary Ki label column, 2,192 positives (66.6%). Endpoint kept pure: Ki only, no IC50/Kd mixing, no re-thresholding, no negatives invented.
- Library: scientific/.artifacts/zinc/library_100k.smi — 100,000 rows, 100,000 featurized, 0 invalid (library scored as provided, not deduplicated).

(a) CHOICES AND RATIONALE
- Representation: Morgan fingerprint radius 2, 2,048 bits + 7 RDKit 2D descriptors (MW, logP, HBD, HBA, TPSA, rotatable bonds, rings). Alternatives tested at seed 17: radius 3 (CatBoost AUROC/AUPRC 0.9417/0.9658), 4,096 bits (0.9421/0.9671 — byte-identical predictions to 2,048-bit CatBoost, i.e. no added signal), descriptor set v2 (0.9363/0.9584). 2,048-bit r2 + v1 descriptors kept: best or tied, smallest/fastest.
- Model: CatBoost on the hashed fingerprint + descriptors. Reasons: highest and most stable scaffold-validation AUPRC/AUROC; handles sparse high-dimensional hashed features without manual hyperparameter tuning; small model file (0.48 MB). XGBoost was within ~0.001 AUPRC and ~0.001 AUROC; LogisticRegression (0.9519 AUPRC) and RandomForest (0.9485) were clearly behind.
- Validation: Bemis–Murcko scaffold split, 60/10/30 (seed 17: 1,977 train / 329 val / 987 test), repeated at seeds 23 and 2050 to avoid selecting on one 329-molecule fold; random split as an optimistic diagnostic only. Selection was by scaffold-validation AUPRC (primary) and AUROC. EF@1%/EF@5% were not useful for selection on 329 molecules: every model put all top-3 and top-16 molecules in the positive class, so EF saturated at 1.645 for all candidates.
- Final refit: same CatBoost, same features, trained on 3,128/3,293 molecules (95%; 164 held out only to satisfy the split interface) for library screening and the locked evaluation. The reported validation numbers below are from the honest 1,977-train selection model; the locked numbers are from the refit model, which is the deployment model and never saw the locked test.
- Fusion: CatBoost+XGBoost mean fusion was run on the 329 shared validation molecules (weights from validation AUPRC, 0.50/0.50). Not used for the final ranking: the two models differ by ~0.0008 AUPRC (well inside fold noise), ml.fuse returns only fused scores (no metrics, no fitted model), and top-K export requires a fitted model. Single CatBoost therefore produces the deliverable ranking.

(b) METRICS (scaffold validation unless noted; 329 molecules, 200 positives; random-split and locked-test prevalences differ, so AUPRC is not directly comparable across rows)
Model comparison, seed-17 scaffold split (AUROC / AUPRC / EF@1%):
- LogisticRegression: 0.9217 / 0.9519 / 1.645
- RandomForest: 0.9273 / 0.9485 / 1.645
- XGBoost: 0.9367 / 0.9639 / 1.645
- CatBoost: 0.9421 / 0.9671 / 1.645
Multi-seed scaffold stability (mean ± sample sd over seeds 17/23/2050):
- CatBoost: AUROC 0.9429 ± 0.0010, AUPRC 0.9674 ± 0.0005; EF@1% 1.645 (saturated).
- XGBoost: AUROC 0.9420 ± 0.0046, AUPRC 0.9666 ± 0.0024.
Random-split diagnostic (CatBoost): AUROC 0.9366, AUPRC 0.9653, EF@1% 1.542 — no better than scaffold, so the scaffold split did not reveal a large hidden generalization gap for this target.
LOCKED FINAL TEST (fixed protected DRD2/Ki set, one-shot, summary receipt): AUROC 0.9206, AUPRC 0.9394, EF@1% 1.824, EF@5% 1.824. This is the independent generalization estimate; the drop from scaffold-val AUROC 0.943 to 0.921 is the realistic penalty for unseen chemistry. EF@1% and EF@5% are both 1.824 (top-k buckets pure; val EF saturated at 1.645 for the same reason). AUPRC is prevalence-dependent; the locked prevalence is not exposed, so AUROC is the safer headline.

(c) TOP-100
- Top-100 file (workspace-relative, as emitted by screening.rank): drd2/top100_drd2_v2.csv — 100 rows, columns rank,id,smiles,score, sha256 67bea2070f81fbc3a8ca3bead7f451b430c50b17e9f28eeb6071ae3b382264f8, 7,671 bytes. Scores span 0.921372–0.982439.
- Full ranking: drd2/library_100k_ranked_v2.csv (100,000 rows, 7.22 MB, sha256 745727fda491a6bf5b2a2f52579219d304ad2ed1ab4390342e8fe628502e98af).
- Screening report: drd2/screening_report_v2.json (rows_read 100,000, rows_featurized 100,000, rows_invalid 0, elapsed 18.8 s, model sha256 ea135fba…).
- Top 10: zinc038472 0.982439; zinc002154 0.978179; zinc074094 0.976801; zinc075234 0.976303; zinc013215 0.975654; zinc033416 0.975441; zinc016326 0.974522; zinc063930 0.974454; zinc020467 0.966900; zinc074854 0.965795.
- Chemistry sanity check (qualitative): the list is dominated by aryl sulfonamides/benzamides/ureas with basic amine or piperazine/piperidinone side chains, plus a thioxanthene–piperazine at rank 1 (zinc038472) and a 1-(2-methoxyphenyl)piperazine at rank 49 (zinc061301) — canonical D2-like GPCR chemotypes, so the ranking is chemically plausible rather than random. This is not a hit-rate claim: the library is unlabeled, so no EF or hit rate is defined for it.

(d) COST
- Total: ≈342 s wall clock, ≈6,240 CPU-seconds (≈104 CPU-minutes), 0 GPU-seconds. 32 tool calls: 5 featurizations, 5 split manifests, 23 model fits, 1 fusion, 2 screening runs (one duplicate caused by a harness serialization retry), 1 locked evaluation.
- Breakdown: CatBoost dominated (8 fits at 28–32 s wall each but 700–870 CPU-s each, ≈6,000 CPU-s total); the final 3,128-molecule fit was 30.0 s wall / 766.8 CPU-s. Screening all 100,000 library molecules took 19.4 s wall / 19.5 CPU-s; locked evaluation 2.5 s.
- Model artifact: drd2/final_cat_r2_2048/model.joblib (481,346 bytes, sha256 ea135fbaa7407d8e63ff038d757b70cee699f8320eb08c15a0fa202ac416fa8f).

(e) WHAT TO REUSE FOR ANOTHER TARGET OF THIS KIND
1) Feature recipe: Morgan r2/2,048 + 7 RDKit descriptors; radius 3/4,096 bits and the v2 descriptor set added no measurable value here, so start with the cheap default and only expand if a fold shows signal.
2) Validation protocol: Bemis–Murcko scaffold split at 60/10/30 with at least three seeds; select on mean AUPRC/AUROC, never on EF@1% when the validation fold is only a few hundred molecules (EF saturates), and keep a random split purely as a diagnostic.
3) Model: CatBoost on hashed fingerprints is a strong, low-tuning default for this data size; XGBoost is an inexpensive near-equivalent backup; avoid linear models on sparse fingerprints for GPCR-type chemistry.
4) Refit the selected family on all available labels (95% here) before screening/deployment, and treat the locked evaluation as a one-shot independent estimate.
5) Guardrails that carried over: one endpoint only (Ki), binary label exactly as provided, no invented negatives, no hit-rate claims on the unlabeled library, and model scores are ranking scores, not calibrated probabilities (class prior 66.6% will not match the library).

INTEGRITY / LIMITATIONS
- Locked test was accessed only through evaluation.locked (one receipt, summary only); no test labels or per-sample errors were read, and no model selection used locked data.
- No cross-target experience store was used; the approach was derived only from this dataset's size, label balance and target class.
- CatBoost trained on 2,048- vs 4,096-bit fingerprints produced byte-identical predictions (model files differ but outputs match) — treated as evidence that extra fingerprint bits add no signal, not as a validated architecture.
- The provided label is binary with 66.6% positives; absolute AUPRC is therefore inflated relative to a balanced screen, and the model output is a ranking score, not an activity probability.
- screening.rank returned a harness JSON-serialization error on both calls although the job succeeded both times; artifacts were verified via job status/read-back. Canonical files are the *_v2 ones (a duplicate set with un-suffixed names exists from the first attempt).
- No PR: the requested deliverable is a report plus ranking artifacts; repository code was not modified, and no data/model/logs were committed.
- Artifact paths above are relative to the scientific tool workspace (ticket workspace); the ticket workspace root is /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/chembl-drd2-arm-a4-89e6ce69b3e6.
