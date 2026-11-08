# M #4 drd2

- task: `seq_m_drd2`
- ticket: `857d183f24c95cdbb131b049491d56ab`
- state: ready
- wall: 272.5s, jobs 13 (failed 1), models 4
- best validation model (any split): drd2/work/train_xgb AUROC=0.9367 AUPRC=0.9639 EF@1%=1.645
- best scaffold model: drd2/work/train_xgb AUROC=0.9367 EF@1%=1.645
- refits excluded from ranking: []
- top-100 artifacts: 1

## agent report

DRD2 (arm-M target #4) completed. Deliverable report follows; no repository change or PR was requested, the outputs are scientific artifacts.

## (a) Choices and rationale
Sequence reuse gate: `experience.retrieve` was called with the exact store path `/home/linhan_cluster/evo_vs_rsi/scientific/.artifacts/experience/experience.json` and returned 6 records (targets #1–#3): `dataset_D2_001`/`model_D2_002` (6811 mol, 0.9621 positive), `dataset_5HT_003`/`model_5HT_004` (4828, 0.9803), `dataset_ADR_005`/`model_ADR_006` (3376, 0.9588). Every applicability note is bounded to "ChEMBL Ki binary sets of ~3.4k–6.8k molecules at ~0.96–0.98 positive rate, scaffold split" and explicitly says "re-check before applying to much smaller or balanced datasets".
DRD2 profile, measured from the artifacts: 3293 molecules, 2192 positives (0.6656), scaffold train/val/test = 1977/329/987 (val positives 200, 0.608). This is both much more balanced and smaller than every stored profile, so no stored model configuration was applicable; the store was used as an explicit negative applicability gate, not as a recipe. What was carried over from the sequence's standard protocol: Ki-only binary labels as provided (no re-thresholding, no Ki/IC50 mixing), Morgan fingerprint radius 2 / 2048 bits + v1 2D descriptors, Bemis–Murcko scaffold split (seed 17). What was re-derived: the classifier was selected on this dataset's scaffold validation rather than transferred — XGBoost beat logreg and RF, and a representation variant (radius 3 / 4096 bits / v2 descriptors) was tested and rejected.
Selected model: XGBoost, r=2 / 2048 bits / v1 descriptors, seed 17, trained on the 1977 scaffold-train molecules (`drd2/work/train_xgb/model.joblib`, sha256 e98c3978…4208).

## (b) Metrics
- Scaffold-validation (329 mol, 200 pos, prevalence 0.608), selected model: AUROC 0.9367, AUPRC 0.9639, EF@1% 1.645, EF@5% 1.645, accuracy 0.848, F1 0.8775.
- Independent locked Ki test (receipt `drd2/work/locked_receipt.json`): AUROC 0.919, AUPRC 0.9412, EF@1% 1.824, EF@5% 1.824. Raw locked metrics stay in the protected tree; the receipt is summary-only.
- Alternatives on validation: logreg 0.9217 / 0.9519 / 1.645; RF 0.9273 / 0.9485 / 1.645; XGB r3/4096/v2 0.9274 / 0.9440 / 1.645 (EF@5% 1.542).
Caveat: validation prevalence 0.608 makes EF@1% saturated at its ceiling 1/0.608 = 1.645, so EF@1% does not discriminate candidates here; AUPRC/AUROC drove selection. No hit rate or EF is defined/claimed for the unlabeled 100k library.

## (c) Top-100 and other paths (executor-workspace relative)
- Top-100: `drd2/work/top100.csv` — columns rank,id,smiles,score; 100 distinct ZINC ids, score 0.994182 (zinc042409) down to 0.956736 (zinc018778), strictly descending; sha256 81bc214f…c90b.
- Full 100k ranking: `drd2/work/library_ranked.csv` (100000 rows, sha256 585f5ca6…e50).
- Screening report: `drd2/work/screening_report.json` (100000 read, 0 invalid SMILES, 17.6 s; library sha256 09446ea1…e17; "predictions are model scores on an unlabeled library").
- Model: `drd2/work/train_xgb/model.joblib`; split manifest `drd2/work/split_scaffold.json`; val metrics `drd2/work/train_xgb/metrics.json`; locked receipt `drd2/work/locked_receipt.json`.
- Inputs were used read-only: dataset sha256 928f3de2…26c, library sha256 09446ea1…e17.

## (d) Cost
0 GPU; no external API spend. 13 executed tool calls totalling ~54 s wall / ~34 s CPU (includes one failed relative-path attempt at 0.4 s); the expensive step was scoring the library, 18.1 s wall / 8.6 s CPU for 100k molecules. Peak RSS was not reported by the runner.

## (e) Experience use: reused vs adapted
IDs consulted: `dataset_D2_001`, `model_D2_002`, `dataset_5HT_003`, `model_5HT_004`, `dataset_ADR_005`, `model_ADR_006`. Reused verbatim: no stored model payload — the retrieve interface returns only experience_id/kind/target/applicability/payload_sha256, not hyperparameters, and the applicability bounds exclude this profile anyway. Reused as protocol conventions: Ki-only binary labels, scaffold split, Morgan r=2/2048 + v1 descriptors. Adapted: model family and representation were re-selected on DRD2 scaffold validation (XGBoost); the size/balance mismatch also motivated testing the r3/4096/v2 variant, which was worse.

## Limitations
- Library scored as provided; no exact-SMILES dedup was performed (stereoisomer pairs such as ranks 16/17 and 65/66 are distinct molecules, not duplicates, but a dedup pass is advisable before ordering).
- Scores are model scores, not binding probabilities; the top-100 is prioritization only, with no docking or experimental confirmation.
- The saved model is fitted on scaffold-train only (1977 molecules); val was used for selection only, so refitting on train+val is a possible future gain that `ml.train` does not expose.
- Because experience payloads are not exposed by the retrieve tool, exact hyperparameter agreement with prior targets cannot be claimed.

## Suggested facts for the next target's store record (recorder)
DRD2 dataset: 3293 molecules, positive rate 0.6656, ChEMBL Ki binary, scaffold split seed 17. Model: xgboost, Morgan r=2/2048 + v1 descriptors; validation AUROC 0.9367 / AUPRC 0.9639 / EF@1% 1.645; locked test AUROC 0.919 / AUPRC 0.9412 / EF@1% 1.824.
