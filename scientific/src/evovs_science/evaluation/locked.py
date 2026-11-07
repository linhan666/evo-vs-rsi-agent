"""Locked-evaluation trigger (docs/EVALUATOR_TRIGGER_DESIGN.md, option 2 adapted).

Option 2 was specced as a worker-bin shim, but the worker has no shell anymore,
so the shim became a registry tool. Properties that matter:
  - the Agent chooses only the target, the endpoint and the model file;
  - the test set and the output location are hard-coded per (target, endpoint);
  - the raw metrics file is written 600 into the protected tree, invisible to
    the ticket;
  - one evaluation per (target, endpoint) per ticket (rate-limit marker);
  - the Agent receives a receipt in its own workspace with summary metrics only.

Ki and IC50 are separate channels: each has its own protected test set and its
own models. Scoring an IC50 model against Ki labels is a cross-endpoint
mismatch, not a result (F-1, 2026-11-06); `--endpoint` makes the channel
explicit and the output name carries it, so two channels can never overwrite
each other's metrics (F-2).
"""

from __future__ import annotations

import argparse
import json
import os

PROTECTED = "/home/linhan_cluster/evo_vs_rsi/protected"

# endpoint -> target -> (protected subdirectory, locked test CSV)
CHANNELS = {
    "Ki": {
        "MOR": ("chembl37_ki", "final_test_Ki.csv"),
        "KOR": ("chembl37_ki_oprk1", "final_test_Ki.csv"),
        "DRD2": ("chembl37_ki_drd2", "final_test_Ki.csv"),
        "D2": ("chembl37_ki_d2", "final_test_Ki.csv"),
        "5HT": ("chembl37_ki_5ht", "final_test_Ki.csv"),
        "ADR": ("chembl37_ki_adr", "final_test_Ki.csv"),
        "CBR": ("chembl37_ki_cbr", "final_test_Ki.csv"),
        "CA2": ("chembl37_ki_ca2", "final_test_Ki.csv"),
        "PT": ("chembl37_ki_pt", "final_test_Ki.csv"),
    },
    "IC50": {
        "MOR": ("chembl37_ic50_oprm1", "final_test_IC50.csv"),
        "KOR": ("chembl37_ic50_oprk1", "final_test_IC50.csv"),
        "DRD2": ("chembl37_ic50_drd2", "final_test_IC50.csv"),
    },
}

# Pre-registered panel order (docs/TRANSFER_DESIGN.md); kept for --target choices.
TARGETS = tuple(CHANNELS["Ki"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="evovs-science locked")
    parser.add_argument("--target", required=True, choices=list(TARGETS))
    parser.add_argument("--endpoint", choices=list(CHANNELS), default="Ki",
                        help="locked channel to score against; must match the labels the model was trained on")
    parser.add_argument("--model", required=True, help="fitted pipeline FILE from modeling.train")
    parser.add_argument("--workspace", required=True, help="ticket directory (rate-limit marker lives here)")
    parser.add_argument("--receipt", required=True, help="summary receipt written into the workspace")
    parser.add_argument("--desc-set", choices=("v1", "v2"), default=None,
                        help="must match the descriptor set the model was trained on")
    args = parser.parse_args(argv)

    marker_dir = os.path.join(args.workspace, ".evaluation")
    marker = os.path.join(marker_dir, f"{args.target}_{args.endpoint}.done")
    if os.path.exists(marker):
        raise SystemExit(
            f"rate limit: this ticket already triggered a locked {args.endpoint} evaluation for {args.target}")
    if not os.path.isfile(args.model):
        raise SystemExit("--model must be the fitted pipeline FILE from modeling.train (e.g. runs/models/<name>/model.joblib)")

    subdir, test_name = CHANNELS[args.endpoint][args.target]
    target_dir = os.path.join(PROTECTED, subdir)
    test_csv = os.path.join(target_dir, test_name)
    if not os.path.isfile(test_csv):
        raise SystemExit(f"locked test set missing for {args.target}/{args.endpoint}: {test_csv}")

    desc_set = args.desc_set or "v1"
    ticket_name = os.path.basename(os.path.normpath(args.workspace))
    # endpoint + desc_set + ticket in the name: no two channels or generations can collide.
    output = os.path.join(
        target_dir, f"metrics_test_locked_agent_{args.endpoint}_{desc_set}_{ticket_name}_{args.target}.json")

    from . import evaluate as evaluator

    code = evaluator.main([
        "--test-csv", test_csv,
        "--model", args.model,
        "--output", output,
        "--label-source", f"locked_agent_{args.endpoint}_{desc_set}",
        "--desc-set", desc_set,
        "--radius", "2",
        "--n-bits", "2048",
    ])
    if code != 0:
        raise SystemExit(f"locked evaluation failed (exit {code}); see the evaluator's own report")

    metrics = json.load(open(output, encoding="utf-8"))["metrics"]
    receipt = {
        "target": args.target,
        "endpoint": args.endpoint,
        "desc_set": desc_set,
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
    print(json.dumps({"target": args.target, "endpoint": args.endpoint, "metrics": metrics}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
