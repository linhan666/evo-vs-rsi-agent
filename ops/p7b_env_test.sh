#!/usr/bin/env bash
# Verify that pushing EVOVS_* into tmux's global environment actually reaches a
# service started later, while a tmux server already exists.
#
# This is the mechanism the orchestrator depends on. The previous version relied
# on `tmux kill-server` to force a fresh server — which killed the orchestrator
# itself, since it runs inside tmux. If set-environment -g does not propagate, the
# chain would silently run an arm under the previous arm's group.
set -uo pipefail
ROOT=/home/linhan_cluster/evo_vs_rsi
cd "$ROOT" || exit 1
PY=$ROOT/scientific/.venv/bin/python

echo "sessions before: $(tmux ls 2>&1 | tr '\n' ' ')"

scripts/dsh-superagent stop >/dev/null 2>&1
sleep 2
tmux kill-session -t dsh-superagent >/dev/null 2>&1 || true

tmux set-environment -g EVOVS_GROUP memory
tmux set-environment -g EVOVS_PYTHON "$PY"
tmux set-environment -g EVOVS_DATA_ROOT "$ROOT/scientific/.artifacts"
tmux set-environment -g EVOVS_MODEL deepseek-flash
tmux set-environment -g EVOVS_USAGE_LOG "$ROOT/scientific/.artifacts/usage_envtest.jsonl"
tmux set-environment -g NODE_OPTIONS "--require $ROOT/ops/usage_hook.cjs"

. ./env.sh >/dev/null 2>&1
scripts/dsh-superagent start >/dev/null 2>&1
sleep 6

pid=$(ps -eo pid,cmd | grep 'bin/dsh --profile superagent' | grep -v grep | awk '{print $1}' | head -1)
echo "pid: $pid"
if [ -z "$pid" ]; then echo "RESULT: FAIL (service did not start)"; exit 1; fi

env_dump=$(tr '\0' '\n' < "/proc/$pid/environ")
echo "group    : $(printf '%s' "$env_dump" | grep '^EVOVS_GROUP=' || echo MISSING)"
echo "usage    : $(printf '%s' "$env_dump" | grep '^EVOVS_USAGE_LOG=' || echo MISSING)"
echo "node_opts: $(printf '%s' "$env_dump" | grep -q 'usage_hook' && echo 'hook present' || echo MISSING)"

if printf '%s' "$env_dump" | grep -qx 'EVOVS_GROUP=memory'; then
  echo "RESULT: PASS (set-environment -g propagates through a pre-existing server)"
else
  echo "RESULT: FAIL (group not applied)"
fi
