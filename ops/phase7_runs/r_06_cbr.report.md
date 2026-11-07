# R #6 cbr

- task: `seq_r_cbr`
- ticket: `e4548657462706282f4927203f167f27`
- state: ready
- wall: 580.3s, jobs 33 (failed 2), models 14
- best validation model (any split): model_rf_v2_rand AUROC=0.8622 AUPRC=0.9956 EF@1%=1.019
- best scaffold model: model_rf_scaf_val20 AUROC=0.8235 EF@1%=1.007
- refits excluded from ranking: []
- top-100 artifacts: 4

## agent report

Cannabinoid receptor (Ki) — sequence target #6: predictor built, validated, and 100k library ranked. Deliverables are workspace artifacts listed below.

DATA/EXPERIENCE. Retrieved the store at the required absolute path (…/scientific/.artifacts/experience/experience.json) at task start: 10 records (5 dataset + 5 model; targets D2, 5HT, ADR, DRD2, MOR). CBR Ki set: 2309 molecules (2267 pos / 42 neg, positive rate 0.9818), id=molecule_chembl_id, smiles=canonical_smiles, binary Ki label only (no Kd/IC50 mixing). Profile is smaller than every stored dataset (min 2790), so the store's "re-check before applying" note applied.

(a) CHOICES/RATIONALE. Reused the store-certified protocol: Bemis-Murcko scaffold split 60/10/30 with seed 17, Morgan radius 2 / 2048 bits + 7 v1 RDKit descriptors, small-data classifier comparison (logreg, RF, XGB). Adapted validation: at 10% val the scaffold fold was single-class at seeds 17, 42 and 101 (230/230 positives), so AUROC/AUPRC/EF@1% were undefined; I therefore used a 20% scaffold validation fold (461 mols: 458 pos / 3 neg) for computable metrics. Representation checks (radius 3, desc_set v2) did not warrant a change (v2 also cannot be used by screening.rank, which recomputes v1 features); kept v1 verbatim. Model family chosen locally by 3-seed random-split ranking performance: RF AUROC 0.8154/0.8519/0.8557 > XGB 0.7560 > logreg 0.6087; RF AUPRC 0.9936/0.9951/0.9947. Final model: scikit RF on scaffold-train (1156 mols), validated on the 461-mol scaffold fold.

(b) METRICS (scaffold-held-out, final RF, seed 17): AUROC 0.8235, AUPRC 0.9985, EF@1% 1.007, accuracy 0.9935, F1 0.9967, validation n=461 (3 negatives). Optimistic random 70/30 diagnostic (3 seeds): AUROC 0.815/0.852/0.856 (mean 0.841, SD 0.018), AUPRC 0.9936/0.9951/0.9947, EF@1% 1.019. The protocol-standard 10% scaffold fold gives null ranking metrics (single-class validation) at all three seeds. Caveats: 42 negatives total → wide AUROC uncertainty; EF@1% ≈1 by construction at 98% positives and is uninformative; evaluation.locked supports only MOR/KOR/DRD2 endpoints, so no locked final test exists for cannabinoid receptor — reported metrics are scaffold-held-out internal validation only.

(c) TOP-100. cbr_ki_top100_rf.csv (100 rows: rank,id,smiles,score; sha256 96e1e797…), cut from the full 100k ranking cbr_ki_ranked_rf.csv (100,000 molecules, 0 invalid), model model_rf_scaf_val20/model.joblib (sha256 97bb6451…), screening report cbr_ki_screening_rf.json. Paths are relative to /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/cannabinoid-seq-e45486574627/. LIMITATION: RF probabilities saturate — all top-100 scores are exactly 1.000000 (top_score_range [1.0,1.0]), so at least 100 library molecules share the maximum score and the internal 1–100 order is tie-broken by library order; XGB and logreg top-100 lists are nearly disjoint from it, so treat the list as a prioritized set, not a strict order. No hit rate/EF claim is made for the unlabeled library.

(d) COST. 27 scientific tool runs, ≈128 s total wall time, CPU-only, 0 GPU-seconds, no paid services or external credentials; two failed screening probes cost 0.54 s combined. (A few extra screening calls returned transport errors after completing; their wall time is included.)

(e) EXPERIENCE USE. Used dataset_5HT_003 / model_5HT_004 (closest positive rate 0.9803), dataset_ADR_005 / model_ADR_006 (high-positive-rate small set), dataset_MOR_009 / model_MOR_010 (closest sample size 2790). Reused verbatim: scaffold split strategy and 30/10/seed-17 protocol, Morgan r2/2048 + v1 descriptor featurization, Ki-binary small-data classifier comparison. Adapted: validation fraction 10%→20% (three 10% folds were single-class), and model-family selection made locally because experience.retrieve v0.1.0 exposes only applicability + payload_sha256, not hyperparameters (provenance hashes recorded in the retrieval output experience_retrieve.json / experience_models.json). No fusion used: no shared library-level validation, and fused rankings cannot be cut to top-100 with the available tooling.

INTEGRITY. Ki endpoint only; scaffold grouping keeps duplicate/near-duplicate standardized molecules in the same fold; 100k library is unlabeled so no enrichment is claimed; final metrics come only from the held-out scaffold fold (test partition untouched); the experience store is read-only and was not modified (sequence harness appends records).
