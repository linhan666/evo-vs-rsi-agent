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
def _lockable() -> dict[str, str]:
    """sequence slug -> locked target code.

    Derived from the evaluator itself. The hand-written version listed only
    drd2/mor/kor, so once phase7b gave all nine targets a locked channel every
    other row was flagged "目标不匹配" even though the receipt was correct.
    """
    try:
        from evovs_science.evaluation.locked import CHANNELS
        return {code.lower(): code for code in CHANNELS["Ki"]}
    except Exception:  # keep the report runnable without the package on the path
        return {"d2": "D2", "5ht": "5HT", "adr": "ADR", "drd2": "DRD2", "mor": "MOR",
                "cbr": "CBR", "kor": "KOR", "ca2": "CA2", "pt": "PT"}


LOCKABLE = _lockable()


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
    parser.add_argument("--rounds", default=None,
                        help="comma-separated rounds, e.g. p7b,p7c -- needed to put the same arm "
                             "under two harness versions into one report")
    args = parser.parse_args()

    wanted = [r.strip() for r in (args.rounds.split(",") if args.rounds else [args.round])]
    rows = []
    for path in sorted(RUNS.glob("[ramw]_[0-9][0-9]_*.json")):
        matched = re.match(r"^([ramw])_(\d\d)_([a-z0-9]+)(?:_(.+))?$", path.stem)
        if not matched:
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        this_round = matched.group(4) or ""
        if this_round not in wanted:
            continue
        arm, target = matched.group(1), matched.group(3)
        # W records carry no `workdir`, and `Path("")` is `.` -- walking it made
        # the report ingest every receipt in the repository and pair them by
        # position, which is why most rows read "目标不匹配". Resolve the receipt
        # directory explicitly per arm and never walk a fallback.
        raw = record.get("workdir") or ""
        if raw and Path(raw).is_dir():
            receipt_dir = Path(raw) / "evaluation"
        else:
            code = (LOCKABLE.get(target) or target).lower()
            receipt_dir = ROOT / ".artifacts" / "p7b_workflow" / code / "evaluation"
        if not receipt_dir.is_dir():
            continue
        for receipt in receipts(receipt_dir):
            evaluated = receipt.get("target")
            expected = LOCKABLE.get(target)
            valid = expected is not None and evaluated == expected
            rows.append({
                "arm": arm,
                "round": this_round,
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
        label = row["arm"].upper() if row["round"] == wanted[0] else f"{row['arm'].upper()}({row['round']})"
        lines.append(f"| {label} | {row['seq']} | {row['target']} | {row['evaluated_as']} | "
                     f"{'✅' if row['valid'] else '❌ 目标不匹配'} | "
                     f"{row['auroc'] if row['auroc'] is not None else '—'} | "
                     f"{row['auprc'] if row['auprc'] is not None else '—'} | "
                     f"{row['ef_at_1pct'] if row['ef_at_1pct'] is not None else '—'} |")
    lines.append("")

    valid = [r for r in rows if r["valid"] and r["auroc"] is not None]
    by_key: dict[tuple[str, str, str], dict] = {}
    for row in valid:
        by_key[(row["evaluated_as"], row["arm"], row["round"])] = row
    base_round = wanted[0]

    pairs = []
    for target in sorted({r["evaluated_as"] for r in valid}):
        r_row = by_key.get((target, "r", base_round))
        a_row = by_key.get((target, "a", base_round))
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
                         f"{2 / (2 ** len(pairs)):.4f}，**不足以做显著性判断**。")
    lines.append("")

    # Same arm, two harness versions. This is the direct test of whether a
    # gate-certified promotion changed anything: the arm, the task text, the
    # target sequence and the locked sets are identical; only the harness
    # version differs.
    for later in wanted[1:]:
        version_pairs = []
        for target in sorted({r["evaluated_as"] for r in valid}):
            before = by_key.get((target, "r", base_round))
            after = by_key.get((target, "r", later))
            if before and after:
                version_pairs.append((target, before["auroc"], after["auroc"],
                                      after["auroc"] - before["auroc"]))
        if not version_pairs:
            continue
        lines.append(f"## 同臂跨版本：R({later}) vs R({base_round})")
        lines.append("")
        lines.append("同一靶点序列、同一锁定测试集、同一任务文本，只有 harness 版本不同。"
                     "差值为「新版本 − 旧版本」。")
        lines.append("")
        lines.append(f"| 靶点 | R({later}) | R({base_round}) | 差 |")
        lines.append("|---|---|---|---|")
        for target, after_value, before_value, diff in version_pairs:
            lines.append(f"| {target} | {after_value:.4f} | {before_value:.4f} | **{diff:+.4f}** |")
        mean = sum(p[3] for p in version_pairs) / len(version_pairs)
        lines.append(f"| **均值** | | | **{mean:+.4f}** |")
        lines.append("")
        ties = sum(1 for p in version_pairs if abs(p[3]) < 1e-9)
        lines.append(f"逐靶点：{len(version_pairs)} 对，其中 {ties} 对完全相同。"
                     "v7 只改训练线程数、不改任何数值，所以质量应当逐点持平——"
                     "持平是「改动如设计般中性」的证据；若出现偏移，说明并行影响了数值，应回滚。")
        lines.append("")

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
