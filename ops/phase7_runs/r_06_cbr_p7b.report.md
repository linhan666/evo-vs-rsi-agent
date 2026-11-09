# R #6 cbr

- task: `p7b_r_cbr`
- ticket: `3c1d482e4193adf253d45c7a2855fcf1`
- state: ready
- wall: 536.9s, jobs 22 (failed 0), models 14
- best validation model (any split): models/cbr_rf_v2_seed3 AUROC=1.0 AUPRC=1.0 EF@1%=1.016
- best scaffold model: models/cbr_rf_v2_seed3 AUROC=1.0 EF@1%=1.016
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

P7b CBR Ki (target 6/9) complete. No code change/PR: the deliverable is the evaluated pipeline, the single locked receipt, the 100k ranking and this report, all in the ticket workspace.

Workspace: /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/cannabinoid-frozen-r-3c1d482e4193

(a) Choices and rationale
- Experience store first: experience.retrieve(store=/home/linhan_cluster/evo_vs_rsi/scientific/.artifacts/experience/experience_r.json) returned count 0 for CBR. A store-wide retrieval returned 10 records from D2, 5HT, ADR, DRD2 and MOR; the exposed record fields are metadata + payload_sha256 only (no hyperparameters/config), and none covers a CBR profile (this set: 1963 molecules, 1925 positives = 98.1%). So no configuration could be reused verbatim; only the generic protocol (exact frozen manifest -> ml.train -> single screening -> one locked evaluation) was reused, and representation/model choice was new exploration, consistent with "only explore if prior experience does not cover this profile".
- Labels used read-only as provided (ChEMBL Ki binary, label_source=chembl_ki_binary); no negatives invented; no data.split called and no self-chosen fractions. Features: rdkit.featurize desc_set v2 (Morgan r=2, 2048 bits + 7 RDKit 2D descriptors), plus v1 comparisons; 1963/1963 molecules valid.
- Split: /home/linhan_cluster/evo_vs_rsi/scientific/.artifacts/chembl/cannabinoid_receptor/ki/splits/frozen_cannabinoid_receptor.json passed verbatim to every arm (strategy=scaffold-manifest). Counts: 1679 train / 196 validation (193 positives / 3 negatives); 88 of the 1963 labeled rows are outside train+validation.
- Frozen-split arm comparison (val AUROC / AUPRC / accuracy; EF@1% = 1.016 for all because validation is 98.5% positive): logreg v1 0.9136/0.9985/0.9745; xgboost v1 0.8946/0.9982/0.9847; catboost v1 0.9965/0.9999/0.9949; RF v1 0.9983/1.0000/0.9847; RF v1 r=3 4096 1.0000/1.0000/0.9847; RF v2 1.0000/1.0000/0.9898; CatBoost v2 1.0000/1.0000/0.9949; xgboost v2 0.7202/0.9937/0.9847.
- Final model: CatBoost, desc_set v2, seed 17 (models/cbr_cat_v2/model.joblib). Rationale: AUROC/AUPRC saturated at 1.000 for RF and CatBoost, so CatBoost was preferred on the best threshold metrics (accuracy 0.9949, F1 0.9974); seed 17 was fixed a priori, and seeds 2/3 were run only as a stability check (all AUROC 1.000; accuracy 0.9949/1.000), not for selection.

(b) Final model frozen-split validation (196 molecules; 193 pos / 3 neg): AUROC 1.000, AUPRC 1.000, EF@1% 1.016 (accuracy 0.9949, F1 0.9974). Material caveat: with only 3 negatives the validation AUROC is a coarse, saturated statistic and cannot be read as evidence of generalization.

(c) Locked test (exactly one call; receipt evaluation/cbr_locked.json, sha256 e03ef62d726da78f3b29e44572780e9dcd8983357fef7509603d85317dde827f): "auroc": 0.6586 verbatim; also "auprc": 0.9943, "ef_at_1pct": 1.012, "ef_at_5pct": 1.012 (target CBR, endpoint Ki, desc_set v2). The validation->locked gap (1.000 -> 0.6586) is the main limitation; the labeled file has only 38 non-active rows total (1925/1963 positives), 3 of them in validation, so negative-class evidence is thin and AUPRC near prevalence is not strong ranking evidence. The locked AUROC is the number that counts.

(d) Top-100: screening/cbr_top100.csv (workspace-relative; absolute /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/cannabinoid-frozen-r-3c1d482e4193/screening/cbr_top100.csv), sha256 93a32c38b3601bd32f9999fa99dbf756114b4db286fb678462dfeaa899e80487. Full 100k ranking: screening/cbr_library_ranked.csv; report screening/cbr_screening_report.json: 100000/100000 rows featurized, 0 invalid, top score range [0.999068, 0.999459], elapsed 90.0 s. The library is unlabeled and was scored as provided (no dedup); no hit-rate/EF is claimed for it.

(e) Cost: 22 scientific jobs; summed tool wall 240.1 s (4.0 min), ticket session ~8 min wall; 2896 CPU-s (~48 CPU-min), 0 GPU-s. Heaviest: screening 90.6 s; CatBoost runs 24.6-29.6 s each (parallel CPU threads).

(f) Experience_ids examined: dataset_D2_001, model_D2_002, dataset_5HT_003, model_5HT_004, dataset_ADR_005, model_ADR_006, dataset_DRD2_007, model_DRD2_008, dataset_MOR_009, model_MOR_010. Used: none (0 CBR records; payloads not exposed by the retrieval interface, only payload_sha256). Reused verbatim: none. Adapted: only the shared frozen-manifest train/validate protocol and the standard descriptor-set/model pipeline; all representation/model choices were re-compared on this dataset.

Key artifacts/hashes: features/cbr_train_v2_r2_2048.npz 77281f5e9f151afd9d8602ad9b9650e148bdac03fcb555569ecf90ee77587a2f; models/cbr_cat_v2/model.joblib 6efeae22ac01cce32910187eb8f4b9af783b5ab61f5010acfee6b939b56d3152; screening/cbr_top100.csv 93a32c38b3601bd32f9999fa99dbf756114b4db286fb678462dfeaa899e80487; evaluation/cbr_locked.json e03ef62d726da78f3b29e44572780e9dcd8983357fef7509603d85317dde827f.

Suggested short user-facing result (for the orchestrator): Locked CBR Ki AUROC 0.6586; top-100 at screening/cbr_top100.csv. Frozen-split validation AUROC 1.0 was saturated on only 3 negatives, so the locked number is the reliable one.
