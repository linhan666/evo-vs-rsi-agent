"""Train/validation/test splitting with an explicit, pre-registered strategy.

Blueprint §9.4: the split is a scientific decision, not a default. Random split is
optimistic and must not be the only conclusion; Bemis-Murcko scaffold split is the
main internal generalisation check; a temporal split is used when reliable years
exist. The Agent chooses the strategy per target — this module makes that choice
*possible* and records which one was made.

Nothing here looks at the final test set's labels to pick the split; the strategy is
declared up front and the same partition is written for every downstream consumer.

Split manifest format (consumed by modeling.train via --split-manifest):
    {"schema_version": "1", "strategy": "scaffold", "seed": 17,
     "test_fraction": 0.3, "rows": {"CHEMBL25": "train", ...}}
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from collections import defaultdict


def read_smiles_id(path: str, id_column: str, smiles_column: str) -> list[tuple[str, str]]:
    from ..chemistry.featurize import resolve_columns

    columns = resolve_columns(path, {"id": id_column, "smiles": smiles_column})
    rows: list[tuple[str, str]] = []
    with open(path, newline="", encoding="utf-8-sig") as handle:
        for index, row in enumerate(csv.DictReader(handle)):
            molecule = str(row.get(columns.get("id")) or f"row{index}")
            rows.append((molecule, row[columns["smiles"]]))
    return rows


def murcko_scaffold(smiles: str) -> str:
    """Bemis-Murcko scaffold; a molecule that cannot be parsed gets its own bucket."""
    try:
        from rdkit import Chem
        from rdkit.Chem.Scaffolds import MurckoScaffold

        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            return f"unparseable:{smiles[:24]}"
        return MurckoScaffold.MurckoScaffoldSmiles(mol=mol) or f"acyclic:{smiles[:24]}"
    except Exception:
        return f"unparseable:{smiles[:24]}"


def assign(groups: dict[str, list[str]], test_fraction: float, val_fraction: float, seed: int) -> dict[str, str]:
    """Greedy group assignment: largest groups first, so the test set gets real scaffolds.

    A group is never split across partitions. If the greedy pass leaves test or val
    empty (one giant scaffold ate the budget), the smallest remaining whole groups
    are moved in — an empty test set is not a usable split.
    """
    names = sorted(groups, key=lambda key: (-len(groups[key]), key))
    total = sum(len(members) for members in groups.values())
    test_budget = max(1, int(total * test_fraction))
    val_budget = max(1, int(total * val_fraction))
    assignment: dict[str, str] = {}
    used = {"test": 0, "val": 0}
    leftovers: list[str] = []
    for name in names:
        members = groups[name]
        if used["test"] + len(members) <= test_budget:
            split = "test"
        elif used["val"] + len(members) <= val_budget:
            split = "val"
        else:
            leftovers.append(name)
            continue
        used[split] += len(members)
        for molecule in members:
            assignment[molecule] = split

    # Guarantee train first (nothing can be fit without it), then test, then val.
    # With fewer groups than partitions, train wins and the short partition stays empty.
    if not any(value == "train" for value in assignment.values()) and leftovers:
        name = max(leftovers, key=lambda key: len(groups[key]))
        leftovers.remove(name)
        for molecule in groups[name]:
            assignment[molecule] = "train"
    if used["test"] == 0 and leftovers:
        name = min(leftovers, key=lambda key: len(groups[key]))
        leftovers.remove(name)
        for molecule in groups[name]:
            assignment[molecule] = "test"
    if used["val"] == 0 and leftovers:
        name = min(leftovers, key=lambda key: len(groups[key]))
        leftovers.remove(name)
        for molecule in groups[name]:
            assignment[molecule] = "val"

    for name in leftovers:
        for molecule in groups[name]:
            assignment[molecule] = "train"
    return assignment


def build(rows: list[tuple[str, str]], strategy: str, test_fraction: float,
          val_fraction: float, seed: int) -> dict[str, str]:
    if strategy == "random":
        import random

        rng = random.Random(seed)
        names = [molecule for molecule, _ in rows]
        rng.shuffle(names)
        cut_test = int(len(names) * (1 - test_fraction))
        cut_val = int(len(names) * (1 - test_fraction - val_fraction))
        return {name: ("test" if index >= cut_test else "val" if index >= cut_val else "train")
                for index, name in enumerate(names)}

    if strategy == "scaffold":
        groups: dict[str, list[str]] = defaultdict(list)
        for molecule, smiles in rows:
            groups[murcko_scaffold(smiles)].append(molecule)
        return assign(groups, test_fraction, val_fraction, seed)

    raise SystemExit(f"unknown split strategy {strategy!r}; use random or scaffold")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evovs-science data.split")
    parser.add_argument("--input", required=True, help="CSV with id and smiles columns")
    parser.add_argument("--output", required=True, help="split manifest json")
    parser.add_argument("--strategy", choices=["random", "scaffold"], required=True,
                        help="scaffold is the main generalisation check; random is a diagnostic baseline")
    parser.add_argument("--test-fraction", type=float, default=0.3)
    parser.add_argument("--val-fraction", type=float, default=0.1)
    parser.add_argument("--seed", type=int, default=17)
    parser.add_argument("--id-column", default="id")
    parser.add_argument("--smiles-column", default="smiles")
    args = parser.parse_args(argv)

    rows = read_smiles_id(args.input, args.id_column, args.smiles_column)
    if len(rows) < 6:
        raise SystemExit(f"NOT_ENOUGH_RELIABLE_DATA: {len(rows)} rows cannot support a three-way split")
    assignment = build(rows, args.strategy, args.test_fraction, args.val_fraction, args.seed)
    counts = {name: sum(1 for value in assignment.values() if value == name)
              for name in ("train", "val", "test")}
    # Both layouts are written: `rows` (molecule -> split) is what this tool reads
    # back, `molecules` (split -> list) is what modeling.train has always expected.
    grouped: dict[str, list[str]] = {"train": [], "validation": [], "test": []}
    for molecule, split in assignment.items():
        grouped["validation" if split == "val" else split].append(molecule)
    manifest = {
        "schema_version": "1",
        "strategy": args.strategy,
        "seed": args.seed,
        "test_fraction": args.test_fraction,
        "val_fraction": args.val_fraction,
        "input": os.path.basename(args.input),
        "counts": counts,
        "rows": assignment,
        "molecules": grouped,
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"strategy": args.strategy, "counts": counts,
                      "scaffold_groups": len(set(assignment.values())) if args.strategy == "scaffold" else None}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
