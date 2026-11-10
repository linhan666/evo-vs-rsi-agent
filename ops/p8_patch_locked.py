#!/usr/bin/env python3
"""Let the locked evaluator reconstruct any feature representation.

`evaluation.locked` hard-coded `--radius 2 --n-bits 2048`, so it could only rebuild
the canonical v1/v2 matrices. Any model trained on a different Morgan setting
(r=1, r=3, 4096 bits) was re-featurised with the wrong width at lock time: predict
then failed, or worse, succeeded against a matrix that was not what the model saw.
That is why three of the five representations in the frozen space could never get a
locked score, and it silently poisoned earlier rounds too.

Adds `--radius` / `--n-bits` (defaults 2 / 2048, so old callers behave exactly as
before) and puts both into the receipt filename: two representations of the same
target must not overwrite each other's locked metrics.
"""
from pathlib import Path

LOCKED = Path("/home/linhan_cluster/evo_vs_rsi/scientific/src/evovs_science/evaluation/locked.py")

ARGS_OLD = '''    parser.add_argument("--desc-set", choices=("v1", "v2"), default=None,
                        help="must match the descriptor set the model was trained on")
    args = parser.parse_args(argv)'''
ARGS_NEW = '''    parser.add_argument("--desc-set", choices=("v1", "v2"), default=None,
                        help="must match the descriptor set the model was trained on")
    parser.add_argument("--radius", type=int, default=2,
                        help="Morgan radius the model was trained with (default 2)")
    parser.add_argument("--n-bits", type=int, default=2048,
                        help="Morgan bit width the model was trained with (default 2048)")
    args = parser.parse_args(argv)'''

PATH_OLD = '''    output = os.path.join(
        target_dir, f"metrics_test_locked_agent_{args.endpoint}_{desc_set}_{ticket_name}_{args.target}.json")'''
PATH_NEW = '''    # radius and bit width are part of the identity of a feature matrix: two
    # representations of the same target must not share one locked metrics file.
    output = os.path.join(
        target_dir,
        f"metrics_test_locked_agent_{args.endpoint}_{desc_set}_r{args.radius}_b{args.n_bits}_"
        f"{ticket_name}_{args.target}.json")'''

CALL_OLD = '''        "--desc-set", desc_set,
        "--radius", "2",
        "--n-bits", "2048",
    ])'''
CALL_NEW = '''        "--desc-set", desc_set,
        "--radius", str(args.radius),
        "--n-bits", str(args.n_bits),
    ])'''

RECEIPT_OLD = '''        "desc_set": desc_set,'''
RECEIPT_NEW = '''        "desc_set": desc_set,
        "radius": args.radius,
        "n_bits": args.n_bits,'''


def main() -> int:
    text = LOCKED.read_text(encoding="utf-8")
    if 'parser.add_argument("--n-bits"' in text:
        print("locked.py: already patched")
        return 0
    for old, new in ((ARGS_OLD, ARGS_NEW), (PATH_OLD, PATH_NEW),
                     (CALL_OLD, CALL_NEW), (RECEIPT_OLD, RECEIPT_NEW)):
        if old not in text:
            print(f"locked.py: ANCHOR MISSING -> {old.splitlines()[0][:60]}")
            return 1
        text = text.replace(old, new, 1)
    LOCKED.write_text(text, encoding="utf-8")
    print("locked.py: radius/n_bits threaded through and into the receipt name")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
