"""Shadow evaluator: replay trace steps in a sandbox and compare artifacts (P4-02).

No LLM, no writes outside `--sandbox`. The candidate is expressed as an
env-delta inside the CandidateSpec (e.g. EVOVS_FEAT_JOBS=8), so baseline and
candidate run the SAME single code path.
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import time

from artifacts import artifact_digest
from failure_clusters import error_class
from spec import validate_spec


def run_step(argv: list[str], cwd: str, env_delta: dict[str, str], timeout: int) -> dict:
    env = {**os.environ, **env_delta}
    os.makedirs(cwd, exist_ok=True)
    started = time.time()
    try:
        process = subprocess.run(argv, cwd=cwd, env=env, capture_output=True, timeout=timeout)
        code = process.returncode
        tail = process.stderr.decode("utf-8", "replace").strip().splitlines()[-3:]
    except subprocess.TimeoutExpired:
        # A candidate that cannot finish inside the budget is a failed candidate,
        # not a broken evaluator: record it and let the verdict say so.
        code = -9
        tail = [f"timed out after {timeout}s"]
    return {"exit_code": code,
            "wall_seconds": round(time.time() - started, 2),
            "stderr_tail": tail}


DERIVED_BASENAMES = {"artifact_manifest.json"}  # index of the other artifacts; no independent information


def evaluate(trace: dict, sandbox: str, steps_filter: list[str] | None, env_delta: dict[str, str],
             timeout: int, replay_baseline: bool = False, include_failed: bool = False) -> dict:
    results = []
    os.makedirs(sandbox, exist_ok=True)
    derived_skipped = 0
    failures_replayed = 0
    failures_remaining = 0
    failures_by_class: dict[str, dict] = {}
    recorded_by_class: dict[str, int] = {}
    for step in trace["steps"]:
        if steps_filter and step["tool_id"] not in steps_filter:
            continue
        failed_before = step["state"] != "SUCCEEDED"
        if failed_before and not include_failed:
            continue
        # A trace records the wall time of a run that may predate the current code
        # (and any promotion in between). For latency claims the baseline must be
        # measured now, on this machine, with this code — otherwise a candidate can
        # "win" against a stale number.
        replayed = run_step(step["argv"], sandbox, {}, timeout) if replay_baseline else None
        run = run_step(step["argv"], sandbox, env_delta, timeout)
        mismatches: list[str] = []
        equal = 0
        total_step = 0
        for artifact in step["artifacts"]:
            if os.path.basename(artifact["path"]) in DERIVED_BASENAMES:
                derived_skipped += 1
                continue
            total_step += 1
            path = os.path.join(sandbox, artifact["path"])
            if not os.path.exists(path):
                mismatches.append(f"{artifact['path']}: missing")
                continue
            if artifact_digest(path) == artifact["digest"]:
                equal += 1
            else:
                mismatches.append(f"{artifact['path']}: digest differs")
        if failed_before:
            failures_replayed += 1
            # Classify both sides: what failed then, and what still fails now.
            recorded_class = "{0}::{1}".format(step["tool_id"], error_class(
                step.get("error", ""), step.get("stderr_tail", ""), step.get("exit_code"),
                step.get("stdout_tail", "")))
            row = failures_by_class.setdefault(recorded_class, {"replayed": 0, "remaining": 0})
            row["replayed"] += 1
            recorded_by_class[recorded_class] = recorded_by_class.get(recorded_class, 0) + 1
            if run["exit_code"] != 0:
                failures_remaining += 1
                row["remaining"] += 1
        results.append({
            "tool_id": step["tool_id"],
            "recorded_state": step["state"],
            "baseline_wall_seconds": step["wall_seconds"],
            "replayed_baseline_wall_seconds": replayed["wall_seconds"] if replayed else None,
            "candidate_wall_seconds": run["wall_seconds"],
            "exit_code": run["exit_code"],
            "artifacts_total": total_step,
            "artifacts_equal": equal,
            "mismatches": mismatches,
            "stderr_tail": run["stderr_tail"],
        })
    total = sum(item["artifacts_total"] for item in results)
    equal = sum(item["artifacts_equal"] for item in results)
    return {
        "schema_version": "1",
        "sandbox": os.path.abspath(sandbox),
        "steps": results,
        "equivalence_rate": round(equal / total, 4) if total else None,
        "artifacts_total": total,
        "artifacts_equal": equal,
        "derived_skipped": derived_skipped,
        "failures_replayed": failures_replayed,
        "failures_remaining": failures_remaining,
        "failures_by_class": failures_by_class,
        "recorded_by_class": recorded_by_class,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evolution shadow")
    parser.add_argument("--trace", required=True)
    parser.add_argument("--spec", required=True, help="CandidateSpec json")
    parser.add_argument("--sandbox", required=True)
    parser.add_argument("--steps", default=None, help="comma-separated tool_id filter")
    parser.add_argument("--timeout", type=int, default=600)
    parser.add_argument("--baseline-replay", action="store_true",
                        help="re-run each step with the baseline environment too, so latency is measured on this code")
    parser.add_argument("--include-failed", action="store_true",
                        help="also replay steps that failed when recorded, and count how many still fail")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)

    trace = json.load(open(args.trace, encoding="utf-8"))
    spec = json.load(open(args.spec, encoding="utf-8"))
    errors = validate_spec(spec)
    if errors:
        raise SystemExit(f"invalid CandidateSpec {spec.get('candidate_id', '?')}: " + "; ".join(errors))
    env_delta = {change["key"]: change["value"] for change in spec.get("changes", [])
                 if change.get("type") == "env"}
    steps = args.steps.split(",") if args.steps else None

    report = evaluate(trace, args.sandbox, steps, env_delta, args.timeout, args.baseline_replay,
                      args.include_failed)
    report["candidate_id"] = spec.get("candidate_id")
    report["hypothesis"] = spec.get("hypothesis")
    report["acceptance"] = spec.get("acceptance")
    report["baseline_source"] = "replayed" if args.baseline_replay else "recorded in the trace"
    for item in report["steps"]:
        baseline = item.get("replayed_baseline_wall_seconds") or item["baseline_wall_seconds"]
        item["effective_baseline_wall_seconds"] = baseline
        item["speedup"] = round(baseline / item["candidate_wall_seconds"], 3) if item["candidate_wall_seconds"] else None

    if "recorded_by_class" not in report or not report["recorded_by_class"]:
        derived: dict[str, int] = {}
        for item in report.get("steps", []):
            if item.get("recorded_state", "SUCCEEDED") == "SUCCEEDED":
                continue
            key = "{0}::{1}".format(item["tool_id"], error_class(
                item.get("error", ""), item.get("stderr_tail", ""), item.get("exit_code"),
                item.get("stdout_tail", "")))
            derived[key] = derived.get(key, 0) + 1
        report["recorded_by_class"] = derived

    acceptance = spec.get("acceptance", {})
    verdict = {"equivalence_ok": report["equivalence_rate"] == 1.0}

    # Cost claims only make sense over steps that succeeded when recorded: a step
    # that used to fail has a meaningless "baseline" wall time.
    timed = [item for item in report["steps"]
             if item["recorded_state"] == "SUCCEEDED" and item["tool_id"] in ("rdkit.featurize", "screening.rank")]
    if timed and (acceptance.get("max_time_ratio") is not None or acceptance.get("min_speedup") is not None):
        ratio = max((item["candidate_wall_seconds"] / item["effective_baseline_wall_seconds"]
                     for item in timed if item["effective_baseline_wall_seconds"]), default=None)
        speedup = max((item["speedup"] or 0) for item in timed)
        report["featurize_time_ratio_max"] = ratio
        report["best_speedup"] = speedup
        verdict["time_ratio_ok"] = (ratio is None) or (ratio <= acceptance.get("max_time_ratio", 1.2))
        verdict["speedup_ok"] = (not acceptance.get("min_speedup")) or speedup >= acceptance["min_speedup"]

    if acceptance.get("failures_in_replay") is not None:
        claimed = acceptance.get("failure_clusters") or []
        by_class = report.get("failures_by_class") or {}
        if claimed:
            replayed = sum(int(by_class.get(name, {}).get("replayed", 0)) for name in claimed)
            remaining = sum(int(by_class.get(name, {}).get("remaining", 0)) for name in claimed)
        else:
            replayed, remaining = report.get("failures_replayed"), report.get("failures_remaining")
        verdict["failures_ok"] = bool(replayed) and remaining is not None \
            and remaining <= int(acceptance["failures_in_replay"])

    report["verdict"] = verdict
    report["verdict"]["pass"] = all(verdict.values())

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as handle:
        json.dump(report, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    print(json.dumps({"candidate": spec.get("candidate_id"), "equivalence_rate": report["equivalence_rate"],
                      "steps": [(item["tool_id"], item["baseline_wall_seconds"], item["candidate_wall_seconds"])
                                for item in report["steps"]]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
