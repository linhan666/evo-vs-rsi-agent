"""Dual-channel shortlist generator: Ki ∪ IC50 union with MaxMin diversity ordering.

The union of the two channel top-N lists is endpoint-specific by construction
(experience: top100 overlap 0-2/100 across targets); diversity ordering makes
the final shortlist cover the union's chemical space instead of clustering on
one scaffold family. Output is the input format a generative feedback loop
consumes: ranked molecules with channel provenance.
"""

from __future__ import annotations

import argparse
import csv
import json
import os

import numpy as np
from rdkit import Chem, DataStructs, RDLogger
from rdkit.Chem import rdFingerprintGenerator
from rdkit.DataStructs import ConvertToNumpyArray

from ..manifest import describe_input, utc_now, write_manifest

RDLogger.DisableLog("rdApp.*")


def read_ranked(path: str, channel: str) -> dict[str, dict]:
    table: dict[str, dict] = {}
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            if int(row["rank"]) <= 0:
                continue
            table[str(row["id"])] = {"smiles": row.get("smiles", ""),
                                     "score": float(row["score"]), "rank": int(row["rank"]),
                                     "channel": channel}
    return table


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evovs-science shortlist")
    parser.add_argument("--ki-ranked", required=True)
    parser.add_argument("--ic50-ranked", required=True)
    parser.add_argument("--target", required=True)
    parser.add_argument("--top-n", type=int, default=100, help="per-channel cut")
    parser.add_argument("--final-size", type=int, default=50)
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args(argv)

    ki = read_ranked(args.ki_ranked, "ki")
    ic50 = read_ranked(args.ic50_ranked, "ic50")

    union: dict[str, dict] = {}
    for source in (ki, ic50):
        for molecule, item in source.items():
            if item["rank"] <= args.top_n:
                if molecule in union:
                    union[molecule]["channels"] = "both"
                else:
                    union[molecule] = {**item, "channels": source is ki and "ki" or "ic50"}
    # fix provenance for molecules seen twice
    for molecule in union:
        in_ki = molecule in ki and ki[molecule]["rank"] <= args.top_n
        in_ic50 = molecule in ic50 and ic50[molecule]["rank"] <= args.top_n
        union[molecule]["channels"] = "both" if (in_ki and in_ic50) else ("ki" if in_ki else "ic50")

    molecules = sorted(union, key=lambda m: min(ki.get(m, {}).get("rank", 10**9),
                                                ic50.get(m, {}).get("rank", 10**9)))
    if not molecules:
        raise SystemExit("union is empty")
    if len(molecules) < args.final_size:
        raise SystemExit(f"union ({len(molecules)}) smaller than final size {args.final_size}")

    # fingerprints for diversity ordering
    gen = rdFingerprintGenerator.GetMorganGenerator(radius=2, fpSize=2048)
    fingerprints: list[DataStructs.ExplicitBitVect] = []
    parsed: list[str] = []
    for molecule in molecules:
        mol = Chem.MolFromSmiles(union[molecule]["smiles"])
        if mol is None:
            continue
        fingerprints.append(gen.GetFingerprint(mol))
        parsed.append(molecule)
    if len(parsed) < args.final_size:
        raise SystemExit("too few parseable union molecules")

    # Tanimoto distance matrix (small: union <= 2*top_n rows)
    n = len(parsed)
    distance = np.zeros((n, n), dtype=np.float32)
    for i in range(n):
        for j in range(i + 1, n):
            sim = DataStructs.TanimotoSimilarity(fingerprints[i], fingerprints[j])
            distance[i, j] = distance[j, i] = 1.0 - sim

    selected = [0]  # seed: union head (best Ki or IC50 rank)
    min_dist = distance[0].copy()
    while len(selected) < min(args.final_size, n):
        next_index = int(np.argmax(min_dist))
        selected.append(next_index)
        min_dist = np.minimum(min_dist, distance[next_index])

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["diversity_rank", "id", "smiles", "channels",
                                                    "ki_rank", "ki_score", "ic50_rank", "ic50_score"])
        writer.writeheader()
        for order, index in enumerate(selected, 1):
            molecule = parsed[index]
            item = union[molecule]
            writer.writerow({
                "diversity_rank": order, "id": molecule, "smiles": item["smiles"],
                "channels": item["channels"],
                "ki_rank": ki.get(molecule, {}).get("rank", ""),
                "ki_score": f"{ki[molecule]['score']:.6f}" if molecule in ki else "",
                "ic50_rank": ic50.get(molecule, {}).get("rank", ""),
                "ic50_score": f"{ic50[molecule]['score']:.6f}" if molecule in ic50 else "",
            })

    provenance = {kind: sum(1 for index in selected if union[parsed[index]]["channels"] == kind)
                  for kind in ("ki", "ic50", "both")}
    report = {
        "schema_version": "1",
        "created_at": utc_now(),
        "target": args.target,
        "inputs": [describe_input(args.ki_ranked), describe_input(args.ic50_ranked)],
        "top_n_per_channel": args.top_n,
        "union_size": len(molecules),
        "parseable": len(parsed),
        "final_size": min(args.final_size, n),
        "provenance": provenance,
        "ordering": "greedy MaxMin Tanimoto diversity, seeded at the union head",
        "purpose": "shortlist for the generative-model feedback loop; ranks are model predictions, not biological confirmation",
    }
    with open(args.report, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    write_manifest(
        os.path.dirname(os.path.abspath(args.output)),
        [{"path": args.output, "content_type": "text/csv", "description": "diverse dual-channel shortlist"},
         {"path": args.report, "content_type": "application/json", "description": "shortlist report"}],
        generator="evovs_science.screening.shortlist",
        inputs=report["inputs"],
        parameters={"target": args.target, "top_n": args.top_n, "final_size": args.final_size},
    )
    print(json.dumps({"target": args.target, "union": len(molecules), "final": min(args.final_size, n),
                      "provenance": provenance}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
