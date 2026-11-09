#!/usr/bin/env python3
"""Measure the within-arm noise floor from the M-arm repeats.

The question this answers
------------------------
Two between-arm differences are on the table:

    R vs A   locked AUROC  +0.0118   (does memory help quality?)
    R' vs R  locked AUROC  +0.0112   (did the v7 promotion change anything?)

The second is confounded (it also changes the harness version), so neither can be
judged without knowing how much a *like-for-like re-run* moves the number. The M
arm was run three times from empty stores (p7b, p7d, p7e), so for each target we
have three independent samples of the same condition.

Reported here, per target: the three locked AUROCs, their sample SD and range.
Pooled over targets: the within-target SD (sqrt of the mean variance), which is
the number the between-arm differences must beat.

Decision rule, fixed before looking at the data (see ops/p7b_calib_repeats.sh):
    pooled SD >> 0.0118  -> the quality claims are not supportable; publish cost
    pooled SD << 0.0118  -> the effects may be real; fund the full 3-rep study
"""
import json
import statistics
from pathlib import Path

ROOT = Path("/home/linhan_cluster/evo_vs_rsi")
RUNS = ROOT / "ops/phase7_runs"
REPS = ("p7b", "p7d", "p7e")
TARGETS = ("d2", "5ht", "adr", "drd2", "mor", "cbr", "kor", "ca2", "pt")
BETWEEN_ARM = 0.0118     # R vs A, locked
BETWEEN_VER = 0.0112     # R' vs R, locked


def locked_auroc(record: dict) -> float | None:
    workdir = record.get("workdir") or ""
    if not workdir:
        return None
    for path in sorted(Path(workdir, "evaluation").glob("*_locked.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if "protected_output" in payload and "metrics" in payload:
            value = (payload.get("metrics") or {}).get("auroc")
            if value is not None:
                return float(value)
    return None


def load(rep: str, target: str) -> dict | None:
    matches = sorted(RUNS.glob(f"m_*_{target}_{rep}.json"))
    if not matches:
        return None
    record = json.loads(matches[0].read_text(encoding="utf-8"))
    tokens = record.get("tokens") or {}
    return {
        "locked": locked_auroc(record),
        "validation": record.get("best_scaffold_auroc"),
        "wall": record.get("wall_seconds"),
        "jobs": record.get("jobs_total"),
        "tokens": tokens.get("total_tokens"),
    }


def pooled_sd(groups: list[list[float]]) -> tuple[float, float, int]:
    variances = [statistics.variance(g) for g in groups if len(g) >= 2]
    if not variances:
        return float("nan"), float("nan"), 0
    mean_var = sum(variances) / len(variances)
    return mean_var ** 0.5, statistics.mean(variances), len(variances)


def section(name: str, per_target: dict[str, list[float]]) -> dict:
    groups = [v for v in per_target.values() if len(v) >= 2]
    sd, var, k = pooled_sd(groups)
    # mean pairwise absolute difference across the reps of one target
    spreads = []
    for values in groups:
        if len(values) < 2:
            continue
        spreads.extend(abs(a - b) for i, a in enumerate(values) for b in values[i + 1:])
    return {
        "metric": name,
        "pooled_sd": round(sd, 4) if sd == sd else None,
        "mean_pairwise_diff": round(statistics.mean(spreads), 4) if spreads else None,
        "max_target_range": round(max((max(g) - min(g)) for g in groups), 4) if groups else None,
        "targets_used": k,
    }


def main() -> int:
    per_target: dict[str, dict[str, list[float]]] = {t: {} for t in TARGETS}
    missing = []
    for target in TARGETS:
        for metric in ("locked", "validation", "wall", "jobs", "tokens"):
            per_target[target].setdefault(metric, [])
        for rep in REPS:
            row = load(rep, target)
            if row is None:
                missing.append(f"{rep}/{target}: no record")
                continue
            for metric in ("locked", "validation", "wall", "jobs", "tokens"):
                value = row[metric]
                if value is None:
                    if metric == "locked":
                        missing.append(f"{rep}/{target}: no locked receipt")
                    continue
                per_target[target][metric].append(float(value))

    summaries = [section(m, {t: per_target[t][m] for t in TARGETS})
                 for m in ("locked", "validation", "wall", "jobs", "tokens")]

    lines = ["# 臂内噪声标定（M 臂三次重复）", ""]
    lines.append("同一条臂、同一 harness 版本、同一任务文本、同一靶点，从空库重跑三次。")
    lines.append("这些差异里**不含**任何处理效应，纯粹是 agent 选择的随机性。")
    lines.append("")
    lines.append("| 靶点 | M(p7b) | M(p7d) | M(p7e) | 极差 |")
    lines.append("|---|---|---|---|---|")
    for target in TARGETS:
        values = per_target[target]["locked"]
        if len(values) < 2:
            lines.append(f"| {target.upper()} | — | — | — | — |")
            continue
        cells = [f"{v:.4f}" for v in values] + ["—"] * (3 - len(values))
        lines.append(f"| {target.upper()} | {' | '.join(cells[:3])} | **{max(values) - min(values):.4f}** |")
    lines.append("")
    lines.append("## 汇总")
    lines.append("")
    lines.append("| 指标 | 池化臂内 SD | 平均成对差 | 最大单靶点极差 |")
    lines.append("|---|---|---|---|")
    for item in summaries:
        if item["pooled_sd"] is None:
            continue
        scale = 1.0 if item["metric"] in ("locked", "validation") else 1.0
        lines.append(f"| {item['metric']} | {item['pooled_sd'] * scale:.4f} | "
                     f"{item['mean_pairwise_diff']:.4f} | {item['max_target_range']:.4f} |")
    lines.append("")

    locked = next(s for s in summaries if s["metric"] == "locked")
    sd = locked["pooled_sd"]
    if sd:
        lines.append("## 判定（规则在看到数据前已写定）")
        lines.append("")
        lines.append(f"- 臂内池化 SD = **{sd:.4f}**，平均成对差 = {locked['mean_pairwise_diff']:.4f}")
        lines.append(f"- 待判效应：记忆 R−A = {BETWEEN_ARM:+.4f}；版本 R′−R = {BETWEEN_VER:+.4f}")
        lines.append("")
        ratio = sd / BETWEEN_ARM if BETWEEN_ARM else float("inf")
        lines.append(f"- 臂内 SD 是记忆效应量的 **{ratio:.1f} 倍**")
        lines.append("")
        if sd > BETWEEN_ARM:
            lines.append("**结论：质量层面的臂间差异落在重跑噪声之内，不成立。**")
            lines.append(f"同一条件重跑一次的逐靶点波动（SD {sd:.4f}）已经大于要检定的效应"
                         f"（{BETWEEN_ARM:.4f}），因此 R vs A 的 +0.0118 不能被解释为记忆的作用。")
            lines.append("可发表的结论是成本：有记忆的两臂 token 约为无记忆臂的 1/8，质量不变。")
        else:
            lines.append("**结论：效应量超过重跑噪声，值得投入全量三次重复。**")
        lines.append("")
    if missing:
        lines.append("## 数据缺口")
        lines.append("")
        for note in missing[:12]:
            lines.append(f"- {note}")
        lines.append("")

    text = "\n".join(lines) + "\n"
    (RUNS / "noise_floor.md").write_text(text, encoding="utf-8")
    (RUNS / "noise_floor.json").write_text(
        json.dumps({"reps": REPS, "summaries": summaries,
                    "per_target_locked": {t: per_target[t]["locked"] for t in TARGETS},
                    "between_arm": BETWEEN_ARM, "between_version": BETWEEN_VER},
                   ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
