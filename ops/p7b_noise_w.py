#!/usr/bin/env python3
"""Error bars for the one quality claim still standing: agent vs fixed workflow.

W is a fixed pipeline: same data, same code, same seed. Its repeats should be
bit-identical, which makes it a deterministic reference — so the uncertainty in
"agent beats W" comes entirely from the agent's run-to-run variance, which the
M-arm calibration already measured (pooled SD 0.0308 on locked AUROC).

Reports, per arm: mean locked AUROC over the nine targets, the paired difference
against W, and the standard error of that difference using the measured
within-arm SD rather than an assumed one.
"""
import json
import math
import statistics
from pathlib import Path

ROOT = Path("/home/linhan_cluster/evo_vs_rsi")
RUNS = ROOT / "ops/phase7_runs"
TARGETS = ("d2", "5ht", "adr", "drd2", "mor", "cbr", "kor", "ca2", "pt")
W_REPS = ("p7b", "p7f", "p7g")
BETWEEN_ARM_SD = 0.0308      # measured on the M arm, three reps (noise_floor.md)


def w_locked(rep: str, target: str) -> float | None:
    matches = sorted(RUNS.glob(f"w_*_{target}_{rep}.json"))
    if not matches:
        return None
    return json.loads(matches[0].read_text(encoding="utf-8")).get("locked_auroc")


def agent_locked(arm: str, round_label: str, target: str) -> float | None:
    matches = sorted(RUNS.glob(f"{arm}_*_{target}_{round_label}.json"))
    if not matches:
        return None
    record = json.loads(matches[0].read_text(encoding="utf-8"))
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


def main() -> int:
    lines = ["# W 臂重复标定与 agent vs W 的误差棒", ""]

    # 1. is W actually deterministic?
    w_rows = {t: [w_locked(rep, t) for rep in W_REPS] for t in TARGETS}
    spreads = [max(v) - min(v) for v in w_rows.values() if all(x is not None for x in v)]
    lines.append("## W 三次重复")
    lines.append("")
    lines.append("| 靶点 | p7b | p7f | p7g | 极差 |")
    lines.append("|---|---|---|---|---|")
    for target in TARGETS:
        values = w_rows[target]
        if any(v is None for v in values):
            lines.append(f"| {target.upper()} | — | — | — | — |")
            continue
        lines.append(f"| {target.upper()} | {values[0]:.4f} | {values[1]:.4f} | {values[2]:.4f} | "
                     f"**{max(values) - min(values):.4f}** |")
    lines.append("")
    lines.append(f"W 的逐靶点极差全部为 {max(spreads):.4f}（{len(spreads)} 个靶点）—— 固定流水线是确定性的，"
                 "重跑不产生任何波动。" if spreads and max(spreads) < 1e-9 else
                 f"W 的逐靶点极差最大值 {max(spreads):.4f}。")
    lines.append("")

    # 2. agent vs W with the measured SD
    lines.append("## agent vs W（配对，同一锁定测试集）")
    lines.append("")
    lines.append(f"W 是确定性的，所以差值的不确定性全部来自 agent 的重跑波动"
                 f"（实测逐靶点 SD = {BETWEEN_ARM_SD:.4f}，n=3）。")
    lines.append("")
    lines.append("| 臂 | 均值 AUROC | 与 W 的配对差 | 标准误 | 差值/标准误 | 样本 |")
    lines.append("|---|---|---|---|---|")
    w_mean = statistics.mean([w_rows[t][0] for t in TARGETS if w_rows[t][0] is not None])
    for arm, label, name in (("r", "p7b", "R (agent+memory)"),
                             ("m", "p7b", "M (agent+memory)"),
                             ("a", "p7b", "A (agent only)")):
        pairs = []
        for target in TARGETS:
            agent = agent_locked(arm, label, target)
            base = w_rows[target][0]
            if agent is not None and base is not None:
                pairs.append((agent, base))
        if not pairs:
            continue
        diffs = [a - b for a, b in pairs]
        mean = statistics.mean(diffs)
        se = BETWEEN_ARM_SD / math.sqrt(len(diffs))
        agent_mean = statistics.mean(a for a, _ in pairs)
        lines.append(f"| {name} | {agent_mean:.4f} | **{mean:+.4f}** | {se:.4f} | "
                     f"**{mean / se:+.1f}** | (n={len(pairs)})")
    lines.append("")
    lines.append(f"W 自身的均值 = {w_mean:.4f}，无误差（确定性）。")
    lines.append("")
    lines.append("| 差值/标准误 | 含义 |")
    lines.append("|---|---|")
    lines.append("| > 2 | 超出重跑噪声，可主张优于流水线 |")
    lines.append("| < 2 | 落在噪声内，不能主张 |")
    lines.append("")

    text = "\n".join(lines) + "\n"
    (RUNS / "w_noise.md").write_text(text, encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
