#!/usr/bin/env python3
"""Phase 6 group W: a fixed workflow, no agent, no LLM.

The point of this arm is the automation baseline from the blueprint (§13.1, W:
"Workflow + AutoML" — preset steps and routing). So this file *is* the workflow:
a hard-coded DAG of featurize -> ml.train -> screening.rank with pre-chosen
arguments, run once per target and repeat. No planning, no tool discovery, no
memory, no self-modification.

It writes the same deliverables the RSI arm produces (runs/<TARGET>_topK.csv)
plus a small record per run so Phase 6 metrics can compare wall clock and exit
codes across arms.

Usage:
  python ops/phase6_workflow.py --target MOR --slug oprm1 --rep 1
  python ops/phase6_workflow.py --all            # 3 targets x 3 repeats
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
RECORDS = os.path.join(ROOT, "phase6", "w")

TARGETS = [
    ("MOR", "OPRM1", "oprm1"),
    ("KOR", "OPRK1", "oprk1"),
    ("DRD2", "DRD2", "drd2"),
]

# The workflow's fixed arguments. Fixed means fixed: same seed, same split, same
# model for every arm that reports itself as automated.
SEED = "17"
MODEL = "xgboost"
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


def one(target: str, gene: str, slug: str, rep: int, scratch: str) -> dict:
    dataset = os.path.join(DATA, "chembl", slug, "ki", "dataset.csv")
    split = os.path.join(DATA, "chembl", slug, "ki", "split_manifest.json")
    library = os.path.join(DATA, "zinc", "library_100k.smi")

    steps = [
        [PYTHON, "-m", "evovs_science.chemistry.featurize",
         "--input", dataset, "--output", "runs/features.npz",
         "--report", "runs/feature_meta.json",
         "--id-column", "molecule_chembl_id", "--smiles-column", "canonical_smiles", "--desc-set", "v1"],
        [PYTHON, "-m", "evovs_science.modeling.train",
         "--features", "runs/features.npz", "--labels", dataset,
         "--output-dir", "runs/models/xgboost", "--model", MODEL,
         "--seed", SEED, "--test-fraction", "0.3",
         "--label-source", LABEL_SOURCE,
         "--label-id-column", "molecule_chembl_id", "--label-column", "label",
         "--split-manifest", split],
        [PYTHON, "-m", "evovs_science.screening.predict",
         "--model", "runs/models/xgboost/model.joblib", "--library", library,
         "--output", f"runs/{target}_all.csv",
         "--top-output", f"runs/{target}_topK.csv",
         "--report", "runs/screening_report.json", "--top-k", "100"],
    ]

    os.makedirs(scratch, exist_ok=True)
    records = []
    for argv in steps:
        records.append(run(argv, scratch))
        if records[-1]["exit_code"] != 0:
            break

    topk = os.path.join(scratch, "runs", f"{target}_topK.csv")
    metrics_path = os.path.join(scratch, "runs", "models", "xgboost", "metrics.json")
    auroc = None
    if os.path.exists(metrics_path):
        try:
            auroc = json.load(open(metrics_path, encoding="utf-8"))["metrics"].get("auroc")
        except Exception:
            pass

    return {
        "group": "workflow",
        "target": target,
        "gene": gene,
        "rep": rep,
        "steps": records,
        "wall_seconds": round(sum(step["wall_seconds"] for step in records), 2),
        "topk": topk if os.path.exists(topk) else None,
        "auroc": auroc,
        "success": bool(os.path.exists(topk)) and all(step["exit_code"] == 0 for step in records),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="phase6 workflow (group W)")
    parser.add_argument("--target")
    parser.add_argument("--slug")
    parser.add_argument("--rep", type=int, default=1)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--scratch", default=None)
    args = parser.parse_args(argv)

    jobs: list[tuple[str, str, str, int]] = []
    if args.all:
        for target, gene, slug in TARGETS:
            for rep in (1, 2, 3):
                jobs.append((target, gene, slug, rep))
    else:
        if not (args.target and args.slug):
            parser.error("give --target and --slug, or --all")
        gene = next((g for t, g, s in TARGETS if s == args.slug), args.slug.upper())
        jobs.append((args.target, gene, args.slug, args.rep))

    os.makedirs(RECORDS, exist_ok=True)
    ok = 0
    for target, gene, slug, rep in jobs:
        scratch = args.scratch or os.path.join(ROOT, ".artifacts", "workflow", f"{slug}_rep{rep}")
        record = one(target, gene, slug, rep, scratch)
        path = os.path.join(RECORDS, f"{target}_rep{rep}.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(record, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        ok += 1 if record["success"] else 0
        print(json.dumps({"target": target, "rep": rep, "success": record["success"],
                          "auroc": record["auroc"], "wall_seconds": record["wall_seconds"]}))
    print(json.dumps({"runs": len(jobs), "succeeded": ok}))
    return 0 if ok == len(jobs) else 1


if __name__ == "__main__":
    sys.exit(main())
