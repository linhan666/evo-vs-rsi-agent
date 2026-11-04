#!/usr/bin/env bash
# Phase 0 remote runner: baseline install + check, safe to run under nohup.
# Never touches system packages; PATH is scoped to this process only.
set -uo pipefail

export PATH="$HOME/software/node-v22.23.4-linux-x64/bin:$PATH"
REPO="$HOME/evo_vs_rsi"
LOGD="$REPO/logs/phase0"
mkdir -p "$LOGD"

{
  echo "== phase0 install start $(date -Is)"
  echo "node: $(node -v)  npm: $(npm -v)  pnpm: $(pnpm -v)"
  echo "repo: $(git -C "$REPO" rev-parse HEAD)"
} > "$LOGD/pnpm_install.log" 2>&1

cd "$REPO" || exit 1
pnpm install --frozen-lockfile --reporter=append-only >> "$LOGD/pnpm_install.log" 2>&1
INSTALL_RC=$?
echo "== install exit=$INSTALL_RC $(date -Is)" >> "$LOGD/pnpm_install.log"

if [ "$INSTALL_RC" -eq 0 ]; then
  {
    echo "== phase0 check start $(date -Is)"
  } > "$LOGD/pnpm_check.log"
  pnpm check >> "$LOGD/pnpm_check.log" 2>&1
  echo "== check exit=$? $(date -Is)" >> "$LOGD/pnpm_check.log"
else
  echo "== SKIPPED: install failed (rc=$INSTALL_RC), see pnpm_install.log" > "$LOGD/pnpm_check.log"
fi

echo "rc_install=$INSTALL_RC $(date -Is)" > "$LOGD/DONE"
