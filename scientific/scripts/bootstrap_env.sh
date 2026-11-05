#!/usr/bin/env bash
# Reproducible Python environment for the scientific package (Blueprint P1-01).
#
# The host has python3 but no pip (docs/BLOCKERS.md B-004), so this bootstraps pip
# from a wheel fetched from the Tsinghua mirror, then installs the pinned set into
# scientific/.venv. Nothing outside scientific/ is written.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
VENV="$ROOT/.venv"
DL="$ROOT/.dl"
INDEX="https://pypi.tuna.tsinghua.edu.cn/simple"
JSON_API="https://pypi.tuna.tsinghua.edu.cn/pypi/pip/json"
mkdir -p "$DL"

PY="${PYTHON:-python3}"
echo "== interpreter: $($PY -V 2>&1)"

if [ ! -x "$VENV/bin/python" ]; then
  echo "== creating venv without pip"
  "$PY" -m venv --without-pip "$VENV"
fi

if ! "$VENV/bin/python" -m pip --version >/dev/null 2>&1; then
  echo "== bootstrapping pip from a wheel"
  WHEEL_URL="$("$PY" - "$JSON_API" <<'PY'
import json, sys, urllib.request
with urllib.request.urlopen(sys.argv[1], timeout=60) as response:
    data = json.load(response)
wheels = [item["url"] for item in data["urls"] if item["filename"].endswith("py3-none-any.whl")]
if not wheels:
    raise SystemExit("no pip wheel found in the JSON API")
print(wheels[0])
PY
)"
  echo "== $WHEEL_URL"
  WHEEL_NAME="$(basename "$WHEEL_URL")"
  curl -fsSL -o "$DL/$WHEEL_NAME" "$WHEEL_URL"
  "$VENV/bin/python" "$DL/$WHEEL_NAME/pip" install --no-index --no-deps "$DL/$WHEEL_NAME"
fi

SITE="$("$VENV/bin/python" -c 'import sysconfig; print(sysconfig.get_paths()["purelib"])')"
echo "$ROOT/src" > "$SITE/evovs_science.pth"
echo "== package path: $SITE/evovs_science.pth -> $ROOT/src"

echo "== pip: $("$VENV/bin/python" -m pip --version)"
"$VENV/bin/python" -m pip install --index-url "$INDEX" --disable-pip-version-check -r "$ROOT/requirements.txt"

echo "== versions"
"$VENV/bin/python" - <<'PY'
import numpy, sklearn, rdkit, joblib
print(f"numpy={numpy.__version__} scikit-learn={sklearn.__version__} rdkit={rdkit.__version__} joblib={joblib.__version__}")
PY
echo "== done: $VENV/bin/python"
