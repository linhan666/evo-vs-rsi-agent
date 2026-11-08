# M #3 adr

- task: `seq_m_adr`
- ticket: `24cda9d7d2f5e9f6f5abf149f8024e0d`
- state: ready
- wall: 1063.6s, jobs 72 (failed 2), models 36
- best validation model (any split): grid_t35_rf_r2 AUROC=0.9838 AUPRC=0.9991 EF@1%=1.053
- best scaffold model: grid_t35_rf_r2 AUROC=0.9838 EF@1%=1.053
- refits excluded from ranking: []
- top-100 artifacts: 10

## agent report

Sequence arm M · target 3 — Adenosine receptor A (Ki) — COMPLETE. Predictor built, 100k library ranked, metrics/cost/reuse reported. No code/PR change (scientific task); all artifacts are in the ticket workspace.

(a) CHOICES & RATIONALE
- Data read as provided: dataset.csv → 3,376 molecules (id=molecule_chembl_id, smiles=canonical_smiles, binary label), 3,237 positives / 139 negatives (95.9% positive; base rate 0.9614). Library 100,000 SMILES (library_100k.smi).
- Protocol: Bemis–Murcko scaffold split, canonical 60/10/30 (train 2,027 / val 337 / test 1,012), seed 17. Note: the scaffold splitter is deterministic w.r.t. seed (identical rows for seeds 11/23/42), so robustness was probed by varying the held-out fraction (0.15–0.45), not the seed.
- Experience retrieved FIRST, before modelling, with the exact store path (4 records): dataset_D2_001, model_D2_002, dataset_5HT_003, model_5HT_004.
- Reused verbatim: the ChEMBL-Ki-binary framing + scaffold-split protocol recorded in dataset_D2_001/dataset_5HT_003, and the workspace-default featurisation (Morgan radius 2, 2,048 bits + 7 v1 2D descriptors).
- Adapted: our set (3,376 @ 95.9% positive) is materially smaller than both recorded profiles (4,828 @ 98.0%, 6,811 @ 96.2%); the records' applicability note says to re-check for much smaller sets. Also experience.retrieve returns applicability + payload_sha256 only (the model payload/hyperparameters are not exposed), so no prior hyperparameters could be copied. I re-validated 4 model families (logreg, RF, XGBoost, CatBoost) × 4 representations (r2/2048/v1, r2/4096/v1, r3/2048/v1, r2/2048/v2) across 5 scaffold splits.
- Selected model: XGBoost on Morgan r2/2048 + v1 descriptors. It matches RF within noise on the 5-split mean and is more stable: XGB mean AUROC 0.880 (SD 0.104), mean AUPRC 0.9927 vs RF 0.876 (SD 0.114) / 0.9904. Critically, RF scores saturate (31/100 top molecules exactly 1.0 and 92 tied at 0.995; RF-4096 has 65 at 1.0), so an RF top-100 order/boundary is arbitrary. XGB scores are continuous and the delivered top-100 is fully resolved.

(b) METRICS (scaffold validation, canonical split; validation = 337 molecules, 324 positives)
- Delivered XGBoost: AUROC 0.9214, AUPRC 0.9955, EF@1% 1.04, EF@5% 1.04, accuracy 0.9763, F1 0.9877.
- Comparators (AUROC/AUPRC): RF 0.9380/0.9965; RF r2/4096 0.9531/0.9975; RF desc-v2 0.9506/0.9975; RF r3/2048 0.9360/0.9964; CatBoost 0.9145/0.9948; LogReg 0.8882/0.9893.
- 5-split robustness (held-out 20–40%): XGB AUROC 0.700/0.833/0.921/0.980/0.967 (mean 0.880, SD 0.104), AUPRC mean 0.9927. RF on the same 5: 0.676/0.824/0.938/0.984/0.960 (mean 0.876, SD 0.114), AUPRC mean 0.9904. Random-split diagnostic: RF 0.9419/0.9946.
- Integrity caveats: EF@1% is capped at 1/base-rate = 1.04 under this class balance and every model hits it, so it does not discriminate. AUPRC's no-skill baseline is 0.9614, so 0.995 is a modest lift. AUROC is the informative metric but each val set has only 13–23 negatives; across 7 held-out fractions RF AUROC ranged 0.292–0.984 (mean 0.804, SD 0.232). These are protocol-specific estimates, not precise generalisation numbers.

(c) TOP-100
- Delivered path: /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/adenosine-arm-m3-24cda9d7d2f5/top100_xgb.csv — 100 unique molecules (columns rank,id,smiles,score; score 0.999979 → 0.999878, fully resolved).
- Full library ranking: /home/.../ranking_xgb.csv (100,000 rows).
- Top-10 ids: zinc096307, zinc058802, zinc024219, zinc021605, zinc089014, zinc015792, zinc094979, zinc027270, zinc068728, zinc001711.
- Cross-model check: RF top-100 (top100_rf_final.csv) overlaps only 4/100 (zinc086745, zinc039629, zinc072718, zinc041961). So the top-100 is a high-confidence candidate set, not a stable ordering; those 4 are the most robust picks. A consensus full ranking (rank-average RF+XGB, weight 0.5/0.5, weights declared from validation AUPRC 0.9965/0.9955, never fitted on test) is at ranking_fused_rf_xgb.csv.
- The library is unlabeled; no hit rate / EF is claimed for it. All top-100 scores are >0.9998, so ordering is driven by small margins — use it as coarse priority, not calibrated probability.

(d) COST
- CPU only, 0 GPU, no paid API. Total ≈5.6 min wall / ≈15.6 CPU-min across >60 tool calls (featurisation 8.1 s; splitting 20.1 s; 34 training runs 189.1 s; 6 full 100k-library screening passes ≈111 s; fusion 5.6 s). Most expensive single run: CatBoost 25.9 s wall / 699.9 CPU-s (rejected).
- Delivered-model marginal cost: ≈27 s wall / ≈17 CPU-s (featurise 1.1 s + split 1.5 s + train 5.8 s + screen 18.5 s). A full 100k scoring pass takes ~18.5 s.

(e) EXPERIENCE IDs USED
- dataset_D2_001, dataset_5HT_003 (reused verbatim: ChEMBL-Ki-binary + scaffold-split protocol, default representation).
- model_D2_002, model_5HT_004 (applicability range used as a re-check; their configuration payload is not returned by experience.retrieve, so nothing beyond the protocol was copied verbatim).
- Retrieved via experience.retrieve with store=/home/linhan_cluster/evo_vs_rsi/scientific/.artifacts/experience/experience.json; result saved as experience_retrieval.json (4 records; the store is read-only and no records were written by this ticket).

LIMITATIONS / NOT AVAILABLE
- Only 139 negatives: scaffold-split AUROC is unstable and AUPRC/EF are inflated by the 96% base rate.
- No independent locked test for adenosine receptor A in this workspace (evaluation.locked supports MOR/KOR/DRD2 only); the 1,012-molecule scaffold test split was left untouched, so all reported metrics are validation, not final-test.
- Exact prior model hyperparameters were not retrievable from the experience store (summary + payload hash only); reuse is therefore at protocol level.
- Top-100 is model-dependent (4/100 cross-family overlap); ranking_fused_rf_xgb.csv is provided for a consensus view.

Key artifacts (all under /home/linhan_cluster/evo_vs_rsi/.artifacts/state/work/adenosine-arm-m3-24cda9d7d2f5/): top100_xgb.csv, ranking_xgb.csv, model_xgb/model.joblib, model_xgb/metrics.json, dataset_features.npz (+ report), split_scaffold.json, top100_rf_final.csv, ranking_fused_rf_xgb.csv, experience_retrieval.json.
