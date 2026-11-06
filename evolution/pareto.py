"""P5-04 Pareto profiles: ranked candidate sets, not one winner.

A single score invites a single answer, and the blueprint asks for the opposite:
keep the non-dominated set and let the profile decide which trade-off to read.
Three profiles, fixed weights (no learned policy):

    lite      cost matters most        quality 0.2 / cost 0.8
    balanced  the default reading      quality 0.5 / cost 0.5
    heavy     quality matters most     quality 0.8 / cost 0.2

Inputs are measurements, not opinions: `quality` is a science delta the operator
supplied (for example the locked-test AUROC change), `cost` is the measured
speedup. A candidate blocked by the promotion gate never enters a front — a fast
wrong answer is not a trade-off.
"""

from __future__ import annotations

import argparse
import json
import os

PROFILES = {
    "lite": {"quality": 0.2, "cost": 0.8},
    "balanced": {"quality": 0.5, "cost": 0.5},
    "heavy": {"quality": 0.8, "cost": 0.2},
}


def _normalise(values: list[float]) -> list[float]:
    """Min-max to 0..1; a flat set maps to all-ones so nothing is punished for being alone."""
    if not values:
        return []
    low, high = min(values), max(values)
    if high - low < 1e-12:
        return [1.0 for _ in values]
    return [(value - low) / (high - low) for value in values]


def rank(entries: list[dict], profile: str) -> list[dict]:
    weights = PROFILES[profile]
    eligible = [entry for entry in entries if entry.get("gates_ok", True)]
    quality = _normalise([float(entry.get("quality", 0.0)) for entry in eligible])
    cost = _normalise([float(entry.get("cost", 0.0)) for entry in eligible])
    scored = []
    for entry, q, c in zip(eligible, quality, cost):
        scored.append({**entry, "quality_norm": round(q, 4), "cost_norm": round(c, 4),
                       "score": round(weights["quality"] * q + weights["cost"] * c, 4)})
    return sorted(scored, key=lambda item: -item["score"])


def frontier(entries: list[dict]) -> list[dict]:
    """Non-dominated on (quality, cost): nobody beats it on both."""
    eligible = [entry for entry in entries if entry.get("gates_ok", True)]
    front = []
    for candidate in eligible:
        dominated = any(
            (other.get("quality", 0.0) >= candidate.get("quality", 0.0)
             and other.get("cost", 0.0) >= candidate.get("cost", 0.0)
             and (other.get("quality", 0.0) > candidate.get("quality", 0.0)
                  or other.get("cost", 0.0) > candidate.get("cost", 0.0)))
            for other in eligible if other is not candidate)
        if not dominated:
            front.append(candidate)
    return sorted(front, key=lambda item: (-item.get("quality", 0.0), -item.get("cost", 0.0)))


def evaluate(entries: list[dict]) -> dict:
    blocked = [entry.get("candidate_id") for entry in entries if not entry.get("gates_ok", True)]
    return {
        "schema_version": "1",
        "profiles": {name: [{"candidate_id": item["candidate_id"], "score": item["score"]}
                            for item in rank(entries, name)] for name in PROFILES},
        "frontier": [entry.get("candidate_id") for entry in frontier(entries)],
        "blocked_by_gate": blocked,
        "note": "Weights are fixed on purpose: a learned router would be the Meta-Policy the blueprint forbids. "
                "A frontier of one means the corpus currently offers no trade-off to choose from.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evolution pareto")
    parser.add_argument("--input", required=True, help='[{"candidate_id","quality","cost","gates_ok"}]')
    parser.add_argument("--output", default=None)
    args = parser.parse_args(argv)

    entries = json.loads(open(args.input, encoding="utf-8").read())
    result = evaluate(entries)
    if args.output:
        os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
        with open(args.output, "w", encoding="utf-8") as handle:
            json.dump(result, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
    print(json.dumps({"frontier": result["frontier"],
                      "balanced": result["profiles"]["balanced"][:3]}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
