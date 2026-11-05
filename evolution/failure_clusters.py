"""Cross-ticket failure-mode clustering over the trace corpus.

Groups every non-SUCCEEDED step by (tool_id, error_class) where the error class
is the leading token of the recorded error. Deliberately dumb: it surfaces
patterns, it does not diagnose them. Useful from ~20 traces onward; the current
corpus gives an early baseline.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
from collections import Counter, defaultdict


def error_class(error: str, exit_code) -> str:
    if not error:
        return f"exit_{exit_code}" if exit_code not in (None, 0) else "no_error_recorded"
    first_line = error.strip().splitlines()[0]
    for token in ("FileNotFoundError", "IsADirectoryError", "NotADirectoryError", "JSONDecodeError",
                  "ValueError", "TypeError", "SyntaxError", "ImportError", "NameError"):
        if token in first_line:
            return token
    return first_line[:60]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evolution failure-clusters")
    parser.add_argument("--traces-dir", default=None)
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)

    traces_dir = args.traces_dir or os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                                 "evolution", "traces")
    clusters: dict[str, list[dict]] = defaultdict(list)
    total_steps, failed_steps = 0, 0
    tickets = 0
    for path in sorted(glob.glob(os.path.join(traces_dir, "*.json"))):
        trace = json.load(open(path, encoding="utf-8"))
        tickets += 1
        for step in trace.get("steps", []):
            total_steps += 1
            if step.get("state") == "SUCCEEDED":
                continue
            failed_steps += 1
            key = f"{step['tool_id']} :: {error_class(step.get('error', ''), step.get('exit_code'))}"
            clusters[key].append({"ticket": os.path.basename(path), "job_id": step.get("job_id"),
                                  "error": step.get("error", "")[:160]})

    report = {
        "schema_version": "1",
        "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(timespec="seconds"),
        "corpus": {"traces": tickets, "steps": total_steps, "failed": failed_steps},
        "clusters": {key: {"count": len(items), "tickets": sorted({item["ticket"] for item in items}),
                           "sample_errors": [item["error"] for item in items[:3]]}
                     for key, items in sorted(clusters.items(), key=lambda kv: -len(kv[1]))},
        "note": "Pattern surfacing only. Clusters become meaningful as the corpus grows past ~20 traces.",
    }
    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        json.dump(report, open(args.output, "w", encoding="utf-8"), ensure_ascii=False, indent=2)
    print(json.dumps({"traces": tickets, "steps": total_steps, "failed": failed_steps,
                      "clusters": {k: v["count"] for k, v in sorted(report["clusters"].items(),
                                                                        key=lambda kv: -kv[1]["count"])[:8]}},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
