#!/usr/bin/env python3
"""Phase 7 summary statistics -- p7b four-arm round plus the p7c/p7d replications.

Four measurement decisions, each forced by an audit of the raw data:

1. Quality is compared on the LOCKED test set only. Every ticket picks its own
   scaffold validation split, so `best_scaffold_auroc` is measured on different
   molecules per arm. On DRD2 the same pair of arms differed by -0.080 on
   validation and +0.012 on the locked set, in opposite order.

2. EF@1% and AUPRC are reported as diagnostics, not as outcomes. The locked test
   sets are 55-99% positive, so EF@1% sits at its ceiling 1/prevalence for every
   competitive model and cannot separate arms.

3. Tokens are NOT compared per ticket. The driver sums the ledger over the
   ticket's [started_at, ended_at] window, but the collection timestamps lag
   `ended_at`, so the tail calls of every ticket (the largest ones) fall outside
   the window. Measured coverage is 51-64% of the ledger. Whole-round ledger
   totals are the only sound token figure.

4. Ties are counted, not hidden: where two arms produced byte-identical models
   the paired difference is exactly zero and the effective sample size falls.

Outputs: ops/phase7_runs/summary_stats.md and summary_stats.json
"""
from __future__ import annotations

import json
import math
import random
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path("/home/linhan_cluster/evo_vs_rsi")
RUNS = ROOT / "ops" / "phase7_runs"
ART = ROOT / "scientific" / ".artifacts"
OUT_MD = RUNS / "summary_stats.md"
OUT_JSON = RUNS / "summary_stats.json"

TARGETS = ["d2", "5ht", "adr", "drd2", "mor", "cbr", "kor", "ca2", "pt"]
SIZES = {"d2": 6811, "5ht": 4828, "adr": 3376, "drd2": 3293, "mor": 2790,
         "cbr": 2309, "kor": 1899, "ca2": 7301, "pt": 2824}
ARM_NAME = {"r": "R 记忆+自改", "a": "A 无记忆", "m": "M 记忆", "w": "W 固定流程"}
LEDGER = {
    ("p7b", "a"): ART / "usage_p7b_a.jsonl",
    ("p7b", "m"): ART / "usage_p7b_m.jsonl",
    ("p7b", "r"): ART / "usage_p7b_r.jsonl",
    ("p7c", "r"): ART / "usage_p7c_r.jsonl",
    ("p7d", "m"): ART / "usage_calib_m.jsonl",
}

# ---------------------------------------------------------------- loading


def load_records() -> list[dict]:
    pat = re.compile(r"^([ramw])_(\d\d)_([a-z0-9]+)(?:_(.+))?$")
    out = []
    for path in sorted(RUNS.glob("[ramw]_[0-9][0-9]_*.json")):
        m = pat.match(path.stem)
        if not m:
            continue
        rec = json.loads(path.read_text(encoding="utf-8"))
        arm, seq, target, label = m.group(1), int(m.group(2)), m.group(3), m.group(4) or ""
        tokens = (rec.get("tokens") or {}).get("total_tokens")
        models = rec.get("models")
        out.append({
            "file": path.name, "arm": arm, "seq": seq, "target": target, "label": label,
            "wall": rec.get("wall_seconds"),
            "jobs": rec.get("jobs_total", rec.get("jobs_run")),
            "failed": rec.get("jobs_failed"),
            "models": len(models) if isinstance(models, list) else models,
            "scaffold_auroc": rec.get("best_scaffold_auroc", rec.get("auroc")),
            "locked_auroc": rec.get("locked_auroc"),
            "tokens_record": float(tokens) if tokens else None,
            "recorded_at": rec.get("recorded_at"),
            "workdir": rec.get("workdir") or "",
        })
    return out


def load_receipts(records: list[dict]) -> dict[tuple[str, str, str], dict]:
    out = {}
    for row in records:
        wd = row["workdir"]
        if not wd or not Path(wd).is_dir():
            continue
        for path in sorted(Path(wd).rglob("*.json")):
            if ".jobs" in path.parts:
                continue
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                continue
            if isinstance(payload, dict) and "metrics" in payload and "protected_output" in payload:
                metrics = payload.get("metrics") or {}
                counts = None
                protected_name = None
                protected = Path(str(payload.get("protected_output") or ""))
                if protected.is_file():
                    protected_name = protected.name
                    try:
                        counts = json.loads(protected.read_text(encoding="utf-8")).get("counts")
                    except (ValueError, OSError):
                        counts = None
                out[(row["arm"], row["label"], row["target"])] = {
                    "auroc": metrics.get("auroc"), "auprc": metrics.get("auprc"),
                    "ef1": metrics.get("ef_at_1pct"), "ef5": metrics.get("ef_at_5pct"),
                    "evaluated_as": payload.get("target"), "desc_set": payload.get("desc_set"),
                    "counts": counts, "protected_name": protected_name, "receipt": path.name,
                }
    return out


def load_ledger(path: Path) -> list[dict]:
    events = []
    if not path.exists():
        return events
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            obj = json.loads(line)
        except ValueError:
            continue
        if "total_tokens" not in obj or not obj.get("ts"):
            continue
        events.append({"ts": datetime.fromisoformat(obj["ts"].replace("Z", "+00:00")),
                       "tokens": float(obj.get("total_tokens") or 0),
                       "cached": float(obj.get("cached_tokens") or 0),
                       "calls": 1})
    return sorted(events, key=lambda e: e["ts"])

# ---------------------------------------------------------------- stats


def median(values: list[float]) -> float:
    v = sorted(values)
    n = len(v)
    if n == 0:
        return float("nan")
    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) / 2


def describe(values: list[float]) -> dict:
    clean = sorted(v for v in values if v is not None)
    n = len(clean)
    if n == 0:
        return {"n": 0}
    mean = sum(clean) / n
    sd = math.sqrt(sum((v - mean) ** 2 for v in clean) / (n - 1)) if n > 1 else 0.0
    q1 = clean[int(0.25 * (n - 1))] if n > 1 else clean[0]
    q3 = clean[int(0.75 * (n - 1))] if n > 1 else clean[0]
    return {"n": n, "median": median(clean), "q1": q1, "q3": q3,
            "min": clean[0], "max": clean[-1], "mean": mean, "sd": sd,
            "cv": (sd / mean) if mean else None}


def geometric_mean(values: list[float]) -> float:
    logs = [math.log(v) for v in values if v and v > 0]
    return math.exp(sum(logs) / len(logs)) if logs else float("nan")


def sign_flip_p(diffs: list[float]) -> tuple[float, int]:
    """Exact two-sided sign-flip permutation test on the mean paired difference."""
    n = len(diffs)
    if n == 0:
        return float("nan"), 0
    observed = abs(sum(diffs) / n)
    hits = 0
    for mask in range(1 << n):
        total = 0.0
        for i, d in enumerate(diffs):
            total += -d if (mask >> i) & 1 else d
        if abs(total / n) >= observed - 1e-12:
            hits += 1
    return hits / (1 << n), 1 << n


def sign_test(diffs: list[float]) -> tuple[float, int, int, int]:
    pos = sum(1 for d in diffs if d > 1e-12)
    neg = sum(1 for d in diffs if d < -1e-12)
    n = pos + neg
    if n == 0:
        return 1.0, pos, neg, 0
    k = min(pos, neg)
    tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
    return min(1.0, 2 * tail), pos, neg, n


def bootstrap_ci(diffs: list[float], reps: int = 10000, seed: int = 20261109) -> tuple[float, float]:
    rng = random.Random(seed)
    n = len(diffs)
    stats = []
    for _ in range(reps):
        sample = [diffs[rng.randrange(n)] for _ in range(n)]
        stats.append(sum(sample) / n)
    stats.sort()
    return stats[int(0.025 * reps)], stats[int(0.975 * reps)]


def ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=lambda i: values[i])
    out = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        avg = (i + j) / 2 + 1
        for k in range(i, j + 1):
            out[order[k]] = avg
        i = j + 1
    return out


def pearson(x: list[float], y: list[float]) -> float:
    n = len(x)
    mx, my = sum(x) / n, sum(y) / n
    num = sum((a - mx) * (b - my) for a, b in zip(x, y))
    den = math.sqrt(sum((a - mx) ** 2 for a in x) * sum((b - my) ** 2 for b in y))
    return num / den if den else 0.0


def spearman_perm(values: list[float], positions: list[float], reps: int = 20000,
                  seed: int = 7) -> tuple[float, float]:
    rho = pearson(ranks(values), ranks(positions))
    rng = random.Random(seed)
    base = list(positions)
    hits = 0
    for _ in range(reps):
        rng.shuffle(base)
        if abs(pearson(ranks(values), ranks(base))) >= abs(rho) - 1e-12:
            hits += 1
    return rho, (hits + 1) / (reps + 1)

# ---------------------------------------------------------------- main


def main() -> int:
    records = load_records()
    receipts = load_receipts(records)
    ledgers = {key: load_ledger(path) for key, path in LEDGER.items()}

    def pick(arm: str, label: str) -> list[dict]:
        return sorted([r for r in records if r["arm"] == arm and r["label"] == label],
                      key=lambda r: r["seq"])

    arms = {a: pick(a, "p7b") for a in "ramw"}
    rprime = pick("r", "p7c")
    mrep = pick("m", "p7d")

    for arm, rows in list(arms.items()) + [("r", rprime), ("m", mrep)]:
        for rec in rows:
            key = (arm, rec["label"] or "p7b", rec["target"])
            info = receipts.get(key) or {}
            rec["locked"] = info.get("auroc") if info else rec.get("locked_auroc")
            rec["auprc"] = info.get("auprc")
            rec["ef1"] = info.get("ef1")
            rec["ef5"] = info.get("ef5")
            rec["counts"] = info.get("counts")
            rec["protected_name"] = info.get("protected_name")
    for rec in arms["w"]:
        rec["locked"] = rec.get("locked_auroc")

    # ---- ledger audit ---------------------------------------------------
    audit = []
    for (round_name, arm), events in ledgers.items():
        if not events:
            continue
        rows = pick(arm, round_name)
        windows = []
        for rec in rows:
            if not rec.get("recorded_at") or not rec.get("wall"):
                continue
            end = datetime.fromisoformat(rec["recorded_at"].replace("Z", "+00:00"))
            windows.append((end - timedelta(seconds=float(rec["wall"])), end))
        total = sum(e["tokens"] for e in events)
        inside = sum(e["tokens"] for e in events if any(a <= e["ts"] <= b for a, b in windows))
        audit.append({
            "round": round_name, "arm": arm,
            "first": events[0]["ts"].isoformat(), "last": events[-1]["ts"].isoformat(),
            "calls": len(events), "total": total,
            "per_target": total / len(rows) if rows else None,
            "window_coverage": (inside / total) if total else None,
            "cached_share": (sum(e["cached"] for e in events) / total) if total else None,
            "n_records": len(rows),
        })

    # ---- descriptive ----------------------------------------------------
    desc = {}
    for arm, rows in list(arms.items()) + [("r_p7c", rprime), ("m_p7d", mrep)]:
        ledger_key = ("p7c", "r") if arm == "r_p7c" else ("p7d", "m") if arm == "m_p7d" else ("p7b", arm)
        entries = [a for a in audit if (a["round"], a["arm"]) == ledger_key]
        desc[arm] = {
            "wall": describe([r["wall"] for r in rows]),
            "jobs": describe([r["jobs"] for r in rows]),
            "models": describe([r["models"] for r in rows]),
            "locked": describe([r["locked"] for r in rows]),
            "fail_rate": (sum(r["failed"] or 0 for r in rows) / sum(r["jobs"] or 0 for r in rows)
                          if sum(r["jobs"] or 0 for r in rows) else None),
            "round_tokens": entries[0]["total"] if entries else None,
            "round_tokens_per_target": entries[0]["per_target"] if entries else None,
        }

    # ---- paired cost ----------------------------------------------------
    def paired_ratio(rows_x: list[dict], rows_y: list[dict], field: str) -> list[float]:
        index = {r["target"]: r for r in rows_y}
        out = []
        for rec in rows_x:
            other = index.get(rec["target"])
            if other and rec.get(field) and other.get(field):
                out.append(rec[field] / other[field])
        return out

    cost = {}
    for label, x, y in (("r_vs_a", arms["r"], arms["a"]), ("m_vs_a", arms["m"], arms["a"]),
                        ("r_vs_m", arms["r"], arms["m"]), ("r_vs_w", arms["r"], arms["w"]),
                        ("m_vs_w", arms["m"], arms["w"]),
                        ("rprime_vs_r", rprime, arms["r"])):
        entry = {}
        for field in ("wall", "jobs", "models"):
            ratios = paired_ratio(x, y, field)
            if ratios:
                logs = [math.log(v) for v in ratios]
                p, nperm = sign_flip_p(logs)
                entry[field] = {"n": len(ratios), "geomean": geometric_mean(ratios),
                                "median": median(ratios), "min": min(ratios), "max": max(ratios),
                                "slower": sum(1 for v in ratios if v > 1),
                                "p": p, "perm": nperm}
        cost[label] = entry

    # ---- paired quality --------------------------------------------------
    def quality_block(x: list[dict], y: list[dict]) -> dict | None:
        index = {r["target"]: r for r in y}
        diffs, pairs = [], []
        for rec in x:
            other = index.get(rec["target"])
            if other and rec.get("locked") is not None and other.get("locked") is not None:
                d = rec["locked"] - other["locked"]
                diffs.append(d)
                identical = (abs(d) < 1e-12 and rec.get("auprc") is not None
                             and rec.get("auprc") == other.get("auprc"))
                pairs.append({"target": rec["target"], "x": rec["locked"], "y": other["locked"],
                              "diff": d, "identical": bool(identical)})
        if not diffs:
            return None
        p_flip, nperm = sign_flip_p(diffs)
        p_sign, pos, neg, n_eff = sign_test(diffs)
        low, high = bootstrap_ci(diffs) if len(diffs) >= 3 else (None, None)
        return {"n": len(diffs), "mean": sum(diffs) / len(diffs), "median": median(diffs),
                "min": min(diffs), "max": max(diffs),
                "ties": sum(1 for d in diffs if abs(d) < 1e-12),
                "pos": pos, "neg": neg, "n_eff": n_eff,
                "p_signflip": p_flip, "perm": nperm, "p_sign": p_sign,
                "ci": [low, high], "pairs": pairs,
                "identical_pairs": sum(1 for p in pairs if p["identical"])}

    quality = {}
    for label, x, y in (("r_vs_a", arms["r"], arms["a"]), ("m_vs_a", arms["m"], arms["a"]),
                        ("r_vs_m", arms["r"], arms["m"]), ("w_vs_r", arms["w"], arms["r"]),
                        ("w_vs_a", arms["w"], arms["a"]),
                        ("rprime_vs_r", rprime, arms["r"]), ("mrep_vs_m", mrep, arms["m"])):
        block = quality_block(x, y)
        if block:
            quality[label] = block

    # ---- trend -----------------------------------------------------------
    trends = {}
    for arm, rows in list(arms.items()) + [("r_p7c", rprime)]:
        usable = [r for r in rows if r.get("wall")]
        if len(usable) < 4:
            continue
        entry = {}
        for field in ("wall", "jobs"):
            vals = [r[field] for r in usable]
            if any(v is None for v in vals):
                continue
            entry[field + "_vs_seq"] = spearman_perm(vals, [r["seq"] for r in usable])
            entry[field + "_vs_size"] = spearman_perm(vals, [SIZES[r["target"]] for r in usable])
        trends[arm] = entry

    # ---- micro -----------------------------------------------------------
    micro = {}
    for arm in "ram":
        for path in sorted(RUNS.glob(f"{arm}_*_p7b.code.json")):
            try:
                code = json.loads(path.read_text(encoding="utf-8"))
            except ValueError:
                continue
            micro.setdefault(arm, []).append({
                "target": path.stem.split("_")[1],
                "n_featurizations": code.get("n_featurizations"),
                "n_models": code.get("n_models"),
                "splits": code.get("split_strategies"),
                "failure_rate": code.get("failure_rate"),
                "first_success_index": code.get("first_success_index"),
            })

    # ---- test-set resolution --------------------------------------------
    counts_by_target, names_by_target = {}, {}
    for rec in arms["r"] + arms["a"] + arms["m"] + rprime:
        if rec.get("counts"):
            counts_by_target.setdefault(rec["target"], rec["counts"])
        if rec.get("protected_name"):
            names_by_target.setdefault(rec["target"], set()).add(rec["protected_name"])

    def hanley_se(a: float, n_pos: int, n_neg: int) -> float:
        q1 = a / (2 - a)
        q2 = 2 * a * a / (1 + a)
        var = (a * (1 - a) + (n_pos - 1) * (q1 - a * a) + (n_neg - 1) * (q2 - a * a)) / (n_pos * n_neg)
        return math.sqrt(max(var, 0.0))

    # ---- ef ceiling ------------------------------------------------------
    ceiling = {}
    for rec in arms["r"] + arms["a"] + arms["m"] + rprime:
        if rec.get("ef1") is not None:
            ceiling.setdefault(rec["target"], {"ef1": set(), "ef5": set(), "auprc": []})
            ceiling[rec["target"]]["ef1"].add(round(rec["ef1"], 3))
            if rec.get("ef5") is not None:
                ceiling[rec["target"]]["ef5"].add(round(rec["ef5"], 3))
            if rec.get("auprc") is not None:
                ceiling[rec["target"]]["auprc"].append(rec["auprc"])

    out = {"generated_at": datetime.now(timezone.utc).isoformat(),
           "counts": {k: len(v) for k, v in arms.items()},
           "n_rprime": len(rprime), "n_mrep": len(mrep),
           "audit": audit, "desc": desc, "cost": cost, "quality": quality,
           "trends": trends, "micro": micro,
           "ef_ceiling": {k: {"ef1": sorted(v["ef1"]), "ef5": sorted(v["ef5"]),
                              "auprc_range": [min(v["auprc"]), max(v["auprc"])] if v["auprc"] else None}
                          for k, v in ceiling.items()},
           "rows": {k: [{kk: vv for kk, vv in r.items() if kk != "workdir"} for r in v]
                    for k, v in list(arms.items()) + [("r_p7c", rprime), ("m_p7d", mrep)]}}
    OUT_JSON.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")

    # ---- markdown --------------------------------------------------------
    L = []
    add = L.append
    add("# Phase 7 汇总统计（p7b 四臂 + p7c/p7d 复现）")
    add("")
    add(f"生成时间：{datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')}")
    add("")
    add("> 质量只用锁定测试集比较；成本只用同靶点配对比值；token 只用整轮台账。")
    add("")

    add("## 一、数据清单")
    add("")
    add("| 轮次 | 臂 | 靶点数 | 用途 |")
    add("|---|---|---|---|")
    for arm in "ramw":
        add(f"| p7b | {ARM_NAME[arm]} | {len(arms[arm])} | 四臂主比较 |")
    add(f"| p7c | R（v7 harness） | {len(rprime)} | 同臂跨版本 |")
    add(f"| p7d | M（标定重复，进行中） | {len(mrep)} | 臂内噪声 |")
    add("")

    add("## 二、token 台账审计")
    add("")
    add("| 轮次 | 臂 | 台账跨度 (UTC) | 调用数 | 整轮 token | 每靶点 | 工单窗口覆盖率 | 缓存占比 |")
    add("|---|---|---|---|---|---|---|---|")
    for a in audit:
        span = f"{a['first'][11:16]}–{a['last'][11:16]}"
        add(f"| {a['round']} | {a['arm'].upper()} | {span} | {a['calls']} | {a['total']:,.0f} | "
            f"{(a['per_target'] or 0):,.0f} | {(a['window_coverage'] or 0) * 100:.1f}% | "
            f"{(a['cached_share'] or 0) * 100:.1f}% |")
    add("")
    add("工单窗口覆盖率 = 落在 `[recorded_at − wall, recorded_at]` 内的 token / 台账总量。"
        "驱动器按 `[started_at, ended_at]` 求和，但采集时间戳晚于 `ended_at`，"
        "每个工单收尾阶段的长上下文调用落在窗口外，因此**逐靶点 token 系统性偏低**，"
        "只能作下界，不能用于臂间配对比较。")
    add("")
    add("R 与 M 的 p7b 记录在 11-09 08:01 被批量重收，`recorded_at` 已不是当时的运行时刻，"
        "所以它们的窗口覆盖率（21% / 0%）不代表漏记，只说明窗口法对重收记录失效；"
        "A 与 R′ 的记录是运行当时写的，覆盖率 63.6–63.8% 才是窗口法的真实上限。")
    add("")

    add("## 三、描述统计（p7b 各臂 n=9；末两行为复现轮）")
    add("")
    add("| 臂 | 墙钟 s 中位 [IQR] | 作业 中位 [IQR] | 模型 中位 | 整轮 token | 锁定 AUROC 均值 [范围] | 失败率 |")
    add("|---|---|---|---|---|---|---|")
    for arm in "ramw":
        d = desc[arm]
        tok = f"{d['round_tokens']:,.0f}" if d["round_tokens"] else "—"
        add(f"| {ARM_NAME[arm]} | {d['wall']['median']:.0f} [{d['wall']['q1']:.0f}–{d['wall']['q3']:.0f}] | "
            f"{d['jobs']['median']:.0f} [{d['jobs']['q1']:.0f}–{d['jobs']['q3']:.0f}] | "
            f"{(f"{d['models']['median']:.0f}" if d['models'].get('n') else '—')} | {tok} | "
            f"{d['locked']['mean']:.4f} [{d['locked']['min']:.4f}–{d['locked']['max']:.4f}] | "
            f"{(d['fail_rate'] or 0) * 100:.1f}% |")
    for key, name in (("r_p7c", "R′ (p7c)"), ("m_p7d", "M (p7d)")):
        d = desc[key]
        if not d["wall"]["n"]:
            continue
        tok = f"{d['round_tokens']:,.0f}" if d["round_tokens"] else "—"
        add(f"| {name} | {d['wall']['median']:.0f} [{d['wall']['q1']:.0f}–{d['wall']['q3']:.0f}] | "
            f"{d['jobs']['median']:.0f} [{d['jobs']['q1']:.0f}–{d['jobs']['q3']:.0f}] | "
            f"{d['models'].get('median', 0):.0f} | {tok} | "
            f"{d['locked']['mean']:.4f} [{d['locked']['min']:.4f}–{d['locked']['max']:.4f}] | "
            f"{(d['fail_rate'] or 0) * 100:.1f}% |")
    add("")

    add("## 四、成本：配对比值（同靶点，>1 表示左侧更贵）")
    add("")
    add("| 对比 | 指标 | n | 几何均值 | 中位 | 范围 | 左侧更贵 | 符号翻转 p |")
    add("|---|---|---|---|---|---|---|---|")
    for label, entry in cost.items():
        for field in ("wall", "jobs", "models"):
            if field not in entry:
                continue
            e = entry[field]
            add(f"| {label} | {field} | {e['n']} | {e['geomean']:.2f}× | {e['median']:.2f}× | "
                f"{e['min']:.2f}–{e['max']:.2f}× | {e['slower']}/{e['n']} | {e['p']:.4f} |")
    add("")

    add("## 五、质量：锁定测试集配对差（AUROC）")
    add("")
    add("| 对比 | n | 均值差 | 中位 | 范围 | 零差 | +/- | 指标全同 | 符号翻转 p | 符号检验 p | 95% CI |")
    add("|---|---|---|---|---|---|---|---|---|---|---|")
    for label, e in quality.items():
        ci = e["ci"]
        ci_text = f"[{ci[0]:+.4f}, {ci[1]:+.4f}]" if ci[0] is not None else "—"
        add(f"| {label} | {e['n']} | {e['mean']:+.4f} | {e['median']:+.4f} | "
            f"{e['min']:+.4f}–{e['max']:+.4f} | {e['ties']} | {e['pos']}/{e['neg']} | "
            f"{e['identical_pairs']} | {e['p_signflip']:.4f} | {e['p_sign']:.4f} | {ci_text} |")
    add("")
    add("`指标全同` = 两臂的 AUROC 与 AUPRC 逐位相同。这些配对不携带臂间信息，只说明两臂交付了同一模型；"
        "有效样本量应减去它们。注意：不能再拿受保护文件的 model_sha256 做佐证——见第十一节。")
    add("")

    add("## 六、序列趋势与数据规模")
    add("")
    add("| 臂 | 墙钟 vs 序列 ρ (p) | 墙钟 vs 样本数 ρ (p) | 作业 vs 序列 ρ (p) | 作业 vs 样本数 ρ (p) |")
    add("|---|---|---|---|---|")

    def fmt(pair):
        return f"{pair[0]:+.3f} ({pair[1]:.3f})" if pair else "—"

    for arm, e in trends.items():
        add(f"| {arm} | {fmt(e.get('wall_vs_seq'))} | {fmt(e.get('wall_vs_size'))} | "
            f"{fmt(e.get('jobs_vs_seq'))} | {fmt(e.get('jobs_vs_size'))} |")
    add("")
    add("序列顺序按样本量降序，所以 `vs 序列` 与 `vs 样本数` 天然负相关；只有两者分离时才能谈「越跑越省」。")
    add("")

    add("## 七、微观指标（p7b）")
    add("")
    add("| 臂 | 靶点 | 特征化种类 | 模型族 | 失败率 | 首个成功作业位次 |")
    add("|---|---|---|---|---|---|")
    for arm in "ram":
        for row in micro.get(arm, []):
            add(f"| {arm.upper()} | {row['target']} | {row['n_featurizations']} | {row['n_models']} | "
                f"{(row['failure_rate'] or 0) * 100:.1f}% | {row['first_success_index']} |")
    add("")

    add("## 八、检验集分辨率：EF 饱和与 AUROC 标准误")
    add("")
    add("| 靶点 | 阳性/阴性 | 阳性率 | EF@1% 取值 | EF@5% 取值 | AUPRC 范围 | AUROC 标准误 |")
    add("|---|---|---|---|---|---|---|")
    for target, v in out["ef_ceiling"].items():
        c = counts_by_target.get(target) or {}
        npos, nneg = c.get("positives"), c.get("negatives")
        prev = f"{npos / (npos + nneg) * 100:.1f}%" if npos and nneg else "—"
        rng = f"{v['auprc_range'][0]:.4f}–{v['auprc_range'][1]:.4f}" if v["auprc_range"] else "—"
        aurocs = [r["locked"] for r in arms["r"] + arms["a"] + arms["m"] + rprime
                  if r["target"] == target and r.get("locked") is not None]
        se = f"{hanley_se(median(aurocs), npos, nneg):.4f}" if aurocs and npos and nneg else "—"
        add(f"| {target} | {npos or '—'}/{nneg or '—'} | {prev} | {v['ef1']} | {v['ef5']} | {rng} | {se} |")
    add("")
    add("EF@1% 的上限就是 1/阳性率：CBR 的检验集只有 4 个阴性分子，top-1% 只有 3 个位置，"
        "任何能用的模型都会顶到上限，因此 EF 不能区分臂；AUPRC 同样被高阳性率压缩到 0.94–1.00。"
        "AUROC 标准误按 Hanley–McNeil 计算：CBR 约 0.12，意味着 +0.15 的臂间差只有约 1.3 个标准误。")
    add("")
    add("")

    add("## 九、逐靶点明细（p7b）")
    add("")
    add("| 靶点 | 臂 | 墙钟 s | 作业 | 失败 | 模型 | 锁定 AUROC | EF@1% |")
    add("|---|---|---|---|---|---|---|---|")
    for target in TARGETS:
        for arm in "ramw":
            rec = next((r for r in arms[arm] if r["target"] == target), None)
            if not rec:
                continue
            add(f"| {target} | {arm.upper()} | {rec['wall']:.0f} | {rec['jobs']} | {rec['failed']} | "
                f"{rec['models'] if rec['models'] is not None else '—'} | "
                f"{rec['locked'] if rec['locked'] is not None else '—'} | "
                f"{rec.get('ef1') if rec.get('ef1') is not None else '—'} |")
    add("")

    add("## 十、复现观测")
    add("")
    add("| 记录 | 靶点 | 墙钟 s | 作业 | 模型 | 锁定 AUROC | 与主轮差 |")
    add("|---|---|---|---|---|---|---|")
    base = {r["target"]: r for r in arms["m"]}
    base_r = {r["target"]: r for r in arms["r"]}
    for rec in mrep:
        ref = base.get(rec["target"], {}).get("locked")
        diff = f"{rec['locked'] - ref:+.4f}" if (ref is not None and rec["locked"] is not None) else "—"
        add(f"| M p7d | {rec['target']} | {rec['wall']:.0f} | {rec['jobs']} | {rec['models']} | "
            f"{rec['locked']} | {diff} |")
    for rec in rprime:
        ref = base_r.get(rec["target"], {}).get("locked")
        diff = f"{rec['locked'] - ref:+.4f}" if (ref is not None and rec["locked"] is not None) else "—"
        add(f"| R p7c | {rec['target']} | {rec['wall']:.0f} | {rec['jobs']} | {rec['models']} | "
            f"{rec['locked']} | {diff} |")
    add("")

    add("## 十一、数据质量问题清单（影响结论的解释范围）")
    add("")
    add("| # | 问题 | 证据 | 后果 |")
    add("|---|---|---|---|")
    collision = []
    for target, names in sorted(names_by_target.items()):
        collision.append(f"{target}:{len(names)}")
    add(f"| 1 | 锁定评测的受保护指标文件跨臂同名 | 每靶点仅 {{{', '.join(collision)}}} 个文件名对应 4 个臂；"
        f"文件名形如 `metrics_test_locked_agent_Ki_v1_._5HT.json` | `--workspace .` 让工单名退化为 `.`，"
        f"后写覆盖先写；model_sha256 无法归属到具体臂，上一版「KOR 两臂 sha 相同」的论据作废 |")
    add("| 2 | EF@1% / AUPRC 饱和 | 见第八节 | 只能用 AUROC 谈质量 |")
    add("| 3 | 逐靶点 token 系统性偏低 | 窗口覆盖率 21%–64% | token 只按整轮台账比较 |")
    add("| 4 | 墙钟被基础设施卡顿污染 | R ca2 2064 s（18 作业）、R′ cbr 4124 s（24 作业） | 墙钟中位数稳健，单点不可用 |")
    add(f"| 5 | 臂内重复未完成 | p7d 仅 {len(mrep)}/9 靶点 | 噪声地板只有 {len(mrep)} 个观测，暂不能定论 |")
    add("")

    add("## 十二、初步结论")
    add("")
    add("1. **记忆机制没有降低 token 成本。** 三臂整轮台账 A 28.8M / R 32.2M / M 33.8M，"
        "每靶点 3.20 / 3.58 / 3.75M，差异 ≤17%，小于同臂同靶点的墙钟重复波动（0.71–3.1 倍）。"
        "上一版「有记忆比 A 省 7.9 倍 token」是把旧轮 101 作业的 A#1（10.13M，估算）当成了 A 臂代表，"
        "而 p7b 的 A 工单只有 19–34 个作业。")
    add("2. **省作业的只有 M。** M/A 作业 0.80×（p=0.090，方向 7/9）、模型数 0.65×（p=0.016）。"
        "R 反而更贵：相对 A 墙钟 1.66×（8/9）、相对 M 作业 1.29×（p=0.043）、墙钟 1.69×（p=0.008）。"
        "**自修改层在当前数据上只增加成本，没有质量回报**（R−M = −0.0172）。")
    add("3. **质量四臂不可区分，只有 W 明显更差。** R−A +0.0118（p=0.50，5/9 对指标完全相同）；"
        "M−A +0.0290（p=0.25，符号检验 0.63）；W−R −0.0275（p=0.035，R 在 8/9 靶点更好）。"
        "唯一显著的质量结论是「固定流程弱于 agent」。")
    add("4. **臂间差与臂内噪声同量级。** M 同靶点重复：5HT −0.0401、其余 0.0000；R′ vs R +0.0112"
        "（4 正 0 负 5 平，p=0.125）。R−A 的 +0.0118 落在同一量级，所以不能主张记忆提升质量。"
        "按现有噪声水平，9 个配对靶点只能检出 >0.04 的效应。")
    add("5. **检验集分辨率是硬约束。** CBR 只有 4 个阴性（AUROC 标准误 0.11）、5HT 6 个、ADR 17 个；"
        "EF@1% 与 AUPRC 全部饱和。要证明哪怕 0.03 的质量差，也得先换更平衡的检验集，而不是加臂。")
    add("6. **唯一干净的「越跑越省」信号来自 M 的墙钟**（vs 序列 ρ=−0.778, p=0.018；vs 样本数 ρ=0.109），"
        "A 无此趋势（墙钟 vs 序列 ρ=+0.367）。但 n=9 且未做多重比较校正，只能算提示。")
    add("7. **p7b 未复现「记忆锚定使搜索变窄」**：三臂每个靶点都用了 2–9 种特征化，没有任何一臂只用 1 种"
        "（base 轮 R 有 4/9 只用 1 种）。失败率 R 9.1% / A 8.2% / M 10.4%，无差异。")
    add("8. **R′（v7）相对 R：墙钟 −37%、token −11%（整轮 28.8M vs 32.2M）、质量 +0.011（不显著）。** 唯一大改善是 CBR +0.097，"
        "代价是 4124 s（比其他靶点贵一个数量级），且该检验集只有 4 个阴性，不足以支撑结论。")
    add("")

    OUT_MD.write_text("\n".join(L) + "\n", encoding="utf-8")
    print(f"wrote {OUT_MD}")
    print(f"wrote {OUT_JSON}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
