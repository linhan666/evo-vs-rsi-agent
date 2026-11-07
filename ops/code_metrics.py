#!/usr/bin/env python3
"""Micro-level code metrics for the RSI experiment.

The macro view (jobs, wall clock, model count) cannot show the real advantage of
a self-improving harness: code reuse. Different targets need different feature
encodings, interaction algorithms and model families, and writing each from
scratch is expensive. This script extracts per-target code-level evidence:

  feature encoding   which featurization was chosen (radius, n_bits, desc_set)
  model family       which algorithm(s) were trained
  validation         which split strategy was used
  code reuse         how much of the ticket's code came from experience
  code cost          how many jobs failed before the first working model

Usage:
  python ops/code_metrics.py --ticket <work-dir> [--experience <store.json>]
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re


def extract(ticket_dir: str) -> dict:
    jobs = []
    for path in sorted(glob.glob(os.path.join(ticket_dir, ".jobs", "*", "result.json"))):
        try:
            jobs.append(json.load(open(path, encoding="utf-8")))
        except Exception:
            pass

    featurizations = set()
    models = set()
    splits = set()
    failures = 0
    first_success_index = None
    total = len(jobs)

    for index, job in enumerate(jobs):
        argv = job.get("argv") or []
        kv = {}
        for i, item in enumerate(argv):
            if item.startswith("--") and i + 1 < len(argv):
                kv[item.lstrip("-")] = argv[i + 1]

        if job.get("tool_id") == "rdkit.featurize":
            featurizations.add(f"r{kv.get('radius','?')}_b{kv.get('n-bits','?')}_{kv.get('desc-set','?')}")
        elif job.get("tool_id") == "ml.train":
            models.add(kv.get("model", "?"))
            if kv.get("split-manifest"):
                splits.add("custom")
        elif job.get("tool_id") == "data.split":
            splits.add(kv.get("strategy", "?"))

        if job.get("state") != "SUCCEEDED":
            failures += 1
        elif first_success_index is None and job.get("tool_id") in ("ml.train", "screening.rank"):
            first_success_index = index

    # code files produced in the workspace
    scripts = glob.glob(os.path.join(ticket_dir, "**", "*.py"), recursive=True)
    total_lines = 0
    for path in scripts:
        try:
            with open(path, encoding="utf-8", errors="ignore") as handle:
                total_lines += sum(1 for _ in handle)
        except Exception:
            pass

    # top-100 produced?
    top100 = bool(glob.glob(os.path.join(ticket_dir, "**", "*top100*"), recursive=True)
                  or glob.glob(os.path.join(ticket_dir, "**", "*top_100*"), recursive=True))

    return {
        "ticket": os.path.basename(ticket_dir),
        "jobs_total": total,
        "jobs_failed": failures,
        "failure_rate": round(failures / max(total, 1), 3),
        "first_success_index": first_success_index,
        "featurizations": sorted(featurizations),
        "models": sorted(models),
        "split_strategies": sorted(splits),
        "n_featurizations": len(featurizations),
        "n_models": len(models),
        "code_lines": total_lines,
        "top100": top100,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="code metrics")
    parser.add_argument("--ticket", required=True)
    parser.add_argument("--experience", default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)

    metrics = extract(args.ticket)

    if args.experience and os.path.exists(args.experience):
        try:
            store = json.load(open(args.experience, encoding="utf-8"))
            records = store.get("records", [])
            # count experience entries that mention the same model/featurization
            used = sum(1 for r in records
                       if any(m in json.dumps(r) for m in metrics["models"]))
            metrics["experience_records_matching"] = used
            metrics["experience_records_total"] = len(records)
        except Exception:
            pass

    if args.output:
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(metrics, handle, ensure_ascii=False, indent=2)
    print(json.dumps(metrics, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
