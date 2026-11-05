#!/usr/bin/env bash
# Push the EvoVS-RSI repository to GitHub WITHOUT storing a credential helper in
# the repository config. dsh-superagent refuses to launch a Ticket whose directory
# sits inside a git repository whose config adds credentials, so the helper must
# only ever be passed per-command with `-c` (see docs/003-execution.md).
#
# Usage: bash ops/push.sh [remote [refspec...]]   (default: origin main)
set -euo pipefail

REPO="$HOME/evo_vs_rsi"
GH="$HOME/.local/bin/gh-agent"
HELPER="!f() { GH_CONFIG_DIR=$HOME/.config/gh-agent exec $GH auth git-credential \"\$@\"; }; f"

cd "$REPO"
if [ "$#" -gt 0 ]; then
  git -c credential.helper="$HELPER" push "$@"
else
  git -c credential.helper="$HELPER" push origin main
fi
git log --oneline -1
