#!/usr/bin/env bash
# Independent watchdog for the phase7b chain.
#
# Why it exists
# -------------
# Twice today the assessment step hung: the trigger was accepted into `trigger`,
# the LLM call never returned, and no `decision` row was ever written — so no
# ticket appeared and the driver kept re-submitting the same task. Counting
# `trigger - decision` does NOT detect this, because the local source dedupes by
# task id: the trigger table stops growing too. The only reliable signal is
# "the arm driver is alive but no new ticket has appeared for a long time".
#
# It restarts the service (which clears the stuck LLM client) and logs loudly.
# It never touches the orchestrator or the drivers.
#
# Run: tmux new-session -d -s p7b-watch -c /home/linhan_cluster/evo_vs_rsi \
#        'bash ops/p7b_watchdog.sh'

set -uo pipefail
ROOT=/home/linhan_cluster/evo_vs_rsi
cd "$ROOT" || exit 1
LOG=$ROOT/ops/p7b_runs/watchdog.log
PY=$ROOT/scientific/.venv/bin/python
IDLE_LIMIT=1200   # 20 min without a new ticket while a driver runs == stuck
mkdir -p "$ROOT/ops/p7b_runs"

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" >>"$LOG"; }

ticket_count() {
  python3 - <<'EOF'
import sqlite3
print(sqlite3.connect('.artifacts/state/orchestrator.sqlite').execute('SELECT COUNT(*) FROM ticket').fetchone()[0])
EOF
}

arm_driver_alive() {
  tmux ls 2>/dev/null | grep -qE '^p7b-(r|m|a):'
}

current_arm() {
  tmux ls 2>/dev/null | grep -oE '^p7b-(r|m|a):' | head -1 | tr -d ':'
}

restart_service() {  # $1 arm letter
  local arm=$1 sgroup usage
  case "$arm" in
    r) sgroup=rsi;    usage=usage_p7b_r.jsonl ;;
    m) sgroup=memory; usage=usage_p7b_m.jsonl ;;
    a) sgroup=fixed;  usage=usage_p7b_a.jsonl ;;
    *) return 1 ;;
  esac
  log "restarting service: arm=$arm group=$sgroup"
  scripts/dsh-superagent stop >>"$LOG" 2>&1
  sleep 3
  tmux kill-session -t dsh-superagent >/dev/null 2>&1 || true
  sleep 1
  tmux set-environment -g EVOVS_GROUP "$sgroup"
  tmux set-environment -g EVOVS_PYTHON "$PY"
  tmux set-environment -g EVOVS_DATA_ROOT "$ROOT/scientific/.artifacts"
  tmux set-environment -g EVOVS_MODEL deepseek-flash
  tmux set-environment -g EVOVS_USAGE_LOG "$ROOT/scientific/.artifacts/$usage"
  tmux set-environment -g NODE_OPTIONS "--require $ROOT/ops/usage_hook.cjs"
  set +u; . ./env.sh >/dev/null 2>&1; set -u
  scripts/dsh-superagent start >>"$LOG" 2>&1
  sleep 8
  local pid
  pid=$(ps -eo pid,cmd | grep 'bin/dsh --profile superagent' | grep -v grep | awk '{print $1}' | head -1)
  if [ -n "$pid" ] && tr '\0' '\n' < "/proc/$pid/environ" | grep -qx "EVOVS_GROUP=$sgroup"; then
    log "service back up: group=$sgroup pid=$pid"
    return 0
  fi
  log "ERROR: service did not come back with group=$sgroup"
  return 1
}

log "watchdog start (pid $$, idle limit ${IDLE_LIMIT}s)"
last_count=$(ticket_count)
last_change=$(date +%s)

while :; do
  sleep 60
  if ! arm_driver_alive; then
    log "no arm driver running; watchdog exits"
    break
  fi
  count=$(ticket_count)
  if [ "$count" != "$last_count" ]; then
    last_count=$count
    last_change=$(date +%s)
    continue
  fi
  idle=$(( $(date +%s) - last_change ))
  if [ "$idle" -ge "$IDLE_LIMIT" ]; then
    arm=$(current_arm)
    log "STUCK: arm $arm alive, ticket count frozen at $count for ${idle}s"
    restart_service "$arm" && last_change=$(date +%s)
    # give the agent a moment to pick the ticket up again
    sleep 60
    last_count=$(ticket_count)
  fi
done
