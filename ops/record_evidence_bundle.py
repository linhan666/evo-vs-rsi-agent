#!/usr/bin/env python3
"""Append a corrected experience record that pins the RIGHT evidence bundle.

The store is append-only and a record carries exactly one payload file, so a
conclusion that cites several artifacts (three targets x one metrics file) has
no single honest payload. This script writes a small bundle that names each
artifact with its sha256, then records THAT as the payload. The superseded
record stays in place; the new one says so in `applicability` (D-2).

Usage:
  record_evidence_bundle.py --kind harness --target HARNESS \
      --subject "candidate3 descv2 acceptance (Ki channel)" \
      --supersedes model_HARNESS_017 \
      --artifact protected/chembl37_ki/metrics_test_locked_agent_._MOR.json \
      --artifact ... \
      --note "..." [--store PATH]
"""
from __future__ import annotations

import argparse
import json
import os
import sys

HOME = os.path.expanduser("~")
ROOT = os.path.join(HOME, "evo_vs_rsi")
sys.path.insert(0, os.path.join(ROOT, "scientific", "src"))

from evovs_science.experience.store import record  # noqa: E402
from evovs_science.manifest import sha256_file, utc_now  # noqa: E402

DEFAULT_STORE = os.path.join(ROOT, "scientific", ".artifacts", "experience", "experience.json")
BUNDLE_DIR = os.path.join(ROOT, "scientific", ".artifacts", "experience", "bundles")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--kind", required=True)
    ap.add_argument("--target", required=True)
    ap.add_argument("--subject", required=True)
    ap.add_argument("--supersedes", default=None)
    ap.add_argument("--artifact", action="append", default=[], required=True,
                    help="repo-relative path of an evidence artifact (repeatable)")
    ap.add_argument("--note", required=True)
    ap.add_argument("--store", default=DEFAULT_STORE)
    args = ap.parse_args()

    bundle = {
        "schema_version": "1",
        "created_at": utc_now(),
        "subject": args.subject,
        "supersedes": args.supersedes,
        "artifacts": [],
    }
    for relative in args.artifact:
        path = os.path.join(ROOT, relative)
        if not os.path.isfile(path):
            raise SystemExit(f"artifact missing: {path}")
        bundle["artifacts"].append({"path": relative, "sha256": sha256_file(path),
                                    "size": os.path.getsize(path)})

    os.makedirs(BUNDLE_DIR, exist_ok=True)
    slug = "".join(ch if ch.isalnum() or ch in "-_" else "-" for ch in args.subject)[:60]
    bundle_path = os.path.join(BUNDLE_DIR, f"{slug}.json")
    with open(bundle_path, "w", encoding="utf-8") as handle:
        json.dump(bundle, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    entry = record(args.store, args.kind, args.target, bundle_path, note=args.note)
    print(json.dumps({"experience_id": entry["experience_id"], "payload": bundle_path,
                      "artifacts": len(bundle["artifacts"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
