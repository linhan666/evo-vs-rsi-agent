#!/usr/bin/env bash
# One-command status for the phase7b chain. Read-only.
# Prints a compact block that answers "where is it, and is anything stuck".
#
#   bash ops/p7b_status.sh
set -uo pipefail
ROOT=/home/linhan_cluster/evo_vs_rsi
cd "$ROOT" || exit 1

echo "== time =="
date '+%Y-%m-%d %H:%M'

echo
echo "== sessions =="
tmux ls 2>&1 | sed 's/^/  /'

echo
echo "== orchestrator =="
grep -E 'step |=== arm|FATAL|service up|driver up|finished' ops/p7b_runs/orchestrator.log 2>/dev/null | tail -6 | sed 's/^/  /'

echo
echo "== watchdog (last 4) =="
tail -4 ops/p7b_runs/watchdog.log 2>/dev/null | sed 's/^/  /' || echo "  (none)"

echo
echo "== records (expect 36 total: 3 agent arms x 9 + W x 9) =="
for arm in r m a w; do
  n=$(ls ops/phase7_runs/${arm}_*_p7b.json 2>/dev/null | wc -l)
  printf '  %s: %s\n' "$arm" "$n"
done

echo
echo "== current workdir =="
newest=$(ls -dt .artifacts/state/work/*/ 2>/dev/null | head -1)
if [ -n "$newest" ]; then
  echo "  $newest"
  echo "  jobs: $(ls -d "${newest}.jobs"/*/ 2>/dev/null | wc -l)"
  age=$(( $(date +%s) - $(stat -c %Y "$newest") ))
  echo "  last touched: ${age}s ago"
fi

echo
echo "== science processes =="
ps -eo etime,pcpu,cmd 2>/dev/null | grep '[e]vovs_science' | cut -c1-100 | sed 's/^/  /' || echo "  none running"

echo
echo "== latest arm log =="
for f in ops/p7b_runs/arm_r.log ops/p7b_runs/arm_m.log ops/p7b_runs/arm_a.log; do
  [ -f "$f" ] && { echo "  --- $f"; tail -2 "$f" | sed 's/^/    /'; }
done
