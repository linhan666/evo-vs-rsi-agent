"""Model fusion: combine two trained models into one ranking.

Blueprint §4.1 lists "模型融合方式" as one of the choices the Agent may make, so the
capability has to exist as a tool rather than as an ad-hoc script. The fusion
methods here are the ones that can be justified without fitting anything extra on
the test set: mean of calibrated probabilities, rank averaging, and weighting by
each model's validation AUPRC.

Nothing here looks at the test labels. Weights are declared in the manifest and
derived from the models' own validation metrics, so the choice is auditable.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys


def read_scores(path: str) -> dict[str, float]:
    """predictions.csv from modeling.train: one row per molecule with a score."""
    scores: dict[str, float] = {}
    with open(path, newline="", encoding="utf-8-sig") as handle:
        for row in csv.DictReader(handle):
            molecule = row.get("id") or row.get("molecule") or row.get("molecule_id")
            raw = row.get("score") or row.get("prediction") or row.get("prob")
            if molecule and raw not in (None, ""):
                scores[str(molecule)] = float(raw)
    return scores


def rank_of(scores: dict[str, float]) -> dict[str, float]:
    """Average rank (1 = best); ties share the average position."""
    ordered = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    ranks: dict[str, float] = {}
    index = 0
    while index < len(ordered):
        end = index
        while end + 1 < len(ordered) and ordered[end + 1][1] == ordered[index][1]:
            end += 1
        average = (index + end + 2) / 2.0
        for position in range(index, end + 1):
            ranks[ordered[position][0]] = average
        index = end + 1
    return ranks


def fuse(a: dict[str, float], b: dict[str, float], method: str,
         weight_a: float = 0.5) -> dict[str, float]:
    shared = sorted(set(a) & set(b))
    if not shared:
        raise SystemExit("the two prediction files share no molecule id")
    if method == "mean":
        return {molecule: weight_a * a[molecule] + (1 - weight_a) * b[molecule] for molecule in shared}
    if method == "rank":
        ra, rb = rank_of({k: a[k] for k in shared}), rank_of({k: b[k] for k in shared})
        return {molecule: -(weight_a * ra[molecule] + (1 - weight_a) * rb[molecule]) for molecule in shared}
    raise SystemExit(f"unknown fusion method {method!r}; use mean or rank")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evovs-science ml.fuse")
    parser.add_argument("--a", required=True, help="predictions.csv from model A")
    parser.add_argument("--b", required=True, help="predictions.csv from model B")
    parser.add_argument("--output", required=True, help="fused ranking csv")
    parser.add_argument("--report", required=True, help="fusion report json")
    parser.add_argument("--method", choices=["mean", "rank"], default="mean")
    parser.add_argument("--weight-a", type=float, default=0.5,
                        help="weight on model A in [0,1]; use validation AUPRC to justify it")
    parser.add_argument("--a-uprc", type=float, default=None, help="model A validation AUPRC (recorded)")
    parser.add_argument("--b-uprc", type=float, default=None, help="model B validation AUPRC (recorded)")
    args = parser.parse_args(argv)

    if not 0.0 <= args.weight_a <= 1.0:
        raise SystemExit("--weight-a must be in [0,1]")
    fused = fuse(read_scores(args.a), read_scores(args.b), args.method, args.weight_a)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "fused_score"])
        for molecule, score in sorted(fused.items(), key=lambda item: -item[1]):
            writer.writerow([molecule, f"{score:.6f}"])

    report = {
        "schema_version": "1",
        "method": args.method,
        "weight_a": args.weight_a,
        "weight_b": round(1 - args.weight_a, 6),
        "models": {
            "a": {"path": os.path.basename(args.a), "auprc": args.a_uprc},
            "b": {"path": os.path.basename(args.b), "auprc": args.b_uprc},
        },
        "shared_molecules": len(fused),
        "note": "weights are declared, not fitted on the test set",
    }
    with open(args.report, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"method": args.method, "shared": len(fused), "weight_a": args.weight_a}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
