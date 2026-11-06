#!/usr/bin/env python3
"""Operator tool: write the path-resolution candidate spec and run the gate on it."""
import json
import os
import subprocess
import sys

ROOT = os.path.expanduser("~/evo_vs_rsi")

SPEC = {
    "candidate_id": "manual-path-resolution",
    "version": "0.1.0",
    "status": "proposal",
    "changes": [{
        "type": "experiment",
        "key": "preflight:input-paths",
        "value": "resolve relative input paths against EVOVS_DATA_ROOT and the repo root, "
                 "and name the closest matches when a file truly does not exist",
    }],
    "hypothesis": "Resolving a relative input path against the data root turns the five repo-relative "
                  "failures into successes, while a file that exists nowhere still fails with the closest "
                  "matches listed.",
    "acceptance": {"equivalence": 1.0, "failures_in_replay": 2,
                   "failure_clusters": ["rdkit.featurize::FileNotFoundError"]},
    "risk": "Resolving a path the caller did not intend could read the wrong file; the resolution only "
            "fires when the literal path is missing.",
    "scope_note": "Two remaining failures are nope.csv, which does not exist under any root; no resolution "
                  "rule can make them succeed, hence the allowance of 2.",
    "rollback": "drop resolve_input_path from chemistry/featurize.py, screening/predict.py and "
                "modeling/train.py and pass the caller's path straight to open()",
    "basis": {
        "generated_by": "operator",
        "kind": "failure-recurrence",
        "tool_id": "rdkit.featurize",
        "evidence": {
            "tickets": ["engine-pass-check-eb69ace79bac.json"],
            "recent_hits": 7,
            "clusters": [{
                "cluster": "rdkit.featurize::FileNotFoundError",
                "recent_hits": 7,
                "claimed": True,
                "samples": [
                    "FileNotFoundError: No such file or directory: '.artifacts/chembl/oprm1/ki/dataset.csv'",
                    "FileNotFoundError: No such file or directory: 'scientific/.artifacts/chembl/oprm1/ki/dataset.csv'",
                ],
            }],
        },
    },
}


def main() -> int:
    spec_path = os.path.join(ROOT, "evolution", "candidates", "manual-path-resolution.json")
    with open(spec_path, "w", encoding="utf-8") as handle:
        json.dump(SPEC, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print("spec written:", spec_path)

    gate_out = os.path.join(ROOT, "evolution", "reports", "gate_paths.json")
    command = [os.path.join(ROOT, "scientific", ".venv", "bin", "python"),
               os.path.join(ROOT, "evolution", "gate.py"),
               "--spec", spec_path,
               "--report", os.path.join(ROOT, "evolution", "reports", "shadow_paths.json"),
               "--canary", os.path.join(ROOT, ".artifacts", "canary_now.json"),
               "--output", gate_out]
    result = subprocess.run(command, cwd=ROOT)
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
