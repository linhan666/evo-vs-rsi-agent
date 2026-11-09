#!/usr/bin/env python3
"""Re-carve the internal split so validation is large enough to choose with.

The p7b manifests gave validation ~10% of the labelled set (287-621 molecules), and
the measured consequence was decisive: across three repeats of one arm the
*validation* AUROC moved by 0.0005, while the *locked* AUROC moved by up to 0.154.
The agent therefore had no usable signal — its "pick the best model" step was
indistinguishable from a lottery, which caps every quality claim downstream.

This writes `frozen_p8_<slug>.json` alongside the p7b manifests with a scaffold-
wise 52.5 / 30 / 17.5 train/validation/test split. The protected locked test sets
are NOT touched, so quality stays comparable across rounds.

Nothing is overwritten: p8 manifests are new files.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path("/home/linhan_cluster/evo_vs_rsi")
sys.path.insert(0, str(ROOT / "ops"))
from phase7b_prepare import carve, scaffolds  # noqa: E402  (shared carving logic)

CHEMBL = ROOT / "scientific/.artifacts/chembl"

VALIDATION_FRACTION = 0.30
TEST_FRACTION_OF_REST = 0.25     # 0.25 x 0.70 = 17.5% of the whole
SEED = 17

TARGETS = (("d(2)_dopamine_recept", "d2"), ("5-hydroxytryptamine_", "5ht"),
           ("adenosine_receptor_a", "adr"), ("drd2", "drd2"),
           ("oprm1", "mor"), ("cannabinoid_receptor", "cbr"),
           ("oprk1", "kor"), ("carbonic_anhydrase_2", "ca2"),
           ("prothrombin", "pt"))


def read_csv(path: Path) -> list[dict]:
    import csv
    with path.open(encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def main() -> int:
    written = []
    for slug, code in TARGETS:
        dataset = CHEMBL / slug / "ki" / "dataset_p7b.csv"
        if not dataset.exists():
            print(f"  skip {code}: no dataset at {dataset}")
            continue
        rows = read_csv(dataset)
        scaffold_of = scaffolds(rows)
        validation, rest = carve(rows, scaffold_of, VALIDATION_FRACTION, SEED)
        internal_test, train = carve(rest, scaffold_of, TEST_FRACTION_OF_REST, SEED)

        manifest = {
            "schema_version": "1",
            "strategy": "scaffold-p8",
            "version": "p8",
            "source": str(dataset),
            "seed": SEED,
            "counts": {"train": len(train), "validation": len(validation), "test": len(internal_test)},
            "note": ("validation enlarged from ~10% to 30% so model selection has a usable "
                     "signal; the protected locked test set is unchanged"),
            "rows": {row["molecule_chembl_id"]: split
                     for split, group in (("train", train), ("validation", validation),
                                          ("test", internal_test))
                     for row in group},
        }
        target = CHEMBL / slug / "ki" / "splits" / f"frozen_p8_{slug}.json"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(manifest, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append((code, manifest["counts"]))
        print(f"  {code:5s} train {len(train):5d}  validation {len(validation):4d}  test {len(internal_test):4d}")

    summary = {"generated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
               "validation_fraction": VALIDATION_FRACTION,
               "targets": {code: counts for code, counts in written}}
    (ROOT / "ops/phase7_runs/p8_splits.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {len(written)} p8 manifests")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
