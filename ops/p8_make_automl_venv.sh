#!/usr/bin/env bash
# Build an isolated interpreter for the AutoML baseline.
#
# Why a second venv
# -----------------
# AutoGluon requires scikit-learn >= 1.6; the agent arms run on 1.5.2 and their 81 p7
# records were produced there. Upgrading in place would silently change the baseline's
# environment, so the AutoML baseline gets its own interpreter and the agent arms keep
# theirs.
#
# This box has no ensurepip, so the venv is created --without-pip and pip is borrowed
# from the existing venv (same CPython 3.12, so the wheels are compatible).
set -uo pipefail
ROOT=/home/linhan_cluster/evo_vs_rsi
cd "$ROOT" || exit 1
NEW=$ROOT/scientific/.venv-automl
LOG=$ROOT/ops/p7b_runs/venv_automl.log
MIRROR=https://pypi.tuna.tsinghua.edu.cn/simple

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$LOG"; }

if [ -x "$NEW/bin/python" ]; then
  log "venv already exists: $NEW"
else
  log "creating $NEW"
  python3 -m venv --without-pip "$NEW" || { log "FATAL: venv creation failed"; exit 1; }
  SITE=$NEW/lib/python3.12/site-packages
  mkdir -p "$SITE"
  for pkg in pip setuptools wheel; do
    if [ -d "$ROOT/scientific/.venv/lib/python3.12/site-packages/$pkg" ]; then
      cp -r "$ROOT/scientific/.venv/lib/python3.12/site-packages/$pkg" "$SITE/" 2>/dev/null || true
    fi
  done
  cp -r "$ROOT"/scientific/.venv/lib/python3.12/site-packages/pip-*.dist-info "$SITE/" 2>/dev/null || true
fi

"$NEW/bin/python" -m pip --version >>"$LOG" 2>&1 || { log "FATAL: pip bootstrap failed"; exit 1; }
log "pip ready: $("$NEW/bin/python" -m pip --version)"

# Deliberately NOT [all]: that pulls torch (526 MB), spacy and fastai for the neural
# and text models, none of which exist in the bounded model-type list this experiment
# compares (linear / RF / extra trees / lightgbm / xgboost / catboost). Downloading them
# would add ~2 GB and buy nothing.
log "installing autogluon.tabular with the GBM extras only"
"$NEW/bin/python" -m pip install --no-input --disable-pip-version-check \
  -i "$MIRROR" "autogluon.tabular[lightgbm,catboost,xgboost]" >>"$LOG" 2>&1
code=$?
if [ $code -ne 0 ]; then
  log "install with GBM extras failed ($code); retrying base package"
  "$NEW/bin/python" -m pip install --no-input --disable-pip-version-check \
    -i "$MIRROR" autogluon.tabular >>"$LOG" 2>&1
  code=$?
fi
# rdkit is needed by the locked-evaluation wrapper: it re-featurises the protected test
# set inside this venv, since the AutoGluon predictor cannot be loaded by the .venv one.
"$NEW/bin/python" -m pip install --no-input --disable-pip-version-check \
  -i "$MIRROR" rdkit >>"$LOG" 2>&1 || log "WARN: rdkit install failed (locked wrapper will not work)"
if [ $code -ne 0 ]; then log "FATAL: autogluon install failed"; exit 1; fi

log "install done"
"$NEW/bin/python" -m pip freeze > "$ROOT/ops/p8_venv_automl.freeze.txt" 2>>"$LOG"
du -sh "$NEW" >>"$LOG" 2>&1
"$NEW/bin/python" - <<'EOF' >>"$LOG" 2>&1
import sklearn, numpy, pandas
print(f"versions: sklearn {sklearn.__version__} numpy {numpy.__version__} pandas {pandas.__version__}")
try:
    from autogluon.tabular import __version__ as ag
    print(f"autogluon.tabular {ag}")
except Exception as e:
    print("autogluon import failed:", e)
EOF
log "done: freeze + size recorded"
