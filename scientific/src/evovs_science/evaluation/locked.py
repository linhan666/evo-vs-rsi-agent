"""Locked-evaluation trigger (docs/EVALUATOR_TRIGGER_DESIGN.md, option 2 adapted).

Option 2 was specced as a worker-bin shim, but the worker has no shell anymore,
so the shim became a registry tool. Properties that matter:
  - the Agent chooses only the target and the model file;
  - the test set and the output location are hard-coded per target;
  - the raw metrics file is written 600 into the protected tree, invisible to
    the ticket;
  - one evaluation per target per ticket (rate limit marker);
  - the Agent receives a receipt in its own workspace with summary metrics only.
"""

from __future__ import annotations

import argparse
import json
import os

PROTECTED = "/home/linhan_cluster/evo_vs_rsi/protected"
TARGET_DIRS = {"MOR": "chembl37_ki", "KOR": "chembl37_ki_oprk1", "DRD2": "chembl37_ki_drd2"}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evovs-science locked")
    parser.add_argument("--target", required=True, choices=list(TARGET_DIRS))
    parser.add_argument("--model", required=True, help="fitted pipeline FILE from modeling.train")
    parser.add_argument("--workspace", required=True, help="ticket directory (rate-limit marker lives here)")
    parser.add_argument("--receipt", required=True, help="summary receipt written into the workspace")
    parser.add_argument("--desc-set", choices=("v1", "v2"), default=None,
                        help="must match the descriptor set the model was trained on")
    args = parser.parse_args(argv)

    marker_dir = os.path.join(args.workspace, ".evaluation")
    marker = os.path.join(marker_dir, f"{args.target}.done")
    if os.path.exists(marker):
        raise SystemExit(f"rate limit: this ticket already triggered a locked evaluation for {args.target}")
    if not os.path.isfile(args.model):
        raise SystemExit("--model must be the fitted pipeline FILE from modeling.train (e.g. runs/models/<name>/model.joblib)")

    target_dir = os.path.join(PROTECTED, TARGET_DIRS[args.target])
    test_csv = os.path.join(target_dir, "final_test_Ki.csv")
    ticket_name = os.path.basename(os.path.normpath(args.workspace))
    output = os.path.join(target_dir, f"metrics_test_locked_agent_{ticket_name}_{args.target}.json")

    from . import evaluate as evaluator

    code = evaluator.main([
        "--test-csv", test_csv,
        "--model", args.model,
        "--output", output,
        "--label-source", "locked_agent",
        "--desc-set", args.desc_set or "v1",
        "--radius", "2",
        "--n-bits", "2048",
    ])
    if code != 0:
        raise SystemExit(f"locked evaluation failed (exit {code}); see the evaluator's own report")

    metrics = json.load(open(output, encoding="utf-8"))["metrics"]
    receipt = {
        "target": args.target,
        "model": os.path.basename(args.model),
        "protected_output": output,
        "metrics": metrics,
        "note": "summary only; the raw locked metrics file is not readable from the ticket",
    }
    os.makedirs(os.path.dirname(os.path.abspath(args.receipt)), exist_ok=True)
    with open(args.receipt, "w", encoding="utf-8") as handle:
        json.dump(receipt, handle, ensure_ascii=False, indent=2)
        handle.write("\n")

    os.makedirs(marker_dir, exist_ok=True)
    with open(marker, "w", encoding="utf-8") as handle:
        handle.write(json.dumps({"receipt": os.path.basename(args.receipt),
                                 "protected_output": output}, indent=2) + "\n")
    os.chmod(marker, 0o600)
    print(json.dumps({"target": args.target, "metrics": metrics}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
