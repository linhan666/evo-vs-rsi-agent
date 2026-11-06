#!/usr/bin/env python3
"""R-group evolution orchestration: run the self-modification loop between rounds.

This is what separates group R from group M. Without it, R and M are the same arm
and the comparison cannot show anything about harness evolution.

The loop follows the blueprint (§2.2, §11):

    traces -> propose -> (implement) -> shadow -> gate -> versions record

Every stage is already a tested tool. This script only sequences them and refuses
to promote anything that does not pass its gate — the same discipline as the manual
promotions in Phase 5. It never edits code by itself: if a candidate needs an
implementation, it is left as a proposal with the evidence attached, which is what
"harness evolution is a human-decided event" means in practice.

Usage (run between rounds, after tickets finish):
  python ops/phase6_r_evolve.py --round 1
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PY = os.path.join(ROOT, "scientific", ".venv", "bin", "python")
EVOLUTION = os.path.join(ROOT, "evolution")


def run(argv: list[str]) -> tuple[int, str]:
    result = subprocess.run(argv, cwd=ROOT, capture_output=True, text=True)
    return result.returncode, (result.stdout + result.stderr).strip()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="phase6 r evolution")
    parser.add_argument("--round", type=int, required=True)
    parser.add_argument("--gate-existing", action="store_true",
                        help="also try to gate and record candidates that already have shadow reports")
    args = parser.parse_args(argv)

    log = {"round": args.round, "stages": []}

    # 1. pull the round's traces into the corpus
    code, out = run([PY, os.path.join(ROOT, "ops", "sync_traces.py")])
    log["stages"].append({"stage": "sync_traces", "exit": code, "out": out[-300:]})

    # 2. mine candidates from the corpus (rules choose the knob; LLM wording is off
    #    during the experiment so the proposal is reproducible)
    code, out = run([PY, os.path.join(EVOLUTION, "propose.py"), "--emit", "--no-llm"])
    log["stages"].append({"stage": "propose", "exit": code, "out": out[-400:]})

    # 3. every candidate that already has a shadow report goes to the gate; a pass is
    #    recorded as a version. Anything without a report stays a proposal — that is
    #    the honest state, not a failure.
    promoted = []
    for path in sorted(glob.glob(os.path.join(EVOLUTION, "candidates", "*.json"))):
        spec = json.load(open(path, encoding="utf-8"))
        if spec.get("status") not in ("proposal", "shadowed"):
            continue
        name = spec.get("candidate_id", "")
        report = os.path.join(EVOLUTION, "reports", f"shadow_{name}.json")
        if not os.path.exists(report):
            log["stages"].append({"stage": "awaiting-shadow", "candidate": name})
            continue
        if not args.gate_existing:
            continue
        gate_out = os.path.join(EVOLUTION, "reports", f"gate_{name}.json")
        code, out = run([PY, os.path.join(EVOLUTION, "gate.py"),
                        "--spec", path, "--report", report,
                        "--canary", os.path.join(ROOT, ".artifacts", "canary_now.json"),
                        "--output", gate_out])
        verdict = "unknown"
        try:
            verdict = json.load(open(gate_out, encoding="utf-8"))["verdict"]
        except Exception:
            pass
        log["stages"].append({"stage": "gate", "candidate": name, "verdict": verdict})
        if verdict == "pass":
            code, out = run([PY, os.path.join(EVOLUTION, "versions.py"), "record",
                            "--spec", path, "--gate", gate_out,
                            "--note", f"round {args.round} automatic promotion"])
            log["stages"].append({"stage": "record", "candidate": name, "exit": code})
            promoted.append(name)

    log["promoted"] = promoted
    out_path = os.path.join(ROOT, "phase6", f"r_evolution_round{args.round}.json")
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as handle:
        json.dump(log, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"round": args.round, "promoted": promoted,
                      "stages": [s["stage"] for s in log["stages"]]}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
