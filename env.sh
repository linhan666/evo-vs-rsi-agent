#!/usr/bin/env bash
# Project environment entry point. Usage: source env.sh
# Keeps Node/pnpm user-scoped and loads the model credential from outside the repo.

export EVOVS_NODE_HOME="${EVOVS_NODE_HOME:-$HOME/software/node-v22.23.4-linux-x64}"
case ":$PATH:" in
  *":$EVOVS_NODE_HOME/bin:"*) ;;
  *) export PATH="$EVOVS_NODE_HOME/bin:$PATH" ;;
esac

# Credential file lives outside the repository and is chmod 600.
if [ -f "$HOME/.config/evo_vs_rsi/secrets.env" ]; then
  set -a
  # shellcheck disable=SC1091
  . "$HOME/.config/evo_vs_rsi/secrets.env"
  set +a
fi

# Single-GPU policy: GPU0/1 are used by other people's jobs. Never touch them.
export CUDA_VISIBLE_DEVICES="${CUDA_VISIBLE_DEVICES:-2}"

echo "[env.sh] node=$(node -v 2>/dev/null) pnpm=$(pnpm -v 2>/dev/null) gpu=$CUDA_VISIBLE_DEVICES model=${EVOVS_MODEL:-unset}"

# --- Cost instrumentation ---------------------------------------------------
# ops/usage_hook.cjs sniffs the `usage` block out of every model response and
# appends it to $EVOVS_USAGE_LOG. It rides along via NODE_OPTIONS=--require, so
# it has to be set here: a service started without it writes no token ledger,
# and that arm then cannot be compared with the others on tokens. Discovered
# missing when arm A was launched on 2026-11-07.
_EVOVS_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]:-$0}")" && pwd)"
if [ -f "$_EVOVS_ROOT/ops/usage_hook.cjs" ]; then
  case ":${NODE_OPTIONS:-}:" in
    *":--require $_EVOVS_ROOT/ops/usage_hook.cjs:"*) ;;
    *) export NODE_OPTIONS="${NODE_OPTIONS:-} --require $_EVOVS_ROOT/ops/usage_hook.cjs" ;;
  esac
fi
unset _EVOVS_ROOT
