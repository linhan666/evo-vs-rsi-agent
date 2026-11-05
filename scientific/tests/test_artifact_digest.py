"""Digest rules must be stable across runs (docs/PHASE4_DESIGN.md §3)."""
import json
import os
import sys
import tempfile
import time
import unittest

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, os.path.join(ROOT, "scientific", "src"))
sys.path.insert(0, ROOT)

import numpy as np  # noqa: E402

from evolution.artifacts import artifact_digest  # noqa: E402


class ArtifactDigestTests(unittest.TestCase):
    def test_npz_digest_ignores_zip_timestamps(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = os.path.join(tmp, "a.npz")
            b = os.path.join(tmp, "b.npz")
            np.savez_compressed(a, X=np.arange(6, dtype=np.uint8).reshape(2, 3))
            time.sleep(2.2)  # zip timestamps have 2s resolution
            np.savez_compressed(b, X=np.arange(6, dtype=np.uint8).reshape(2, 3))
            self.assertEqual(artifact_digest(a), artifact_digest(b))

    def test_json_digest_ignores_volatile_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = os.path.join(tmp, "a.json")
            b = os.path.join(tmp, "b.json")
            json.dump({"created_at": "2026-01-01", "metrics": {"auroc": 0.9}}, open(a, "w"))
            json.dump({"created_at": "2027-06-06", "metrics": {"auroc": 0.9}}, open(b, "w"))
            self.assertEqual(artifact_digest(a), artifact_digest(b))

    def test_object_array_digest_ignores_pickle_encoding(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = os.path.join(tmp, "a.npz")
            b = os.path.join(tmp, "b.npz")
            ids = [f"CHEMBL{i}" for i in range(50)]
            np.savez_compressed(a, ids=np.asarray(ids, dtype=object))
            # Same strings, but a different construction path (list of np.str_)
            np.savez_compressed(b, ids=np.asarray([np.str_(x) for x in ids], dtype=object))
            self.assertEqual(artifact_digest(a), artifact_digest(b))

    def test_json_digest_ignores_derived_sha256(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = os.path.join(tmp, "a.json")
            b = os.path.join(tmp, "b.json")
            json.dump({"artifacts": [{"path": "x.npz", "sha256": "aaa"}]}, open(a, "w"))
            json.dump({"artifacts": [{"path": "x.npz", "sha256": "bbb"}]}, open(b, "w"))
            self.assertEqual(artifact_digest(a), artifact_digest(b))

    def test_csv_digest_is_byte_level(self):
        with tempfile.TemporaryDirectory() as tmp:
            a = os.path.join(tmp, "a.csv")
            b = os.path.join(tmp, "b.csv")
            open(a, "w").write("rank,id\n1,zinc000001\n")
            open(b, "w").write("rank,id\n2,zinc000002\n")
            self.assertNotEqual(artifact_digest(a), artifact_digest(b))


if __name__ == "__main__":
    unittest.main()
