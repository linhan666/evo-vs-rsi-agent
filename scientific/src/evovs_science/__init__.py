"""Scientific Execution Environment for EvoVS-RSI — Phase 0 placeholder.

This package implements ONLY the TypeScript→Python job contract described in
Blueprint §8.1 (``ScientificJobSpec`` / ``ScientificJobResult``).  It performs
no chemistry, no model training and no process execution.

Design constraint: standard library only, so the contract can be validated on
a host without ``pip`` (see ``docs/BLOCKERS.md`` B-004).  Real scientific
dependencies (RDKit, scikit-learn, …) arrive in Phase 1 behind an isolated
environment.
"""

from .schemas import (
    SCHEMA_VERSION,
    STATES,
    TERMINAL_STATES,
    JobResult,
    JobSpec,
    Resources,
    SchemaError,
    Usage,
    is_terminal,
    job_result_to_dict,
    job_spec_from_dict,
)

__all__ = [
    "SCHEMA_VERSION",
    "STATES",
    "TERMINAL_STATES",
    "JobResult",
    "JobSpec",
    "Resources",
    "SchemaError",
    "Usage",
    "is_terminal",
    "job_result_to_dict",
    "job_spec_from_dict",
]

__version__ = "0.0.1"
