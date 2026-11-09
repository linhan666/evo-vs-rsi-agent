#!/usr/bin/env python3
"""Make the delivered model the best model, and record the search budget.

Two defects this closes, both measured on the p7 round:

1. **Shipped model was often not the best model.** On 6/9 targets (R), 5/9 (M) and
   6/9 (A) the locked evaluation ran on an earlier model than the one the arm had
   trained best. The recorded quality therefore understated every arm, and by a
   different amount per arm — a bias, not noise. Here the collector re-runs the
   locked evaluation on the best model and marks the record, so "quality" means
   "quality of the model the arm would ship".

2. **The search budget was never recorded.** The tool refuses draw N+1, but the
   record did not say how many draws were used or whether the arm stopped early.
   Both are read from `<workdir>/.search_budget.json` and written onto the record.

Usage:  python ops/p8_finalize.py --label p8b100
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path("/home/linhan_cluster/evo_vs_rsi")
RUNS = ROOT / "ops/phase7_runs"
PYTHON = str(ROOT / "scientific/.venv/bin/python")
ARMS = ("r", "m", "a", "w")


def locked_receipt_auroc(workdir: Path) -> tuple[float | None, str | None]:
    best, best_model = None, None
    for path in sorted((workdir / "evaluation").glob("*_locked.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (ValueError, OSError):
            continue
        value = (payload.get("metrics") or {}).get("auroc")
        if value is not None:
            best, best_model = float(value), str(payload.get("model") or "")
    return best, best_model


def rerun_locked(record: dict, model_rel: str, code: str, desc_set: str, workdir: Path) -> float | None:
    receipt = f"evaluation/{code.lower()}_final_locked.json"
    argv = [PYTHON, "-m", "evovs_science.evaluation.locked",
            "--target", code, "--endpoint", "Ki", "--desc-set", desc_set,
            "--model", model_rel, "--workspace", ".", "--receipt", receipt]
    done = subprocess.run(argv, cwd=str(workdir), capture_output=True, text=True)
    if done.returncode != 0:
        record["locked_rerun_error"] = (done.stderr.strip().splitlines() or [""])[-1:][0][:200]
        return None
    path = workdir / receipt
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    return (payload.get("metrics") or {}).get("auroc")


def process(path: Path, arm: str) -> str:
    record = json.loads(path.read_text(encoding="utf-8"))
    workdir = Path(record.get("workdir") or "")
    if arm == "w":
        # W has no ticket workdir; its scratch is recorded by the workflow itself.
        workdir = Path(record.get("scratch") or "")
    changed = []

    ledger = workdir / ".search_budget.json" if workdir.is_dir() else None
    if ledger and ledger.exists():
        try:
            state = json.loads(ledger.read_text(encoding="utf-8"))
            record["configs_used"] = state.get("used")
            record["budget_limit"] = state.get("limit")
            record["space_version"] = state.get("space_version")
            used, limit = state.get("used") or 0, state.get("limit") or 0
            record["stop_reason"] = "budget_exhausted" if limit and used >= limit else "stopped_early"
            changed.append("budget")
        except (ValueError, OSError):
            pass

    best = record.get("best_scaffold_model") or record.get("best_config_model")
    if workdir.is_dir() and best:
        current, current_model = locked_receipt_auroc(workdir)
        shipped = (current_model or "").rsplit("/model.joblib", 1)[0]
        best_dir = best.rsplit("/model.joblib", 1)[0]
        if shipped and best_dir.split("/")[-1] != shipped.split("/")[-1]:
            code = record.get("target") or ""
            desc = record.get("featurization") or "v1"
            value = rerun_locked(record, f"{best_dir}/model.joblib", code, desc, workdir)
            if value is not None:
                record["locked_auroc_original"] = current
                record["locked_auroc"] = value
                record["locked_reevaluated"] = True
                changed.append("locked")

    if changed:
        record["finalized"] = changed
        path.write_text(json.dumps(record, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return ",".join(changed) or "-"


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="p8 finalize")
    parser.add_argument("--label", required=True)
    args = parser.parse_args(argv)

    total = 0
    for arm in ARMS:
        for path in sorted(RUNS.glob(f"{arm}_*_{args.label}.json")):
            outcome = process(path, arm)
            total += 1
            print(f"  {path.name}: {outcome}")
    print(f"finalized {total} records for {args.label}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
