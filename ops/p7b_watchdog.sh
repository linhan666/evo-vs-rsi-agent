#!/usr/bin/env bash
# Independent watchdog for the phase7b chain.
#
# History (read before changing the signal)
# -----------------------------------------
# v1 used "ticket count unchanged for 20 min" and produced nothing but false
# positives: a ticket is created once per *target*, so the count legitimately sits
# still for the 15-20 minutes a target takes. Worse, its arm-name lookup returned
# "p7b-r" while the mapping expected "r", so every restart silently no-opped —
# which is the only reason it did not restart the service every two minutes and
# destroy the run.
#
# The real failure it must catch: the assessment LLM call hangs, so a trigger never
# becomes a ticket and the driver re-submits the same task forever. The reliable
# signature is "the driver is alive, nothing scientific is running, and no new job
# has appeared for a long time".
#
# Run: tmux new-session -d -s p7b-watch -c /home/linhan_cluster/evo_vs_rsi \
#        'bash ops/p7b_watchdog.sh'

set -uo pipefail
ROOT=/home/linhan_cluster/evo_vs_rsi
cd "$ROOT" || exit 1
LOG=$ROOT/ops/p7b_runs/watchdog.log
PY=$ROOT/scientific/.venv/bin/python
WORK=$ROOT/.artifacts/state/work
IDLE_LIMIT=1080   # 18 min with no new job and nothing running == stuck
mkdir -p "$ROOT/ops/p7b_runs"

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" >>"$LOG"; }

arm_driver() {  # prints r|m|a or nothing
  tmux ls 2>/dev/null | sed -n 's/^p7b-\([rma]\):.*/\1/p' | head -1
}

newest_job_age() {
  # seconds since the most recently touched job directory, or 99999 if none
  local dir job
  dir=$(ls -dt "$WORK"/*/ 2>/dev/null | head -1)
  if [ -z "$dir" ]; then echo 99999; return; fi
  job=$(ls -dt "${dir}.jobs"/*/ 2>/dev/null | head -1)
  if [ -z "$job" ]; then echo 99999; return; fi
  echo $(( $(date +%s) - $(stat -c %Y "$job") ))
}

science_running() {
  ps -eo cmd 2>/dev/null | grep -c '[e]vovs_science' || true
}

restart_service() {  # $1 arm letter r|m|a
  local arm=$1 sgroup usage
  case "$arm" in
    r) sgroup=rsi;    usage=usage_p7b_r.jsonl ;;
    m) sgroup=memory; usage=usage_p7b_m.jsonl ;;
    a) sgroup=fixed;  usage=usage_p7b_a.jsonl ;;
    *) log "ERROR: unknown arm '$arm'"; return 1 ;;
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
stuck=0

while :; do
  sleep 60
  arm=$(arm_driver)
  if [ -z "$arm" ]; then
    log "no arm driver running; watchdog exits"
    break
  fi
  age=$(newest_job_age)
  busy=$(science_running)
  if [ "$age" -ge "$IDLE_LIMIT" ] && [ "$busy" -eq 0 ]; then
    stuck=$((stuck + 1))
    log "suspect: arm=$arm no new job for ${age}s, 0 science processes (${stuck}/3)"
    if [ "$stuck" -ge 3 ]; then
      log "STUCK confirmed on arm $arm -- restarting the service"
      restart_service "$arm" && stuck=0
      sleep 60
    fi
  else
    stuck=0
  fi
done
