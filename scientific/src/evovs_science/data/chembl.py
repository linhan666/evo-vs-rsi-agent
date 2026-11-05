"""ChEMBL activity snapshot importer (Blueprint §9.2, P2-01/P2-02).

Rules this module enforces, because a later model must not paper over them:
  * one snapshot per run: the ChEMBL version, release date, API query and the
    hash of every raw page are recorded;
  * `Ki / Kd / IC50 / EC50` stay in separate columns and are **never averaged
    across endpoints**;
  * `<` and `>` relations are kept, never coerced into exact values;
  * an unparseable SMILES is dropped and counted, not silently repaired;
  * duplicate measurements are reported, not collapsed.

It reads the public API only. No credentials, no writes outside `--outdir`.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import time
import urllib.error
import urllib.request

from ..manifest import describe_input, utc_now, write_manifest

API = "https://www.ebi.ac.uk/chembl/api/data"
DEFAULT_TARGET = "CHEMBL233"  # OPRM1, human mu opioid receptor
FIELDS = [
    "activity_id", "molecule_chembl_id", "canonical_smiles", "standard_type", "standard_relation",
    "standard_value", "standard_units", "assay_chembl_id", "assay_type", "confidence_score",
    "target_chembl_id", "target_pref_name", "document_chembl_id", "data_validity_comment", "potential_duplicate",
]


def fetch_json(url: str, retries: int = 3) -> dict:
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(url, timeout=90) as response:
                return json.load(response)
        except (urllib.error.URLError, TimeoutError) as error:
            if attempt == retries - 1:
                raise SystemExit(f"cannot read {url}: {error}")
            time.sleep(2 * (attempt + 1))
    raise SystemExit("unreachable")


def target_of(target_id: str) -> dict:
    data = fetch_json(f"{API}/target/{target_id}.json")
    return {"target_chembl_id": data.get("target_chembl_id"), "pref_name": data.get("pref_name"),
            "organism": data.get("organism"), "target_type": data.get("target_type")}


def pull(target_id: str, types: list[str], outdir: str, max_pages: int) -> tuple[list[dict], list[dict]]:
    raw_dir = os.path.join(outdir, "raw")
    os.makedirs(raw_dir, exist_ok=True)
    rows: list[dict] = []
    pages: list[dict] = []
    offset, page = 0, 0
    type_filter = ",".join(types)
    while page < max_pages:
        url = (f"{API}/activity.json?target_chembl_id={target_id}&standard_type__in={type_filter}"
               f"&limit=1000&offset={offset}")
        payload = fetch_json(url)
        path = os.path.join(raw_dir, f"page-{page:04d}.json")
        with open(path, "w", encoding="utf-8") as handle:
            json.dump(payload, handle)
        pages.append({"path": path, "url": url, "activities": len(payload.get("activities", []))})
        rows.extend(payload.get("activities", []))
        meta = payload.get("page_meta", {})
        if not meta.get("next"):
            break
        offset += 1000
        page += 1
    return rows, pages


def fetch_assays(assay_ids: list[str], outdir: str, batch: int = 80) -> dict[str, dict]:
    """`confidence_score` lives on the assay, not on the activity, so fetch it there.

    Cached in `assays.json`; a rerun only asks for ids it has not seen.
    """
    cache_path = os.path.join(outdir, "assays.json")
    cache: dict[str, dict] = {}
    if os.path.exists(cache_path):
        with open(cache_path, encoding="utf-8") as handle:
            cache = json.load(handle)
    missing = [item for item in dict.fromkeys(assay_ids) if item and item not in cache]
    for start in range(0, len(missing), batch):
        chunk = missing[start:start + batch]
        url = (f"{API}/assay.json?assay_chembl_id__in={','.join(chunk)}&limit=1000"
               f"&only=assay_chembl_id,confidence_score,assay_type")
        payload = fetch_json(url)
        for item in payload.get("assays", []):
            cache[item.get("assay_chembl_id")] = {
                "confidence_score": item.get("confidence_score"),
                "assay_type": item.get("assay_type"),
            }
    with open(cache_path, "w", encoding="utf-8") as handle:
        json.dump(cache, handle, indent=2)
    return cache


def normalize(rows: list[dict], target: dict, assays: dict[str, dict] | None = None) -> tuple[list[dict], dict]:
    from rdkit import Chem, RDLogger

    RDLogger.DisableLog("rdApp.*")
    out: list[dict] = []
    invalid: list[dict] = []
    for row in rows:
        smiles = (row.get("canonical_smiles") or "").strip()
        if not smiles:
            invalid.append({"activity_id": row.get("activity_id"), "reason": "missing_smiles"})
            continue
        mol = Chem.MolFromSmiles(smiles)
        if mol is None:
            invalid.append({"activity_id": row.get("activity_id"), "reason": "unparseable_smiles"})
            continue
        out.append({
            "activity_id": row.get("activity_id"),
            "molecule_chembl_id": row.get("molecule_chembl_id"),
            "canonical_smiles": Chem.MolToSmiles(mol),
            "standard_type": row.get("standard_type"),
            "standard_relation": row.get("standard_relation"),
            "standard_value": row.get("standard_value"),
            "standard_units": row.get("standard_units"),
            "assay_chembl_id": row.get("assay_chembl_id"),
            "assay_type": (assays or {}).get(str(row.get("assay_chembl_id")), {}).get("assay_type") or row.get("assay_type"),
            "confidence_score": (assays or {}).get(str(row.get("assay_chembl_id")), {}).get("confidence_score"),
            "target_chembl_id": row.get("target_chembl_id"),
            "target_pref_name": target.get("pref_name"),
            "document_chembl_id": row.get("document_chembl_id"),
            "data_validity_comment": row.get("data_validity_comment"),
            "potential_duplicate": row.get("potential_duplicate"),
        })

    by_type: dict[str, int] = {}
    by_relation: dict[str, int] = {}
    by_units: dict[str, int] = {}
    by_assay_type: dict[str, int] = {}
    seen: dict[tuple, int] = {}
    duplicates = 0
    for row in out:
        by_type[str(row["standard_type"])] = by_type.get(str(row["standard_type"]), 0) + 1
        by_relation[str(row["standard_relation"])] = by_relation.get(str(row["standard_relation"]), 0) + 1
        by_units[str(row["standard_units"])] = by_units.get(str(row["standard_units"]), 0) + 1
        by_assay_type[str(row["assay_type"])] = by_assay_type.get(str(row["assay_type"]), 0) + 1
        key = (row["molecule_chembl_id"], row["standard_type"], row["standard_value"], row["standard_relation"])
        if key in seen:
            duplicates += 1
        seen[key] = seen.get(key, 0) + 1

    audit = {
        "rows_pulled": len(rows), "rows_kept": len(out), "rows_dropped": len(invalid),
        "by_type": by_type, "by_relation": by_relation, "by_units": by_units, "by_assay_type": by_assay_type,
        "exact_duplicate_groups": duplicates,
        "note": "Types are counted separately; no cross-endpoint averaging is performed anywhere in this pipeline.",
    }
    return out, {"audit": audit, "invalid": invalid[:500]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evovs-science chembl")
    parser.add_argument("--target", default=DEFAULT_TARGET)
    parser.add_argument("--types", default="Ki,Kd,IC50,EC50")
    parser.add_argument("--outdir", required=True)
    parser.add_argument("--max-pages", type=int, default=60)
    args = parser.parse_args(argv)

    status = fetch_json(f"{API}/status.json")
    version, released = status.get("chembl_db_version"), status.get("chembl_release_date")
    if version is None:
        raise SystemExit("the ChEMBL status endpoint returned no version")

    target = target_of(args.target)
    types = [item.strip() for item in args.types.split(",") if item.strip()]
    os.makedirs(args.outdir, exist_ok=True)

    rows, pages = pull(args.target, types, args.outdir, args.max_pages)
    assays = fetch_assays([str(row.get("assay_chembl_id")) for row in rows], args.outdir)
    normalized, extra = normalize(rows, target, assays)

    csv_path = os.path.join(args.outdir, "activities_normalized.csv")
    with open(csv_path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(normalized)

    audit = {
        "schema_version": "1", "created_at": utc_now(),
        "chembl_version": version, "chembl_release_date": released,
        "api": API, "target": target, "standard_types": types,
        "pages": len(pages), "assays_resolved": len(assays),
        "activities_pulled": len(rows), "activities_kept": len(normalized),
        **extra,
    }
    audit_path = os.path.join(args.outdir, "dataset_audit.json")
    with open(audit_path, "w", encoding="utf-8") as handle:
        json.dump(audit, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    inputs = [describe_input(page["path"]) for page in pages]
    write_manifest(
        args.outdir,
        [
            {"path": csv_path, "content_type": "text/csv", "description": "normalized activities"},
            {"path": audit_path, "content_type": "application/json", "description": "dataset audit"},
        ],
        generator="evovs_science.data.chembl",
        inputs=inputs,
        parameters={"target": args.target, "types": types, "limit_per_page": 1000},
        extra={"chembl_version": version, "release_date": released, "query": [page["url"] for page in pages]},
    )

    print(json.dumps({"chembl": version, "target": target.get("pref_name"), "pulled": len(rows),
                      "kept": len(normalized), "dropped": len(extra["invalid"]), "audit": audit["audit"]}))
    return 0 if normalized else 2


if __name__ == "__main__":
    raise SystemExit(main())
