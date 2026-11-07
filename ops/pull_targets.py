#!/usr/bin/env python3
"""Expand the GPCR benchmark from 3 targets to 10.

The RSI experiment needs enough sequential targets to show whether experience
transfer reduces marginal cost. Three targets cannot show a trend; ten can.
This script queries ChEMBL for human GPCR targets with the most Ki activity
records, pulls them with the existing data.chembl adapter, and normalises each
to the same schema the three current datasets use.

Usage:
  python ops/pull_targets.py --top 7 --types Ki --outdir scientific/.artifacts/chembl
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.request

API = "https://www.ebi.ac.uk/chembl/api/data"


def fetch(url: str) -> dict:
    with urllib.request.urlopen(url, timeout=60) as response:
        return json.load(response)


def gpcr_target_ids(limit: int = 40) -> list[dict]:
    """Human GPCR targets ordered by Ki activity count (descending)."""
    url = (f"{API}/target.json?target_type=SINGLE%20PROTEIN"
           f"&organism=Homo%20sapiens&target_class__icontains=GPCR&limit=100")
    payload = fetch(url)
    rows = []
    for target in payload.get("targets", []):
        tid = target.get("target_chembl_id")
        name = target.get("pref_name", tid)
        # count Ki activities
        count_url = f"{API}/activity.json?target_chembl_id={tid}&standard_type=Ki&limit=0"
        try:
            count = fetch(count_url).get("page_meta", {}).get("total_count", 0)
        except Exception:
            continue
        if count >= 500:
            rows.append({"target_chembl_id": tid, "pref_name": name, "ki_count": count})
    rows.sort(key=lambda r: -r["ki_count"])
    return rows[:limit]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="pull GPCR targets")
    parser.add_argument("--top", type=int, default=7)
    parser.add_argument("--types", default="Ki")
    parser.add_argument("--outdir", default="scientific/.artifacts/chembl")
    args = parser.parse_args(argv)

    existing = set(os.listdir(args.outdir)) if os.path.isdir(args.outdir) else set()
    print(f"existing datasets: {sorted(existing)}")

    candidates = gpcr_target_ids(limit=args.top * 3)
    print(f"candidate GPCR targets with >=500 Ki records:")
    for c in candidates:
        print(f"  {c['target_chembl_id']:16s} {c['pref_name']:40s} {c['ki_count']}")

    picked = [c for c in candidates if c["target_chembl_id"].lower() not in existing
              and c["pref_name"].lower().replace(" ", "_") not in existing]
    picked = picked[:args.top]
    print(f"\npulling {len(picked)} new targets...")

    sys.path.insert(0, "scientific/src")
    from evovs_science.data.chembl import pull, target_of

    for c in picked:
        tid = c["target_chembl_id"]
        slug = c["pref_name"].lower().replace(" ", "_")[:20]
        outdir = os.path.join(args.outdir, slug, "ki")
        os.makedirs(outdir, exist_ok=True)
        try:
            rows, warnings = pull(tid, [args.types], outdir, max_pages=20)
            print(f"  {slug}: {len(rows)} rows")
        except Exception as error:
            print(f"  {slug}: FAILED ({error})")
            continue

    return 0


if __name__ == "__main__":
    sys.exit(main())
