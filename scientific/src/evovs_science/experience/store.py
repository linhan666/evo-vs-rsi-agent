"""Experience store (Blueprint §10, P3-01) — auditable facts, never a policy.

A plain JSON file under the data root. Every record carries its provenance
(hashes) and an explicit `applicability` note, so a later task can retrieve
what was done and under which rules without anyone hard-coding a conclusion.
Retrieval is read-only and presents facts plus limits; it never decides.
"""

from __future__ import annotations

import argparse
import json
import os

from ..manifest import describe_input, sha256_file, utc_now

SCHEMA_VERSION = "1"


def store_path(default: str = "experience/experience.json") -> str:
    return os.environ.get("EVOVS_EXPERIENCE_PATH", default)


def load(path: str) -> list[dict]:
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def save(path: str, records: list[dict]) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(records, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def record(path: str, kind: str, target: str, payload_path: str, *, note: str) -> dict:
    """Append one experience record; `payload_path` is summarised and hashed."""
    with open(payload_path, encoding="utf-8") as handle:
        payload = json.load(handle)
    entry = {
        "schema_version": SCHEMA_VERSION,
        "experience_id": f"{kind}_{target}_{len(load(path)) + 1:03d}",
        "kind": kind,
        "target": target,
        "created_at": utc_now(),
        "payload_path": os.path.basename(payload_path),
        "payload_sha256": sha256_file(payload_path),
        "payload": payload,
        "applicability": note,
    }
    records = load(path)
    records.append(entry)
    save(path, records)
    return entry


def retrieve(path: str, target: str | None = None, kind: str | None = None) -> list[dict]:
    records = load(path)
    return [item for item in records
            if (target is None or item["target"] == target) and (kind is None or item["kind"] == kind)]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evovs-science experience")
    parser.add_argument("--store", default=None, help="experience file (default from EVOVS_EXPERIENCE_PATH)")
    sub = parser.add_subparsers(dest="command", required=True)

    rec = sub.add_parser("record")
    rec.add_argument("--kind", required=True, choices=["dataset", "model", "screening"])
    rec.add_argument("--target", required=True)
    rec.add_argument("--payload", required=True, help="audit/metrics/report json to store")
    rec.add_argument("--note", required=True, help="applicability limits, one sentence")

    get = sub.add_parser("retrieve")
    get.add_argument("--target", default=None)
    get.add_argument("--kind", default=None)

    args = parser.parse_args(argv)
    path = args.store or store_path()

    if args.command == "record":
        entry = record(path, args.kind, args.target, args.payload, note=args.note)
        print(json.dumps({"experience_id": entry["experience_id"], "target": entry["target"]}))
        return 0

    records = retrieve(path, args.target, args.kind)
    print(json.dumps({"count": len(records),
                      "records": [{key: item[key] for key in ("experience_id", "kind", "target", "applicability")}
                                  for item in records]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
