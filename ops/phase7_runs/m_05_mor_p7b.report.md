# M #5 mor

- task: `p7b_m_mor`
- ticket: `50f0727a7e71816b44e70fa0b11191dc`
- state: ready
- wall: 271.2s, jobs 14 (failed 0), models 7
- best validation model (any split): models/rf_v2_s23 AUROC=0.9424 AUPRC=0.9715 EF@1%=1.416
- best scaffold model: models/rf_v2_s23 AUROC=0.9424 EF@1%=1.416
- refits excluded from ranking: []
- top-100 artifacts: 3

## agent report

MOR Ki arm M complete: frozen split honored (data.split never called), 11-config model comparison on the frozen validation split, ONE locked evaluation, 100k library ranked, top-100 written and re-validated. All outputs are in the ticket workspace /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/mor-frozen-m-50f0727a7e71.

CHOICES AND WHY
- Featurization: Morgan radius 2, 2048 bits + 7 RDKit 2D descriptors (desc_set v2), defaults kept so ml.train, screening.rank and evaluation.locked all agree on the feature space. v2 chosen over v1 on the same rf: val AUROC 0.9410 vs 0.9362, AUPRC 0.9738 vs 0.9722.
- Labels: dataset_p7b.csv (2790 rows, 0 invalid; 2219 positives, 79.5%). Binary column used as provided; label_source=chembl_oprm1_ki_p7b; no threshold re-derivation, no endpoint mixing (Ki only), no negatives invented.
- Split: --split-manifest frozen_oprm1.json (scaffold-manifest): train 2385, validation 279 (197 positives). Test never touched by training or model selection.
- Models compared on the SAME frozen validation molecules: rf v2 AUROC 0.9410/AUPRC 0.9738; rf v1 0.9362/0.9722; xgboost v2 0.9277/0.9621; catboost v2 0.9253/0.9637; logreg v2 0.8781/0.9374. RF was the best and most stable choice (trees handle the 2055-dim sparse+fractional mix; logreg underfit).
- Seed check (not cherry-picked): rf v2 seeds 17/23/42 -> AUROC 0.9410/0.9424/0.9422, AUPRC 0.9738/0.9715/0.9747 (mean AUROC 0.9419, sd 0.0006; mean AUPRC 0.9733, sd 0.0014). Kept seed 17 (tool default) rather than selecting the best seed.
- No ensemble/fusion: ml.fuse yields a ranking, not a lock-evaluable pipeline; the same single model is both locked-evaluated and used to rank, so ranking and receipt are coherent.

VALIDATION (frozen val, 279 molecules/197 positives, rf v2 seed 17)
AUROC 0.9410 | AUPRC 0.9738 | EF@1% 1.416 | EF@5% 1.416 | accuracy 0.8674 | F1 0.9086.
Caveat stated honestly: validation positive rate is 0.706, so EF@1% is saturated at its ceiling 1/0.706=1.416 (the top 2 molecules are all positives). EF carries no discriminative signal at this base rate; AUROC/AUPRC are the meaningful numbers.

LOCKED TEST (receipt evaluation/mor_locked.json, quoted verbatim)
target MOR, endpoint Ki, desc_set v2 -> AUROC 0.9425 | AUPRC 0.9745 | EF@1% 1.379 | EF@5% 1.379. Receipt sha256 6ea308740a0590b0f22a7a0de4251ca068fc4eae9703d47ac6cd997c149adb8b. Raw locked metrics stay in the protected tree (not readable from the ticket). Validation vs locked is consistent (0.9410->0.9425), i.e. no leakage signature. Again EF@1% is saturated: 1.379 = 1/0.725 implies ~91 positives in the 126-molecule locked test, and top-1% all positive. Limitation to carry into interpretation: n=126 test molecules -> AUROC 95% CI is wide (roughly +-0.04-0.05) and EF cannot rank models here.

LIBRARY RANKING
100,000/100,000 library rows read, 0 invalid, 0 unparseable (library_100k.smi, sha256 09446ea1110f8af61ae6065a5941ddac2a131baaeef02219b27c53cc7e767e17; scored as provided, deduplication is caller preprocessing). Top-100 re-featurized independently: 100/100 valid. Top score 0.945 (zinc025392, score 0.910 for ranks 2-3), top-100 score floor ~0.860. Scores are model probabilities on an unlabeled library: NO hit rate, NO EF, NO enrichment is defined or claimed here.

TOP-100 PATH
/home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/mor-frozen-m-50f0727a7e71/screening/mor_rf_v2_top100.csv (sha256 9153155e8cedd6eb0ed94eab14763bd8d1ac39c77ff4ef7625d6f297a2b66ed5); full ranking screening/mor_rf_v2_ranked.csv (sha256 87f4d24147f44ffda18d05b59a45021c8568daca71aeb342e6eced57118e1875); report screening/mor_rf_v2_report.json.

EXPERIENCE IDS REUSED
Use (store=experience_m.json): 0 reusable. experience.retrieve with target=MOR returned count 0; the unfiltered retrieval returned 8 records, all other targets (dataset/model_D2_001-002, 5HT_003-004, ADR_005-006, DRD2_007-008). Their applicability notes bind them to different datasets (~3293-6811 molecules, positive rates 0.6657-0.9803), so none was applied to MOR (2790, 0.795). No experience fact influenced model choice; record this as "0 ids reused".

COST
Wall clock 17:59:27Z -> 18:03:45Z = 4 min 18 s total; 13 scientific job runs (2 experience.retrieve, 2 rdkit.featurize for v1/v2 + 1 verification featurize, 5 ml.train, 1 screening.rank, 1 evaluation.locked, 1 verification); 0 GPU, CPU only. screening.rank dominated (95.7 s); catboost was the only CPU-heavy train (829 CPU-s); everything else < 6 s.

ARTIFACTS (ticket workspace, all sha256-recorded): evaluation/mor_locked.json; models/rf_v2/{model.joblib,metrics.json,predictions.csv,artifact_manifest.json}; features/mor_ki_v2.npz+report; screening/{mor_rf_v2_top100.csv,mor_rf_v2_ranked.csv,mor_rf_v2_report.json}; experience/{retrieved_m.json,retrieved_all.json}; verification/top100_check.json.

RISKS/LIMITS: (1) locked test n=126 -> wide AUROC CI, single evaluation by design (rate-limited to one per target/endpoint/ticket); (2) EF@1%/5% saturated in both val and test due to high positive rate, so they are uninformative -- do not compare models on EF here; (3) the binary label is upstream-provided; no relation-symbol/threshold handling was performed or re-verified by this session, so censoring correctness rests on dataset_p7b.csv as delivered; (4) library scored as provided, no dedup; top-100 all ZINC ids, no ChEMBL overlap check performed (not required by the request).

No code change and no PR: the assignment's deliverable is the evaluation + ranked library, not repository code.
