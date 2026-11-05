"""Artifact provenance: sha256, sizes and a manifest per output directory.

Blueprint §8.4 requires every artifact to carry `sha256 / content_type / size /
generator / dataset_hash / code_commit / environment_hash / created_at`.
This module owns the hashing and the manifest file; callers pass the descriptive
fields they know (generator, inputs) and never hand-write a digest.
"""

from __future__ import annotations

import hashlib
import json
import os
import platform
import sys
from datetime import datetime, timezone
from typing import Any, Iterable

SCHEMA_VERSION = "1"


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def environment_ref() -> dict[str, str]:
    """What identifies the interpreter that produced an artifact."""
    return {
        "python": sys.version.split()[0],
        "implementation": platform.python_implementation(),
        "platform": platform.platform(),
    }


def write_manifest(
    output_dir: str,
    artifacts: Iterable[dict[str, Any]],
    *,
    generator: str,
    inputs: Iterable[dict[str, Any]] = (),
    parameters: dict[str, Any] | None = None,
    code_commit: str | None = None,
    extra: dict[str, Any] | None = None,
) -> str:
    """Write `artifact_manifest.json` next to the artifacts and return its path."""
    entries = []
    for artifact in artifacts:
        path = artifact["path"]
        entry = {
            "path": os.path.relpath(path, output_dir),
            "sha256": sha256_file(path),
            "size": os.path.getsize(path),
            "content_type": artifact.get("content_type", "application/octet-stream"),
            "generator": generator,
        }
        if artifact.get("description"):
            entry["description"] = artifact["description"]
        entries.append(entry)

    manifest: dict[str, Any] = {
        "schema_version": SCHEMA_VERSION,
        "created_at": utc_now(),
        "generator": generator,
        "environment": environment_ref(),
        "code_commit": code_commit or os.environ.get("EVOVS_CODE_COMMIT", "unknown"),
        "parameters": parameters or {},
        "inputs": list(inputs),
        "artifacts": entries,
    }
    if extra:
        manifest.update(extra)

    path = os.path.join(output_dir, "artifact_manifest.json")
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(manifest, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return path


def describe_input(path: str) -> dict[str, Any]:
    """An input entry for the manifest: path, size and digest of what was read."""
    return {
        "path": os.path.basename(path),
        "sha256": sha256_file(path),
        "size": os.path.getsize(path),
    }
