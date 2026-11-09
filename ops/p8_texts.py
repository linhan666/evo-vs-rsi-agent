#!/usr/bin/env python3
"""Generate the p8 task texts: bounded search space, explicit budget, forced finalize.

What changed from the p7 texts, and why
---------------------------------------
1. The split is `frozen_p8_<slug>.json`, whose validation slice is ~30% instead of
   ~10%. The measured consequence of the old slice: validation AUROC moved by 0.0005
   across repeats while the locked AUROC moved by up to 0.154, so "pick the best
   model" had no signal to act on.
2. The search space is frozen and bounded (`search.space`, 100 configurations). An
   arm may not invent a configuration, and `ml.train --config-id` charges the
   budget, refusing draw N+1. Searching within a budget is the experimental
   variable; without a bound, "efficiency" is unmeasurable.
3. The last step must be `evaluation.locked` on the model the arm would ship. In p7
   five to six of nine targets shipped a model that was not the best one trained,
   which silently understated every arm's quality.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path("/home/linhan_cluster/evo_vs_rsi")
DATA = ROOT / "scientific/.artifacts"
OUT = ROOT / "ops/p8_tasks"

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
ARMS = ("r", "m", "a")
PANEL = {
    "r": "self-evolving harness: memory + harness.propose available; correct memory and propose harness changes when the traces show waste",
    "m": "memory only: reuse prior experience; do not propose harness changes",
    "a": "no memory: no experience store, no prior rounds",
}


def store_path(arm: str, budget: int) -> str:
    return str(DATA / "experience" / f"experience_p8_{arm}_b{budget}.json")


def build_text(arm: str, seq: int, name: str, slug: str, code: str, budget: int) -> str:
    labels = DATA / "chembl" / slug / "ki" / "dataset_p7b.csv"
    frozen = DATA / "chembl" / slug / "ki" / "splits" / f"frozen_p8_{slug}.json"
    library = DATA / "zinc" / "library_100k.smi"

    lines = [
        f"Target {seq}/9: {name} (Ki). Reach the best locked quality you can within {budget} search draws.",
        "",
        f"role: {PANEL[arm]}",
        f"labels: {labels}",
        f"library: {library}",
        f"split: pass {frozen} as --split-manifest to ml.train (validation is ~30% of the label set)",
        "",
        f"space: call search.space first. It lists the {100} configurations you may train.",
        f"budget: {budget} draws for this ticket. Every ml.train must carry --config-id <id>, "
        f"--budget-limit {budget} and --workspace . ; the tool refuses draw {budget + 1}.",
        "You may stop before the budget is spent. Stopping early is a result, not a failure.",
    ]
    if arm != "a":
        lines.append(f"store: {store_path(arm, budget)} (the `store` argument of experience.retrieve)")
    if arm == "r":
        lines.append("if the traces show the harness wasting work, use harness.propose to file a "
                     "candidate; the operator adjudicates promotion")
    lines += [
        "",
        "finish: call evaluation.locked exactly once, on the model you would actually ship "
        "(the same one screening.rank used). The collector re-runs it if the shipped model "
        "differs from your best, so ship deliberately.",
        "",
        "Report: configurations drawn and why you stopped; validation and locked AUROC of the "
        "shipped model; wall clock and job count; experience ids reused.",
    ]
    return "\n".join(lines) + "\n"


def main() -> int:
    budgets = [100, 50, 20, 10, 5]
    written = 0
    for budget in budgets:
        for arm in ARMS:
            for seq, name, slug, code in TARGETS:
                prefix = f"p8b{budget}"   # driver convention: {prefix}_{group}_{code}
                task = {
                    "task_id": f"{prefix}_{arm}_{code.lower()}",
                    "sender": "operator",
                    "title": f"P8 b{budget} arm {arm.upper()} target {seq} ({code})",
                    "text": build_text(arm, seq, name, slug, code, budget),
                }
                OUT.mkdir(parents=True, exist_ok=True)
                path = OUT / f"{task['task_id']}.json"
                path.write_text(json.dumps(task, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                written += 1
    print(f"wrote {written} task files to {OUT}")
    print("task ids look like p8b100_r_d2; drive with --prefix p8b100 --label p8b100 --budget-limit 100")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
