#!/usr/bin/env python3
"""How noisy is a single scaffold validation split? Five re-splits, one config.

The problem this measures
------------------------
Every ticket picks its own scaffold validation split, so a "best validation
AUROC" carries the split's luck. On DRD2 the same pair of arms differed by 0.080
on their own validation splits and by 0.012 on the locked test set, in the
opposite order. Before adopting any replacement estimator (a frozen split, or
k-fold cross-validation) we need to know how large that luck is.

What it does
------------
For one already-fitted configuration (features file + model family + seed), it
re-splits the same labels five times with different scaffold seeds and retrains
each time. The spread across those five AUROCs is the split noise; their mean is
the cheap approximation of a cross-validated estimate. The locked-test AUROC, when
a receipt exists, is the reference the estimators are judged against.

This deliberately reuses the harness's own `data.split` and `modeling.train`
entry points, so the semantics match the agent's tool calls exactly — it is not a
reimplementation that might featurize differently.

Usage:
  python3 ops/cv_repeat.py --workdir <workdir> --model-dir models/foo --label-source chembl_drd2_ki
  python3 ops/cv_repeat.py --batch          # every (arm, target) with a recorded finalist
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "ops" / "phase7_runs"
PYTHON = ROOT / "scientific" / ".venv" / "bin" / "python"
DATA = ROOT / "scientific" / ".artifacts"
SEEDS = ["17", "23", "42", "7", "2024"]
TEST_FRACTION = "0.2"
VAL_FRACTION = "0.1"
OUT = RUNS / "cv_repeat.md"


def job_argvs(workdir: Path) -> list[dict]:
    out = []
    for path in (workdir / ".jobs").glob("*/result.json"):
        try:
            out.append(json.loads(path.read_text(encoding="utf-8")))
        except (ValueError, OSError):
            continue
    return out


def kv_of(job: dict) -> dict:
    argv = [item for item in job.get("argv") or [] if isinstance(item, str)]
    kv = {}
    for position, item in enumerate(argv):
        if item.startswith("--") and position + 1 < len(argv):
            kv[item.lstrip("-")] = argv[position + 1]
    return kv


def finalist_config(workdir: Path, model_dir: str) -> dict | None:
    """Recover the training arguments that produced `model_dir`."""
    target_name = os.path.basename(model_dir.rstrip("/"))
    features = labels = model = seed = label_source = None
    for job in job_argvs(workdir):
        if job.get("tool_id") != "ml.train" or job.get("state") != "SUCCEEDED":
            continue
        kv = kv_of(job)   # keys carry no leading dashes
        if os.path.basename(str(kv.get("output-dir") or "").rstrip("/")) != target_name:
            continue
        features = kv.get("features")
        labels = kv.get("labels")
        model = kv.get("model")
        seed = kv.get("seed")
        label_source = kv.get("label-source")
    if not (features and labels and model):
        return None
    return {"features": features, "labels": labels, "model": model,
            "seed": seed or "17", "label_source": label_source or ""}


def resolve(workdir: Path, relative: str) -> Path | None:
    path = (workdir / relative)
    if path.exists():
        return path
    # absolute paths in argv keep working
    candidate = Path(relative)
    return candidate if candidate.exists() else None


def run(argv: list[str], cwd: Path) -> tuple[int, str]:
    result = subprocess.run(argv, cwd=str(cwd), capture_output=True, text=True)
    tail = (result.stderr or "").strip().splitlines()[-2:]
    return result.returncode, " | ".join(tail)


def scaffold_folds(labels: Path, n_folds: int, seed: int = 17) -> list[set[str]] | None:
    """Partition molecules into `n_folds` groups of whole Murcko scaffolds.

    Bemis-Murcko scaffolds are grouped before splitting so that no scaffold
    appears in both the training and the held-out part of a fold — the same
    generalisation question the scaffold split asks, but repeated over the whole
    dataset instead of one 10% slice.
    """
    try:
        import csv
        from rdkit import Chem, RDLogger
        from rdkit.Chem.Scaffolds import MurckoScaffold
        import random
    except ImportError:
        return None
    RDLogger.DisableLog("rdApp.*")

    buckets: dict[str, list[str]] = {}
    with labels.open(encoding="utf-8", errors="ignore") as handle:
        for row in csv.DictReader(handle):
            molecule = (row.get("molecule_chembl_id") or "").strip()
            smiles = (row.get("canonical_smiles") or "").strip()
            if not molecule or not smiles:
                continue
            mol = Chem.MolFromSmiles(smiles)
            if mol is None:
                continue
            try:
                scaffold = MurckoScaffold.MurckoScaffoldSmiles(mol=mol, includeChirality=False)
            except Exception:
                scaffold = ""
            buckets.setdefault(scaffold, []).append(molecule)

    groups = [sorted(members) for _, members in sorted(buckets.items(), key=lambda kv: -len(kv[1]))]
    random.Random(seed).shuffle(groups)

    folds: list[set[str]] = [set() for _ in range(n_folds)]
    for index, members in enumerate(groups):
        folds[index % n_folds].update(members)
    return folds


def evaluate(workdir: Path, model_dir: str, n_folds: int = 5) -> dict:
    # every path handed to a subprocess must be absolute: the child runs with
    # cwd=workdir, so a relative feature path would be prefixed twice
    workdir = workdir.resolve()
    config = finalist_config(workdir, model_dir)
    if not config:
        return {"error": "could not recover training arguments"}

    features = resolve(workdir, config["features"])
    labels = resolve(workdir, config["labels"])
    features = features.resolve() if features else None
    labels = labels.resolve() if labels else None
    if not features or not labels:
        return {"error": f"missing features or labels: {features} / {labels}"}

    folds = scaffold_folds(labels, n_folds)
    if not folds:
        return {"error": "scaffold grouping unavailable (rdkit missing?)"}

    scratch = RUNS / "cv_scratch" / f"{workdir.name}__{os.path.basename(model_dir.rstrip('/'))}"
    if scratch.exists():
        shutil.rmtree(scratch)
    scratch.mkdir(parents=True, exist_ok=True)

    all_ids = set().union(*folds)
    rows = []
    for index, held_out in enumerate(folds):
        manifest_rows = {}
        train_pool = sorted(all_ids - held_out)
        # ml.train wants a test partition as well; keep a small slice of train.
        test_slice = set(train_pool[: max(1, len(train_pool) // 20)])
        for molecule in all_ids:
            if molecule in held_out:
                manifest_rows[molecule] = "val"
            elif molecule in test_slice:
                manifest_rows[molecule] = "test"
            else:
                manifest_rows[molecule] = "train"
        manifest = scratch / f"fold_{index}.json"
        manifest.write_text(json.dumps({
            "schema_version": "1", "strategy": "scaffold-grouped-kfold", "seed": 17,
            "n_folds": n_folds, "fold": index,
            "counts": {"train": len(manifest_rows) - len(held_out) - len(test_slice),
                       "val": len(held_out), "test": len(test_slice)},
            "rows": manifest_rows,
        }, ensure_ascii=False), encoding="utf-8")

        out_dir = scratch / f"m_{index}"
        argv = [str(PYTHON), "-m", "evovs_science.modeling.train",
                "--features", str(features), "--labels", str(labels),
                "--output-dir", str(out_dir), "--model", config["model"],
                "--seed", config["seed"], "--test-fraction", "0.05",
                "--label-id-column", "molecule_chembl_id", "--label-column", "label",
                "--split-manifest", str(manifest)]
        if config["label_source"]:
            argv += ["--label-source", config["label_source"]]
        code, err = run(argv, workdir)
        if code != 0:
            rows.append({"fold": index, "error": f"train failed: {err}"})
            continue
        metrics = {}
        metrics_path = out_dir / "metrics.json"
        if metrics_path.exists():
            try:
                metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            except (ValueError, OSError):
                metrics = {}
        rows.append({"fold": index,
                     "auroc": (metrics.get("metrics") or {}).get("auroc"),
                     "n_val": (metrics.get("counts") or {}).get("validation")})

    values = [r["auroc"] for r in rows if isinstance(r.get("auroc"), (int, float))]
    mean = sum(values) / len(values) if values else None
    sd = None
    if len(values) > 1:
        sd = (sum((v - mean) ** 2 for v in values) / (len(values) - 1)) ** 0.5
    return {"config": config, "rows": rows, "mean": mean, "sd": sd,
            "min": min(values) if values else None, "max": max(values) if values else None,
            "n_ok": len(values)}


def locked_auroc(workdir: Path) -> float | None:
    for path in workdir.rglob("*.json"):
        if ".jobs" in path.parts:
            continue
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        if isinstance(payload, dict) and "protected_output" in payload:
            value = (payload.get("metrics") or {}).get("auroc")
            if isinstance(value, (int, float)):
                return float(value)
    return None


def canonical_records(round_label: str = "") -> list[dict]:
    records = []
    for path in sorted(RUNS.glob("[ramw]_[0-9][0-9]_*.json")):
        matched = re.match(r"^([ramw])_(\d\d)_([a-z0-9]+)(?:_(.+))?$", path.stem)
        if not matched or (matched.group(4) or "") != round_label:
            continue
        record = json.loads(path.read_text(encoding="utf-8"))
        if not record.get("best_scaffold_model"):
            continue
        record["arm"] = matched.group(1)
        record["seq"] = int(matched.group(2))
        record["target"] = matched.group(3)
        records.append(record)
    return records


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--workdir")
    parser.add_argument("--model-dir")
    parser.add_argument("--batch", action="store_true")
    parser.add_argument("--round", default="", help="'' for round 7, 'p7b' for the redesigned round")
    args = parser.parse_args()

    jobs = []
    if args.batch:
        for record in canonical_records(args.round):
            jobs.append({"arm": record["arm"], "target": record["target"],
                         "workdir": Path(record["workdir"]),
                         "model_dir": record["best_scaffold_model"],
                         "single": record.get("best_scaffold_auroc")})
    elif args.workdir and args.model_dir:
        jobs.append({"arm": "?", "target": "?", "workdir": Path(args.workdir),
                     "model_dir": args.model_dir, "single": None})
    else:
        parser.error("give --batch, or --workdir with --model-dir")

    lines = ["# scaffold 分组 5 折交叉验证 vs 单次切分", ""]
    lines.append("同一份特征、同一个模型族、同一个种子，按 Bemis-Murcko 骨架分组切成 5 折，"
                 "每折整组骨架留出做验证，其余训练。")
    lines.append("")
    lines.append("> 为什么不是「换种子重切」：实测 `data.split --strategy scaffold` 的验证集"
                 "**与种子完全无关**（同 test/val 比例下 100% 重叠）。真正改变验证集的是 "
                 "`test_fraction` —— R 用 0.2、A 用 0.3，两臂验证集重叠为 0。")
    lines.append("")
    lines.append("| 臂 | 靶点 | 模型 | 单次切分 | 5 次均值 | sd | 极差 | 锁定测试集 |")
    lines.append("|---|---|---|---|---|---|---|---|")
    payload = []
    for job in jobs:
        arm, target, workdir, model_dir = job["arm"], job["target"], job["workdir"], job["model_dir"]
        if not workdir.exists():
            continue
        result = evaluate(workdir, model_dir)
        locked = locked_auroc(workdir)
        single = job.get("single")
        single_text = f"{single:.4f}" if isinstance(single, (int, float)) else "—"
        locked_text = f"{locked:.4f}" if locked else "—"
        if "error" in result:
            lines.append(f"| {arm.upper()} | {target} | {os.path.basename(model_dir.rstrip('/'))} | "
                         f"{single_text} | — | — | — | {locked_text} |")
            payload.append({"arm": arm, "target": target, "error": result["error"], "locked": locked})
            continue
        mean_text = f"{result['mean']:.4f}" if result.get("mean") is not None else "失败"
        sd_text = f"{result['sd']:.4f}" if result.get("sd") is not None else "—"
        span_text = (f"{result['max'] - result['min']:.4f}"
                     if result.get("max") is not None and result.get("min") is not None else "—")
        lines.append(f"| {arm.upper()} | {target} | {os.path.basename(model_dir.rstrip('/'))} | "
                     f"{single_text} | {mean_text} | {sd_text} | {span_text} | {locked_text} |")
        payload.append({"arm": arm, "target": target, "single": single, "mean": result["mean"],
                        "sd": result["sd"], "min": result["min"], "max": result["max"],
                        "locked": locked, "rows": result["rows"]})
        print(f"{arm} {target}: single={single_text} mean={mean_text} sd={sd_text} locked={locked_text}", flush=True)
        if result.get("mean") is None:
            for row in result.get("rows") or []:
                print("   fold", row.get("seed"), "->", row.get("error"), flush=True)

    lines.append("")
    lines.append("判读：5 折均值覆盖全部分子，标准误约为 sd/√5，是比单个 10% 切片更稳的估计；"
                 "若它与锁定测试集的排序一致而单次切分不一致，就说明该改用交叉验证。")
    lines.append("")
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    (RUNS / "cv_repeat.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"wrote {OUT}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
