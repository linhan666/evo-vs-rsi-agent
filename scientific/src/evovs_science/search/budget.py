"""Per-ticket search budget, enforced by the tool that spends it.

The experiment compares arms on how well they spend a *bounded* budget, so the
bound must not be advisory. Every `ml.train --config-id` draws one configuration
from the frozen space and records it here; a draw beyond the limit is refused by
the tool, not by convention.

The ledger lives in the ticket workspace (`.search_budget.json`) so it travels
with the run and the collector can read the stop point directly:

    {"space_version": ..., "limit": 100, "used": 37, "ids": [...]}

`used < limit` means the arm chose to stop early — the behaviour the memory and
self-evolving arms are supposed to exhibit.
"""
from __future__ import annotations

import json
import os
from pathlib import Path

from .space import SPACE_VERSION, get

LEDGER = ".search_budget.json"


def _path(workspace: str | os.PathLike[str]) -> Path:
    return Path(workspace) / LEDGER


def read(workspace: str | os.PathLike[str]) -> dict:
    path = _path(workspace)
    if not path.exists():
        return {"space_version": SPACE_VERSION, "limit": None, "used": 0, "ids": []}
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return {"space_version": SPACE_VERSION, "limit": None, "used": 0, "ids": []}
    payload.setdefault("ids", [])
    payload.setdefault("used", len(payload["ids"]))
    return payload


def _write(workspace: str | os.PathLike[str], payload: dict) -> None:
    path = _path(workspace)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def consume(workspace: str | os.PathLike[str], config_id: str, limit: int | None) -> dict:
    """Draw one configuration. Raises SystemExit with a clear code when refused.

    Re-drawing a configuration already spent is allowed and does not consume
    again: retraining the same point is a reproducibility check, not new search.
    """
    get(config_id)  # validates the id against the frozen space
    state = read(workspace)
    effective_limit = limit if limit is not None else state.get("limit")
    if effective_limit is None:
        effective_limit = 100

    if config_id in state["ids"]:
        state["limit"] = effective_limit
        _write(workspace, state)
        return state

    if state["used"] >= effective_limit:
        raise SystemExit(
            f"SEARCH_BUDGET_EXHAUSTED: {state['used']}/{effective_limit} configurations already "
            f"spent on this ticket; '{config_id}' would be draw {state['used'] + 1}. "
            f"The budget is the experimental variable — stopping here is the expected behaviour.")

    state["ids"].append(config_id)
    state["used"] = len(state["ids"])
    state["limit"] = effective_limit
    state["space_version"] = SPACE_VERSION
    _write(workspace, state)
    return state


def stop_reason(state: dict) -> str:
    limit = state.get("limit") or 100
    if state.get("used", 0) >= limit:
        return "budget_exhausted"
    return "stopped_early"
