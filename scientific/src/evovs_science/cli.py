"""CLI entry point for the scientific environment.

Phase 0 scope: contract validation only.  ``run-job`` is deliberately
unimplemented — it must not pretend to execute science before the sandboxed
runner (Phase 1, P1-02) exists.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Sequence

from . import __version__
from .schemas import SCHEMA_VERSION, JobSpec, SchemaError, job_spec_from_dict

EXIT_OK = 0
EXIT_INVALID = 2
EXIT_NOT_IMPLEMENTED = 3


def _cmd_version(_: argparse.Namespace) -> int:
    print(f"evovs-science {__version__} (job schema {SCHEMA_VERSION})")
    return EXIT_OK


def _cmd_validate_spec(args: argparse.Namespace) -> int:
    try:
        with open(args.path, encoding="utf-8") as handle:
            payload = json.load(handle)
    except OSError as exc:
        print(f"cannot read {args.path}: {exc}", file=sys.stderr)
        return EXIT_INVALID
    except json.JSONDecodeError as exc:
        print(f"{args.path} is not valid JSON: {exc}", file=sys.stderr)
        return EXIT_INVALID

    try:
        spec: JobSpec = job_spec_from_dict(payload)
    except SchemaError as exc:
        print(f"INVALID: {exc}", file=sys.stderr)
        return EXIT_INVALID

    print(f"OK ticket={spec.ticket_id} tool={spec.tool_id} argv={len(spec.argv)} args")
    return EXIT_OK


def _cmd_run_job(_: argparse.Namespace) -> int:
    print(
        "run-job is not implemented in Phase 0.\n"
        "The sandboxed runner, resource guard and artifact registry arrive in "
        "Phase 1 (P1-02..P1-04); see docs/ARCHITECTURE.md.",
        file=sys.stderr,
    )
    return EXIT_NOT_IMPLEMENTED


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="evovs-science", description="EvoVS-RSI scientific environment")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("version", help="print versions").set_defaults(func=_cmd_version)

    validate = sub.add_parser("validate-spec", help="validate a JobSpec JSON file")
    validate.add_argument("path")
    validate.set_defaults(func=_cmd_validate_spec)

    run_job = sub.add_parser("run-job", help="(not implemented in Phase 0)")
    run_job.add_argument("spec")
    run_job.set_defaults(func=_cmd_run_job)

    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
