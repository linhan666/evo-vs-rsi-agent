#!/usr/bin/env python3
"""W: the AutoML baseline — exhaustive search over the same frozen space.

W has no LLM. It walks the 100-configuration space in order until the budget is
spent, trains each point, keeps the best by validation AUROC, then screens and runs
the locked evaluation on that single model. This is the reference the LLM arms are
supposed to match with fewer draws.

It uses exactly the same tools and the same arguments as the agent arms, so the
comparison isolates who decides, not what is available:

  rdkit.featurize -> ml.train (per config) -> screening.rank -> evaluation.locked

Feature matrices are built once per feature representation (5 of them) and reused
across the 20 configurations that share it; otherwise the baseline would pay 100
featurisations for 5 distinct matrices.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from datetime import datetime, timezone

ROOT = "/home/linhan_cluster/evo_vs_rsi"
DATA = os.path.join(ROOT, "scientific/.artifacts")
PYTHON = os.path.join(ROOT, "scientific/.venv/bin/python")
RUNS = os.path.join(ROOT, "ops/phase7_runs")
sys.path.insert(0, os.path.join(ROOT, "scientific/src"))
from evovs_science.search.space import CONFIGS, FEATURE_SPECS, fingerprint  # noqa: E402

TARGETS = (
    (1, "D2", "d(2)_dopamine_recept", "D2"),
    (2, "5HT", "5-hydroxytryptamine_", "5HT"),
    (3, "ADR", "adenosine_receptor_a", "ADR"),
    (4, "DRD2", "drd2", "DRD2"),
    (5, "MOR", "oprm1", "MOR"),
    (6, "CBR", "cannabinoid_receptor", "CBR"),
    (7, "KOR", "oprk1", "KOR"),
    (8, "CA2", "carbonic_anhydrase_2", "CA2"),
    (9, "PT", "prothrombin", "PT"),
)


def run(argv: list[str], cwd: str) -> dict:
    started = time.time()
    done = subprocess.run(argv, cwd=cwd, capture_output=True, text=True)
    return {"argv": argv, "exit_code": done.returncode,
            "wall_seconds": round(time.time() - started, 2),
            "stderr_tail": done.stderr.strip().splitlines()[-2:]}


def features_for(spec_id: str, dataset: str, scratch: str) -> tuple[str | None, dict]:
    spec = FEATURE_SPECS[spec_id]
    rel = f"features/{spec_id}.npz"
    path = os.path.join(scratch, rel)
    if os.path.exists(path):
        return rel, {"cached": True}
    argv = [PYTHON, "-m", "evovs_science.chemistry.featurize",
            "--input", dataset, "--output", rel, "--report", f"features/{spec_id}.json",
            "--id-column", "molecule_chembl_id", "--smiles-column", "canonical_smiles",
            "--desc-set", spec["desc_set"], "--radius", str(spec["radius"]),
            "--n-bits", str(spec["n_bits"])]
    record = run(argv, scratch)
    return (rel if record["exit_code"] == 0 else None), record


def one(seq: int, name: str, slug: str, code: str, budget: int, label: str, scratch_root: str) -> dict:
    dataset = os.path.join(DATA, "chembl", slug, "ki", "dataset_p7b.csv")
    frozen = os.path.join(DATA, "chembl", slug, "ki", "splits", f"frozen_p8_{slug}.json")
    library = os.path.join(DATA, "zinc", "library_100k.smi")
    tag = code.lower()
    scratch = os.path.join(scratch_root, tag)
    os.makedirs(scratch, exist_ok=True)

    started = time.time()
    steps: list[dict] = []
    tried: list[dict] = []

    for config in CONFIGS[:budget]:
        rel, record = features_for(config.desc_set, dataset, scratch)
        if record.get("argv"):
            steps.append(record)
        if rel is None:
            tried.append({"config_id": config.id, "status": "featurize_failed"})
            continue
        out_dir = f"models/{config.id}"
        argv = [PYTHON, "-m", "evovs_science.modeling.train",
                "--features", rel, "--labels", dataset, "--output-dir", out_dir,
                "--model", config.model, "--seed", str(config.seed),
                "--test-fraction", "0.05", "--label-source", "chembl",
                "--label-id-column", "molecule_chembl_id", "--label-column", "label",
                "--split-manifest", frozen,
                "--config-id", config.id, "--workspace", ".", "--budget-limit", str(budget)]
        record = run(argv, scratch)
        steps.append(record)
        metrics_path = os.path.join(scratch, out_dir, "metrics.json")
        auroc = None
        if os.path.exists(metrics_path):
            try:
                auroc = (json.load(open(metrics_path, encoding="utf-8")).get("metrics") or {}).get("auroc")
            except (ValueError, OSError):
                auroc = None
        tried.append({"config_id": config.id, "auroc": auroc,
                      "exit_code": record["exit_code"]})

    scored = [row for row in tried if row.get("auroc") is not None]
    best = max(scored, key=lambda row: row["auroc"]) if scored else None

    locked = None
    if best:
        model = f"models/{best['config_id']}/model.joblib"
        desc = next(c.desc_set for c in CONFIGS if c.id == best["config_id"])
        steps.append(run([PYTHON, "-m", "evovs_science.screening.predict",
                          "--model", model, "--library", library,
                          "--output", f"runs/{tag}_all.csv",
                          "--top-output", f"runs/{tag}_topK.csv",
                          "--report", "runs/screening_report.json", "--top-k", "100"], scratch))
        steps.append(run([PYTHON, "-m", "evovs_science.evaluation.locked",
                          "--target", code, "--endpoint", "Ki", "--desc-set", desc,
                          "--model", model, "--workspace", ".",
                          "--receipt", f"evaluation/{tag}_locked.json"], scratch))
        receipt = os.path.join(scratch, "evaluation", f"{tag}_locked.json")
        if os.path.exists(receipt):
            try:
                locked = (json.load(open(receipt, encoding="utf-8")).get("metrics") or {}).get("auroc")
            except (ValueError, OSError):
                locked = None

    budget_ledger = os.path.join(scratch, ".search_budget.json")
    used = budget
    if os.path.exists(budget_ledger):
        try:
            used = json.load(open(budget_ledger, encoding="utf-8")).get("used", budget)
        except (ValueError, OSError):
            used = budget

    return {
        "group": "w", "seq": seq, "target": name, "slug": slug, "label": label,
        "panel": "AutoML baseline: exhaustive over the frozen space, no LLM",
        "space_version": fingerprint(), "budget_limit": budget,
        "configs_used": used, "stop_reason": "budget_exhausted" if used >= budget else "stopped_early",
        "best_config": best["config_id"] if best else None,
        "best_config_auroc": best["auroc"] if best else None,
        "configs": tried,
        "steps": len(steps),
        "wall_seconds": round(time.time() - started, 2),
        "jobs_failed": sum(1 for step in steps if step["exit_code"] != 0),
        "auroc": best["auroc"] if best else None,
        "locked_auroc": locked,
        "success": locked is not None,
        "recorded_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
    }


def main(argv: list[str] | None = None) -> int:
    import argparse
    parser = argparse.ArgumentParser(prog="p8 workflow (group W)")
    parser.add_argument("--slug", default=None)
    parser.add_argument("--all", action="store_true")
    parser.add_argument("--budget", type=int, default=100)
    parser.add_argument("--label", default="p8w100")
    parser.add_argument("--scratch-root", default=os.path.join(DATA, "p8_workflow"))
    args = parser.parse_args(argv)
    if not args.all and not args.slug:
        parser.error("give --all or --slug")

    chosen = [row for row in TARGETS if args.all or row[2] == args.slug]
    if not chosen:
        parser.error(f"--slug must be one of {[row[2] for row in TARGETS]}")

    os.makedirs(RUNS, exist_ok=True)
    ok = 0
    for seq, name, slug, code in chosen:
        record = one(seq, name, slug, code, args.budget, args.label,
                     os.path.join(args.scratch_root, f"{args.label}-b{args.budget}"))
        path = os.path.join(RUNS, f"w_{seq:02d}_{code.lower()}_{args.label}.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(record, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        ok += 1 if record["success"] else 0
        print(json.dumps({"seq": seq, "target": name, "budget": args.budget,
                          "configs_used": record["configs_used"],
                          "best_config": record["best_config"],
                          "val": record["best_config_auroc"], "locked": record["locked_auroc"],
                          "wall": record["wall_seconds"]}, ensure_ascii=False), flush=True)
    print(json.dumps({"runs": len(chosen), "succeeded": ok}), flush=True)
    return 0 if ok == len(chosen) else 1


if __name__ == "__main__":
    raise SystemExit(main())
