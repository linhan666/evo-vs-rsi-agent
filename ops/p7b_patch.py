#!/usr/bin/env python3
"""Idempotent patches that extend the locked-evaluation channel to all nine targets.

Two files must agree on the target list:
  scientific/src/evovs_science/evaluation/locked.py   CHANNELS["Ki"]  (runtime)
  src/research/registry.ts                            LockedInput.target (schema gate)

The Python side is safe to apply while the service runs: every job invokes it as
`python -m evovs_science.evaluation.locked`, so a changed file is picked up on the
next job. The TypeScript side must be rebuilt (`pnpm build`) and the service
restarted, so it is gated behind --include-ts.

Usage:
  python3 ops/p7b_patch.py                  # python only
  python3 ops/p7b_patch.py --include-ts     # python + registry.ts
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCKED = ROOT / "scientific" / "src" / "evovs_science" / "evaluation" / "locked.py"
REGISTRY = ROOT / "src" / "research" / "registry.ts"

NEW_TARGETS = [
    ("D2", "chembl37_ki_d2"),
    ("5HT", "chembl37_ki_5ht"),
    ("ADR", "chembl37_ki_adr"),
    ("CBR", "chembl37_ki_cbr"),
    ("CA2", "chembl37_ki_ca2"),
    ("PT", "chembl37_ki_pt"),
]
ALL_TARGETS = ["MOR", "KOR", "DRD2"] + [code for code, _ in NEW_TARGETS]


def patch_python() -> str:
    text = LOCKED.read_text(encoding="utf-8")
    if '"D2": ("chembl37_ki_d2"' in text:
        return "python: already patched"
    anchor = re.search(r'("Ki": \{\n(?:.*\n)*?)(    \},\n)', text)
    if not anchor:
        return "python: ANCHOR NOT FOUND"
    block = "".join(
        f'        "{code}": ("{directory}", "final_test_Ki.csv"),\n'
        for code, directory in NEW_TARGETS)
    text = text[:anchor.end(1)] + block + text[anchor.end(1):]
    LOCKED.write_text(text, encoding="utf-8")
    return f"python: added {len(NEW_TARGETS)} Ki targets"


def patch_ts() -> str:
    text = REGISTRY.read_text(encoding="utf-8")
    enum = "target: z.enum([" + ", ".join(f"'{code}'" for code in ALL_TARGETS) + "])"
    current = re.search(r"target: z\.enum\(\[[^\]]*\]\)", text)
    if not current:
        return "ts: ANCHOR NOT FOUND"
    if current.group(0) == enum:
        return "ts: already patched"
    text = text[:current.start()] + enum + text[current.end():]
    REGISTRY.write_text(text, encoding="utf-8")
    return "ts: enum extended to 9 targets"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--include-ts", action="store_true")
    args = parser.parse_args()
    print(patch_python())
    if args.include_ts:
        print(patch_ts())
    else:
        print("ts: skipped (needs pnpm build + service restart)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
