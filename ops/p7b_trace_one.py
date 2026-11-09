#!/usr/bin/env python3
"""Print what each arm actually did on one target: the ordered tool calls.

The aggregate tables say nothing about behaviour. This walks each arm's ticket
workdir, reads `.jobs/<id>/job.json`, and prints the call sequence with only the
arguments that distinguish one arm from another (model, features, split, output).

Usage: p7b_trace_one.py d2
"""
import json
import sys
from pathlib import Path

ROOT = Path("/home/linhan_cluster/evo_vs_rsi")
RUNS = ROOT / "ops/phase7_runs"
ARMS = (("r", "R  agent+memory+selfmod"), ("m", "M  agent+memory"),
        ("a", "A  agent only"), ("w", "W  fixed pipeline"))
INTERESTING = ("--model", "--features", "--split-manifest", "--output-dir",
               "--desc-set", "--endpoint", "--target", "--top-k", "--output",
               "--seed", "--strategy")


def args_of(argv: list[str]) -> str:
    picked = []
    for index, item in enumerate(argv):
        if item in INTERESTING and index + 1 < len(argv):
            value = str(argv[index + 1])
            value = value.replace("/home/linhan_cluster/evo_vs_rsi/", "").replace(
                "scientific/.artifacts/", "")
            if len(value) > 46:
                value = "…" + value[-44:]
            picked.append(f"{item.lstrip('-')}={value}")
    return " ".join(picked)


def jobs_of(workdir: Path) -> list[dict]:
    jobs = []
    for path in sorted((workdir / ".jobs").glob("*/job.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        jobs.append(payload)
    jobs.sort(key=lambda j: str(j.get("started_at") or ""))
    return jobs


def main() -> int:
    target = sys.argv[1] if len(sys.argv) > 1 else "d2"
    for arm, label in ARMS:
        matches = sorted(RUNS.glob(f"{arm}_*_{target}_p7b.json"))
        if not matches:
            print(f"\n### {label}: no record")
            continue
        record = json.loads(matches[0].read_text(encoding="utf-8"))
        if arm == "w":
            workdir = ROOT / ".artifacts" / "p7b_workflow" / target
        else:
            workdir = Path(record.get("workdir") or "")
        jobs = jobs_of(workdir)
        print(f"\n### {label} — {len(jobs)} jobs, wall {record.get('wall_seconds')}s")
        for index, job in enumerate(jobs, 1):
            argv = [a for a in job.get("argv") or [] if isinstance(a, str)]
            print(f"  {index:2d}. {job.get('tool_id'):22s} {args_of(argv)}")
        locked = record.get("locked_auroc") if arm == "w" else None
        print(f"  -> selected {record.get('best_scaffold_model')} "
              f"val {record.get('best_scaffold_auroc')} locked {locked}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
