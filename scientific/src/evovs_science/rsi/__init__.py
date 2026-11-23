"""RSIAgent-inspired exploration contracts for EvoVS (control plane only).

This module does not replace DSH, the protected evaluator, or evolution/gate.py.
"""
from .protocol import (
    ProtocolError,
    attest_frozen,
    begin_deep_target,
    begin_wave,
    canonical_hash,
    commit_wave,
    create_run,
    freeze_for_test,
    register_harness_promotion,
    submit_focused_practice,
    submit_target_attempt,
    submit_wave_result,
)

__all__ = [
    "ProtocolError", "attest_frozen", "begin_deep_target", "begin_wave",
    "canonical_hash", "commit_wave", "create_run", "freeze_for_test",
    "register_harness_promotion", "submit_focused_practice",
    "submit_target_attempt", "submit_wave_result",
]
