"""Export a ticket's scientific-job history into a replayable trace (P4-01).

Failure diagnosis needs the text the tool actually printed. `result.json` only
carries a structured `error` for spawn failures / missing outputs / host
interruptions; a plain non-zero exit leaves it empty and the real message sits
in `stderr.log`. So every step also carries a bounded `stderr_tail` (and, when
stderr is silent, a `stdout_tail` for failed steps) — D-1, 2026-11-06.
"""

from __future__ import annotations

import argparse
import glob
import json
import os

from artifacts import artifact_digest

TAIL_BYTES = 1600
TAIL_CHARS = 1200


def read_tail(path: str, limit: int = TAIL_BYTES, chars: int = TAIL_CHARS) -> str:
    """Return the last `chars` characters of `path`, or '' when it does not exist."""
    if not os.path.exists(path):
        return ""
    with open(path, "rb") as handle:
        try:
            handle.seek(-limit, os.SEEK_END)
        except OSError:  # file shorter than `limit`; seek(negative) is invalid
            handle.seek(0)
        data = handle.read()
    return data.decode("utf-8", "replace")[-chars:].strip()


def export(ticket_dir: str) -> dict:
    steps = []
    for job_dir in sorted(glob.glob(os.path.join(ticket_dir, ".jobs", "*"))):
        result_path = os.path.join(job_dir, "result.json")
        if not os.path.exists(result_path):
            continue
        record = json.loads(open(result_path, encoding="utf-8").read())
        artifacts = []
        for artifact in record.get("artifacts", []):
            path = os.path.join(ticket_dir, artifact["path"])
            artifacts.append({
                "path": artifact["path"],
                "recorded_sha256": artifact["sha256"],
                "digest": artifact_digest(path),
            })
        stderr_tail = read_tail(os.path.join(job_dir, "stderr.log"))
        state = record["state"]
        steps.append({
            "job_id": record["job_id"],
            "tool_id": record["tool_id"],
            "state": state,
            "started_at": record.get("started_at"),
            "argv": record.get("argv", []),
            "wall_seconds": record.get("usage", {}).get("wall_seconds"),
            "exit_code": record.get("exit_code"),
            "error": (record.get("error") or "")[:400],
            "stderr_tail": stderr_tail,
            # Some CLIs report failures on stdout; only kept when stderr was silent
            # and the step did not succeed, so successful-step noise stays out.
            "stdout_tail": ("" if state == "SUCCEEDED" or stderr_tail
                            else read_tail(os.path.join(job_dir, "stdout.log"), chars=600)),
            "artifacts": artifacts,
        })
    steps.sort(key=lambda step: step["started_at"] or "")
    return {
        "schema_version": "2",
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
