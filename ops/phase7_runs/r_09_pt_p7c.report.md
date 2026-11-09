# R #9 pt

- task: `p7c_r_pt`
- ticket: `3f3aac3700e1169985be54aa020a1079`
- state: ready
- wall: 238.0s, jobs 22 (failed 3), models 10
- best validation model (any split): models/pt_ki_rf AUROC=0.9423 AUPRC=0.9754 EF@1%=1.437
- best scaffold model: models/pt_ki_rf AUROC=0.9423 EF@1%=1.437
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

PT / Ki (prothrombin, target 9/9) completed end-to-end on the frozen split; one locked evaluation used; 100k library ranked; top-100 delivered.

INPUTS (as instructed)
- labels: scientific/.artifacts/chembl/prothrombin/ki/dataset_p7b.csv (2400 rows, 0 invalid SMILES, id=molecule_chembl_id, smiles=canonical_smiles, label column `label`; read as provided — no Ki/IC50 mixing, no re-binarisation by me)
- split: .../ki/splits/frozen_prothrombin.json passed as --split-manifest to ml.train for every fit; data.split was NOT called. ml.train reports split_strategy "scaffold-manifest": 2052 train / 240 validation (167 val positives, 69.6% prevalence); the remaining 108 manifest rows were never used for fitting or reported here.
- library: scientific/.artifacts/zinc/library_100k.smi (100000 rows, 100000 featurized, 0 invalid)
- experience store: scientific/.artifacts/experience/experience_r.json

CHOICES AND WHY
1) Features: Morgan r=2, 2048 bits + 7 RDKit 2D descriptors; desc_set v1 and v2 both featurized (2400/2400 valid). radius=2 / n_bits=2048 deliberately kept at the evaluator's defaults so the locked model's features match what evaluation.locked and screening.rank recompute.
2) Models: logreg, rf, xgboost, catboost × {v1, v2}, seed 17, all on the frozen manifest. Validation (AUROC / AUPRC / EF@1%):
   - rf v1: 0.9423 / 0.9754 / 1.437  <- selected
   - rf v2: 0.9404 / 0.9732 / 1.437
   - cat v1: 0.9132 / 0.9581 / 1.437 ; cat v2: 0.9367 / 0.9699 / 1.437
   - xgb v1: 0.9039 / 0.9522 / 1.437 ; xgb v2: 0.9347 / 0.9699 / 1.437
   - logreg v1: 0.8197 / 0.8996 / 1.437
   rf v1 (seed 17) won on both AUROC and AUPRC.
3) Seed stability for the selected rf v1 (guards against picking a lucky seed): seeds 7 / 17 / 42 / 101 → AUROC 0.9287 / 0.9423 / 0.9370 / 0.9311, AUPRC 0.9679 / 0.9754 / 0.9716 / 0.9679; mean AUROC 0.9348, mean AUPRC 0.9707. Seed 17 chosen (best, and its margin over other seeds is small — i.e. the result is not seed-fragile).
4) EF caveat: validation EF@1% = 1.437 = 1/0.6958, exactly the ceiling for this prevalence, so EF is not discriminative on validation (top 1% of 240 = 2 molecules, both positive). AUROC/AUPRC carry the signal.
5) Locked model: models/pt_ki_rf/model.joblib (sha256 583bccc9e07826ab9a90203bd3f4082a49ed8f0fb4ea6c96cc6ac3813872f2d7), desc_set v1. This is the same file hashed by the screening report (model_sha256 matches), so ranking and locked evaluation are the same model.

LOCKED EVALUATION (called exactly once: evaluation.locked --target PT --endpoint Ki --desc-set v1 --receipt evaluation/pt_locked.json; job 5d515c451ff3, 2.29 s)
- receipt evaluation/pt_locked.json, sha256 4a505440fd1d9197c7492f18cefc7b5e5b3f2f02dd5deb99cf8114b0546a63c8
- quoted metrics: auroc 0.9545, auprc 0.9933, ef_at_1pct 1.134, ef_at_5pct 1.134
- raw per-sample locked metrics live in the protected tree and were not read by this ticket ("summary only" per receipt).
- Note: locked EF@1% = 1.134 = 1/0.882, i.e. again at the ceiling for a ~88% positive test set; locked AUROC 0.9545 is above validation 0.9423.

TOP-100 RANKING
- top-100: screening/pt_ki_top100.csv (relative to the run workspace / ticket work dir), sha256 6392ce93d5db712e2066fc047198bcca284aabb4726229554f1a5caed4f688f2, 100 data rows verified (ranks 1..100, scores 0.935 down to 0.880, descending, ids zinc*)
- full ranking: screening/pt_ki_ranked.csv (100000 rows, sha256 009e1cc444d53e7a3701e690b6b2998857098321ddf5aafbd59d1f19cd3624de)
- screening report: screening/pt_ki_screening.json (100000 rows read/featurized, 0 invalid, top_k=100, elapsed 16.5 s; top_score_range [0.88, 0.935]); top hit zinc072072 CCOc1ccc(Oc2ccc(Cl)cc2NC(=O)Cn2cnc3ccsc3c2=O)cc1, score 0.935
- Integrity note: this is a model score on an unlabeled library — no hit rate / enrichment / EF is defined or claimed. Library scored as provided, no dedup (tool note); ids in the top-100 are unique.

COST
- Wall clock: first job 22:43:27Z → last 22:46:29Z ≈ 182 s (~3 min); summed job wall time ≈ 60 s. CPU only (no GPU), single user.
- Job count: 22 tool jobs = 14 core compute jobs (2 featurize, 10 ml.train, 1 evaluation.locked, 1 screening.rank) + 5 experience.retrieve + 3 failed diagnostic path probes (no artifacts, no effect on results; they were attempts to locate the run workspace root).
- Artifacts also present: feat/pt_ki_v1.npz + report, feat/pt_ki_v2.npz + report, models/{pt_ki_logreg, pt_ki_rf, pt_ki_xgb, pt_ki_cat, pt_ki_v2_rf, pt_ki_v2_xgb, pt_ki_v2_cat, pt_ki_rf_s7, pt_ki_rf_s42, pt_ki_rf_s101}/ with metrics.json, predictions.csv, model.joblib, artifact_manifest.json.

EXPERIENCE IDS REUSED: none — the store is readable (no STORE_UNREADABLE) but returns 0 records: PT, unfiltered, kind=screening, MOR, and kind=model+PT all produced the identical 34-byte payload {"count":0,"records":[]} (sha256 b8dbaa59b5dd2388328685c87ba46e4e7d9de0c7ab0dc1783d872d8ba941f537). So there was nothing to reuse; this is a data gap in experience_r.json, not a skipped step. Retrieval outputs: experience/pt_retrieve.json, experience/all_retrieve.json, experience/screening_retrieve.json, experience/mor_retrieve.json, experience/model_retrieve.json.

SELF-REVIEW / LIMITATIONS
- No code change was required or made, so there is no PR; the deliverable is the artifacts + locked receipt above. No test-set labels or per-sample locked errors were accessed; only the frozen public split was used.
- Validation positives are 69.6% and locked positive prevalence ~88%, so EF@1%/EF@5% are saturated ceilings on both; do not read them as screening power. AUPRC is inflated by prevalence for the same reason.
- Model is fitted on 2052 molecules only (frozen manifest); 108 manifest rows remain untouched. Seed choice was made on validation (not test), and the 4-seed spread is reported so the choice is auditable.
- Failed probes (3 jobs) were path-resolution diagnostics; they produced no artifacts and no metrics, and are excluded from all reported numbers.
