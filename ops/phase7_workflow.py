#!/usr/bin/env python3
"""Phase 7 group W: the fixed workflow over the same nine targets, no agent, no LLM.

Group W is the automation baseline: one hard-coded DAG of
split -> featurize -> train -> screen, identical arguments and seed for every
target, run once each. It is what `ops/phase6_workflow.py` did for the three
Phase 6 targets; this file extends the same idea to the Phase 7 sequence and
writes records in the Phase 7 layout so the four arms can be joined on
`sequence_index`.

Why a split step is added for every target
------------------------------------------
phase6_workflow.py consumed a `split_manifest.json` that already existed for its
three targets. Only three of the nine Phase 7 targets have one, so W would have
followed two different DAGs depending on the target. `data.split` therefore runs
for all nine, so the baseline is uniform.

Usage
-----
  python3 ops/phase7_workflow.py --all
  python3 ops/phase7_workflow.py --target MOR --slug oprm1
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
SCRATCH_ROOT = os.path.join(ROOT, ".artifacts", "workflow7")

# (sequence_index, display name, slug) — the same order as ops/phase7_seq.py.
TARGETS = [
    (1, "D2", "d(2)_dopamine_recept"),
    (2, "5HT", "5-hydroxytryptamine_"),
    (3, "ADR", "adenosine_receptor_a"),
    (4, "DRD2", "drd2"),
    (5, "MOR", "oprm1"),
    (6, "CBR", "cannabinoid_receptor"),
    (7, "KOR", "oprk1"),
    (8, "CA2", "carbonic_anhydrase_2"),
    (9, "PT", "prothrombin"),
]

# Fixed means fixed: same seed, same split, same model, same features for every
# target in this arm.
SEED = "17"
MODEL = "xgboost"
DESC_SET = "v1"
TEST_FRACTION = "0.3"
VAL_FRACTION = "0.1"
LABEL_SOURCE = "chembl37_ki_pX7_6"
TOP_K = "100"


def run(argv: list[str], cwd: str) -> dict:
    started = time.time()
    result = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
    return {
        "argv": argv,
        "exit_code": result.returncode,
        "wall_seconds": round(time.time() - started, 2),
        "stderr_tail": result.stderr.strip().splitlines()[-3:],
    }


def one(name: str, slug: str, seq: int, scratch: str) -> dict:
    dataset = os.path.join(DATA, "chembl", slug, "ki", "dataset.csv")
    library = os.path.join(DATA, "zinc", "library_100k.smi")
    tag = slug.replace("(", "").replace(")", "")
    manifest = "runs/split_manifest.json"

    steps = [
        [PYTHON, "-m", "evovs_science.data.split",
         "--input", dataset, "--output", manifest, "--strategy", "scaffold",
         "--test-fraction", TEST_FRACTION, "--val-fraction", VAL_FRACTION,
         "--seed", SEED, "--id-column", "molecule_chembl_id", "--smiles-column", "canonical_smiles"],
        [PYTHON, "-m", "evovs_science.chemistry.featurize",
         "--input", dataset, "--output", "runs/features.npz",
         "--report", "runs/feature_meta.json",
         "--id-column", "molecule_chembl_id", "--smiles-column", "canonical_smiles",
         "--desc-set", DESC_SET],
        [PYTHON, "-m", "evovs_science.modeling.train",
         "--features", "runs/features.npz", "--labels", dataset,
         "--output-dir", "runs/models/xgboost", "--model", MODEL,
         "--seed", SEED, "--test-fraction", TEST_FRACTION,
         "--label-source", LABEL_SOURCE,
         "--label-id-column", "molecule_chembl_id", "--label-column", "label",
         "--split-manifest", manifest],
        [PYTHON, "-m", "evovs_science.screening.predict",
         "--model", "runs/models/xgboost/model.joblib", "--library", library,
         "--output", f"runs/{tag}_all.csv",
         "--top-output", f"runs/{tag}_topK.csv",
         "--report", "runs/screening_report.json", "--top-k", TOP_K],
    ]

    os.makedirs(scratch, exist_ok=True)
    records = []
    for argv in steps:
        records.append(run(argv, scratch))
        if records[-1]["exit_code"] != 0:
            break

    topk = os.path.join(scratch, "runs", f"{tag}_topK.csv")
    metrics_path = os.path.join(scratch, "runs", "models", "xgboost", "metrics.json")
    metrics = {}
    if os.path.exists(metrics_path):
        try:
            metrics = json.load(open(metrics_path, encoding="utf-8")).get("metrics", {})
        except (ValueError, OSError):
            pass

    return {
        "group": "w",
        "seq": seq,
        "target": name,
        "slug": slug,
        "panel": "fixed workflow (split -> featurize -> train -> screen), no agent",
        "steps": records,
        "wall_seconds": round(sum(step["wall_seconds"] for step in records), 2),
        "jobs_run": len(records),
        "jobs_failed": sum(1 for step in records if step["exit_code"] != 0),
        "top100": os.path.relpath(topk, scratch) if os.path.exists(topk) else None,
        "auroc": metrics.get("auroc"),
        "auprc": metrics.get("auprc"),
        "ef_at_1pct": metrics.get("ef_at_1pct"),
        "success": bool(os.path.exists(topk)) and all(step["exit_code"] == 0 for step in records),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="phase7 workflow (group W)")
    parser.add_argument("--slug", default=None, help="run a single target by slug")
    parser.add_argument("--all", action="store_true", help="run all nine targets in sequence")
    args = parser.parse_args(argv)

    if not args.all and not args.slug:
        parser.error("give --all or --slug")

    chosen = TARGETS if args.all else [row for row in TARGETS if row[2] == args.slug]
    if not chosen:
        parser.error(f"--slug must be one of {[row[2] for row in TARGETS]}")

    os.makedirs(RECORDS, exist_ok=True)
    ok = 0
    for seq, name, slug in chosen:
        scratch = os.path.join(SCRATCH_ROOT, slug)
        record = one(name, slug, seq, scratch)
        path = os.path.join(RECORDS, f"w_{seq:02d}_{slug}.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(record, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        ok += 1 if record["success"] else 0
        print(json.dumps({"seq": seq, "target": name, "success": record["success"],
                          "auroc": record["auroc"], "ef_at_1pct": record["ef_at_1pct"],
                          "wall_seconds": record["wall_seconds"]}), flush=True)
    print(json.dumps({"runs": len(chosen), "succeeded": ok}))
    return 0 if ok == len(chosen) else 1


if __name__ == "__main__":
    sys.exit(main())
