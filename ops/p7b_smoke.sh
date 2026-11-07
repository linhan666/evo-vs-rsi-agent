#!/usr/bin/env bash
# Smoke-test the phase7b frozen split end to end on one target.
# Parentheses in the ChEMBL slug break inline shell, hence this file.
set -euo pipefail
cd /home/linhan_cluster/evo_vs_rsi

SLUG='d(2)_dopamine_recept'
D="scientific/.artifacts/chembl/${SLUG}/ki"
S="/home/linhan_cluster/evo_vs_rsi/.artifacts/p7b_smoke"
PY="scientific/.venv/bin/python"

rm -rf "$S"
mkdir -p "$S"

"$PY" -m evovs_science.chemistry.featurize \
  --input "$D/dataset_p7b.csv" --output "$S/feat.npz" --report "$S/meta.json" \
  --id-column molecule_chembl_id --smiles-column canonical_smiles \
  --desc-set v1 --radius 2 --n-bits 2048 2>&1 | tail -2

"$PY" -m evovs_science.modeling.train \
  --features "$S/feat.npz" --labels "$D/dataset_p7b.csv" \
  --output-dir "$S/m" --model xgboost --seed 17 \
  --label-id-column molecule_chembl_id --label-column label \
  --split-manifest "$D/splits/frozen_${SLUG}.json" 2>&1 | tail -3

"$PY" - <<'EOF'
import json
d = json.load(open('/home/linhan_cluster/evo_vs_rsi/.artifacts/p7b_smoke/m/metrics.json'))
print('strategy:', d.get('split_strategy'))
print('counts  :', d.get('counts'))
print('auroc   :', (d.get('metrics') or {}).get('auroc'))
EOF
