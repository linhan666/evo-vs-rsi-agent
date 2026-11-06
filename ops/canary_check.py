#!/usr/bin/env python3
"""Integrity canary for the assets a same-user escape would touch.

Without OS-level isolation (B-005: no dedicated account possible), detection is
the remaining control. The canary watches only files WE own or manage — never
other projects: the operator's API key file, the agent's GitHub token store, a
canary file at the home root, and the protected directory's permissions.

  python3 ops/canary_check.py --init    # record baseline (creates the canary file)
  python3 ops/canary_check.py           # verify; exit 1 on drift
"""
import argparse
import hashlib
import json
import os
import pathlib
import stat
import sys

HOME = pathlib.Path.home()
FILES = [
    HOME / ".config/evo_vs_rsi/secrets.env",
    HOME / ".config/gh-agent/hosts.yml",
    HOME / "evovs_canary.txt",
]
PROTECTED = HOME / "evo_vs_rsi/protected"
BASELINE = HOME / "evo_vs_rsi/.artifacts/canary_baseline.json"


def sha256(path: pathlib.Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def snapshot() -> dict:
    state: dict[str, object] = {}
    for path in FILES:
        if path.exists():
            state[str(path)] = {"sha256": sha256(path), "mode": stat.S_IMODE(path.stat().st_mode)}
        else:
            state[str(path)] = {"missing": True}
    if PROTECTED.exists():
        state[str(PROTECTED)] = {"mode": stat.S_IMODE(PROTECTED.stat().st_mode)}
        for child in sorted(PROTECTED.iterdir()):
            state[str(child)] = {"mode": stat.S_IMODE(child.stat().st_mode)}
    return state


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--init", action="store_true", help="create the canary file and record the baseline")
    parser.add_argument("--json", action="store_true", help="machine-readable result for the promotion gate")
    args = parser.parse_args()

    if args.init:
        canary = FILES[-1]
        if not canary.exists():
            canary.write_text("evovs integrity canary — do not edit\n", encoding="utf-8")
            os.chmod(canary, 0o600)
        BASELINE.write_text(json.dumps(snapshot(), indent=2) + "\n", encoding="utf-8")
        print("baseline recorded:", BASELINE)
        return 0

    if not BASELINE.exists():
        print("no baseline; run with --init first")
        return 1

    baseline = json.loads(BASELINE.read_text(encoding="utf-8"))
    current = snapshot()
    drift: list[str] = []
    for key, expected in baseline.items():
        actual = current.get(key, {"missing": True})
        if actual != expected:
            drift.append(key)
    if drift:
        if args.json:
            print(json.dumps({"state": "error", "drift": drift}, indent=2))
            return 1
        print("DRIFT DETECTED — these watched assets changed:")
        for key in drift:
            print(" ", key)
        return 1
    if args.json:
        print(json.dumps({"state": "ok", "drift": [], "watched": len(baseline)}, indent=2))
        return 0
    print("all watched assets intact")
    return 0


if __name__ == "__main__":
    sys.exit(main())
