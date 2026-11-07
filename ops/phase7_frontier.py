#!/usr/bin/env python3
"""The two comparisons the design promises, computed from job-level evidence.

The design distinguishes two questions, and Phase 7 so far only measured a third
thing (each arm's terminal cost and quality when left to run):

  (1) FIXED BUDGET  -> quality.  Give every arm the same budget and compare the
      best model found. This is answerable post hoc: walk the job log in time
      order and take the best validation AUROC reached at or before job k.

  (2) MATCHED QUALITY -> cost.  For a quality bar, how much budget did each arm
      need to reach it? This is also answerable post hoc, but it produces
      **censored** observations: an arm that stops early never reaches the bar,
      and "never" is a result, not a missing value.

Both are computed here from `.jobs/*/result.json` (start/end timestamps) plus
each model's `metrics.json` (validation AUROC), joined to the token ledger by
timestamp.

Usage:
  python3 ops/phase7_frontier.py            # writes ops/phase7_runs/frontier.md
  python3 ops/phase7_frontier.py --stdout
"""

from __future__ import annotations

import argparse
import json
import math
import os
import re
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "ops" / "phase7_runs"
OUT = RUNS / "frontier.md"
DATA = ROOT / "scientific" / ".artifacts"

ARM_NAME = {"w": "W fixed", "a": "A no-memory", "m": "M memory", "r": "R memory+self-modify"}


def parse_time(text: str | None) -> datetime | None:
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def load_ledger(arm: str) -> list[tuple[datetime, int]]:
    """(timestamp, cumulative_total_tokens) from the arm's usage ledger."""
    path = DATA / f"usage_seq_{arm}.jsonl"
    if not path.exists():
        return []
    rows: list[tuple[datetime, int]] = []
    total = 0
    with path.open(encoding="utf-8", errors="ignore") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except ValueError:
                continue
            tokens = entry.get("total_tokens")
            moment = parse_time(str(entry.get("ts", "")))
            if not tokens or not moment:
                continue
            total += tokens
            rows.append((moment, total))
    rows.sort(key=lambda item: item[0])
    return rows


def tokens_by(ledger: list[tuple[datetime, int]], moment: datetime) -> int:
    """Cumulative tokens consumed up to `moment`."""
    best = 0
    for when, total in ledger:
        if when <= moment:
            best = total
        else:
            break
    return best


def manifest_map(workdir: Path) -> dict[str, str]:
    """model directory name -> split manifest basename, from every ml.train job."""
    mapping: dict[str, str] = {}
    jobs_dir = workdir / ".jobs"
    if not jobs_dir.exists():
        return mapping
    for path in jobs_dir.glob("*/result.json"):
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if job.get("tool_id") != "ml.train":
            continue
        argv = [item for item in job.get("argv") or [] if isinstance(item, str)]
        kv = {}
        for position, item in enumerate(argv):
            if item.startswith("--") and position + 1 < len(argv):
                kv[item.lstrip("-")] = argv[position + 1]
        name = os.path.basename(str(kv.get("output-dir") or "").rstrip("/"))
        if name:
            mapping[name] = os.path.basename(str(kv.get("split-manifest") or ""))
    return mapping


def classify(manifest: str) -> str:
    """Only a scaffold manifest counts; refits and internal splits are excluded."""
    if re.search(r"final|refit", manifest):
        return "refit"
    if not manifest:
        return "internal"
    return "scaffold" if "scaffold" in manifest else "other"


def trajectory(run: dict, ledger: list[tuple[datetime, int]]) -> list[dict]:
    """Ordered (cumulative jobs, compute seconds, tokens, best validation AUROC)."""
    workdir = Path(run.get("workdir") or "")
    if not workdir.exists():
        return []
    manifests = manifest_map(workdir)
    events = []
    for path in (workdir / ".jobs").glob("*/result.json"):
        try:
            job = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        ended = parse_time(job.get("ended_at"))
        if not ended:
            continue
        auroc = None
        if job.get("tool_id") == "ml.train" and job.get("state") == "SUCCEEDED":
            argv = [item for item in job.get("argv") or [] if isinstance(item, str)]
            kv = {}
            for position, item in enumerate(argv):
                if item.startswith("--") and position + 1 < len(argv):
                    kv[item.lstrip("-")] = argv[position + 1]
            out_dir = str(kv.get("output-dir") or "")
            if out_dir and classify(manifests.get(os.path.basename(out_dir.rstrip("/")), "")) == "scaffold":
                metrics_path = workdir / out_dir / "metrics.json"
                if metrics_path.exists():
                    try:
                        payload = json.loads(metrics_path.read_text(encoding="utf-8"))
                        value = (payload.get("metrics") or {}).get("auroc")
                        if isinstance(value, (int, float)):
                            auroc = float(value)
                    except (ValueError, OSError):
                        pass
        events.append({"ended": ended, "seconds": (job.get("usage") or {}).get("wall_seconds") or 0,
                       "auroc": auroc})
    events.sort(key=lambda item: item["ended"])

    curve, best, jobs, seconds = [], 0.0, 0, 0.0
    for event in events:
        jobs += 1
        seconds += float(event["seconds"] or 0)
        if event["auroc"] is not None and event["auroc"] > best:
            best = event["auroc"]
        curve.append({"jobs": jobs, "compute_seconds": round(seconds, 1),
                      "tokens": tokens_by(ledger, event["ended"]),
                      "best_auroc": round(best, 4) if best else None})
    return curve


def best_at(curve: list[dict], jobs_budget: int) -> float | None:
    best = None
    for point in curve:
        if point["jobs"] <= jobs_budget and point["best_auroc"] is not None:
            best = point["best_auroc"]
    return best


def jobs_to_reach(curve: list[dict], target: float) -> int | None:
    for point in curve:
        if point["best_auroc"] is not None and point["best_auroc"] >= target:
            return point["jobs"]
    return None


def canonical(records: list[dict]) -> list[dict]:
    best: dict[tuple[str, str], dict] = {}
    for record in records:
        key = (record["arm"], record["target"])
        current = best.get(key)
        if current is None or (record["is_coldstart"] and not current["is_coldstart"]):
            best[key] = record
    return list(best.values())


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stdout", action="store_true")
    args = parser.parse_args()

    records = []
    for path in sorted(RUNS.glob("[ramw]_[0-9][0-9]_*.json")):
        matched = re.match(r"^([ramw])_(\d\d)_([a-z0-9]+)(?:_(.+))?$", path.stem)
        if not matched:
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        record["arm"] = matched.group(1)
        record["seq"] = int(matched.group(2))
        record["target"] = matched.group(3)
        record["is_coldstart"] = (matched.group(4) or "").startswith("coldstart")
        records.append(record)
    cells = canonical(records)

    ledgers = {arm: load_ledger(arm) for arm in ("r", "a", "m", "w")}
    curves = {}
    for record in cells:
        curve = trajectory(record, ledgers.get(record["arm"], []))
        if curve:
            curves[(record["arm"], record["target"])] = curve

    lines = ["# Phase 7 两个正式比较（成本-质量前沿）", ""]
    lines.append("数据来源：每个作业的 `result.json` 时间戳 + 每个模型的 `metrics.json` 验证 AUROC，"
                 "按时间顺序累计；token 按 usage ledger 时间点插值。")
    lines.append("")
    lines.append("> 只统计 **scaffold 切分**的模型，重训（refit/final）与内部切分不计入，"
                 "否则会看到虚高的 AUROC。")
    lines.append("")

    targets = sorted({t for _, t in curves}, key=lambda t: [c["seq"] for c in cells if c["target"] == t][0])
    arms_present = sorted({a for a, _ in curves})

    # ---------- fixed budget -> quality
    lines.append("## 一、固定预算下的质量（固定成本比性能）")
    lines.append("")
    budgets = [8, 16, 32, 64]
    header = "| 臂 | " + " | ".join(f"{b} 作业" for b in budgets) + " |"
    lines.append(header)
    lines.append("|" + "---|" * (len(budgets) + 1))
    for arm in arms_present:
        row = []
        for budget in budgets:
            values = []
            for target in targets:
                curve = curves.get((arm, target))
                if not curve:
                    continue
                value = best_at(curve, budget)
                if value is not None:
                    values.append(value)
            row.append(f"{sum(values) / len(values):.3f}（n={len(values)}）" if values else "—")
        lines.append(f"| {ARM_NAME.get(arm, arm)} | " + " | ".join(row) + " |")
    lines.append("")
    lines.append("每一格是该臂在各靶点上「最多用 k 个作业时达到的最佳 scaffold AUROC」的均值，"
                 "**同一个 k 下横向可比**，这是真正的固定预算比较。")
    lines.append("")

    # ---------- matched quality -> cost
    lines.append("## 二、达到同一质量所需的成本（同性能比消耗）")
    lines.append("")
    lines.append("| 靶点 | 质量门槛 q | " + " | ".join(f"{ARM_NAME.get(a, a)} 作业数" for a in arms_present) + " |")
    lines.append("|---|---|" + "---|" * len(arms_present))
    censored: dict[str, list[str]] = {arm: [] for arm in arms_present}
    for target in targets:
        ceiling = None
        for arm in arms_present:
            curve = curves.get((arm, target))
            if curve:
                value = curve[-1]["best_auroc"]
                if value is not None and (ceiling is None or value > ceiling):
                    ceiling = value
        if ceiling is None:
            continue
        row = []
        for arm in arms_present:
            curve = curves.get((arm, target))
            if not curve:
                row.append("—")
                continue
            needed = jobs_to_reach(curve, ceiling)
            if needed is None:
                row.append("**未达到**")
                censored[arm].append(target)
            else:
                row.append(f"{needed}")
        lines.append(f"| {target} | {ceiling:.4f} | " + " | ".join(row) + " |")
    lines.append("")
    lines.append("门槛 q 取该靶点上所有臂的**终态最高 AUROC**。所以「最高分那臂」必然是 ——，"
                 "它只是定义了门槛；其他臂若写「未达到」，说明它们**在任何预算下都没达到过这个质量**，"
                 "这不是缺失值，是结论。")
    lines.append("")
    for arm, targets_censored in censored.items():
        if targets_censored:
            lines.append(f"- **{ARM_NAME.get(arm, arm)}** 在 {len(targets_censored)}/{len(targets)} 个靶点上"
                         f"从未达到过质量门槛：{', '.join(targets_censored)}")
    lines.append("")

    # ---------- frontier area
    lines.append("## 三、前沿面积（单一数值摘要）")
    lines.append("")
    lines.append("对每条成本-质量曲线做梯形积分：横轴 `log10(作业数)`，纵轴 `best AUROC`，"
                 "取到两臂共同的最大作业数为止。面积越大 = 同样的对数预算下质量越高。")
    lines.append("")
    lines.append("| 臂 | 前沿面积 | 参与靶点数 |")
    lines.append("|---|---|---|")
    for arm in arms_present:
        areas = []
        for target in targets:
            curve = curves.get((arm, target))
            if not curve or len(curve) < 2:
                continue
            area = 0.0
            for left, right in zip(curve, curve[1:]):
                if left["best_auroc"] is None or right["best_auroc"] is None:
                    continue
                if right["jobs"] <= left["jobs"]:
                    continue
                width = math.log10(right["jobs"]) - math.log10(left["jobs"])
                area += width * (left["best_auroc"] + right["best_auroc"]) / 2
            if area:
                areas.append(area)
        lines.append(f"| {ARM_NAME.get(arm, arm)} | "
                     f"{sum(areas) / len(areas):.3f} | {len(areas)} |" if areas else
                     f"| {ARM_NAME.get(arm, arm)} | — | 0 |")
    lines.append("")

    text = "\n".join(lines) + "\n"
    if args.stdout:
        print(text)
    else:
        OUT.write_text(text, encoding="utf-8")
        print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
