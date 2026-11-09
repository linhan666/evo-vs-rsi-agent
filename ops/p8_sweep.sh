#!/usr/bin/env bash
# Budget sweep: the experiment the design asks for.
#
# For each budget B in 100 50 20 10 5:
#   W        exhaustive over the first B configurations, no LLM
#   A / M / R  the same bounded space, driven by the agent (no memory / memory /
#              memory + harness.propose), each stopped wherever it chooses
#
# Every arm faces the same frozen space and the same budget; only who decides
# differs. That is what makes "reached this quality with fewer draws" measurable.
#
# Order: W first (it defines the reference at that budget), then A, M, R. Records
# land as <arm>_NN_<target>_p8b<B>.json so the analysis can pair by label.
#
# Run: tmux new-session -d -s p8-sweep -c /home/linhan_cluster/evo_vs_rsi \
#        'bash ops/p8_sweep.sh 100 50 20 10 5'
set -uo pipefail
ROOT=/home/linhan_cluster/evo_vs_rsi
cd "$ROOT" || exit 1
PY=$ROOT/scientific/.venv/bin/python
LOG=$ROOT/ops/p7b_runs/p8_sweep.log
mkdir -p "$ROOT/ops/p7b_runs"

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$LOG"; }

BUDGETS=${*:-"100 50 20 10 5"}

arm_session() {  # prints r|m|a for a live p7b-<arm> session, exact match only
  for candidate in r m a; do
    if tmux has-session -t "=p7b-$candidate" 2>/dev/null; then echo "$candidate"; return; fi
  done
}

start_service() {  # $1 group
  local group=$1
  scripts/dsh-superagent stop >>"$LOG" 2>&1
  sleep 3
  tmux kill-session -t =dsh-superagent >/dev/null 2>&1 || true
  sleep 1
  tmux set-environment -g EVOVS_GROUP "$group"
  tmux set-environment -g EVOVS_PYTHON "$PY"
  tmux set-environment -g EVOVS_DATA_ROOT "$ROOT/scientific/.artifacts"
  tmux set-environment -g EVOVS_MODEL deepseek-flash
  tmux set-environment -g EVOVS_USAGE_LOG "$ROOT/scientific/.artifacts/usage_p8_${group}.jsonl"
  tmux set-environment -g NODE_OPTIONS "--require $ROOT/ops/usage_hook.cjs"
  set +u; . ./env.sh >/dev/null 2>&1; set -u
  export EVOVS_GROUP="$group" EVOVS_PYTHON="$PY" EVOVS_DATA_ROOT="$ROOT/scientific/.artifacts"
  export EVOVS_MODEL=deepseek-flash EVOVS_USAGE_LOG="$ROOT/scientific/.artifacts/usage_p8_${group}.jsonl"
  scripts/dsh-superagent start >>"$LOG" 2>&1
  sleep 8
  local pid
  pid=$(scripts/dsh-superagent status 2>/dev/null | "$PY" -c 'import json,sys
try: print((json.load(sys.stdin).get("pids") or [""])[0])
except Exception: print("")')
  if [ -z "$pid" ] || ! tr '\0' '\n' < "/proc/$pid/environ" | grep -qx "EVOVS_GROUP=$group"; then
    log "FATAL: service did not come up with group=$group (pid=$pid)"; return 1
  fi
  log "service up: group=$group pid=$pid"
}

run_w() {  # $1 budget
  local budget=$1 label="p8w$1"
  log "=== W budget $budget ==="
  "$PY" ops/p8_workflow.py --all --budget "$budget" --label "$label" >>"$LOG" 2>&1 \
    && log "W budget $budget done" || log "W budget $budget FAILED"
}

run_agent_arm() {  # $1 arm letter, $2 group, $3 budget
  local arm=$1 group=$2 budget=$3 prefix="p8b$budget"
  local store="$ROOT/scientific/.artifacts/experience/experience_p8_${arm}_b${budget}.json"
  log "=== arm $arm budget $budget ==="
  start_service "$group" || return 1
  tmux kill-session -t "=p7b-$arm" >/dev/null 2>&1 || true
  local store_arg=""
  [ "$arm" != "a" ] && store_arg="--store $store"
  tmux new-session -d -s "p7b-$arm" -c "$ROOT" \
    "python3 -u ops/phase7_seq.py --group $arm --prefix $prefix --tasks-dir ops/p8_tasks \
     --label $prefix --budget-limit $budget $store_arg \
     --usage-log usage_p8_${group}.jsonl >> ops/p7b_runs/arm_${arm}_${prefix}.log 2>&1"
  sleep 15
  tmux has-session -t "=p7b-$arm" 2>/dev/null || { log "FATAL: arm $arm driver died"; return 1; }
  log "arm $arm driver up ($prefix)"
  while tmux has-session -t "=p7b-$arm" 2>/dev/null; do sleep 60; done
  tmux kill-session -t "=p7b-$arm" >/dev/null 2>&1 || true
  local n
  n=$(ls ops/phase7_runs/${arm}_*_${prefix}.json 2>/dev/null | wc -l)
  log "arm $arm budget $budget finished, records: $n"
  "$PY" ops/p8_finalize.py --label "$prefix" >>"$LOG" 2>&1 && log "finalized $prefix"
}

log "p8 sweep start (budgets: $BUDGETS)"
for budget in $BUDGETS; do
  run_w "$budget"
  "$PY" ops/p8_finalize.py --label "p8w$budget" >>"$LOG" 2>&1 || true
  run_agent_arm a fixed  "$budget"
  run_agent_arm m memory "$budget"
  run_agent_arm r rsi    "$budget"
  log "=== budget $budget complete ==="
done
log "p8 sweep complete"
