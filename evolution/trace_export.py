"""Export a ticket's scientific-job history into a replayable trace (P4-01)."""

from __future__ import annotations

import argparse
import glob
import json
import os

from artifacts import artifact_digest


def export(ticket_dir: str) -> dict:
    steps = []
    for job_dir in sorted(glob.glob(os.path.join(ticket_dir, ".jobs", "*"))):
        result_path = os.path.join(job_dir, "result.json")
        if not os.path.exists(result_path):
            continue
        record = json.load(open(result_path, encoding="utf-8"))
        artifacts = []
        for artifact in record.get("artifacts", []):
            path = os.path.join(ticket_dir, artifact["path"])
            artifacts.append({
                "path": artifact["path"],
                "recorded_sha256": artifact["sha256"],
                "digest": artifact_digest(path),
            })
        steps.append({
            "job_id": record["job_id"],
            "tool_id": record["tool_id"],
            "state": record["state"],
            "started_at": record.get("started_at"),
            "argv": record.get("argv", []),
            "wall_seconds": record.get("usage", {}).get("wall_seconds"),
            "exit_code": record.get("exit_code"),
            "error": (record.get("error") or "")[:400],
            "artifacts": artifacts,
        })
    steps.sort(key=lambda step: step["started_at"] or "")
    return {
        "schema_version": "1",
        "ticket_dir": os.path.abspath(ticket_dir),
        "exported_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
            .isoformat(timespec="seconds"),
        "steps": steps,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evolution trace-export")
    parser.add_argument("--ticket-dir", required=True)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    trace = export(args.ticket_dir)
    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(trace, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"steps": len(trace["steps"]),
                      "tools": [step["tool_id"] for step in trace["steps"]]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
