#!/usr/bin/env bash
# Watchdog + assessment-retry for the phase7b chain.
#
# Two jobs, both consequences of failures actually observed on 2026-11-08/09:
#
# 1. RETRY FAILED ASSESSMENTS. The routing LLM sometimes times out (decision
#    `unavailable`, reason `timeout`). The local source dedupes by task id, so the
#    driver's 30-second re-submissions never create a fresh trigger and the arm
#    sits at zero tickets forever. Deleting the failed trigger + decision lets the
#    next re-submission be assessed again. All nine R-arm tasks went through this
#    path successfully, so the model is fine — it is flaky, and a retry loop is the
#    right shape.
#
# 2. DETECT A DEAD CHAIN. If the arm driver is alive, nothing scientific is
#    running, and no new job has appeared for IDLE_LIMIT, restart the service.
#
# Signals deliberately NOT used: "ticket count unchanged" (a ticket is created
# once per target, so 15-20 min of stillness is normal) and "trigger - decision
# count" (dedupe means neither table grows when the assessment hangs).
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

arm_driver() {
  tmux ls 2>/dev/null | sed -n 's/^p7b-\([rma]\):.*/\1/p' | head -1
}

newest_job_age() {
  # Seconds since the newest job directory, scanning workdirs newest-first for one
  # that actually has jobs. Prints NOTHING when no scorable workdir exists.
  #
  # It used to print 99999 here, and the caller compared it against IDLE_LIMIT --
  # so a workdir that had no .jobs yet (the normal state right after a ticket is
  # claimed) read as "idle for 27 hours". That produced the 2026-11-09 05:05/05:15
  # `no new job for 99999s` reports on a perfectly healthy run, and because the
  # sentinel appeared and disappeared between samples the counter kept resetting
  # between 1/3 and 0/3. An unknown must never accumulate as idleness.
  local dir job
  for dir in $(ls -dt "$WORK"/*/ 2>/dev/null); do
    job=$(ls -dt "${dir}.jobs"/*/ 2>/dev/null | head -1)
    if [ -n "$job" ]; then
      echo $(( $(date +%s) - $(stat -c %Y "$job") ))
      return
    fi
  done
}

science_running() {
  ps -eo cmd 2>/dev/null | grep -c '[e]vovs_science' || true
}

# Delete triggers whose assessment failed so the driver's next re-submission is
# assessed afresh. The decision references the trigger's thread id.
retry_failed_assessments() {
  "$PY" - <<'EOF'
import json, sqlite3
con = sqlite3.connect('.artifacts/state/orchestrator.sqlite')
failed = set()
for (v,) in con.execute('SELECT value FROM decision'):
    d = json.loads(v)
    # only retry the flaky-transport verdict; a real `ignore` should stand
    if d.get('kind') == 'unavailable':
        # the decision points at its triggers through `triggerIds` (an array),
        # not a singular field -- matching the wrong key silently cleared nothing
        for tid in (d.get('triggerIds') or []):
            failed.add(tid)
cleared = 0
for rowid, v in list(con.execute('SELECT rowid, value FROM trigger')):
    t = json.loads(v)
    ids = {t.get('id')} | {th.get('id') for th in (t.get('threads') or [])}
    if ids & failed:
        con.execute('DELETE FROM trigger WHERE rowid=?', (rowid,))
        cleared += 1
if cleared:
    con.commit()
print(cleared)
EOF
}

restart_service() {  # $1 arm letter
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
  pid=$(scripts/dsh-superagent status 2>/dev/null | "$PY" -c 'import json,sys
try: print((json.load(sys.stdin).get("pids") or [""])[0])
except Exception: print("")')
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
    # Do NOT exit. Arm handovers leave a window with no driver, and exiting there
    # is exactly how the A->W stall on 2026-11-09 went unwatched -- the second time
    # a handover lost its monitor. Stay alive and keep sampling.
    idle=$(( ${idle:-0} + 60 ))
    if [ $((idle % 600)) -eq 0 ]; then
      log "no arm driver yet (${idle}s); staying alive for the next arm"
    fi
    continue
  fi
  idle=0

  cleared=$(retry_failed_assessments 2>/dev/null || echo 0)
  if [ "${cleared:-0}" -gt 0 ]; then
    log "retry: cleared $cleared trigger(s) whose assessment failed; the next re-submission will be re-assessed"
    stuck=0
    continue
  fi

  age=$(newest_job_age)
  busy=$(science_running)
  if [ -z "$age" ]; then
    # nothing scorable yet (a fresh ticket, or every workdir is empty): not evidence
    stuck=0
    continue
  fi
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
