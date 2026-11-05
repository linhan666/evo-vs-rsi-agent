"""Artifact equivalence rules (docs/PHASE4_DESIGN.md §3, pre-registered)."""

from __future__ import annotations

import hashlib
import json

VOLATILE_JSON_KEYS = ("created_at", "started_at", "ended_at", "elapsed_seconds")
DERIVED_JSON_KEYS = ("sha256",)  # digests of other artifacts; checked via their own entries


def _sha256(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _npz_digest(path: str) -> str:
    """Content digest of an npz: array names, shapes, dtypes and raw bytes.

    np.savez wraps arrays in a zip container whose timestamps change between
    runs, so the file-level sha256 is not stable even for identical content.
    """
    import numpy as np

    data = np.load(path, allow_pickle=True)
    digest = hashlib.sha256()
    for name in sorted(data.files):
        array = data[name]
        digest.update(name.encode())
        digest.update(str(array.dtype).encode())
        digest.update(str(array.shape).encode())
        if array.dtype == object:
            # object arrays serialize via pickle, whose encoding is not stable
            # across machines for equal content; hash canonical strings instead.
            canonical = json.dumps([str(item) for item in array.ravel().tolist()],
                                   ensure_ascii=False, sort_keys=True)
            digest.update(canonical.encode())
        else:
            digest.update(np.ascontiguousarray(array).tobytes())
    return "npz:" + digest.hexdigest()


def _json_digest(path: str) -> str:
    """Semantic digest: canonical JSON with volatile timestamp fields removed."""
    payload = json.load(open(path, encoding="utf-8"))

    def strip(node):
        if isinstance(node, dict):
            return {key: strip(value) for key, value in node.items()
                    if key not in VOLATILE_JSON_KEYS and key not in DERIVED_JSON_KEYS}
        if isinstance(node, list):
            return [strip(item) for item in node]
        return node

    canonical = json.dumps(strip(payload), sort_keys=True, ensure_ascii=False)
    return "json:" + hashlib.sha256(canonical.encode()).hexdigest()


def artifact_digest(path: str) -> str:
    """Digest of an artifact under the pre-registered equivalence rules."""
    lower = path.lower()
    if lower.endswith(".npz"):
        return _npz_digest(path)
    if lower.endswith(".json"):
        return _json_digest(path)
    return "sha256:" + _sha256(path)
