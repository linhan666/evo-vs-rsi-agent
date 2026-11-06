"""P4-04 (hybrid): mine candidate opportunities from the trace corpus, then let a
fixed LLM phrase the hypothesis.

Division of labour, on purpose:
  - **code decides what is worth proposing** — a rule mines an opportunity from
    numbers in the corpus (a failure class that recurs recently, or a tool that
    owns most of the wall clock), together with the knob and the acceptance
    criteria it would be judged by;
  - **the LLM only writes prose** — one hypothesis sentence and one risk
    sentence. It cannot invent a knob, a metric or an acceptance rule, so two
    runs over the same corpus produce the same proposal modulo wording;
  - **nothing is applied**. The output is a CandidateSpec that must pass
    `spec.validate_spec` and then the normal Intake → shadow → promotion path.

Usage:
  python evolution/propose.py [--traces-dir D] [--out-dir D] [--emit]
                             [--recent 5] [--no-llm]
"""
from __future__ import annotations

import argparse
import glob
import json
import os
import re
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from failure_clusters import error_class, last_meaningful_line  # noqa: E402
from spec import validate_spec  # noqa: E402

SHARE_THRESHOLD = 0.40      # a tool must own this much of the corpus wall clock
MEDIAN_THRESHOLD = 2.0      # ...and be slow in absolute terms
RECENT_WINDOW = 5           # only failures inside the last N traces still count

# Knobs that exist (or are named here for the implementation to follow). A tool
# without an entry still gets a proposal, but as an experiment rather than env.
THROUGHPUT_KNOBS = {
    "screening.rank": ("EVOVS_SCREEN_JOBS", "8"),
    "rdkit.featurize": ("EVOVS_FEAT_JOBS", "16"),
}


def load_traces(traces_dir: str) -> list[dict]:
    traces = []
    for path in sorted(glob.glob(os.path.join(traces_dir, "*.json"))):
        trace = json.loads(open(path, encoding="utf-8").read())
        trace["_name"] = os.path.basename(path)
        traces.append(trace)
    traces.sort(key=lambda item: item.get("exported_at") or "")
    return traces


def mine_failures(traces: list[dict], recent: int) -> list[dict]:
    """A failure class is worth a proposal when it still happens in recent traces."""
    recent_names = {trace["_name"] for trace in traces[-recent:]}
    seen: dict[str, dict] = {}
    for trace in traces:
        for step in trace.get("steps", []):
            if step.get("state") == "SUCCEEDED":
                continue
            key = "{0}::{1}".format(step["tool_id"], error_class(
                step.get("error", ""), step.get("stderr_tail", ""),
                step.get("exit_code"), step.get("stdout_tail", "")))
            entry = seen.setdefault(key, {"tool_id": step["tool_id"], "key": key, "tickets": set(),
                                          "recent": 0, "samples": []})
            entry["tickets"].add(trace["_name"])
            if trace["_name"] in recent_names:
                entry["recent"] += 1
            evidence = (step.get("error") or "").strip() or last_meaningful_line(step.get("stderr_tail", ""))
            if evidence and len(entry["samples"]) < 2:
                entry["samples"].append(evidence[:160])

    opportunities = []
    for entry in seen.values():
        if entry["recent"] < 1 or len(entry["tickets"]) < 2:
            continue
        opportunities.append({
            "kind": "failure-recurrence",
            "tool_id": entry["tool_id"],
            "cluster": entry["key"],
            "evidence": {"tickets": sorted(entry["tickets"]), "recent_hits": entry["recent"],
                         "samples": entry["samples"]},
            "change": {"type": "experiment", "key": "preflight:{0}".format(entry["tool_id"]),
                       "value": "validate the job inputs before launch (required columns, file kind) and fail fast with an actionable message"},
            "acceptance": {"equivalence": 1.0, "failures_in_replay": 0},
            "risk": "pre-flight checks add a small fixed cost to every job and may reject inputs the tool would have tolerated",
        })
    return opportunities


def mine_latency(traces: list[dict]) -> list[dict]:
    """The tool that owns the wall clock is the one worth making faster.

    Guards against two traps seen in practice:
      - one ticket is one observation: a probe run cannot speak for the workload,
        so a tool needs calls in at least two distinct tickets;
      - a corpus spans promotions, so a slow historical number may already be
        fixed. The window is recorded in the spec, and `shadow.py
        --baseline-replay` is what must settle any latency claim.
    """
    total, per_tool = 0.0, {}
    for trace in traces:
        for step in trace.get("steps", []):
            if step.get("state") != "SUCCEEDED":
                continue
            seconds = step.get("wall_seconds") or 0.0
            total += seconds
            row = per_tool.setdefault(step["tool_id"], {"seconds": 0.0, "n": 0, "tickets": {}})
            row["seconds"] += seconds
            row["n"] += 1
            row["tickets"][trace["_name"]] = row["tickets"].get(trace["_name"], 0) + 1
    if total <= 0:
        return []

    window = {"first": traces[0].get("exported_at"), "last": traces[-1].get("exported_at"),
              "traces": len(traces)}
    opportunities = []
    for tool_id, row in sorted(per_tool.items(), key=lambda kv: -kv[1]["seconds"]):
        share = row["seconds"] / total
        median = row["seconds"] / row["n"] if row["n"] else 0.0
        # Two independent tickets, not one: a single ticket is one observation and
        # cannot speak for the workload. The median also keeps sub-second probe
        # jobs out, which is what the tail of the corpus is full of.
        if share < SHARE_THRESHOLD or median < MEDIAN_THRESHOLD or len(row["tickets"]) < 2:
            continue
        knob = THROUGHPUT_KNOBS.get(tool_id)
        change = ({"type": "env", "key": knob[0], "value": knob[1]} if knob
                  else {"type": "experiment", "key": "throughput:{0}".format(tool_id),
                        "value": "chunk the work over inputs and keep output order, so the result is byte-identical"})
        opportunities.append({
            "kind": "latency-share",
            "tool_id": tool_id,
            "evidence": {"share": round(share, 4), "median_seconds": round(median, 2),
                         "calls": row["n"], "substantial_tickets": sorted(row["tickets"]),
                         "corpus_seconds": round(total, 2), "corpus_window": window,
                         "caveat": "wall clock spans the whole corpus, which may predate a promotion; "
                                   "re-measure the baseline with shadow.py --baseline-replay before trusting it"},
            "change": change,
            "acceptance": {"equivalence": 1.0, "max_time_ratio": 1.2, "min_speedup": 1.3},
            "risk": "parallel work multiplies peak memory; the single code path must keep output order byte-identical",
        })
    return opportunities


def slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")


def template_hypothesis(opportunity: dict) -> str:
    if opportunity["kind"] == "latency-share":
        return ("{0} owns {1:.0%} of the corpus wall clock at a {2:.1f}s median, so making it cheaper "
                "should shorten every screening ticket without changing a single artifact.").format(
            opportunity["tool_id"], opportunity["evidence"]["share"], opportunity["evidence"]["median_seconds"])
    return ("{0} keeps failing the same way in recent tickets ({1}), so rejecting that input before launch "
            "should remove the retry loop without touching the success path.").format(
        opportunity["tool_id"], opportunity["cluster"])


_LAST_LLM_ERROR = ""


def llm_wording(opportunity: dict, model: str) -> dict | None:
    """Ask a fixed model for prose only. Any failure falls back to the template."""
    global _LAST_LLM_ERROR
    key = os.environ.get("DEEPSEEK_API_KEY")
    if not key:
        _LAST_LLM_ERROR = "DEEPSEEK_API_KEY is not set"
        return None
    prompt = (
        "You are writing two sentences for a Harness change proposal. The change, its evidence and its "
        "acceptance criteria are fixed and must not be altered. Reply with JSON only: "
        '{"hypothesis": "...", "risk": "..."} — one sentence each, no numbers you were not given.\n\n'
        + json.dumps({k: opportunity[k] for k in ("kind", "tool_id", "change", "acceptance", "evidence")},
                     ensure_ascii=False)
    )
    # Generous token budget: these models emit reasoning_content before the answer,
    # and a small budget truncates the JSON (observed with 300).
    body = json.dumps({"model": model, "temperature": 0, "max_tokens": 1500,
                       "messages": [{"role": "user", "content": prompt}]}).encode("utf-8")
    request = urllib.request.Request("https://api.deepseek.com/chat/completions", data=body,
                                     headers={"Content-Type": "application/json",
                                              "Authorization": "Bearer " + key})
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            payload = json.loads(response.read().decode("utf-8"))
        text = (payload["choices"][0]["message"].get("content") or "").strip()
        text = re.sub(r"^```(?:json)?|```$", "", text, flags=re.MULTILINE).strip()
        parsed = json.loads(text)
        if isinstance(parsed.get("hypothesis"), str) and isinstance(parsed.get("risk"), str):
            return {"hypothesis": parsed["hypothesis"][:400], "risk": parsed["risk"][:400]}
        _LAST_LLM_ERROR = "the reply lacked hypothesis or risk"
    except Exception as error:  # network, quota, truncated JSON: the template is always available
        _LAST_LLM_ERROR = "{0}: {1}".format(type(error).__name__, str(error)[:160])
    return None


def to_spec(opportunity: dict, wording: dict | None) -> dict:
    candidate_id = "auto-{0}-{1}".format(slug(opportunity["kind"]), slug(opportunity["tool_id"]))
    return {
        "candidate_id": candidate_id,
        "version": "0.1.0-auto",
        "status": "proposal",
        "changes": [opportunity["change"]],
        "hypothesis": (wording or {}).get("hypothesis") or template_hypothesis(opportunity),
        "acceptance": opportunity["acceptance"],
        "risk": (wording or {}).get("risk") or opportunity["risk"],
        "basis": {"generated_by": "evolution/propose.py", "kind": opportunity["kind"],
                  "tool_id": opportunity["tool_id"], "evidence": opportunity["evidence"],
                  **({"cluster": opportunity["cluster"]} if "cluster" in opportunity else {})},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evolution propose")
    parser.add_argument("--traces-dir", default=None)
    parser.add_argument("--out-dir", default=None)
    parser.add_argument("--recent", type=int, default=RECENT_WINDOW)
    parser.add_argument("--no-llm", action="store_true")
    parser.add_argument("--verbose", action="store_true", help="report why the LLM wording fell back")
    parser.add_argument("--emit", action="store_true", help="write the specs; without it, print only")
    args = parser.parse_args(argv)

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    traces_dir = args.traces_dir or os.path.join(root, "evolution", "traces")
    out_dir = args.out_dir or os.path.join(root, "evolution", "candidates")

    traces = load_traces(traces_dir)
    opportunities = mine_failures(traces, args.recent) + mine_latency(traces)
    model = os.environ.get("EVOVS_MODEL") or "deepseek-flash"

    written, skipped = [], []
    for opportunity in opportunities:
        spec = to_spec(opportunity, None if args.no_llm else llm_wording(opportunity, model))
        problems = validate_spec(spec)
        if problems:
            print(json.dumps({"rejected": spec["candidate_id"], "problems": problems}), file=sys.stderr)
            continue
        path = os.path.join(out_dir, spec["candidate_id"] + ".json")
        if os.path.exists(path):
            skipped.append(spec["candidate_id"])  # one proposal per opportunity; re-runs are idempotent
            continue
        if args.emit:
            os.makedirs(out_dir, exist_ok=True)
            with open(path, "w", encoding="utf-8") as handle:
                json.dump(spec, handle, ensure_ascii=False, indent=2)
                handle.write("\n")
        written.append(spec["candidate_id"])

    if args.verbose and _LAST_LLM_ERROR:
        print(json.dumps({"llm_fallback": _LAST_LLM_ERROR}), file=sys.stderr)
    print(json.dumps({"traces": len(traces), "opportunities": len(opportunities),
                      "written": written, "already_present": skipped, "emitted": bool(args.emit)},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
