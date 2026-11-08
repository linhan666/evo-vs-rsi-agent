# M #8 ca2

- task: `p7b_m_ca2`
- ticket: `65a7a1072a176cebc2b051ba3d213bbd`
- state: ready
- wall: 262.5s, jobs 17 (failed 5), models 6
- best validation model (any split): models/ca2_rf_v1_s42 AUROC=0.9852 AUPRC=0.9992 EF@1%=1.056
- best scaffold model: models/ca2_rf_v1_s42 AUROC=0.9852 EF@1%=1.056
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

CA2 Ki (arm M) complete: frozen split, experience lookup, predictor, one locked evaluation, 100k ranking, metrics/evidence/cost.

SPLIT: passed frozen `.../chembl/carbonic_anhydrase_2/ki/splits/frozen_carbonic_anhydrase_2.json` to ml.train as --split-manifest; did NOT call data.split. Joined 6206 molecules (id `molecule_chembl_id`, label `label`; 5751 positives = 92.7%); train 5306 / validation 621 / test 279 held out.

MODEL CHOICE: desc_set=v1 (Morgan r=2, 2048 bits) is the only trainable set here — `ml.train` on the v2 feature file exits 1 with no artifacts, reproduced 5x across all four families. Compared on frozen scaffold-validation:
- logreg: AUROC 0.9156, AUPRC 0.9936
- rf: AUROC 0.9838, AUPRC 0.9991  <-- selected
- xgboost: AUROC 0.9716, AUPRC 0.9983
- catboost: AUROC 0.9675, AUPRC 0.9981
RF stable across seeds: seed7 0.9830/0.9990, seed42 0.9852/0.9992. Kept seed 17 (default; avoided seed-shopping). Final pipeline: `models/ca2_rf_v1/model.joblib` sha256 dd238e4f6deaa6fd77f869998c4bb088504b7567bb2ed041cb277031c4cc91db.

VALIDATION (RF v1 seed17): AUROC 0.9838, AUPRC 0.9991, EF@1% 1.056, EF@5% 1.056. Validation is 588/621 positives (94.7%), so EF@1% ceiling is 1.056 — top-ranked validation molecules are all positive and EF is saturated/non-discriminating here.

LOCKED (evaluation.locked --target CA2 --endpoint Ki --desc-set v1 --receipt evaluation/ca2_locked.json): AUROC 0.9687, AUPRC 0.9969, EF@1% 1.063, EF@5% 1.063. Receipt sha256 008be1e29635c0e105d56472508151fa66e511fb500494970b1dce14fff26a46; protected raw metrics not readable from the ticket.

LIBRARY: screening.rank scored 100000/100000 valid molecules, 0 invalid, top score range [0.985, 1.0]. Full ranking `screening/ca2_library_ranked.csv`; top-100 `screening/ca2_top100.csv`. Top hits are primary benzenesulfonamides (e.g. zinc042824, zinc030977), chemically consistent with CA2. Library is unlabeled: no true hit-rate/EF claim.

ARTIFACTS (workspace /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/anhydrase-frozen-m-65a7a1072a17):
- evaluation/ca2_locked.json (413 B)
- screening/ca2_top100.csv (7257 B, sha a96cc2317ffbe2c506a61ef258eb3ac1a72fdbc16bb19e45e40d5d7e5af69a06)
- screening/ca2_library_ranked.csv (7.2 MB, sha 5a8a546490f15a9cd545fb52c3f12da7d96302afaec387c3a839ef2f68d6ccd3)
- screening/ca2_rank_report.json (sha 651b3085979ad58c4c507505b66e661bbee495716f87d78aad3dc719e265cef3)
- models/ca2_rf_v1/{model.joblib,metrics.json,predictions.csv,artifact_manifest.json}
- features/ca2_v1.npz (sha 672d83cbeda2fa2b34a0b6426e0c5deb6202eab2d636c2898591db80afc3dcb1)
- experience/all_m_retrieval.json (sha c0e280d8c5287e49118c82db120707d0db8d2f0365988596f4afa08a86c576b2)

COST: 17 scientific jobs (12 succeeded, 5 failed v2 attempts); total tool wall time 72.5 s (featurize 8.4 s; training 42.6 s incl. failures; screening 18.9 s; locked eval 2.4 s; retrieval 0.2 s).

EXPERIENCE: `experience_m.json` has 14 records (D2/5HT/ADR/DRD2/MOR/CBR/KOR); 0 CA2 records, 0 applicable, so 0 experience ids reused; applicability notes are dataset/target-specific.

LIMITATIONS: v2 descriptor set unusable with ml.train in this environment; validation AUROC based on 621 molecules (588 positives); the ticket's single locked evaluation has been consumed. No PR: no code change, artifacts only; data/models are not committed per AGENTS.md.
