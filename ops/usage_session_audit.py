#!/usr/bin/env python3
"""Recover token usage from DSH session transcripts, and calibrate it against the ledger.

Why this exists
---------------
`ops/usage_hook.cjs` records provider-reported usage, but it only runs when the
service was started with `NODE_OPTIONS=--require`. Arm A's first target was run
before that line existed in `env.sh`, so its ledger is empty. The session
transcript stores a per-message `usage` block as well, in a slightly different
accounting: `inputTokens` + `cacheReadTokens` + `cacheWriteTokens` is smaller
than the provider's `prompt_tokens`.

This script sums the transcript, sums the ledger over the same ticket window,
and reports the ratio. If the ratio is stable across tickets, a transcript sum
can be corrected into ledger units for the one ticket that has no ledger.

Usage:
  python3 ops/usage_session_audit.py            # audit every run record that has a session
"""

from __future__ import annotations

import glob
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "ops" / "phase7_runs"
SESSIONS = Path(os.path.expanduser("~")) / ".dsh" / "sessions"


def transcript_usage(session_file: Path) -> dict:
    """Sum the per-message usage blocks of a compressed DSH session transcript."""
    try:
        raw = subprocess.run(["zstd", "-dc", str(session_file)],
                             capture_output=True, check=True).stdout
    except (subprocess.SubprocessError, OSError):
        return {}
    calls = prompt = completion = total = 0
    for line in raw.decode("utf-8", "replace").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except ValueError:
            continue
        if entry.get("type") != "assistant/message":
            continue
        usage = (entry.get("data") or {}).get("usage")
        if not usage:
            continue
        calls += 1
        prompt += ((usage.get("inputTokens") or 0)
                   + (usage.get("cacheReadTokens") or 0)
                   + (usage.get("cacheWriteTokens") or 0))
        completion += usage.get("outputTokens") or 0
        total += usage.get("totalTokens") or 0
    return {"calls": calls, "prompt": prompt, "completion": completion, "total": total}


def find_session(workdir: str) -> Path | None:
    """The session directory encodes the workspace path; match on its tail."""
    if not workdir:
        return None
    tail = workdir.rstrip("/").replace("/home/linhan_cluster/evo_vs_rsi", "").strip("/")
    key = tail.replace("/", "-")
    hits = sorted(SESSIONS.glob(f"*{key}*"), key=lambda p: p.stat().st_mtime, reverse=True)
    for hit in hits:
        workers = sorted(hit.glob("worker-*/session.v4.jsonl.zstd"),
                         key=lambda p: p.stat().st_mtime, reverse=True)
        if workers:
            return workers[0]
    return None


def main() -> int:
    rows = []
    for path in sorted(RUNS.glob("[ramw]_[0-9][0-9]_*.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        ledger = record.get("tokens") or {}
        session_file = find_session(record.get("workdir") or "")
        if not session_file:
            continue
        seen = transcript_usage(session_file)
        if not seen.get("calls"):
            continue
        ratio = (ledger.get("total_tokens") / seen["total"]) if ledger.get("total_tokens") and seen.get("total") else None
        rows.append({
            "run": path.stem,
            "ticket": os.path.basename(record.get("workdir") or ""),
            "ledger_calls": ledger.get("llm_calls"),
            "ledger_total": ledger.get("total_tokens"),
            "session_calls": seen["calls"],
            "session_total": seen["total"],
            "ratio": round(ratio, 4) if ratio else None,
        })

    print(f"{'run':<22}{'ledg_calls':>11}{'ledg_total':>12}{'sess_calls':>11}{'sess_total':>12}{'ratio':>8}")
    ratios = []
    for row in rows:
        print(f"{row['run']:<22}{str(row['ledger_calls']):>11}{str(row['ledger_total']):>12}"
              f"{row['session_calls']:>11}{row['session_total']:>12}{str(row['ratio']):>8}")
        if row["ratio"]:
            ratios.append(row["ratio"])
    if ratios:
        mean = sum(ratios) / len(ratios)
        print(f"\nratio (ledger / transcript): mean {mean:.4f}, "
              f"min {min(ratios):.4f}, max {max(ratios):.4f}, n {len(ratios)}")
        print(f"to convert a transcript sum into ledger units, multiply by {mean:.4f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
