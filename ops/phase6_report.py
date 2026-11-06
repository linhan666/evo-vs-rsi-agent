#!/usr/bin/env python3
"""Phase 6 comparison table: W / A / M / R on the same 3-target x 3-repeat task set.

Pulls every number from artefacts that already exist:

  wall + success + auroc   from ticket runs (A/M/R) and phase6/w records (W)
  failure retries          from exported traces (steps that were not SUCCEEDED)
  failure classes          from evolution/traces/<ticket>.json, per group
  llm cost                 from scientific/.artifacts/usage_<group>.jsonl via ops/cost_report.py

Usage:
  python ops/phase6_report.py --output phase6/phase6_report.json
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import subprocess
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
WORK = os.path.join(ROOT, ".artifacts", "state", "work")
W_RECORDS = os.path.join(ROOT, "phase6", "w")
TRACES = os.path.join(ROOT, "evolution", "traces")
USAGE = os.path.join(ROOT, "scientific", ".artifacts")

def ticket_group(name: str) -> str:
    """Explicit name patterns: traces are exported in batches, so the group stamp
    cannot separate arms that were exported together. The ticket name is stable."""
    if "rsi" in name:
        return "rsi"
    if re.search(r"-(a|a[0-9])", name) or name.startswith(("mor-a", "kor-a", "chembl-drd2-a")):
        return "fixed"
    if re.search(r"-(m|m[0-9])", name) or name.startswith(("mor-m", "kor-m", "chembl-drd2-m")):
        return "memory"
    return "other"


def auroc_of(ticket_dir: str):
    for path in glob.glob(os.path.join(ticket_dir, "runs", "models", "*", "metrics.json")):
        try:
            value = json.load(open(path, encoding="utf-8"))["metrics"].get("auroc")
            return round(float(value), 4) if value is not None else None
        except Exception:
            return None
    return None


def wall_of(ticket_dir: str):
    total = 0.0
    for path in glob.glob(os.path.join(ticket_dir, ".jobs", "*", "result.json")):
        try:
            total += float(json.load(open(path, encoding="utf-8")).get("usage", {}).get("wall_seconds") or 0)
        except Exception:
            pass
    return round(total, 1)


def failures_of(ticket_dir: str) -> int:
    total = 0
    for path in glob.glob(os.path.join(ticket_dir, ".jobs", "*", "result.json")):
        try:
            if json.load(open(path, encoding="utf-8")).get("state") != "SUCCEEDED":
                total += 1
        except Exception:
            pass
    return total


def cost_of(group: str):
    name = {"fixed": "usage_a.jsonl", "memory": "usage_m.jsonl", "rsi": "usage_rsi.jsonl"}.get(group)
    if not name:
        return {"calls": 0, "cost_cny": 0.0}
    path = os.path.join(USAGE, name)
    if not os.path.exists(path):
        return {"calls": 0, "cost_cny": 0.0}
    result = subprocess.run([sys.executable, os.path.join(ROOT, "ops", "cost_report.py"),
                             "--usage", path, "--json"], capture_output=True, text=True, cwd=ROOT)
    try:
        data = json.loads(result.stdout)
        return {"calls": data["calls"], "cost_cny": round(data["cost_cny"], 4),
                "prompt_tokens": data["prompt_tokens"], "completion_tokens": data["completion_tokens"]}
    except Exception:
        return {"calls": 0, "cost_cny": 0.0}


def collect_agent_groups() -> dict:
    groups = {"fixed": [], "memory": [], "rsi": []}
    for name in sorted(os.listdir(WORK)):
        ticket_dir = os.path.join(WORK, name)
        if not os.path.isdir(ticket_dir):
            continue
        group = ticket_group(name)
        if group not in groups:
            continue
        groups[group].append({
            "ticket": name,
            "success": bool(glob.glob(os.path.join(ticket_dir, "runs", "*_topK.csv"))),
            "auroc": auroc_of(ticket_dir),
            "wall_seconds": wall_of(ticket_dir),
            "failed_steps": failures_of(ticket_dir),
        })
    return groups


def collect_workflow() -> list[dict]:
    rows = []
    for path in sorted(glob.glob(os.path.join(W_RECORDS, "*.json"))):
        record = json.load(open(path, encoding="utf-8"))
        rows.append({
            "ticket": f"{record['target']}_rep{record['rep']}",
            "success": record["success"],
            "auroc": record["auroc"],
            "wall_seconds": record["wall_seconds"],
            "failed_steps": sum(1 for step in record["steps"] if step["exit_code"] != 0),
        })
    return rows


def failure_classes(group: str) -> set[str]:
    classes = set()
    for path in glob.glob(os.path.join(TRACES, "*.json")):
        try:
            trace = json.load(open(path, encoding="utf-8"))
        except Exception:
            continue
        if (trace.get("group") or "rsi") != group:
            continue
        for step in trace.get("steps", []):
            if step.get("state") != "SUCCEEDED":
                classes.add("{0}::{1}".format(step["tool_id"],
                                             (step.get("error") or "").split(":")[0][:40]))
    return classes


def summarise(rows: list[dict], cost: dict, classes: set[str]) -> dict:
    if not rows:
        return {"tickets": 0}
    return {
        "tickets": len(rows),
        "success_rate": round(sum(1 for r in rows if r["success"]) / len(rows), 3),
        "auroc": {k: sorted({r["auroc"] for r in rows if r["auroc"]}) for k in ("MOR", "KOR", "DRD2")
                  } if False else sorted({r["auroc"] for r in rows if r["auroc"]}),
        "wall_seconds_mean": round(sum(r["wall_seconds"] for r in rows) / len(rows), 1),
        "failed_steps_mean": round(sum(r["failed_steps"] for r in rows) / len(rows), 2),
        "failed_steps_total": sum(r["failed_steps"] for r in rows),
        "failure_classes": sorted(classes),
        "llm": cost,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="phase6 report")
    parser.add_argument("--output", default=os.path.join(ROOT, "phase6", "phase6_report.json"))
    args = parser.parse_args(argv)

    agent = collect_agent_groups()
    report = {
        "schema_version": "1",
        "design": "4 groups x 3 targets (MOR/KOR/DRD2) x 3 repeats, same 100k library",
        "groups": {
            "W_workflow": summarise(collect_workflow(), {"calls": 0, "cost_cny": 0.0, "note": "no LLM"}, set()),
            "A_fixed": summarise(agent["fixed"], cost_of("fixed"), failure_classes("fixed")),
            "M_memory": summarise(agent["memory"], cost_of("memory"), failure_classes("memory")),
            "R_rsi": summarise(agent["rsi"], cost_of("rsi"), failure_classes("rsi")),
        },
    }
    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({name: {"tickets": row.get("tickets"), "success": row.get("success_rate"),
                             "wall": row.get("wall_seconds_mean"), "fails": row.get("failed_steps_mean"),
                             "cost": row.get("llm", {}).get("cost_cny")}
                      for name, row in report["groups"].items()}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
