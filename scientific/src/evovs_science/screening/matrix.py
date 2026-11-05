"""Merge per-target screening ranks into one multi-target matrix (Blueprint §9.6, P3-05).

The join is inner on molecule id: a row exists only for molecules every target model
scored. Selectivity columns are NOT emitted here — comparing pKi-scale scores across
targets requires calibrated, comparable outputs (§9.6), which plain class scores are
not. The matrix therefore carries scores and ranks per target, nothing derived.
"""

from __future__ import annotations

import argparse
import csv
import json
import os

from ..manifest import describe_input, utc_now, write_manifest


def read_ranked(path: str) -> dict[str, dict]:
    table: dict[str, dict] = {}
    with open(path, newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            table[str(row["id"])] = {"smiles": row.get("smiles", ""), "score": float(row["score"]), "rank": int(row["rank"])}
    return table


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evovs-science matrix")
    parser.add_argument("--inputs", required=True, help="comma-separated ranked CSVs, one per target")
    parser.add_argument("--targets", required=True, help="comma-separated target names, same order as --inputs")
    parser.add_argument("--output", required=True)
    parser.add_argument("--report", required=True)
    args = parser.parse_args(argv)

    inputs = [item.strip() for item in args.inputs.split(",") if item.strip()]
    targets = [item.strip() for item in args.targets.split(",") if item.strip()]
    if len(inputs) != len(targets) or not targets:
        raise SystemExit("--targets must match --inputs one to one")
    if len(set(targets)) != len(targets):
        raise SystemExit("target names must be unique")

    tables = {target: read_ranked(path) for target, path in zip(targets, inputs)}
    common = set.intersection(*(set(table) for table in tables.values()))
    order = sorted(common, key=lambda molecule: min(table[molecule]["rank"] for table in tables.values()))

    fields = ["id", "smiles"]
    for target in targets:
        fields += [f"{target}_score", f"{target}_rank"]

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for molecule in order:
            row: dict[str, str] = {"id": molecule, "smiles": next(iter(tables.values()))[molecule]["smiles"]}
            for target in targets:
                row[f"{target}_score"] = f"{tables[target][molecule]['score']:.6f}"
                row[f"{target}_rank"] = str(tables[target][molecule]["rank"])
            writer.writerow(row)

    report = {
        "schema_version": "1",
        "created_at": utc_now(),
        "targets": targets,
        "inputs": [describe_input(path) for path in inputs],
        "library_per_target": {target: len(table) for target, table in tables.items()},
        "joint_rows": len(common),
        "note": "Inner join on molecule id. Scores are per-target model outputs and are NOT directly comparable "
                "across targets; no selectivity column is derived.",
    }
    with open(args.report, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    write_manifest(
        os.path.dirname(os.path.abspath(args.output)),
        [
            {"path": args.output, "content_type": "text/csv", "description": "multi-target score matrix"},
            {"path": args.report, "content_type": "application/json", "description": "matrix report"},
        ],
        generator="evovs_science.screening.matrix",
        inputs=report["inputs"],
        parameters={"targets": targets},
    )

    print(json.dumps({"targets": targets, "joint_rows": len(common),
                      "per_target": report["library_per_target"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
