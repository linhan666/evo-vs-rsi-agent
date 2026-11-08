#!/usr/bin/env bash
# Write a machine-readable progress snapshot every 60 s.
#
# Why: the recurring health-check automation can only run hourly (RFC 5545 RRULE
# has no sub-hourly granularity in this tool). "Real time" therefore has to come
# from the machine side: this loop keeps a snapshot fresh to the minute, so any
# observer -- the automation, or a person running one command -- reads current
# state instead of whatever happened to be logged an hour ago.
#
# Output: .artifacts/p7b_status.jsonl (one JSON line per sample, appended; the
# last line is current). Read-only with respect to the experiment.
#
# Run: tmux new-session -d -s p7b-progress -c /home/linhan_cluster/evo_vs_rsi \
#        'bash ops/p7b_progress.sh'

set -uo pipefail
ROOT=/home/linhan_cluster/evo_vs_rsi
cd "$ROOT" || exit 1
PY=$ROOT/scientific/.venv/bin/python
OUT=$ROOT/.artifacts/p7b_status.jsonl
mkdir -p "$ROOT/.artifacts"

while :; do
  "$PY" - <<'EOF' >>"$OUT" 2>/dev/null
import glob, json, os, sqlite3, subprocess, time

ROOT = "/home/linhan_cluster/evo_vs_rsi"
os.chdir(ROOT)

def records(arm):
    return len(glob.glob(f"ops/phase7_runs/{arm}_*_p7b.json"))

def tmux_sessions():
    try:
        out = subprocess.run(["tmux", "ls"], capture_output=True, text=True, timeout=10).stdout
    except Exception:
        return []
    return sorted(line.split(":")[0] for line in out.splitlines() if ":" in line)

def current_target():
    """Most recent 'waiting' line across whichever arm logs exist."""
    best = None
    for path in sorted(glob.glob("ops/p7b_runs/arm_*.log")):
        try:
            with open(path) as f:
                lines = [l.strip() for l in f if "waiting (state=" in l or "sequence complete" in l]
        except OSError:
            continue
        if lines:
            candidate = (os.path.getmtime(path), os.path.basename(path), lines[-1])
            if best is None or candidate[0] > best[0]:
                best = candidate
    if not best:
        return None
    # A finished arm keeps its last "waiting" line forever; reporting it next to
    # records=9 is contradictory and hides a stall (2026-11-09 report).
    if "sequence complete" in best[2]:
        return f"{best[1]}: arm completed"
    head = best[2].split(" waiting")[0]
    return f"{best[1]}: {head} (running)"

def unfinished():
    try:
        con = sqlite3.connect(".artifacts/state/orchestrator.sqlite")
        rows = [json.loads(v) for (v,) in con.execute("SELECT value FROM ticket")]
        return sum(1 for r in rows
                   if r.get("assignments") and not (r["assignments"][-1].get("report") or {}).get("state"))
    except Exception:
        return None

def newest_job_seconds():
    dirs = sorted(glob.glob(".artifacts/state/work/*/"), key=os.path.getmtime, reverse=True)
    if not dirs:
        return None
    jobs = sorted(glob.glob(dirs[0] + ".jobs/*/"), key=os.path.getmtime, reverse=True)
    if not jobs:
        return None
    return int(time.time() - os.path.getmtime(jobs[0]))

def science_processes():
    try:
        out = subprocess.run(["ps", "-eo", "cmd"], capture_output=True, text=True, timeout=10).stdout
        return sum(1 for line in out.splitlines() if "evovs_science" in line and "grep" not in line)
    except Exception:
        return None

print(json.dumps({
    "ts": time.strftime("%Y-%m-%dT%H:%M:%S"),
    "records": {arm: records(arm) for arm in ("r", "m", "a", "w")},
    "sessions": tmux_sessions(),
    "current_target_line": current_target(),
    "unfinished_tickets": unfinished(),
    "newest_job_age_seconds": newest_job_seconds(),
    "science_processes": science_processes(),
}, ensure_ascii=False))
EOF
  sleep 60
done
