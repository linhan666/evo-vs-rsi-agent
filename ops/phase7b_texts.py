#!/usr/bin/env python3
"""Emit the phase7b task files: frozen split, de-leaked data, mandatory locked eval.

What changes from the phase7 round
----------------------------------
1. Labels point at `dataset_p7b.csv`, which has the protected test molecules
   removed (verified leak 0). The round-7 files trained on molecules that the
   locked test also scored, which is why six targets could not be compared at all
   and the three that could were compared on splits with zero overlap.
2. The split is **given, not chosen**. The task hands over the exact manifest and
   forbids calling `data.split`. In round 7 each ticket picked its own
   `test_fraction`, and since `--seed` is inert for scaffold splits that single
   number decided which molecules every arm was scored on.
3. A locked evaluation is a required deliverable, and the receipt path is named,
   so every target ends up with one comparable number. In round 7 only 3 of 9
   tickets happened to run one.
4. Each memory-bearing arm gets its own store file, so M and R cannot inherit each
   other's records.

Usage:  python3 ops/phase7b_texts.py [--out-dir ops/phase7b_custom]
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "scientific" / ".artifacts"
EXPERIENCE = DATA / "experience"

# sequence position, display name, artifact slug, locked target code
TARGETS = [
    (1, "D2", "d(2)_dopamine_recept", "D2"),
    (2, "5HT", "5-hydroxytryptamine_", "5HT"),
    (3, "ADR", "adenosine_receptor_a", "ADR"),
    (4, "DRD2", "drd2", "DRD2"),
    (5, "MOR", "oprm1", "MOR"),
    (6, "CBR", "cannabinoid_receptor", "CBR"),
    (7, "KOR", "oprk1", "KOR"),
    (8, "CA2", "carbonic_anhydrase_2", "CA2"),
    (9, "PT", "prothrombin", "PT"),
]

ARM_TITLE = {
    "a": "no experience store, derive the approach from first principles",
    "m": "experience store available, reuse what fits",
    "r": "experience store available, reuse what fits (self-modifying harness)",
}


def store_path(arm: str) -> str:
    return str(EXPERIENCE / f"experience_{arm}.json")


def build_text(arm: str, seq: int, name: str, slug: str, code: str) -> str:
    labels = DATA / "chembl" / slug / "ki" / "dataset_p7b.csv"
    frozen = DATA / "chembl" / slug / "ki" / "splits" / f"frozen_{slug}.json"
    library = DATA / "zinc" / "library_100k.smi"

    if arm == "a":
        memory = (
            "- there is NO experience store in this arm and no experience.retrieve tool: "
            "derive the approach from first principles\n"
        )
    else:
        store = store_path(arm)
        memory = (
            f"- experience store: {store} (pass this absolute path as the `store` argument "
            "of experience.retrieve; a wrong or missing path silently returns zero records)\n"
        )

    text = f"""Goal: build the most reliable binding-activity predictor for {name} and produce a top-100 ranking of the 100k library.

Constraints:
- labels: {labels} (read-only). Molecules reserved for the locked test set have already been removed from this file, so everything you see is yours to train on.
- library: {library}
- FROZEN SPLIT: {frozen}
  Pass this exact path as `--split-manifest` to ml.train. Do NOT call data.split, and do not pick your own fractions: every arm is scored on this one manifest so the numbers are comparable.
{memory}- locked evaluation (REQUIRED): when you have a final model, call evaluation.locked exactly once with --target {code} --endpoint Ki --desc-set <the descriptor set you trained on> and --receipt evaluation/{code.lower()}_locked.json. The receipt holds the AUROC that counts; report it verbatim.
- this is target #{seq} in a sequence of 9.
"""
    if arm != "a":
        text += (
            "\nBefore choosing your modelling approach, retrieve prior experience from that store and reuse "
            "any configuration that fits this dataset's characteristics (sample size, positive rate, target class). "
            "Only explore new configurations if prior experience does not cover this data profile.\n"
        )
    text += f"""
You may choose representation, model family, and fusion.

Deliverable: report with
  (a) choices and rationale,
  (b) frozen-split validation AUROC/AUPRC/EF@1%,
  (c) the locked-test AUROC from evaluation/{code.lower()}_locked.json (quote it),
  (d) top-100 path,
  (e) cost (wall clock, jobs),
  (f) which experience_id(s) you used, and what you reused verbatim versus adapted.
"""
    return text


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--out-dir", default="ops/phase7b_custom")
    args = parser.parse_args()
    out_dir = ROOT / args.out_dir
    out_dir.mkdir(parents=True, exist_ok=True)

    written = 0
    for arm in ("a", "m", "r"):
        for seq, name, slug, code in TARGETS:
            # the driver keys on the short target code (ORDER in phase7_seq.py),
            # not on the artifact directory name
            task_id = f"p7b_{arm}_{code.lower()}"
            payload = {
                "task_id": task_id,
                "sender": "operator",
                "title": f"Phase7b arm {arm.upper()} target {seq} ({name}): {ARM_TITLE[arm]}",
                "text": build_text(arm, seq, name, slug, code),
            }
            (out_dir / f"{task_id}.json").write_text(
                json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
            written += 1
    print(f"wrote {written} task files to {out_dir}")
    print("task ids look like p7b_r_drd2; the driver needs --prefix p7b --tasks-dir ops/phase7b_custom")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
