#!/usr/bin/env python3
"""Corpus auto-expansion: export a trace for every ticket with scientific jobs.

Idempotent: each ticket directory maps to evolution/traces/<dirname>.json and is
re-exported (digests recomputed from the current artifacts) whenever the job set
changes, so the trace corpus always matches the current digest rules. Run after
each real-ticket batch; wired into the operator closeout flow, not the engine.
"""
import glob
import json
import os
import subprocess
import sys

HOME = pathlib_home = os.path.expanduser("~")
ROOT = os.path.join(HOME, "evo_vs_rsi")
TRACES = os.path.join(ROOT, "evolution", "traces")
PY = os.environ.get("EVOVS_PYTHON") or os.path.join(ROOT, "scientific/.venv/bin/python")


def has_scientific_jobs(ticket_dir: str) -> bool:
    for result in glob.glob(os.path.join(ticket_dir, ".jobs", "*", "result.json")):
        try:
            record = json.load(open(result, encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        if record.get("tool_id", "").startswith(("rdkit.", "ml.", "sklearn.", "screening.", "experience.")):
            if record.get("state") == "SUCCEEDED":
                return True
    return False


def main() -> int:
    tickets = sorted(glob.glob(os.path.join(ROOT, ".artifacts", "state", "work", "*")))
    os.makedirs(TRACES, exist_ok=True)
    exported, skipped = [], []
    for ticket in tickets:
        if not has_scientific_jobs(ticket):
            skipped.append(os.path.basename(ticket))
            continue
        name = os.path.basename(ticket)
        out = os.path.join(TRACES, f"{name}.json")
        subprocess.run([PY, os.path.join(ROOT, "evolution", "trace_export.py"),
                        "--ticket-dir", ticket, "--output", out], check=True)
        exported.append(name)
    print(f"exported={len(exported)} skipped(no scientific jobs)={len(skipped)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
