#!/usr/bin/env bash
# User-space Node.js + pnpm bootstrap for EvoVS-RSI.
# Does NOT touch system packages, does NOT modify ~/.bashrc,
# and only writes under $HOME/software and $HOME/.npm.
set -euo pipefail

NV="${NV:-v22.23.4}"
PNPM_VER="${PNPM_VER:-11.7.0}"
ROOT="$HOME/software"
ND="$ROOT/node-$NV-linux-x64"
URL="https://nodejs.org/dist/$NV/node-$NV-linux-x64.tar.xz"

echo "== target: $ND"
mkdir -p "$ROOT/_dl"

if [ ! -x "$ND/bin/node" ]; then
  echo "== downloading $URL"
  curl -fL --retry 3 --connect-timeout 20 -o "$ROOT/_dl/node-$NV.tar.xz" "$URL"
  echo "== extracting"
  tar -xJf "$ROOT/_dl/node-$NV.tar.xz" -C "$ROOT"
else
  echo "== node already present, skip download"
fi

export PATH="$ND/bin:$PATH"
echo "== node: $(node -v)"
echo "== npm : $(npm -v)"

if [ ! -x "$ND/bin/pnpm" ]; then
  echo "== installing pnpm@$PNPM_VER into user prefix"
  npm install -g "pnpm@$PNPM_VER" --no-fund --no-audit --loglevel=error
else
  echo "== pnpm already present, skip install"
fi

echo "== pnpm: $($ND/bin/pnpm -v)"
echo "== prefix: $($ND/bin/npm config get prefix)"
echo "== done"
