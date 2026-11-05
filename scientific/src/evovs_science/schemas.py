"""Job contract for the Scientific Execution Environment (Blueprint §8.1).

Scope of this module
--------------------
* Parse and validate ``ScientificJobSpec`` payloads coming from the TypeScript
  harness over a process boundary.
* Serialise ``ScientificJobResult`` payloads back to the harness.
* Enforce the structural invariants that the blueprint calls out explicitly:
  ``argv`` is a list of strings (never a shell string), resources are positive
  (GPU count may be zero), and the job state is one of the six declared states.

Out of scope (Phase 1+): sandboxed execution, artifact registry, resource
enforcement, idempotency lookup, cancellation.  Those must not be faked here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping

SCHEMA_VERSION = "1"

STATES = (
    "PENDING",
    "RUNNING",
    "SUCCEEDED",
    "FAILED",
    "CANCELLED",
    "TIMED_OUT",
)
TERMINAL_STATES = frozenset({"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"})

_REQUIRED_STRINGS = (
    "ticket_id",
    "experiment_id",
    "tool_id",
    "workspace_id",
    "output_prefix",
    "idempotency_key",
)


class SchemaError(ValueError):
    """Raised when a job payload violates the contract."""


@dataclass(frozen=True, slots=True)
class Resources:
    max_cpu_cores: int
    max_gpu_count: int
    max_wall_seconds: int
    max_memory_gb: int


@dataclass(frozen=True)
class JobSpec:
    schema_version: str
    ticket_id: str
    experiment_id: str
    tool_id: str
    workspace_id: str
    argv: tuple[str, ...]
    input_artifacts: tuple[str, ...]
    output_prefix: str
    resources: Resources
    idempotency_key: str
    environment_ref: str | None = None


@dataclass(frozen=True)
class Usage:
    cpu_seconds: float | None = None
    gpu_seconds: float | None = None
    max_rss_mb: float | None = None


@dataclass(frozen=True)
class JobResult:
    job_id: str
    state: str
    started_at: str | None = None
    ended_at: str | None = None
    exit_code: int | None = None
    stdout_artifact: str | None = None
    stderr_artifact: str | None = None
    output_artifacts: tuple[str, ...] = ()
    usage: Usage = field(default_factory=Usage)


def is_terminal(state: str) -> bool:
    if state not in STATES:
        raise SchemaError(f"unknown job state: {state!r}")
    return state in TERMINAL_STATES


def _require_mapping(value: Any, what: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise SchemaError(f"{what} must be a mapping, got {type(value).__name__}")
    return value


def _require_text(payload: Mapping[str, Any], key: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value.strip():
        raise SchemaError(f"{key} must be a non-empty string")
    return value


def _require_str_list(value: Any, what: str, *, allow_empty: bool) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)):
        raise SchemaError(f"{what} must be a list of strings, got {type(value).__name__}")
    items = tuple(value)
    if not items and not allow_empty:
        raise SchemaError(f"{what} must not be empty")
    for index, item in enumerate(items):
        if not isinstance(item, str):
            raise SchemaError(f"{what}[{index}] must be a string, got {type(item).__name__}")
        if "\x00" in item:
            raise SchemaError(f"{what}[{index}] contains a NUL byte")
    return items


def _require_positive_int(payload: Mapping[str, Any], key: str, *, allow_zero: bool = False) -> int:
    value = payload.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise SchemaError(f"resources.{key} must be an integer")
    minimum = 0 if allow_zero else 1
    if value < minimum:
        raise SchemaError(f"resources.{key} must be >= {minimum}, got {value}")
    return value


def job_spec_from_dict(payload: Mapping[str, Any]) -> JobSpec:
    """Validate a harness-provided job spec. Raises :class:`SchemaError`."""
    payload = _require_mapping(payload, "job spec")

    version = payload.get("schema_version")
    if version != SCHEMA_VERSION:
        raise SchemaError(f"schema_version must be {SCHEMA_VERSION!r}, got {version!r}")

    text = {key: _require_text(payload, key) for key in _REQUIRED_STRINGS}

    argv = _require_str_list(payload.get("argv"), "argv", allow_empty=False)
    inputs = _require_str_list(payload.get("input_artifacts", ()), "input_artifacts", allow_empty=True)

    resources_raw = _require_mapping(payload.get("resources"), "resources")
    resources = Resources(
        max_cpu_cores=_require_positive_int(resources_raw, "max_cpu_cores"),
        max_gpu_count=_require_positive_int(resources_raw, "max_gpu_count", allow_zero=True),
        max_wall_seconds=_require_positive_int(resources_raw, "max_wall_seconds"),
        max_memory_gb=_require_positive_int(resources_raw, "max_memory_gb"),
    )

    environment_ref = payload.get("environment_ref")
    if environment_ref is not None and not isinstance(environment_ref, str):
        raise SchemaError("environment_ref must be a string when present")

    return JobSpec(
        schema_version=SCHEMA_VERSION,
        argv=argv,
        input_artifacts=inputs,
        resources=resources,
        environment_ref=environment_ref,
        **text,
    )


def job_result_to_dict(result: JobResult) -> dict[str, Any]:
    """Serialise a result for the TypeScript side; validates the state."""
    if result.state not in STATES:
        raise SchemaError(f"unknown job state: {result.state!r}")
    payload: dict[str, Any] = {
        "job_id": result.job_id,
        "state": result.state,
        "output_artifacts": list(result.output_artifacts),
        "usage": {
            "cpu_seconds": result.usage.cpu_seconds,
            "gpu_seconds": result.usage.gpu_seconds,
            "max_rss_mb": result.usage.max_rss_mb,
        },
    }
    for key in ("started_at", "ended_at", "exit_code", "stdout_artifact", "stderr_artifact"):
        value = getattr(result, key)
        if value is not None:
            payload[key] = value
    return payload
