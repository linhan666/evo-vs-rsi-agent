"""Negative-transfer CI for pooled vs per-target models (docs/TRANSFER_DESIGN.md).

Cluster bootstrap over Bemis–Murcko scaffolds: ordinary bootstrap would resample
individual molecules and grossly understate the variance of a scaffold split.
Inputs are the evaluator's prediction dumps (written inside the protected tree);
the output is a CI record, not a conclusion.
"""

from __future__ import annotations

import argparse
import csv
import json
import os

import numpy as np
from sklearn.metrics import average_precision_score, roc_auc_score

from ..chemistry.featurize import featurize as _unused_featurize  # noqa: F401  (keeps rdkit import path consistent)
from rdkit import Chem, RDLogger
from rdkit.Chem.Scaffolds import MurckoScaffold

from ..manifest import describe_input, sha256_file, utc_now, write_manifest

RDLogger.DisableLog("rdApp.*")


def scaffold_of(smiles: str) -> str:
    mol = Chem.MolFromSmiles(smiles)
    scaffold = MurckoScaffold.MurckoScaffoldSmiles(mol=mol) if mol is not None else smiles
    return scaffold or smiles


def read_test(path: str) -> dict[str, dict]:
    rows: dict[str, dict] = {}
    with open(path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            if row.get("label", "") == "":
                continue
            rows[row["molecule_chembl_id"]] = {
                "label": int(float(row["label"])),
                "smiles": row["canonical_smiles"],
            }
    return rows


def read_dump(path: str) -> dict[str, float]:
    dump = json.load(open(path, encoding="utf-8"))
    return {str(item["id"]): float(item["score"]) for item in dump["records"]}


def auroc(y: np.ndarray, scores: np.ndarray) -> float:
    return float(roc_auc_score(y, scores))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evovs-science bootstrap")
    parser.add_argument("--test-csv", required=True)
    parser.add_argument("--pooled-dump", required=True)
    parser.add_argument("--baseline-dump", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--resamples", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args(argv)

    test = read_test(args.test_csv)
    pooled = read_dump(args.pooled_dump)
    baseline = read_dump(args.baseline_dump)

    ids = sorted(set(test) & set(pooled) & set(baseline))
    if len(ids) < 10:
        raise SystemExit("overlap between test set and dumps is too small")
    y = np.asarray([test[molecule]["label"] for molecule in ids], dtype=int)
    scores_pooled = np.asarray([pooled[molecule] for molecule in ids])
    scores_baseline = np.asarray([baseline[molecule] for molecule in ids])

    clusters: dict[str, list[int]] = {}
    for index, molecule in enumerate(ids):
        clusters.setdefault(scaffold_of(test[molecule]["smiles"]), []).append(index)
    cluster_list = list(clusters.values())

    rng = np.random.default_rng(args.seed)
    deltas: list[float] = []
    for _ in range(args.resamples):
        picks = rng.integers(0, len(cluster_list), size=len(cluster_list))
        chosen = [index for pick in picks for index in cluster_list[pick]]
        if len(np.unique(y[chosen])) < 2:
            continue
        deltas.append(roc_auc_score(y[chosen], scores_pooled[chosen]) - roc_auc_score(y[chosen], scores_baseline[chosen]))

    delta = auroc(y, scores_pooled) - auroc(y, scores_baseline)
    ci_low, ci_high = (round(float(value), 4) for value in np.percentile(deltas, [2.5, 97.5]))
    record = {
        "schema_version": "1",
        "created_at": utc_now(),
        "target": args.target,
        "comparison": "pooled-fit-all vs per-target, locked test",
        "counts": {"test_used": len(ids), "scaffold_clusters": len(cluster_list)},
        "auroc": {"pooled": round(auroc(y, scores_pooled), 4), "per_target": round(auroc(y, scores_baseline), 4),
                  "delta": round(delta, 4)},
        "delta_ci95": [ci_low, ci_high],
        "resamples": len(deltas),
        "seed": args.seed,
        "negative_transfer": bool(delta <= -0.02 and ci_high < 0),
        "auprc": {"pooled": round(float(average_precision_score(y, scores_pooled)), 4),
                  "per_target": round(float(average_precision_score(y, scores_baseline)), 4)},
        "note": "Cluster bootstrap over scaffolds; a CI containing 0 means 'no observed difference', not 'no effect'.",
    }

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(record, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    os.chmod(args.output, 0o600)

    write_manifest(
        os.path.dirname(os.path.abspath(args.output)),
        [{"path": args.output, "content_type": "application/json", "description": "negative-transfer CI"}],
        generator="evovs_science.evaluation.bootstrap",
        inputs=[describe_input(args.pooled_dump), describe_input(args.baseline_dump)],
        parameters={"target": args.target, "resamples": args.resamples, "seed": args.seed},
    )

    print(json.dumps({"target": args.target, "auroc": record["auroc"], "ci95": [ci_low, ci_high],
                      "negative_transfer": record["negative_transfer"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
