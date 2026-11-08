# A #8 ca2

- task: `p7b_a_ca2`
- ticket: `316de8f4b2a2a2982465ca11172bb1ec`
- state: ready
- wall: 483.0s, jobs 31 (failed 9), models 12
- best validation model (any split): runs/rf_v1_r2_4096 AUROC=0.9865 AUPRC=0.9992 EF@1%=1.056
- best scaffold model: runs/rf_v1_r2_4096 AUROC=0.9865 EF@1%=1.056
- refits excluded from ranking: []
- top-100 artifacts: 2

## agent report

CA2 Ki predictor built, ranked the 100k library, and completed the single successful locked evaluation; all artifacts are in the ticket workspace.

DATA/SPLIT: dataset_p7b.csv (6206 valid molecules; 5751 positives / 455 negatives; ids = molecule_chembl_id). Used frozen_carbonic_anhydrase_2.json directly as --split-manifest (no data.split): 5306 train / 621 validation; locked test untouched.

CHOICES: Morgan radius 2, 2048 bits, desc_set v1 — this is the fixed featurization evaluation.locked uses (it exposes only desc_set, no radius/bits). Model selected on validation only: RandomForest (rf, seed 17) beats logreg (AUROC 0.9156), xgboost (0.9716) and catboost (0.9675) at the same features. A 4096-bit rf variant scored higher on validation (0.9865) but evaluation.locked rejected it (feature-dimension mismatch with the fixed 2048-bit locked featurizer), so the 2048-bit rf is the best lock-compatible model. desc_set v2 features were rejected by ml.train on every attempt (exit 1), so v1 was used.

VALIDATION (selected rf, frozen manifest): AUROC 0.9838, AUPRC 0.9991, EF@1% 1.056, EF@5% 1.056 (acc 0.9581, F1 0.9783). Model: runs/rf_v1_frozen/model.joblib.
LOCKED (receipt evaluation/ca2_locked.json, quoted): AUROC 0.9687, AUPRC 0.9969, EF@1% 1.063, EF@5% 1.063.
TOP-100: screening/ca2_ki_top100_2048.csv (100 rows, scores 1.000–0.985, all benzenesulfonamide/sulfonamide chemotypes); full ranking screening/ca2_ki_ranked_2048.csv (100,000/100,000 valid, 0 invalid SMILES). Predictions only — no hit rate/EF is claimed for the unlabeled library.
COST: 31 scientific jobs (22 succeeded, 9 failed diagnostics), ~158 s aggregate job runtime, ~6.2 min from first job (19:09:51Z) to receipt (19:16:02Z); CPU only, no GPU. Experience ids reused: none (arm A has no experience store).

LIMITATIONS: validation is 588/621 positive (94.7%), so EF@1% is saturated at ~1.056 and AUROC rests on only 33 negatives; locked AUROC (0.9687) is below validation. Top-100 scores are heavily tied (many 1.000/0.995/0.990), so ordering inside tied bands is arbitrary. One earlier evaluation.locked call using the 4096-bit model failed without producing a receipt (feature-dimensionality mismatch with the fixed locked featurizer); the quoted receipt is from the single successful locked call.
