#!/usr/bin/env bash
# Noise-floor calibration: run the M arm twice more, from empty stores.
#
# Why
# ---
# The only within-arm noise estimate we have is R' vs R: mean locked-AUROC
# difference +0.0112, worst target +0.0965. But that pair also changes the harness
# version, so it is confounded. The R vs A quality claim (+0.0118) sits at exactly
# the same magnitude, which means the honest conclusion right now is "no quality
# effect", not "memory helps".
#
# To settle it we need the distribution of "same arm, same version, same target,
# re-run". Two extra reps of M give three samples per target (M + rep2 + rep3),
# enough for a per-target standard deviation, for ~2 h of compute instead of the
# ~18 h a full four-arm x 3-rep study would cost.
#
# Decision rule afterwards:
#   within-arm SD >> 0.0118  -> the quality claim is dead; publish the cost result
#   within-arm SD << 0.0118  -> the effect may be real; fund the full 3-rep study
#
# Each rep uses its own EMPTY store, because M itself started empty. Reusing a
# filled store would make later reps a different condition.
set -uo pipefail
ROOT=/home/linhan_cluster/evo_vs_rsi
cd "$ROOT" || exit 1
PY=$ROOT/scientific/.venv/bin/python
LOG=$ROOT/ops/p7b_runs/calib.log
mkdir -p "$ROOT/ops/p7b_runs"

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*" | tee -a "$LOG"; }

# service must carry the memory group for the M condition
scripts/dsh-superagent stop >>"$LOG" 2>&1
sleep 3
tmux kill-session -t =dsh-superagent >/dev/null 2>&1 || true
sleep 1
tmux set-environment -g EVOVS_GROUP memory
tmux set-environment -g EVOVS_PYTHON "$PY"
tmux set-environment -g EVOVS_DATA_ROOT "$ROOT/scientific/.artifacts"
tmux set-environment -g EVOVS_MODEL deepseek-flash
tmux set-environment -g EVOVS_USAGE_LOG "$ROOT/scientific/.artifacts/usage_calib_m.jsonl"
tmux set-environment -g NODE_OPTIONS "--require $ROOT/ops/usage_hook.cjs"
set +u; . ./env.sh >/dev/null 2>&1; set -u
export EVOVS_GROUP=memory EVOVS_PYTHON="$PY" EVOVS_DATA_ROOT="$ROOT/scientific/.artifacts"
export EVOVS_MODEL=deepseek-flash EVOVS_USAGE_LOG="$ROOT/scientific/.artifacts/usage_calib_m.jsonl"
scripts/dsh-superagent start >>"$LOG" 2>&1
sleep 8
pid=$(scripts/dsh-superagent status 2>/dev/null | "$PY" -c 'import json,sys
try: print((json.load(sys.stdin).get("pids") or [""])[0])
except Exception: print("")')
if [ -z "$pid" ] || ! tr '\0' '\n' < "/proc/$pid/environ" | grep -qx 'EVOVS_GROUP=memory'; then
  log "FATAL: service not on group memory (pid=$pid)"; exit 1
fi
log "service up: group=memory pid=$pid"

for rep in 2 3; do
  prefix="p7d"
  [ "$rep" = "3" ] && prefix="p7e"
  tasks="ops/calib_m_rep${rep}"
  store="$ROOT/scientific/.artifacts/experience/experience_m_rep${rep}.json"
  rm -f "$store"

  "$PY" - "$rep" "$prefix" "$tasks" <<'EOF'
import json, sys
from pathlib import Path
rep, prefix, out = sys.argv[1], sys.argv[2], sys.argv[3]
root = Path("/home/linhan_cluster/evo_vs_rsi")
dst = root / out
dst.mkdir(parents=True, exist_ok=True)
for path in sorted((root / "ops/phase7b_custom").glob("p7b_m_*.json")):
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["task_id"] = payload["task_id"].replace("p7b_m_", f"{prefix}_m_", 1)
    payload["title"] = f"Calib M rep{rep}: " + payload["title"]
    text = payload["text"].replace("experience_m.json", f"experience_m_rep{rep}.json")
    payload["text"] = text
    (dst / f"{payload['task_id']}.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
print(f"{out}: {len(list(dst.glob('*.json')))} task files")
EOF

  log "=== calib rep${rep} (prefix ${prefix}) ==="
  tmux kill-session -t ="p7b-m" >/dev/null 2>&1 || true
  tmux new-session -d -s p7b-m -c "$ROOT" \
    "python3 -u ops/phase7_seq.py --group m --prefix $prefix --tasks-dir $tasks \
     --label $prefix --store $store --usage-log usage_calib_m.jsonl \
     >> ops/p7b_runs/calib_rep${rep}.log 2>&1"
  sleep 15
  tmux has-session -t =p7b-m 2>/dev/null || { log "FATAL: rep${rep} driver died"; exit 1; }
  log "rep${rep} driver up"

  while tmux has-session -t =p7b-m 2>/dev/null; do sleep 60; done
  n=$(ls ops/phase7_runs/m_*_${prefix}.json 2>/dev/null | wc -l)
  log "rep${rep} finished, records: $n"
done

log "calibration complete"
