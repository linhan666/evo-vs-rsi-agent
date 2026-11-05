"""Dual-endpoint agreement: Ki vs IC50 model ranks over the SAME 100k library.

Both rankings are model predictions on an unlabeled library, so this measures
how concordant the binding-affinity view and the functional-potency view of the
same chemical space are — it is NOT biological confirmation of either list.
"""

from __future__ import annotations

import argparse
import csv
import json
import os

from scipy.stats import kendalltau, spearmanr

from ..manifest import describe_input, utc_now, write_manifest


def read_ranked(path: str) -> dict[str, dict]:
    table: dict[str, dict] = {}
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            table[str(row["id"])] = {"smiles": row.get("smiles", ""),
                                     "score": float(row["score"]), "rank": int(row["rank"])}
    return table


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evovs-science dual")
    parser.add_argument("--ki-ranked", required=True)
    parser.add_argument("--ic50-ranked", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    parser.add_argument("--top-k", type=int, default=100)
    args = parser.parse_args(argv)

    ki = read_ranked(args.ki_ranked)
    ic50 = read_ranked(args.ic50_ranked)
    common = sorted(set(ki) & set(ic50))
    if len(common) < 100:
        raise SystemExit(f"overlap too small: {len(common)}")

    ki_scores = [ki[m]["score"] for m in common]
    ic50_scores = [ic50[m]["score"] for m in common]
    rho, _ = spearmanr(ki_scores, ic50_scores)
    tau, _ = kendalltau(ki_scores, ic50_scores)

    top_ki = {m for m in common if ki[m]["rank"] <= args.top_k}
    top_ic50 = {m for m in common if ic50[m]["rank"] <= args.top_k}
    overlap = len(top_ki & top_ic50)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["id", "smiles",
                                                    "ki_score", "ki_rank", "ic50_score", "ic50_rank"])
        writer.writeheader()
        for m in sorted(common, key=lambda m: ki[m]["rank"]):
            writer.writerow({"id": m, "smiles": ki[m]["smiles"],
                             "ki_score": f"{ki[m]['score']:.6f}", "ki_rank": ki[m]["rank"],
                             "ic50_score": f"{ic50[m]['score']:.6f}", "ic50_rank": ic50[m]["rank"]})

    report = {
        "schema_version": "1",
        "created_at": utc_now(),
        "target": args.target,
        "inputs": [describe_input(args.ki_ranked), describe_input(args.ic50_ranked)],
        "joint_molecules": len(common),
        "spearman_rho": round(float(rho), 4),
        "kendall_tau": round(float(tau), 4),
        f"top{args.top_k}_overlap": overlap,
        f"top{args.top_k}_overlap_ratio": round(overlap / args.top_k, 3),
        "note": "Both rankings are model predictions on an unlabeled library; agreement describes "
                "model-view concordance between binding (Ki) and functional (IC50) channels, "
                "not biological confirmation.",
    }
    with open(args.report, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    write_manifest(
        os.path.dirname(os.path.abspath(args.output)),
        [{"path": args.output, "content_type": "text/csv", "description": "dual-endpoint joined ranks"},
         {"path": args.report, "content_type": "application/json", "description": "agreement report"}],
        generator="evovs_science.screening.dual_endpoint",
        inputs=report["inputs"],
        parameters={"target": args.target, "top_k": args.top_k},
    )
    print(json.dumps({"target": args.target, "joint": len(common), "spearman": report["spearman_rho"],
                      "kendall": report["kendall_tau"], f"top{args.top_k}_overlap": overlap}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
