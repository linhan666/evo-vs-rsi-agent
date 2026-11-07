#!/usr/bin/env python3
"""Cross-arm quality comparison on the ONLY common yardstick: the locked test set.

Why this file exists
--------------------
Every ticket picks its own scaffold validation split, so the "best validation
AUROC" of one arm and another arm are computed on **different molecules**. On
DRD2 the same pair of arms differed by 0.080 on validation and by 0.012 on the
locked test, in the opposite order — the validation difference was split noise,
not model quality.

The locked test set (`protected/`) is fixed per target and shared by every arm,
so it is the only valid basis for an arm-to-arm quality claim. This script
harvests the `evaluation.locked` receipts and prints the paired comparison.

Two traps it guards against:
  * `evaluation.locked` only accepts MOR / KOR / DRD2. A ticket for a different
    target (e.g. sequence target #1 "D2" = d(2)_dopamine_recept) that calls it
    is evaluating a model trained on one target against another target's test
    set. Those rows are reported but marked INVALID and excluded from the mean.
  * Identical receipts are not necessarily a bug: two arms can converge to the
    same pipeline (same split manifest, same features, same model, same seed),
    which produces byte-identical models and therefore identical metrics.

Usage:  python3 ops/phase7_locked.py [--stdout]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "ops" / "phase7_runs"
OUT = RUNS / "locked.md"

# sequence position -> the target the locked tool can actually evaluate
LOCKABLE = {"drd2": "DRD2", "mor": "MOR", "kor": "KOR"}


def receipts(workdir: Path) -> list[dict]:
    """Every locked-evaluation receipt under a work directory."""
    found = []
    if not workdir.exists():
        return found
    for path in workdir.rglob("*.json"):
        if ".jobs" in path.parts:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if isinstance(payload, dict) and "protected_output" in payload and "metrics" in payload:
            found.append({"path": str(path.relative_to(workdir)), **payload})
    return found


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--stdout", action="store_true")
    parser.add_argument("--round", default="", help="'' for round 7, 'p7b' for the redesigned round")
    args = parser.parse_args()

    rows = []
    for path in sorted(RUNS.glob("[ramw]_[0-9][0-9]_*.json")):
        matched = re.match(r"^([ramw])_(\d\d)_([a-z0-9]+)(?:_(.+))?$", path.stem)
        if not matched:
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        if (matched.group(4) or "") != args.round:
            continue
        arm, target = matched.group(1), matched.group(3)
        workdir = Path(record.get("workdir") or "")
        for receipt in receipts(workdir):
            evaluated = receipt.get("target")
            expected = LOCKABLE.get(target)
            valid = expected is not None and evaluated == expected
            rows.append({
                "arm": arm,
                "seq": int(matched.group(2)),
                "target": target,
                "evaluated_as": evaluated,
                "valid": valid,
                "auroc": (receipt.get("metrics") or {}).get("auroc"),
                "auprc": (receipt.get("metrics") or {}).get("auprc"),
                "ef_at_1pct": (receipt.get("metrics") or {}).get("ef_at_1pct"),
                "receipt": receipt["path"],
            })

    lines = ["# 跨臂质量比较：锁定测试集", ""]
    lines.append("每张工单自选 scaffold 验证集，所以「最佳验证 AUROC」在不同臂之间**不在同一批分子上**。"
                 "`protected/` 里的锁定测试集按靶点固定、各臂共享，是唯一合法的横向标尺。")
    lines.append("")
    lines.append("| 臂 | seq | 序列靶点 | 评测目标 | 有效 | AUROC | AUPRC | EF@1% |")
    lines.append("|---|---|---|---|---|---|---|---|")
    for row in sorted(rows, key=lambda r: (r["arm"], r["seq"])):
        lines.append(f"| {row['arm'].upper()} | {row['seq']} | {row['target']} | {row['evaluated_as']} | "
                     f"{'✅' if row['valid'] else '❌ 目标不匹配'} | "
                     f"{row['auroc'] if row['auroc'] is not None else '—'} | "
                     f"{row['auprc'] if row['auprc'] is not None else '—'} | "
                     f"{row['ef_at_1pct'] if row['ef_at_1pct'] is not None else '—'} |")
    lines.append("")

    valid = [r for r in rows if r["valid"] and r["auroc"] is not None]
    by_key: dict[tuple[str, str], dict] = {}
    for row in valid:
        by_key[(row["evaluated_as"], row["arm"])] = row

    pairs = []
    for target in sorted({r["evaluated_as"] for r in valid}):
        r_row = by_key.get((target, "r"))
        a_row = by_key.get((target, "a"))
        if r_row and a_row:
            diff = r_row["auroc"] - a_row["auroc"]
            pairs.append((target, r_row["auroc"], a_row["auroc"], diff))
    if pairs:
        lines.append("## 配对比较（同一锁定测试集）")
        lines.append("")
        lines.append("| 靶点 | R | A | 差（R−A） |")
        lines.append("|---|---|---|---|")
        for target, r_value, a_value, diff in pairs:
            lines.append(f"| {target} | {r_value:.4f} | {a_value:.4f} | **{diff:+.4f}** |")
        mean = sum(p[3] for p in pairs) / len(pairs)
        lines.append(f"| **均值** | | | **{mean:+.4f}** |")
        lines.append("")
        if len(pairs) < 6:
            lines.append(f"⚠️ 只有 {len(pairs)} 对，Wilcoxon 双侧最小可达 p = "
                         f"{2 / (2 ** len(pairs)):.4f}，**不足以做显著性判断**。"
                         "而且 9 个靶点里只有 MOR/KOR/DRD2 有受保护测试集，"
                         "其余 6 个靶点的跨臂质量比较在方法上不成立。")
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
