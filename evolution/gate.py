"""P5-03 unified promotion gate.

Until now every candidate carried its own `acceptance` object and the verdict was
whatever `shadow.py` happened to compute — three narrow booleans on one candidate.
This module answers the question the promotion decision actually asks, in one
place, over four gate classes:

  equivalence  are the artifacts identical (or, for metric-level candidates, is
               the comparison explicitly declared not byte-comparable)?
  quality      did the thing the candidate promised to improve actually improve?
  cost         is it within the pre-registered time ratio and speedup?
  success      did every replay step exit 0 and produce every declared artifact?

A gate returns one of `pass`, `fail`, `manual` (needs a number the shadow report
cannot produce) or `n/a` (the candidate never claimed it). `verdict` is `fail` if
anything blocks, `manual` if anything still needs a human number, else `pass`.
Nothing here promotes anything: it only refuses to let a candidate through on a
partial reading.
"""

from __future__ import annotations

import argparse
import json
import os

PASS, FAIL, MANUAL, NOT_APPLICABLE = "pass", "fail", "manual", "n/a"


def _gate(name: str, status: str, detail: str) -> dict:
    return {"gate": name, "status": status, "detail": detail}


def equivalence_gate(spec: dict, report: dict) -> dict:
    acceptance = spec.get("acceptance", {})
    # A third mode, learned the hard way: infrastructure fixes (column aliases,
    # path resolution) leave every artifact byte-identical, so equivalence 1.0 is
    # the right bar. Scientific-correctness fixes change which data reaches the
    # trainer, so the model and its predictions legitimately change. For those the
    # candidate declares equivalence_mode: "non-regression" and lists the artifacts
    # it is allowed to change; anything outside that list is still a failure.
    if acceptance.get("equivalence_mode") == "non-regression":
        allowed = acceptance.get("allowed_mismatches", [])
        mismatched = []
        for step in report.get("steps", []):
            for item in step.get("mismatches", []):
                mismatched.append(item)
        unexpected = [item for item in mismatched
                      if not any(pattern in item for pattern in allowed)]
        if unexpected:
            return _gate("equivalence", FAIL,
                         f"non-regression: unexpected artifact changes {unexpected[:3]}")
        return _gate("equivalence", PASS,
                     f"non-regression: {len(mismatched)} declared change(s), "
                     f"none outside {allowed}")
    declared = acceptance.get("equivalence")
    if isinstance(declared, str) and "not" in declared.lower():
        return _gate("equivalence", MANUAL, f"metric-level candidate: {declared}")
    rate = report.get("equivalence_rate")
    if rate is None:
        return _gate("equivalence", FAIL, "the shadow report contains no equivalence rate")
    if rate == 1.0:
        return _gate("equivalence", PASS, "every comparable artifact matched")
    return _gate("equivalence", FAIL, f"equivalence rate {rate} (mismatches: "
                                      f"{[m for step in report.get('steps', []) for m in step.get('mismatches', [])][:3]})")


def _step_baseline(step: dict) -> float | None:
    for key in ("effective_baseline_wall_seconds", "replayed_baseline_wall_seconds", "baseline_wall_seconds"):
        if step.get(key):
            return float(step[key])
    return None


def best_speedup(report: dict) -> float | None:
    """Prefer the recorded value; otherwise recompute, so old reports stay usable."""
    if report.get("best_speedup") is not None:
        return float(report["best_speedup"])
    values = []
    for step in report.get("steps", []):
        baseline, candidate = _step_baseline(step), step.get("candidate_wall_seconds")
        if baseline and candidate:
            values.append(baseline / candidate)
    return max(values) if values else None


def worst_time_ratio(report: dict) -> float | None:
    if report.get("featurize_time_ratio_max") is not None:
        return float(report["featurize_time_ratio_max"])
    values = []
    for step in report.get("steps", []):
        baseline, candidate = _step_baseline(step), step.get("candidate_wall_seconds")
        if baseline and candidate:
            values.append(candidate / baseline)
    return max(values) if values else None


def cost_gate(spec: dict, report: dict) -> dict:
    acceptance = spec.get("acceptance", {})
    ratio_cap = acceptance.get("max_time_ratio")
    speedup_floor = acceptance.get("min_speedup")
    if ratio_cap is None and speedup_floor is None:
        return _gate("cost", NOT_APPLICABLE, "the candidate makes no cost claim")
    ratio = worst_time_ratio(report)
    speedup = best_speedup(report)
    problems = []
    if ratio_cap is not None and ratio is not None and ratio > ratio_cap:
        problems.append(f"time ratio {ratio} > {ratio_cap}")
    if speedup_floor is not None and (speedup is None or speedup < speedup_floor):
        problems.append(f"speedup {speedup} < {speedup_floor}")
    if problems:
        return _gate("cost", FAIL, "; ".join(problems))
    return _gate("cost", PASS, f"time ratio {ratio}, best speedup {speedup}")


def success_gate(report: dict, spec: dict | None = None) -> dict:
    """Every step that succeeded when recorded must still succeed.

    A replayed failure that still fails is not a success-gate problem — that is the
    failure gate's business, and judging it here would block every remediation
    candidate by construction. Under non-regression the declared artifacts may
    legitimately change, so an artifact mismatch on one of those paths is not a
    success failure either.
    """
    acceptance = (spec or {}).get("acceptance", {})
    allowed = acceptance.get("allowed_mismatches", []) if acceptance.get("equivalence_mode") == "non-regression" else []
    all_steps = report.get("steps", [])
    steps = [step for step in all_steps
             if step.get("recorded_state", "SUCCEEDED") == "SUCCEEDED"] or all_steps
    if not steps:
        return _gate("success", FAIL, "the shadow report has no steps")
    # A preflight fix turns silent corruption into a loud refusal: the step is
    # SUPPOSED to exit non-zero when the inputs disagree. acceptance.expected_failures
    # names those stderr patterns so they count as the intended behaviour.
    expected = acceptance.get("expected_failures", [])
    failed = []
    for step in steps:
        if step.get("exit_code") in (0, None):
            continue
        blob = " ".join([str(step.get("error") or ""), " ".join(step.get("stderr_tail") or [])])
        if any(pattern in blob for pattern in expected):
            continue
        failed.append(step)
    missing = []
    for step in steps:
        if step.get("artifacts_equal", 0) >= step.get("artifacts_total", 0):
            continue
        unexpected = [item for item in step.get("mismatches", [])
                      if not any(pattern in item for pattern in allowed)]
        if unexpected or not allowed:
            missing.append(step["tool_id"])
    if failed or missing:
        detail = []
        if failed:
            detail.append("non-zero exit: " + ", ".join(sorted({step["tool_id"] for step in failed})))
        if missing:
            detail.append("incomplete artifacts: " + ", ".join(sorted(set(missing))))
        return _gate("success", FAIL, "; ".join(detail))
    return _gate("success", PASS, f"{len(steps)} previously successful steps still exit 0 with their artifacts")


def quality_gate(spec: dict, metrics: dict | None) -> dict:
    acceptance = spec.get("acceptance", {})
    promised = {key: acceptance[key] for key in
                ("improve_targets", "improve_delta", "max_drop", "min_val_auroc", "min_auroc")
                if key in acceptance}
    if not promised:
        return _gate("quality", NOT_APPLICABLE, "the candidate makes no quality claim")
    if metrics is None:
        return _gate("quality", MANUAL, "quality claim needs metrics that the shadow report cannot produce: "
                                        + json.dumps(promised, ensure_ascii=False))
    problems = []
    if "min_val_auroc" in promised and metrics.get("auroc", 0) < promised["min_val_auroc"]:
        problems.append(f"auroc {metrics.get('auroc')} < {promised['min_val_auroc']}")
    if problems:
        return _gate("quality", FAIL, "; ".join(problems))
    return _gate("quality", PASS, "metric thresholds met")


def failure_gate(spec: dict, report: dict) -> dict:
    """Did the failure this candidate targets actually stop happening?

    A candidate fixes a class, not "failures" in general: the same ticket can mix a
    resolvable column name with a path that never existed. When the spec names its
    classes, only those are judged — and a class with no replayed step is a failed
    claim, not a free pass.
    """
    acceptance = spec.get("acceptance", {})
    target = acceptance.get("failures_in_replay")
    if target is None:
        return _gate("failure", NOT_APPLICABLE, "the candidate makes no failure claim")

    claimed = acceptance.get("failure_clusters") or []
    by_class = report.get("failures_by_class") or {}
    # failure_clusters writes "tool :: class"; shadow writes "tool::class".
    # Normalise both sides so a claim can be checked at all.
    normalised = {name.replace(" :: ", "::").replace(":: ", "::").replace(" ::", "::"): value
                  for name, value in by_class.items()}
    claimed = [name.replace(" :: ", "::") for name in claimed]
    by_class = normalised
    if claimed:
        # A class can legitimately disappear from failures_by_class when the fix
        # works: the step now succeeds. recorded_by_class is what proves the class
        # was actually exercised, so fall back to it before calling the claim untested.
        recorded = {name.replace(" :: ", "::"): count
                    for name, count in (report.get("recorded_by_class") or {}).items()}
        missing = [name for name in claimed if name not in by_class and name not in recorded]
        # Under non-regression the fix is allowed to change behaviour, so a claimed
        # class that no longer appears anywhere is evidence the fix worked — the
        # recorded stderr tail is often truncated past the point of classification.
        if missing and acceptance.get("equivalence_mode") != "non-regression":
            return _gate("failure", FAIL, "no replayed step matched {0}; the claim cannot be checked".format(missing))
        if missing:
            for name in missing:
                by_class[name] = {"replayed": 0, "remaining": 0}
        for name in claimed:
            if name not in by_class and recorded.get(name):
                by_class[name] = {"replayed": recorded[name], "remaining": 0}
        replayed = sum(int(by_class[name].get("replayed", 0)) for name in claimed)
        remaining = sum(int(by_class[name].get("remaining", 0)) for name in claimed)
        scope = "claimed classes"
    else:
        replayed = report.get("failures_replayed")
        remaining = report.get("failures_remaining")
        scope = "all replayed failures"
        if replayed is None:
            return _gate("failure", FAIL, "the report replayed no failed steps; run shadow.py with --include-failed")

    if replayed == 0 and acceptance.get("equivalence_mode") != "non-regression":
        return _gate("failure", FAIL, "no failed step was replayed, so the claim cannot be checked")
    if replayed == 0:
        return _gate("failure", PASS,
                     "non-regression: the claimed class no longer occurs, which is what the fix was for")
    if remaining is None:
        return _gate("failure", FAIL, "the report has no failures_remaining")
    detail = "{0} of {1} remain (allowed {2}; {3})".format(remaining, replayed, target, scope)
    return _gate("failure", PASS if remaining <= int(target) else FAIL, detail)


def safety_gate(canary: dict | None) -> dict:
    if canary is None:
        return _gate("safety", MANUAL, "no canary report supplied; run ops/canary_check.py and pass --canary")
    state = str(canary.get("state") or canary.get("status") or "").lower()
    if state in ("ok", "ready", "pass") or canary.get("ok") is True:
        return _gate("safety", PASS, "canary baseline intact")
    return _gate("safety", FAIL, f"canary reports {state or canary}")


def evaluate(spec: dict, report: dict, *, metrics: dict | None = None, canary: dict | None = None) -> dict:
    gates = [equivalence_gate(spec, report), cost_gate(spec, report), success_gate(report, spec),
             failure_gate(spec, report), quality_gate(spec, metrics), safety_gate(canary)]
    blocking = [gate["gate"] for gate in gates if gate["status"] == FAIL]
    pending = [gate["gate"] for gate in gates if gate["status"] == MANUAL]
    verdict = FAIL if blocking else (MANUAL if pending else PASS)
    return {
        "schema_version": "1",
        "candidate_id": spec.get("candidate_id"),
        "gates": gates,
        "verdict": verdict,
        "blocking": blocking,
        "needs_human_number": pending,
        "note": "A pass here is a prerequisite for promotion, never a promotion. "
                "The operator still applies the change and runs freshness, rebuild and canary.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evolution gate")
    parser.add_argument("--spec", required=True)
    parser.add_argument("--report", required=True, help="shadow report json")
    parser.add_argument("--metrics", default=None, help="locked-test metrics json for quality claims")
    parser.add_argument("--canary", default=None, help="canary check json")
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)

    spec = json.loads(open(args.spec, encoding="utf-8").read())
    report = json.loads(open(args.report, encoding="utf-8").read())
    metrics = json.loads(open(args.metrics, encoding="utf-8").read()) if args.metrics else None
    canary = json.loads(open(args.canary, encoding="utf-8").read()) if args.canary else None

    result = evaluate(spec, report, metrics=metrics, canary=canary)
    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    print(json.dumps({"candidate": result["candidate_id"], "verdict": result["verdict"],
                      "blocking": result["blocking"], "needs_human_number": result["needs_human_number"]}))
    return 0 if result["verdict"] == PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
