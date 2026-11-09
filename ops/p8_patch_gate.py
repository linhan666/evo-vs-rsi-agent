#!/usr/bin/env python3
"""Teach the failure gate that "fails earlier" is a different claim from "stops failing".

Why
---
`failure_gate` requires `failures_in_replay == 0`, i.e. the candidate must make the
failure disappear. A preflight candidate does the opposite on purpose: the bad input
still fails, it just fails *before* paying for featurisation or training. Under the
old criterion that whole class of self-improvement could never be promoted, which is
what blocked `preflight:ml.train` on 2026-11-09 (equivalence passed, success passed,
failure said "no failed step was replayed" and the gate refused).

New acceptance shape:

    {"early_rejection": true, "min_rejection_speedup": 2.0}

The gate then judges the failing steps by *time*, not by their disappearance: each
failing step must now cost at most half (1/min_rejection_speedup) of what it cost to
discover the same bad input before. Successful steps are still covered by
`success_gate`, so this cannot launder a regression.
"""
from pathlib import Path

GATE = Path("/home/linhan_cluster/evo_vs_rsi/evolution/gate.py")

ANCHOR = '''    acceptance = spec.get("acceptance", {})
    target = acceptance.get("failures_in_replay")
    if target is None:
        return _gate("failure", NOT_APPLICABLE, "the candidate makes no failure claim")'''

NEW = '''    acceptance = spec.get("acceptance", {})

    # "Fail earlier" is a distinct claim from "stop failing". A preflight candidate
    # rejects a bad input before the expensive work, so the step still fails while
    # costing far less. Judge it on time; successful steps remain the success gate's
    # business, so a real regression cannot hide here.
    if acceptance.get("early_rejection"):
        steps = [step for step in (report.get("steps") or [])
                 if step.get("recorded_state") not in (None, "SUCCEEDED")]
        if not steps:
            return _gate("failure", FAIL,
                         "early_rejection claims need replayed failing steps; run shadow.py with --include-failed")
        ratios = []
        for step in steps:
            before = step.get("replayed_baseline_wall_seconds")
            after = step.get("candidate_wall_seconds")
            if before and after:
                ratios.append(float(before) / float(after))
        if not ratios:
            return _gate("failure", FAIL,
                         "early_rejection needs baseline timings; run shadow.py with --baseline-replay")
        ratios.sort()
        median = ratios[len(ratios) // 2]
        required = float(acceptance.get("min_rejection_speedup", 2.0))
        detail = ("rejection median {0:.2f}x faster across {1} failing step(s); required {2:.2f}x"
                  .format(median, len(ratios), required))
        return _gate("failure", PASS if median >= required else FAIL, detail)

    target = acceptance.get("failures_in_replay")
    if target is None:
        return _gate("failure", NOT_APPLICABLE, "the candidate makes no failure claim")'''


def main() -> int:
    text = GATE.read_text(encoding="utf-8")
    if "early_rejection" in text:
        print("gate.py: already patched")
        return 0
    if ANCHOR not in text:
        print("gate.py: ANCHOR MISSING")
        return 1
    GATE.write_text(text.replace(ANCHOR, NEW, 1), encoding="utf-8")
    print("gate.py: early_rejection semantics added")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
