#!/usr/bin/env bash
# Launch arm R' : the R arm re-run under v7 (EVOVS_TRAIN_JOBS=8, gate-certified).
#
# Why a new prefix (p7c) instead of reusing p7b:
#  * task ids are the trigger identity downstream; re-submitting the same id after
#    an earlier decision is treated as already-addressed and never re-assessed
#    (that is what stalled the M arm for 40 minutes on 2026-11-09)
#  * records must not collide with the completed R arm, so they land as *_p7c
#
# The experience store is a fresh file on purpose: R' is a new arm, and inheriting
# R's store would confound "promoted harness" with "more accumulated memory".
set -uo pipefail
ROOT=/home/linhan_cluster/evo_vs_rsi
cd "$ROOT" || exit 1
PY=$ROOT/scientific/.venv/bin/python
LOG=$ROOT/ops/p7b_runs/launch_rprime.log
mkdir -p "$ROOT/ops/p7b_runs"

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$LOG"; }

# 1. task files for the new prefix
"$PY" - <<'EOF'
import json, shutil
from pathlib import Path
root = Path("/home/linhan_cluster/evo_vs_rsi")
src, dst = root / "ops/phase7b_custom", root / "ops/phase7c_custom"
dst.mkdir(parents=True, exist_ok=True)
n = 0
for path in sorted(src.glob("p7b_r_*.json")):
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["task_id"] = payload["task_id"].replace("p7b_", "p7c_", 1)
    payload["title"] = payload["title"].replace("Phase7b", "Phase7c R'")
    (dst / f"{payload['task_id']}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    n += 1
print(f"p7c task files: {n}")
EOF

# 2. service back to group rsi, with the same hard verification as the orchestrator
scripts/dsh-superagent stop >>"$LOG" 2>&1
sleep 3
tmux kill-session -t =dsh-superagent >/dev/null 2>&1 || true
sleep 1
tmux set-environment -g EVOVS_GROUP rsi
tmux set-environment -g EVOVS_PYTHON "$PY"
tmux set-environment -g EVOVS_DATA_ROOT "$ROOT/scientific/.artifacts"
tmux set-environment -g EVOVS_MODEL deepseek-flash
tmux set-environment -g EVOVS_USAGE_LOG "$ROOT/scientific/.artifacts/usage_p7c_r.jsonl"
tmux set-environment -g NODE_OPTIONS "--require $ROOT/ops/usage_hook.cjs"
set +u; . ./env.sh >/dev/null 2>&1; set -u
export EVOVS_GROUP=rsi EVOVS_PYTHON="$PY" EVOVS_DATA_ROOT="$ROOT/scientific/.artifacts"
export EVOVS_MODEL=deepseek-flash EVOVS_USAGE_LOG="$ROOT/scientific/.artifacts/usage_p7c_r.jsonl"
scripts/dsh-superagent start >>"$LOG" 2>&1
sleep 8
pid=$(scripts/dsh-superagent status 2>/dev/null | "$PY" -c 'import json,sys
try: print((json.load(sys.stdin).get("pids") or [""])[0])
except Exception: print("")')
if [ -z "$pid" ] || ! tr '\0' '\n' < "/proc/$pid/environ" | grep -qx 'EVOVS_GROUP=rsi'; then
  log "FATAL: service did not come back with group rsi (pid=$pid)"
  exit 1
fi
log "service up: group=rsi pid=$pid"

# 3. driver
tmux kill-session -t =p7b-r >/dev/null 2>&1 || true
tmux new-session -d -s p7b-r -c "$ROOT" \
  "python3 -u ops/phase7_seq.py --group r --prefix p7c --tasks-dir ops/phase7c_custom \
   --label p7c --store $ROOT/scientific/.artifacts/experience/experience_r_p7c.json \
   >> ops/p7b_runs/arm_rprime.log 2>&1"
sleep 12
tmux has-session -t =p7b-r 2>/dev/null || { log "FATAL: R' driver did not stay up"; exit 1; }
log "R' driver up: tmux p7b-r (prefix p7c, label p7c)"
