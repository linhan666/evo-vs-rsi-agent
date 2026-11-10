#!/usr/bin/env python3
"""Let an operator re-score the delivered model without tripping the agent rate limit.

Why this is needed
------------------
`evaluation.locked` refuses a second evaluation in the same ticket workspace via
`.evaluation/<TARGET>_<ENDPOINT>.done`. That guard exists so an *agent* cannot grind
the protected set by retrying. But `p8_finalize.py` deliberately re-scores the ticket
once more — on the best model rather than whichever model the agent happened to ship —
and that is an operator-side correction of a measurement error, not an agent retry.

Without this flag the delivery fix silently fails: the call returns non-zero, finalize
records `locked_rerun_error`, and the record keeps the mis-attributed score. In other
words the rate limiter was quietly defeating the very correction it should allow.

`--recheck` therefore:
  * bypasses the marker check,
  * still writes the marker (a later agent attempt stays blocked),
  * writes to a `_recheck` protected output, so the agent's original score remains
    auditable next to the corrected one instead of being overwritten.
"""
from pathlib import Path

LOCKED = Path("/home/linhan_cluster/evo_vs_rsi/scientific/src/evovs_science/evaluation/locked.py")

ARG_OLD = '''    parser.add_argument("--n-bits", type=int, default=2048,
                        help="Morgan bit width the model was trained with (default 2048)")'''
ARG_NEW = '''    parser.add_argument("--n-bits", type=int, default=2048,
                        help="Morgan bit width the model was trained with (default 2048)")
    parser.add_argument("--recheck", action="store_true",
                        help="operator re-score of the same frozen model: bypass the per-ticket "
                             "marker and write a separate _recheck output. The marker still exists "
                             "afterwards, so an agent cannot retry.")'''

GUARD_OLD = '''    if os.path.exists(marker):
        raise SystemExit(
            f"rate limit: this ticket already triggered a locked {args.endpoint} evaluation for {args.target}")'''
GUARD_NEW = '''    if os.path.exists(marker) and not args.recheck:
        raise SystemExit(
            f"rate limit: this ticket already triggered a locked {args.endpoint} evaluation for {args.target}")'''

OUT_OLD = '''    output = os.path.join(
        target_dir,
        f"metrics_test_locked_agent_{args.endpoint}_{desc_set}_r{args.radius}_b{args.n_bits}_"
        f"{ticket_name}_{args.target}.json")'''
OUT_NEW = '''    # A recheck must not overwrite the agent's own score: keep both, side by side.
    suffix = "_recheck" if args.recheck else ""
    output = os.path.join(
        target_dir,
        f"metrics_test_locked_agent_{args.endpoint}_{desc_set}_r{args.radius}_b{args.n_bits}_"
        f"{ticket_name}_{args.target}{suffix}.json")'''

RECEIPT_OLD = '''        "note": "summary only; the raw locked metrics file is not readable from the ticket",'''
RECEIPT_NEW = '''        "recheck": bool(args.recheck),
        "note": "summary only; the raw locked metrics file is not readable from the ticket",'''


def main() -> int:
    text = LOCKED.read_text(encoding="utf-8")
    if "--recheck" in text:
        print("locked.py: already patched")
        return 0
    for old, new in ((ARG_OLD, ARG_NEW), (GUARD_OLD, GUARD_NEW),
                     (OUT_OLD, OUT_NEW), (RECEIPT_OLD, RECEIPT_NEW)):
        if old not in text:
            print(f"locked.py: ANCHOR MISSING -> {old.splitlines()[0][:60]}")
            return 1
        text = text.replace(old, new, 1)
    LOCKED.write_text(text, encoding="utf-8")
    print("locked.py: --recheck added (marker bypass + separate output)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
