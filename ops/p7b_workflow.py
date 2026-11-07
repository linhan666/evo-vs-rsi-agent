#!/usr/bin/env python3
"""Group W under the phase7b protocol: same nine targets, fixed DAG, no agent.

Differences from ops/phase7_workflow.py (round 7)
------------------------------------------------
1. Labels are `dataset_p7b.csv`, which has the protected test molecules removed.
2. There is no `data.split` step. The manifest is handed over as
   `splits/frozen_<slug>.json`, so W is scored on exactly the molecules the three
   agent arms are scored on. In round 7 W split for itself and ended up on a
   different partition from the agents.
3. W also runs `evaluation.locked` at the end, so all four arms have the one
   number that is comparable across arms.

Everything else is deliberately dumb: one feature set, one model, one seed, four
steps. That is the point of the baseline.

Usage:
  python3 ops/p7b_workflow.py --all
  python3 ops/p7b_workflow.py --slug oprk1
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "scientific", ".artifacts")
PYTHON = os.path.join(ROOT, "scientific", ".venv", "bin", "python")
RECORDS = os.path.join(ROOT, "ops", "phase7_runs")
SCRATCH_ROOT = os.path.join(ROOT, ".artifacts", "p7b_workflow")

# (sequence_index, display name, slug, locked target code) — same order as phase7_seq.py
TARGETS = [
    (1, "D2", "d(2)_dopamine_recept", "D2"),
    (2, "5HT", "5-hydroxytryptamine_", "5HT"),
    (3, "ADR", "adenosine_receptor_a", "ADR"),
    (4, "DRD2", "drd2", "DRD2"),
    (5, "MOR", "oprm1", "MOR"),
    (6, "CBR", "cannabinoid_receptor", "CBR"),
    (7, "KOR", "oprk1", "KOR"),
    (8, "CA2", "carbonic_anhydrase_2", "CA2"),
    (9, "PT", "prothrombin", "PT"),
]

SEED = "17"
MODEL = "xgboost"
DESC_SET = "v1"
TOP_K = "100"
LABEL_SOURCE = "chembl37_ki_pX7_6"


def run(argv: list[str], cwd: str) -> dict:
    started = time.time()
    result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
    return {
        "argv": argv,
        "exit_code": result.returncode,
        "wall_seconds": round(time.time() - started, 2),
        "stderr_tail": result.stderr.strip().splitlines()[-3:],
    }


def one(name: str, slug: str, code: str, seq: int, scratch: str) -> dict:
    dataset = os.path.join(DATA, "chembl", slug, "ki", "dataset_p7b.csv")
    frozen = os.path.join(DATA, "chembl", slug, "ki", "splits", f"frozen_{slug}.json")
    library = os.path.join(DATA, "zinc", "library_100k.smi")
    tag = code.lower()

    steps = [
        [PYTHON, "-m", "evovs_science.chemistry.featurize",
         "--input", dataset, "--output", "runs/features.npz",
         "--report", "runs/feature_meta.json",
         "--id-column", "molecule_chembl_id", "--smiles-column", "canonical_smiles",
         "--desc-set", DESC_SET, "--radius", "2", "--n-bits", "2048"],
        [PYTHON, "-m", "evovs_science.modeling.train",
         "--features", "runs/features.npz", "--labels", dataset,
         "--output-dir", "runs/models/xgboost", "--model", MODEL,
         "--seed", SEED, "--test-fraction", "0.05",
         "--label-source", LABEL_SOURCE,
         "--label-id-column", "molecule_chembl_id", "--label-column", "label",
         "--split-manifest", frozen],
        [PYTHON, "-m", "evovs_science.screening.predict",
         "--model", "runs/models/xgboost/model.joblib", "--library", library,
         "--output", f"runs/{tag}_all.csv",
         "--top-output", f"runs/{tag}_topK.csv",
         "--report", "runs/screening_report.json", "--top-k", TOP_K],
        [PYTHON, "-m", "evovs_science.evaluation.locked",
         "--target", code, "--endpoint", "Ki", "--desc-set", DESC_SET,
         "--model", "runs/models/xgboost/model.joblib",
         "--workspace", ".", "--receipt", f"evaluation/{tag}_locked.json"],
    ]

    os.makedirs(scratch, exist_ok=True)
    records = []
    for argv in steps:
        records.append(run(argv, scratch))
        if records[-1]["exit_code"] != 0:
            break

    topk = os.path.join(scratch, "runs", f"{tag}_topK.csv")
    metrics = {}
    metrics_path = os.path.join(scratch, "runs", "models", "xgboost", "metrics.json")
    if os.path.exists(metrics_path):
        try:
            metrics = json.load(open(metrics_path, encoding="utf-8")).get("metrics", {})
        except (ValueError, OSError):
            pass
    locked = None
    receipt = os.path.join(scratch, "evaluation", f"{tag}_locked.json")
    if os.path.exists(receipt):
        try:
            locked = (json.load(open(receipt, encoding="utf-8")).get("metrics") or {}).get("auroc")
        except (ValueError, OSError):
            pass

    return {
        "group": "w", "seq": seq, "target": name, "slug": slug, "label": "p7b",
        "panel": "fixed workflow (featurize -> train -> screen -> locked), no agent",
        "steps": records,
        "wall_seconds": round(sum(step["wall_seconds"] for step in records), 2),
        "jobs_run": len(records),
        "jobs_failed": sum(1 for step in records if step["exit_code"] != 0),
        "top100": os.path.relpath(topk, scratch) if os.path.exists(topk) else None,
        "auroc": metrics.get("auroc"),
        "auprc": metrics.get("auprc"),
        "ef_at_1pct": metrics.get("ef_at_1pct"),
        "locked_auroc": locked,
        "success": bool(os.path.exists(topk)) and all(step["exit_code"] == 0 for step in records),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="phase7b workflow (group W)")
    parser.add_argument("--slug", default=None, help="run a single target by slug")
    parser.add_argument("--all", action="store_true")
    args = parser.parse_args(argv)
    if not args.all and not args.slug:
        parser.error("give --all or --slug")

    chosen = TARGETS if args.all else [row for row in TARGETS if row[2] == args.slug]
    if not chosen:
        parser.error(f"--slug must be one of {[row[2] for row in TARGETS]}")

    os.makedirs(RECORDS, exist_ok=True)
    ok = 0
    for seq, name, slug, code in chosen:
        scratch = os.path.join(SCRATCH_ROOT, code.lower())
        record = one(name, slug, code, seq, scratch)
        path = os.path.join(RECORDS, f"w_{seq:02d}_{code.lower()}_p7b.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(record, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        ok += 1 if record["success"] else 0
        print(json.dumps({"seq": seq, "target": name, "success": record["success"],
                          "auroc": record["auroc"], "locked": record["locked_auroc"],
                          "wall_seconds": record["wall_seconds"]}), flush=True)
    print(json.dumps({"runs": len(chosen), "succeeded": ok}))
    return 0 if ok == len(chosen) else 1


if __name__ == "__main__":
    sys.exit(main())
