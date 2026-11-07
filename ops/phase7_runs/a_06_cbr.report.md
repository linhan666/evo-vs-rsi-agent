# A #6 cbr

- task: `seq_a_cbr`
- ticket: `68cd7d990d2b7878739c88b0b8ead7c5`
- state: ready
- wall: 1251.9s, jobs 93 (failed 7), models 36
- best validation model (any split): cbr/m_cat_r3v1_bigval_s23 AUROC=0.9402 AUPRC=0.9996 EF@1%=1.007
- best scaffold model: cbr/m_cat_r3v1_bigval_s23 AUROC=0.9402 EF@1%=1.007
- refits excluded from ranking: []
- top-100 artifacts: 8

## agent report

Cannabinoid receptor (ChEMBL Ki artifact) — first-principles model, 100k screen, honest metrics.

## 0. Critical data-audit finding (drives everything below)
dataset.csv has 2,309 unique molecules. Its only resolvable activity field is a precomputed binary `label`: **2,267 positive (98.18%) / 42 negative (1.82%)**. Probeable string columns are only molecule_chembl_id, canonical_smiles, standard_type ("Ki"), label; numeric Ki/units/relation columns are not addressable through the toolchain, so no alternative active/inactive threshold could be derived. The 42 negatives are **scaffold-clustered**: the nominal Bemis-Murcko 60/10/30 split places all 42 in train, making the 230-molecule validation fold single-class (AUROC/AUPRC/EF undefined; reproduced with seeds 17/7/42). Consequence: this artifact supports a one-class-dominant "cannabinoid-likeness" ranker, not a calibrated binding-activity classifier; AUPRC base rate is 0.981 and EF@1% is structurally capped at 1.019, so those two metrics are near-vacuous here. This is reported, not papered over.

## (a) Choices and rationale
- Representation: Morgan radius 3, 2048 bits + RDKit 2D descriptors (MW, logP, HBD, HBA, TPSA, rotatable bonds, rings; desc_set v1). Radius 3 beat radius 2 on random-split AUROC for both model families (RF 0.867 vs 0.805 mean). desc_set v2 scored marginally higher in training (RF 0.881) but screening.rank only rebuilds v1 features, so v1 was kept to make validation and deployment consistent.
- Models: logreg, RF, XGBoost, CatBoost. RF is best on the optimistic random split; **CatBoost is clearly best on scaffold-held-out data** (0.91 vs 0.66 RF) and it emits non-tied scores, so it is the deployed ranker. RF's top-100 library scores are all exactly 1.000000 (verified), making its ordering arbitrary — rejected for ranking.
- Validation: Bemis-Murcko scaffold split is the primary generalisation check; random split is only an optimistic diagnostic. Because the nominal 10% scaffold-val fold is single-class, scaffold AUROC was measured on an enlarged 55/40/5 scaffold split (923 val, 6 negatives) and repeated over seeds.
- Label: used as supplied; its imbalance and clustering are treated as a first-class limitation.

## (b) Metrics actually obtained
Random split (70/30; 693 val, 13 negatives), seeds 17/23/42:
- RF, r3/2048/v1: AUROC 0.8354 / 0.8727 / 0.8914 → 0.867 ± 0.028; AUPRC 0.9954 / 0.9968 / 0.9970 → 0.9964; EF@1% 1.019
- CatBoost, r3/2048/v1: AUROC 0.7620 / 0.8061 / 0.8824 → 0.817 ± 0.061; AUPRC 0.9944 / 0.9953 / 0.9960 → 0.9952; EF@1% 1.019
- seed 17: logreg 0.7331 (AUPRC 0.9923), XGBoost 0.6715 (AUPRC 0.9832, EF 0.874); RF r2 0.8154, CatBoost r2 0.8245
Baselines: AUPRC 0.9818; EF@1% 1.019 = the structural ceiling (1/0.9818), so EF@1% is uninformative and is not evidence of enrichment.
Scaffold split (primary): nominal 60/10/30 → validation 230/230 positive, AUROC/AUPRC/EF undefined (seeds 17/7/42). Enlarged scaffold val (923, 6 negatives): CatBoost 0.8862 / 0.9402 / 0.9015 → 0.909 ± 0.028, AUPRC 0.9993-0.9996, EF 1.007 (ceiling 1.007); RF 0.6334 / 0.6954.
No locked external test exists for cannabinoid (evaluation.locked covers MOR/KOR/DRD2 only), so no test-set numbers are claimed. The 100k library is unlabeled: no hit rate or EF is defined for it.

## (c) Top-100 paths
- **Top-100 (deliverable): `cbr/top100_cat_r3v1_train90.csv`** — 100 rows, ranks 1-100, columns rank,id,smiles,score; verified 100/100 valid SMILES. Model: CatBoost r3/2048/v1 trained on 2,078 molecules (90% split); top-100 scores span 0.99938-0.99976 (saturated, differences ~1e-4 — ordering within the top-100 is low-confidence; treat as a hypothesis set, not a validated hit list).
- Full 100k ranking: `cbr/rank_cat_r3v1_train90.csv`. RF alternative: `cbr/top100_rf_r3v1_s42.csv` (all 100 scores exactly 1.000000).
- Paths are relative to this ticket's scientific workspace (DSH_SUPERAGENT_DIR). Dominant chemotypes: benzothiazole/benzimidazole/thiazole amides, 1,2,4-triazole carboxamides, pyrazole/imidazopyridine carboxamides, chloro/fluoro aromatics with piperazine/morpholine solubilizers. Library audited: 100,000 rows, 100,000 valid, 0 invalid.

## (d) Cost (measured unless noted)
CPU only, no GPU. Dataset featurization (2,309 mols, r3/2048/v1): 0.81 s wall / 0.37 s CPU. Scaffold split: 1.5 s wall / 1.5 s CPU. RF train (1,616): 3.0-3.6 s wall / ~3 s CPU. CatBoost train (2,078): 35.4 s wall / 934 s CPU (multithreaded). CatBoost screening of 100k: ~20-25 s wall (inferred; the tool's job report was not retrievable — see note), dominated by 100k-molecule featurization (13.6 s / 3.5 s CPU in a direct check). End-to-end modelling pipeline ≈ 1.5-2 min wall, <20 min CPU. Whole ticket ~21 min wall, most of it audit/probing.

## (e) What I would reuse for another target of this kind
Reuse the protocol, not the scores: (1) before any modelling, audit the label — count positives, check per-scaffold distribution, and refuse to report AUPRC/EF when the positive rate is ~98%; (2) Bemis-Murcko scaffold split first, random split only as a diagnostic; (3) Morgan r3/2048 + 7 descriptors as the default sparse representation; (4) RF as the random-split sanity model and CatBoost as the scaffold-robust, non-tied ranker; (5) verify that the ranking tool reproduces the training feature set (desc_set v1) before committing a model; (6) report the metric ceiling explicit (EF@1% ≤ 1/positive_rate).

## Material limitations / what a human should know
- The supplied label is 98.2% positive with 42 scaffold-clustered negatives; no reliable quantitative binding-activity predictor can be validated from it. The delivered top-100 is a best-effort ligand-likeness ranking, not a validated hit list, and must not be used for synthesis decisions without experimental follow-up.
- Reported AUROC comes from very few negatives (13 random-split; 6 scaffold-held-out), so confidence intervals are wide; AUPRC and EF@1% are at/near their structural ceilings and should be ignored as evidence of quality.
- Tooling note (internal): `screening.rank` results could not be read back through the job API ("value is not lossless JSON" for every call); the jobs ran and wrote their CSVs, which were verified independently by re-reading the top-100 files (100/100 valid) and probing columns. No deliverable depends on the hidden job record. No code/PR was required or produced for this analysis ticket; artifacts only.
