"""CandidateSpec validation (P4-03 Intake hardening).

A candidate enters the loop ONLY through a spec that passes this validator;
shadow.py refuses to run on an invalid spec, so a malformed proposal can never
reach the sandbox.
"""

from __future__ import annotations

CHANGE_TYPES = ("env", "experiment")
KINDS = ("dataset", "model", "screening", "transfer", "harness")


def validate_spec(spec) -> list[str]:
    """Return a list of problems; empty list means the spec is well-formed."""
    errors: list[str] = []
    if not isinstance(spec, dict):
        return ["spec must be a JSON object"]
    for key in ("candidate_id", "version", "hypothesis", "risk"):
        value = spec.get(key)
        if not isinstance(value, str) or not value.strip():
            errors.append(f"{key} must be a non-empty string")
    changes = spec.get("changes")
    if not isinstance(changes, list):
        errors.append("changes must be a list")
    else:
        for index, change in enumerate(changes):
            if not isinstance(change, dict):
                errors.append(f"changes[{index}] must be an object")
                continue
            if change.get("type") not in CHANGE_TYPES:
                errors.append(f"changes[{index}].type must be one of {CHANGE_TYPES}")
            if not isinstance(change.get("key"), str) or not change.get("key"):
                errors.append(f"changes[{index}].key must be a non-empty string")
            if "value" not in change:
                errors.append(f"changes[{index}].value is required")
    acceptance = spec.get("acceptance")
    if not isinstance(acceptance, dict) or "equivalence" not in acceptance:
        errors.append("acceptance must be an object including 'equivalence'")
    if spec.get("status") not in (None, "proposal", "shadowed", "promoted", "rejected"):
        errors.append("status must be proposal|shadowed|promoted|rejected when present")
    return errors
