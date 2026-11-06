"""Cross-ticket failure-mode clustering over the trace corpus.

Groups every non-SUCCEEDED step by (tool_id, error_class). The class comes from
the structured `error` when the runner recorded one, otherwise from the final
line of `stderr_tail` (a Python traceback ends with `XxxError: message`), then
`stdout_tail`, then the exit code. Deliberately dumb: it surfaces patterns, it
does not diagnose them.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
from collections import defaultdict

# Ordered longest-first-ish: `FileNotFoundError` must win over the generic tail.
EXCEPTIONS = (
    "FileNotFoundError", "IsADirectoryError", "NotADirectoryError", "PermissionError",
    "JSONDecodeError", "KeyError", "ValueError", "TypeError", "AttributeError",
    "SyntaxError", "ImportError", "ModuleNotFoundError", "NameError",
)

# Absolute paths differ per machine; a cluster key must not (the corpus may be
# replayed elsewhere, and a key containing /home/<user> is not a class).
ABSOLUTE_PATH = re.compile(r"(?:/[\w.\-]+){2,}")


def last_meaningful_line(text: str) -> str:
    for line in reversed((text or "").splitlines()):
        if line.strip():
            return line.strip()
    return ""


def error_class(error: str, stderr_tail: str, exit_code, stdout_tail: str = "") -> str:
    text = (error or "").strip() or last_meaningful_line(stderr_tail) or last_meaningful_line(stdout_tail)
    if not text:
        return f"exit_{exit_code}" if exit_code not in (None, 0) else "no_error_recorded"
    for token in EXCEPTIONS:
        if token in text:
            return token
    missing = re.search(r"has no '([^']+)' column", text)
    if missing:
        return f"missing_column:{missing.group(1)}"
    if re.search(r"needs .+ columns", text):
        return "missing_columns"
    if "unrecognized arguments" in text or "unknown option" in text:
        return "bad_arguments"
    return ABSOLUTE_PATH.sub("<path>", text)[:60]


def step_evidence(step: dict) -> str:
    """The best human-readable line we have for one failed step."""
    error = (step.get("error") or "").strip()
    if error:
        return error
    return (last_meaningful_line(step.get("stderr_tail", ""))
            or last_meaningful_line(step.get("stdout_tail", "")))


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
        trace = json.loads(open(path, encoding="utf-8").read())
        tickets += 1
        for step in trace.get("steps", []):
            total_steps += 1
            if step.get("state") == "SUCCEEDED":
                continue
            failed_steps += 1
            key = "{0} :: {1}".format(
                step["tool_id"],
                error_class(step.get("error", ""), step.get("stderr_tail", ""),
                            step.get("exit_code"), step.get("stdout_tail", "")))
            clusters[key].append({"ticket": os.path.basename(path), "job_id": step.get("job_id"),
                                  "evidence": step_evidence(step)[:200]})

    report = {
        "schema_version": "2",
        "created_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(timespec="seconds"),
        "corpus": {"traces": tickets, "steps": total_steps, "failed": failed_steps},
        "clusters": {key: {"count": len(items), "tickets": sorted({item["ticket"] for item in items}),
                           "sample_errors": [item["evidence"] for item in items[:3]]}
                     for key, items in sorted(clusters.items(), key=lambda kv: -len(kv[1]))},
        "note": "Pattern surfacing only. Classes come from the structured error or the stderr tail.",
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
