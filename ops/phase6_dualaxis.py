#!/usr/bin/env python3
"""Phase 6 dual-axis evaluation: science quality and code quality in one table.

The blueprint's central claim is that a self-improving harness helps with
*customised modelling for virtual screening*, and customisation is a coding
problem (§4.1: the Agent chooses representation, model, validation and fusion,
writing scripts when the tools do not cover the choice). So the experiment has to
report two axes, not one:

  science   AUROC / AUPRC / EF@1% / cost per unit quality
  code      job success, replay equivalence, reuse across targets, retry count

Each row is one ticket. The table answers two questions at once: did the Agent
pick a good model for THIS dataset, and did it write reliable code to get there.

Usage:
  python ops/phase6_dualaxis.py --output phase6/dualaxis.json
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, ".artifacts", "state", "work")
USAGE = os.path.join(ROOT, "scientific", ".artifacts")


def ticket_rows() -> list[dict]:
    rows = []
    for name in sorted(os.listdir(WORK)):
        ticket = os.path.join(WORK, name)
        if not os.path.isdir(ticket):
            continue
        metrics = {}
        for path in glob.glob(os.path.join(ticket, "runs", "models", "*", "metrics.json")):
            try:
                metrics = json.load(open(path, encoding="utf-8")).get("metrics", {})
            except Exception:
                pass
            if metrics:
                break
        jobs = []
        for path in glob.glob(os.path.join(ticket, ".jobs", "*", "result.json")):
            try:
                jobs.append(json.load(open(path, encoding="utf-8")))
            except Exception:
                pass
        reused = sum(1 for job in jobs if job.get("reused"))
        failed = sum(1 for job in jobs if job.get("state") != "SUCCEEDED")
        wall = round(sum(float(job.get("usage", {}).get("wall_seconds") or 0) for job in jobs), 1)
        splits = glob.glob(os.path.join(ticket, "splits", "*.json"))
        strategy = None
        for path in splits:
            try:
                strategy = json.load(open(path, encoding="utf-8")).get("strategy")
            except Exception:
                pass
            if strategy:
                break
        rows.append({
            "ticket": name,
            "target": ("MOR" if "mor" in name.lower() or "oprm1" in name.lower()
                       else "KOR" if "kor" in name.lower() or "oprk1" in name.lower()
                       else "DRD2" if "drd2" in name.lower() else "other"),
            # --- science axis ---
            "auroc": metrics.get("auroc"),
            "auprc": metrics.get("auprc"),
            "ef_at_1pct": metrics.get("ef_at_1pct"),
            "split_strategy": strategy,
            # --- code axis ---
            "jobs": len(jobs),
            "jobs_failed": failed,
            "jobs_reused": reused,
            "wall_seconds": wall,
            "topk": bool(glob.glob(os.path.join(ticket, "runs", "*_topK.csv"))),
        })
    return rows


def summarise(rows: list[dict]) -> dict:
    def mean(key):
        values = [row[key] for row in rows if row.get(key) is not None]
        return round(sum(values) / len(values), 4) if values else None

    return {
        "tickets": len(rows),
        "science": {
            "auroc_mean": mean("auroc"),
            "auprc_mean": mean("auprc"),
            "ef_at_1pct_mean": mean("ef_at_1pct"),
            "split_strategies": sorted({row["split_strategy"] for row in rows if row["split_strategy"]}),
            "topk_rate": round(sum(1 for r in rows if r["topk"]) / max(len(rows), 1), 3),
        },
        "code": {
            "jobs_total": sum(row["jobs"] for row in rows),
            "jobs_failed": sum(row["jobs_failed"] for row in rows),
            "jobs_reused": sum(row["jobs_reused"] for row in rows),
            "failure_rate": round(sum(row["jobs_failed"] for row in rows) /
                                  max(sum(row["jobs"] for row in rows), 1), 3),
            "wall_mean": round(sum(row["wall_seconds"] for row in rows) / max(len(rows), 1), 1),
        },
    }




GROUP_RULES = [
    ("R2", lambda n: "rep2" in n or "open-rep2" in n),
    ("R1", lambda n: "rep1" in n or "open-rep1" in n or "rep1b" in n),
    ("A", lambda n: "control-a" in n or "ctl-a" in n or "-a-" in n),
    ("M", lambda n: "control-m" in n or "ctl-m" in n or "-m-" in n),
]


def group_of(name: str) -> str:
    for label, rule in GROUP_RULES:
        if rule(name):
            return label
    return "other"


def per_group(rows: list[dict]) -> dict:
    buckets: dict[str, list[dict]] = {}
    for row in rows:
        buckets.setdefault(group_of(row["ticket"]), []).append(row)
    return {label: summarise(items) for label, items in sorted(buckets.items())}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="phase6 dual-axis")
    parser.add_argument("--output", default=os.path.join(ROOT, "phase6", "dualaxis.json"))
    parser.add_argument("--filter", default=None, help="substring to keep only matching tickets")
    args = parser.parse_args(argv)

    rows = ticket_rows()
    if args.filter:
        rows = [row for row in rows if args.filter in row["ticket"]]
    report = {"schema_version": "1", "axes": ["science", "code"],
              "per_ticket": rows, "summary": summarise(rows), "by_group": per_group(rows)}
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"summary": report["summary"], "by_group": report["by_group"]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
