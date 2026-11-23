"""RSIAgent-style exploration protocol for EvoVS.

Control-plane only: no LLM calls, scientific scoring, or access to locked labels.
The host must isolate Actor and Verifier execution and authenticate receipts.
This state machine refuses to learn from unresolved/infrastructure outcomes and
refuses to enter test-time execution until a verified target retry succeeds.
Inspired by RSIAgent (Apache-2.0); this is an original implementation.
"""

from __future__ import annotations

import copy
import hashlib
import json
import re
from typing import Any, Mapping

SCHEMA = "evovs-rsiagent-protocol-v0"
_VERDICTS = {"PASS", "FAIL", "UNRESOLVED", "INFRA_ERROR"}
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class ProtocolError(ValueError):
    """A phase, evidence, memory, or isolation boundary was violated."""


def canonical_hash(value: Any) -> str:
    """Content hash; excludes whitespace/order and disallows NaN/Inf."""
    rendered = json.dumps(value, sort_keys=True, separators=(",", ":"),
                          ensure_ascii=False, allow_nan=False)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _sha(value: Any, label: str) -> str:
    if not isinstance(value, str) or not _SHA256.fullmatch(value):
        raise ProtocolError(f"{label} must be a lowercase SHA-256")
    return value


def _word(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ProtocolError(f"{label} must be nonempty text")
    return value.strip()


def _copy(state: dict) -> dict:
    if state.get("schema") != SCHEMA:
        raise ProtocolError("incompatible protocol state")
    if canonical_hash(state["memory"]) != state.get("memory_sha256"):
        raise ProtocolError("memory integrity mismatch")
    if state["phase"] == "TEST" and state.get("frozen_sha256") != state["memory_sha256"]:
        raise ProtocolError("test-time memory was modified")
    return copy.deepcopy(state)


def create_run(run_id: str, *, arm: str, search_space_sha256: str,
               data_manifest_sha256: str, harness_sha256: str) -> dict:
    """Create a protocol lineage using the existing frozen scientific setup.

    W is excluded: it uses the separate non-agent AutoML pipeline.
    A has no memory; M/R may consolidate verified memories, while only R may
    submit separate Harness proposals (never automatic promotion).
    """
    if arm not in {"A", "M", "R"}:
        raise ProtocolError("arm must be A, M, or R; W has no actor")
    state = {
        "schema": SCHEMA,
        "run_id": _word(run_id, "run_id"),
        "arm": arm,
        "phase": "BRS",
        "search_space_sha256": _sha(search_space_sha256, "search_space_sha256"),
        "data_manifest_sha256": _sha(data_manifest_sha256, "data_manifest_sha256"),
        "harness_sha256": _sha(harness_sha256, "harness_sha256"),
        "memory": [],
        "memory_sha256": canonical_hash([]),
        "wave": None,
        "wave_history": [],
        "target": None,
        "frozen_sha256": None,
        "protocol_history": [],
    }
    return state


def _lesson(value: Any) -> dict:
    if not isinstance(value, dict):
        raise ProtocolError("lesson must be an object")
    # An Actor owns interpretation; the host owns the verdict and provenance.
    return {
        "claim": _word(value.get("claim"), "lesson.claim"),
        "applicability": _word(value.get("applicability"), "lesson.applicability"),
        "limitations": _word(value.get("limitations"), "lesson.limitations"),
    }


def _receipt(value: Mapping[str, Any]) -> dict:
    """Validate shape; the trusted host MUST supply/authenticate the receipt.

    Never infer verification from Actor self-report. A receipt only refers to
    task-visible training/validation evidence, never the official locked test.
    """
    if not isinstance(value, Mapping):
        raise ProtocolError("verifier receipt must be an object")
    outcome = value.get("verdict")
    if outcome not in _VERDICTS:
        raise ProtocolError(f"invalid verifier verdict: {outcome}")
    actor = _word(value.get("actor_id"), "actor_id")
    verifier = _word(value.get("verifier_id"), "verifier_id")
    if actor == verifier:
        raise ProtocolError("Actor and Verifier must be distinct principals")
    source = value.get("evidence_scope")
    if source not in {"practice", "train_validation"}:
        raise ProtocolError("evidence_scope must be practice or train_validation")
    return {
        "verdict": outcome,
        "actor_id": actor,
        "verifier_id": verifier,
        "actor_artifact_sha256": _sha(value.get("actor_artifact_sha256"), "actor_artifact_sha256"),
        "verified_artifact_sha256": _sha(value.get("verified_artifact_sha256"), "verified_artifact_sha256"),
        "report_sha256": _sha(value.get("report_sha256"), "report_sha256"),
        "evidence_scope": source,
    }


def _episode(result: Mapping[str, Any], *, expected_scope: str | None = None) -> dict:
    receipt = _receipt(result.get("verification", {}))
    if receipt["actor_artifact_sha256"] != receipt["verified_artifact_sha256"]:
        raise ProtocolError("Verifier did not inspect the submitted Actor artifact")
    if expected_scope is not None and receipt["evidence_scope"] != expected_scope:
        raise ProtocolError("episode evidence scope mismatch")
    lessons = [_lesson(v) for v in result.get("lessons", [])]
    if receipt["verdict"] not in {"PASS", "FAIL"} and lessons:
        raise ProtocolError("unresolved/infrastructure episodes cannot teach memory")
    return {"verification": receipt, "lessons": lessons}


def begin_wave(state: dict, projects: list[dict]) -> dict:
    """RSIAgent BRS: all projects consume the same pre-wave memory snapshot."""
    new = _copy(state)
    if new["phase"] != "BRS" or new["wave"] is not None:
        raise ProtocolError("BRS wave cannot start in this state")
    if not isinstance(projects, list) or not projects:
        raise ProtocolError("Curriculum wave must contain at least one project")
    ids: set[str] = set()
    normalized = []
    for item in projects:
        if not isinstance(item, dict):
            raise ProtocolError("project must be an object")
        project_id = _word(item.get("id"), "project.id")
        if project_id in ids:
            raise ProtocolError("duplicate project id")
        ids.add(project_id)
        normalized.append({
            "id": project_id,
            "target": _word(item.get("target"), "project.target"),
            "objective": _word(item.get("objective"), "project.objective"),
            "rationale": _word(item.get("rationale"), "project.rationale"),
            "memory_before_sha256": new["memory_sha256"],
            "result": None,
        })
    new["wave"] = {"projects": normalized, "memory_before_sha256": new["memory_sha256"]}
    return new


def submit_wave_result(state: dict, project_id: str, result: dict) -> dict:
    """Store one branch, but do not publish memory until the full wave closes."""
    new = _copy(state)
    if new["phase"] != "BRS" or new["wave"] is None:
        raise ProtocolError("no active BRS wave")
    project = next((p for p in new["wave"]["projects"] if p["id"] == project_id), None)
    if project is None or project["result"] is not None:
        raise ProtocolError("unknown or already submitted BRS project")
    project["result"] = _episode(result)
    return new


def _apply_lessons(state: dict, source_id: str, episode: dict) -> None:
    if state["arm"] == "A":
        return
    verifier = episode["verification"]
    if verifier["verdict"] not in {"PASS", "FAIL"}:
        raise ProtocolError("cannot distill an unresolved outcome")
    for lesson in episode["lessons"]:
        state["memory"].append({
            "source_id": source_id,
            "terminal_outcome": verifier["verdict"],
            "evidence_scope": verifier["evidence_scope"],
            "actor_artifact_sha256": verifier["actor_artifact_sha256"],
            "verifier_report_sha256": verifier["report_sha256"],
            **lesson,
        })
    state["memory_sha256"] = canonical_hash(state["memory"])


def commit_wave(state: dict) -> dict:
    """All-or-nothing wave barrier; ordered Actor-owned memory consolidation."""
    new = _copy(state)
    if new["phase"] != "BRS" or new["wave"] is None:
        raise ProtocolError("no active wave to commit")
    wave = new["wave"]
    if any(p["result"] is None or
           p["result"]["verification"]["verdict"] not in {"PASS", "FAIL"}
           for p in wave["projects"]):
        raise ProtocolError("wave blocked: pending/unresolved/infrastructure branch")
    if wave["memory_before_sha256"] != new["memory_sha256"]:
        raise ProtocolError("memory changed before wave barrier")
    for project in wave["projects"]:
        _apply_lessons(new, project["id"], project["result"])
    new["wave_history"].append({
        "projects": [p["id"] for p in wave["projects"]],
        "memory_before_sha256": wave["memory_before_sha256"],
        "memory_after_sha256": new["memory_sha256"],
        "outcomes": [p["result"]["verification"]["verdict"] for p in wave["projects"]],
    })
    new["wave"] = None
    return new


def begin_deep_target(state: dict, target_id: str) -> dict:
    """Start RSIAgent DRS with a concrete target attempt, not practice first."""
    new = _copy(state)
    if new["phase"] != "BRS" or new["wave"] is not None:
        raise ProtocolError("finish all BRS waves before DRS")
    new["phase"] = "DRS"
    new["target"] = {
        "id": _word(target_id, "target_id"),
        "attempts": [],
        "practices": [],
        "needs_practice": False,
        "retry_required": False,
        "verified_ready": False,
    }
    return new


def submit_target_attempt(state: dict, result: dict) -> dict:
    """After practice, the unchanged target MUST be attempted again."""
    new = _copy(state)
    if new["phase"] != "DRS" or new["target"] is None:
        raise ProtocolError("no active deep target")
    target = new["target"]
    if target["verified_ready"] or target["needs_practice"]:
        raise ProtocolError("target is ready or requires focused practice")
    episode = _episode(result, expected_scope="train_validation")
    verdict = episode["verification"]["verdict"]
    target["attempts"].append(episode)
    if verdict in {"PASS", "FAIL"}:
        _apply_lessons(new, f"target:{target['id']}:attempt:{len(target['attempts'])}", episode)
    if verdict == "PASS":
        target["verified_ready"] = True
        target["retry_required"] = False
    else:
        target["needs_practice"] = verdict == "FAIL"
        target["retry_required"] = True
    return new


def submit_focused_practice(state: dict, practice_id: str, result: dict) -> dict:
    new = _copy(state)
    if new["phase"] != "DRS" or not new["target"] or not new["target"]["needs_practice"]:
        raise ProtocolError("practice requires a verified failed target attempt")
    episode = _episode(result, expected_scope="practice")
    target = new["target"]
    target["practices"].append({"id": _word(practice_id, "practice_id"), **episode})
    if episode["verification"]["verdict"] in {"PASS", "FAIL"}:
        _apply_lessons(new, f"practice:{practice_id}", episode)
    if episode["verification"]["verdict"] == "PASS":
        target["needs_practice"] = False
    return new



def register_harness_promotion(state: dict, *, candidate_id: str,
                               gate_report_sha256: str, operator_id: str,
                               new_harness_sha256: str) -> dict:
    """Record an externally authorized Harness upgrade; never execute a patch.

    Only the trusted host/operator can prove gate approval and install the
    candidate. This ledger method deliberately does not replace gate.py.
    """
    new = _copy(state)
    if new["arm"] != "R" or new["phase"] not in {"BRS", "DRS"} or new["wave"] is not None:
        raise ProtocolError("only R may record promotion outside an active wave")
    candidate = _word(candidate_id, "candidate_id")
    gate = _sha(gate_report_sha256, "gate_report_sha256")
    operator = _word(operator_id, "operator_id")
    next_sha = _sha(new_harness_sha256, "new_harness_sha256")
    if next_sha == new["harness_sha256"]:
        raise ProtocolError("promotion must change the harness digest")
    new["protocol_history"].append({
        "event": "operator_approved_promotion",
        "candidate_id": candidate,
        "gate_report_sha256": gate,
        "operator_id": operator,
        "old_harness_sha256": new["harness_sha256"],
        "new_harness_sha256": next_sha,
    })
    new["harness_sha256"] = next_sha
    return new


def freeze_for_test(state: dict) -> dict:
    """Frozen RSI memory: no Curriculum, no distillation, no official score reuse."""
    new = _copy(state)
    if new["phase"] != "DRS" or new["target"] is None:
        raise ProtocolError("a verified deep target is required before test")
    if not new["target"]["verified_ready"] or new["target"]["retry_required"]:
        raise ProtocolError("target not verified ready after deep exploration")
    new["phase"] = "TEST"
    new["frozen_sha256"] = new["memory_sha256"]
    return new


def attest_frozen(state: dict, *, expected_sha256: str,
                  search_space_sha256: str, harness_sha256: str) -> None:
    new = _copy(state)
    if new["phase"] != "TEST":
        raise ProtocolError("not in frozen test phase")
    if new["frozen_sha256"] != _sha(expected_sha256, "expected_sha256"):
        raise ProtocolError("memory snapshot changed")
    if new["search_space_sha256"] != _sha(search_space_sha256, "search_space_sha256"):
        raise ProtocolError("search space changed")
    if new["harness_sha256"] != _sha(harness_sha256, "harness_sha256"):
        raise ProtocolError("harness changed")
