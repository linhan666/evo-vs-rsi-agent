#!/usr/bin/env bash
# Unattended phase7b chain.
#
#   0. wait for the round-7 M driver to exit and for its tickets to settle
#   1. extend the locked-eval schema (TS), typecheck, build
#   2. run the four arms in order: R (rsi) -> M (memory) -> A (fixed) -> W (no agent)
#   3. emit the three reports
#
# Every service restart is a hard gate: if the new process does not report the
# expected EVOVS_GROUP and the usage hook in /proc/<pid>/environ, the chain aborts
# instead of silently running an arm under the wrong configuration.
#
# Run it inside tmux:
#   tmux new-session -d -s p7b-all -c /home/linhan_cluster/evo_vs_rsi \
#     'bash ops/p7b_run_all.sh'
#
# set -e is deliberately not used: each stage checks its own failure and the
# orchestrator is expected to log and stop rather than unwind half-deployed.

set -uo pipefail

ROOT=/home/linhan_cluster/evo_vs_rsi
cd "$ROOT" || exit 1

LOGDIR=$ROOT/ops/p7b_runs
LOG=$LOGDIR/orchestrator.log
mkdir -p "$LOGDIR"

EXPERIENCE=$ROOT/scientific/.artifacts/experience
PY=$ROOT/scientific/.venv/bin/python

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$LOG"; }
die() { log "FATAL: $*"; exit 1; }

unfinished_tickets() {
  python3 - <<'EOF'
import json, sqlite3
con = sqlite3.connect('.artifacts/state/orchestrator.sqlite')
rows = [json.loads(v) for (v,) in con.execute('SELECT value FROM ticket')]
print(sum(1 for r in rows
          if r.get('assignments') and not (r['assignments'][-1].get('report') or {}).get('state')))
EOF
}

# ---------------------------------------------------------------- step 0
wait_round7() {
  log "step 0: waiting for the round-7 M driver"
  local waited=0
  while tmux has-session -t phase7-seq-m 2>/dev/null; do
    sleep 60
    waited=$((waited + 60))
    if [ $((waited % 900)) -eq 0 ]; then log "  still waiting (${waited}s)"; fi
  done
  log "step 0: driver gone; waiting for tickets to settle"
  local guard=0 n
  while :; do
    n=$(unfinished_tickets)
    [ "$n" = "0" ] && break
    guard=$((guard + 1))
    [ $guard -gt 120 ] && die "tickets still unfinished after 60 min: $n"
    sleep 30
  done
  log "step 0: clean, 0 unfinished tickets"
}

# ---------------------------------------------------------------- step 1
deploy() {
  log "step 1: extending the locked-eval schema"
  "$PY" ops/p7b_patch.py --include-ts >>"$LOG" 2>&1 || die "p7b_patch failed"
  set +u; . ./env.sh >/dev/null 2>&1; set -u   # env.sh is now -u safe, this is belt and braces
  log "step 1: pnpm typecheck"
  pnpm typecheck >>"$LOG" 2>&1 || die "typecheck failed"
  log "step 1: pnpm build"
  pnpm build >>"$LOG" 2>&1 || die "build failed"
  log "step 1: deploy ok"
}

# ---------------------------------------------------------------- service
service_start() {  # $1 group  $2 usage-log filename
  local group=$1 usage=$2
  scripts/dsh-superagent stop >>"$LOG" 2>&1
  sleep 3
  # NEVER `tmux kill-server` here: this orchestrator runs inside tmux itself, so
  # killing the server killed the chain at 06:16 on the first attempt. Drop only
  # the agent session, then push the arm configuration into tmux's *global*
  # environment so a new session picks it up even though the server predates it.
  tmux kill-session -t dsh-superagent >/dev/null 2>&1 || true
  sleep 1
  tmux set-environment -g EVOVS_GROUP "$group"
  tmux set-environment -g EVOVS_PYTHON "$PY"
  tmux set-environment -g EVOVS_DATA_ROOT "$ROOT/scientific/.artifacts"
  tmux set-environment -g EVOVS_MODEL deepseek-flash
  tmux set-environment -g EVOVS_USAGE_LOG "$ROOT/scientific/.artifacts/$usage"
  tmux set-environment -g NODE_OPTIONS "--require $ROOT/ops/usage_hook.cjs"
  set +u; . ./env.sh >/dev/null 2>&1; set -u   # env.sh is now -u safe, this is belt and braces
  export EVOVS_GROUP="$group"
  export EVOVS_PYTHON="$PY"
  export EVOVS_DATA_ROOT="$ROOT/scientific/.artifacts"
  export EVOVS_MODEL=deepseek-flash
  export EVOVS_USAGE_LOG="$ROOT/scientific/.artifacts/$usage"
  scripts/dsh-superagent start >>"$LOG" 2>&1 || die "service start failed for group $group"
  sleep 5
  local pid
  pid=$(ps -eo pid,cmd | grep 'bin/dsh --profile superagent' | grep -v grep | awk '{print $1}' | head -1)
  [ -n "$pid" ] || die "no service pid after start ($group)"
  tr '\0' '\n' < "/proc/$pid/environ" | grep -qx "EVOVS_GROUP=$group" \
    || die "EVOVS_GROUP=$group not applied (pid $pid) -- tmux server probably survived the stop"
  tr '\0' '\n' < "/proc/$pid/environ" | grep -q 'usage_hook' \
    || die "NODE_OPTIONS missing the usage hook (pid $pid)"
  log "  service up: group=$group pid=$pid"
}

# ---------------------------------------------------------------- arms

pending_triggers() {
  python3 - <<'EOF'
import sqlite3
con = sqlite3.connect('.artifacts/state/orchestrator.sqlite')
t = con.execute('SELECT COUNT(*) FROM trigger').fetchone()[0]
d = con.execute('SELECT COUNT(*) FROM decision').fetchone()[0]
print(t - d)
EOF
}

run_agent_arm() {  # $1 driver group (r|a|m)  $2 service group (rsi|memory|fixed)  $3 store  $4 usage
  local dgroup=$1 sgroup=$2 store=$3 usage=$4
  log "=== arm $dgroup (service group $sgroup) ==="
  service_start "$sgroup" "$usage"
  local cmd="python3 -u ops/phase7_seq.py --group $dgroup --prefix p7b --tasks-dir ops/phase7b_custom --label p7b"
  [ -n "$store" ] && cmd="$cmd --store $store"
  tmux new-session -d -s "p7b-$dgroup" -c "$ROOT" \
    "$cmd >> ops/p7b_runs/arm_${dgroup}.log 2>&1"
  sleep 12
  tmux has-session -t "p7b-$dgroup" 2>/dev/null || die "driver for $dgroup did not stay up"
  log "  driver up: tmux p7b-$dgroup"
  # Watchdog for the failure seen twice: the assessment LLM call hangs and the
  # trigger never gets a decision, so it never becomes a ticket and the driver
  # just re-submits forever. A restart of the service clears the stuck client.
  local stuck=0 pend
  while tmux has-session -t "p7b-$dgroup" 2>/dev/null; do
    sleep 60
    pend=$(pending_triggers 2>/dev/null || echo 0)
    if [ "${pend:-0}" -gt 0 ]; then
      stuck=$((stuck + 1))
      log "  watchdog: $pend trigger(s) without a decision (${stuck}/4)"
      if [ "$stuck" -ge 4 ]; then
        log "  WATCHDOG: assessment stuck for 4 min -- restarting the service"
        service_start "$sgroup" "$usage"
        stuck=0
      fi
    else
      stuck=0
    fi
  done
  local n
  n=$(unfinished_tickets)
  log "  arm $dgroup finished, unfinished tickets: $n"
  [ "$n" = "0" ] || die "arm $dgroup left $n unfinished tickets"
}

run_w_arm() {
  log "=== arm w (fixed workflow) ==="
  "$PY" ops/p7b_workflow.py --all >>"$LOG" 2>&1
  local rc=$?
  log "  arm w exit=$rc (1 means some target failed; records still written)"
}

# ---------------------------------------------------------------- step 3
reports() {
  log "step 3: reports"
  "$PY" ops/phase7_analysis.py --round p7b >>"$LOG" 2>&1 || log "  analysis failed"
  "$PY" ops/phase7_locked.py --round p7b >>"$LOG" 2>&1 || log "  locked report failed"
  "$PY" ops/cv_repeat.py --batch --round p7b >>"$LOG" 2>&1 || log "  cv report failed"
  log "step 3: reports written to ops/phase7_runs/{analysis,locked,cv_repeat}.md"
}

# ---------------------------------------------------------------- main
log "phase7b oracle chain start (pid $$)"
wait_round7
deploy

# each memory-bearing arm starts from an empty store, and they must not share one
rm -f "$EXPERIENCE/experience_r.json" "$EXPERIENCE/experience_m.json"
log "stores cleared for the new round"

run_agent_arm r rsi       "$EXPERIENCE/experience_r.json" usage_p7b_r.jsonl
run_agent_arm m memory    "$EXPERIENCE/experience_m.json" usage_p7b_m.jsonl
run_agent_arm a fixed     ""                              usage_p7b_a.jsonl
run_w_arm
reports

log "phase7b chain complete"
