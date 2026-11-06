"""Phase 6 comparison metrics: one number set per group, from traces alone.

Every metric is read off the corpus, not off a model's opinion:

  success_rate        tickets whose last report was ready / all tickets
  failure_retries     failed steps per ticket (a retry loop shows up here first)
  wall_seconds        sum of step wall time per ticket
  classes_eliminated  failure classes that appeared before and no longer do, per
                      the group's later traces (the RSI claim in one number)

Usage:
  python evolution/metrics.py --group rsi=traces/dir1,traces/dir2 --group fixed=... --output out.json
"""

from __future__ import annotations

import argparse
import glob
import json
import os
from collections import Counter


def load_group(spec: str) -> list[dict]:
    """spec is name=path[,path...]"""
    name, _, paths = spec.partition("=")
    traces: list[dict] = []
    for path in paths.split(","):
        pattern = path if path.endswith("*.json") else os.path.join(path, "*.json")
        for file_path in sorted(glob.glob(pattern)):
            trace = json.loads(open(file_path, encoding="utf-8").read())
            trace["_name"] = os.path.basename(file_path)
            traces.append(trace)
    return name, traces


def classes_of(trace: dict) -> set[str]:
    from failure_clusters import error_class  # local import keeps this module cheap to test
    names = set()
    for step in trace.get("steps", []):
        if step.get("state") == "SUCCEEDED":
            continue
        names.add("{0}::{1}".format(step["tool_id"], error_class(
            step.get("error", ""), step.get("stderr_tail", ""),
            step.get("exit_code"), step.get("stdout_tail", ""))))
    return names


def summarise(traces: list[dict], earlier_classes: set[str] | None = None) -> dict:
    failures = []
    walls = []
    for trace in traces:
        steps = trace.get("steps", [])
        walls.append(round(sum(step.get("wall_seconds") or 0 for step in steps), 1))
        failures.append(sum(1 for step in steps if step.get("state") != "SUCCEEDED"))
    later_classes = set().union(*(classes_of(trace) for trace in traces)) if traces else set()
    eliminated = sorted(earlier_classes - later_classes) if earlier_classes else []
    return {
        "tickets": len(traces),
        "success_rate": None,  # filled by the caller, which knows each ticket's report
        "failure_retries": {"total": sum(failures), "per_ticket": failures,
                            "mean": round(sum(failures) / len(failures), 2) if failures else 0},
        "wall_seconds": {"total": round(sum(walls), 1), "per_ticket": walls,
                         "mean": round(sum(walls) / len(walls), 1) if walls else 0},
        "failure_classes": sorted(later_classes),
        "classes_eliminated": eliminated,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evolution metrics")
    parser.add_argument("--group", action="append", required=True,
                        help="name=path[,path...] traces of one experimental group")
    parser.add_argument("--baseline", default=None,
                        help="name of the group whose failure classes the others are compared against")
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)

    groups = dict(load_group(spec) for spec in args.group)
    baseline = groups.get(args.baseline, []) if args.baseline else []
    earlier = set().union(*(classes_of(trace) for trace in baseline)) if baseline else None
    report = {"schema_version": "1", "groups": {}}
    for name, traces in groups.items():
        report["groups"][name] = summarise(traces, None if name == args.baseline else earlier)
    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    print(json.dumps({name: {"tickets": summary["tickets"],
                             "mean_failures": summary["failure_retries"]["mean"],
                             "mean_wall": summary["wall_seconds"]["mean"],
                             "eliminated": len(summary["classes_eliminated"])}
                      for name, summary in report["groups"].items()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
