"""Intake gate: malformed specs must be rejected before the sandbox."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from spec import validate_spec


class SpecValidationTests(unittest.TestCase):
    def test_minimal_env_spec_is_valid(self):
        spec = {"candidate_id": "c1", "version": "1", "hypothesis": "h", "risk": "r",
                "changes": [{"type": "env", "key": "K", "value": "V"}],
                "acceptance": {"equivalence": 1.0}}
        self.assertEqual(validate_spec(spec), [])

    def test_missing_required_fields_rejected(self):
        errors = validate_spec({"candidate_id": "c1"})
        self.assertTrue(any("hypothesis" in e for e in errors))
        self.assertTrue(any("risk" in e for e in errors))
        self.assertTrue(any("changes" in e for e in errors))

    def test_unknown_change_type_rejected(self):
        spec = {"candidate_id": "c", "version": "1", "hypothesis": "h", "risk": "r",
                "changes": [{"type": "shell", "key": "K", "value": "rm -rf"}],
                "acceptance": {"equivalence": 1.0}}
        self.assertTrue(any("type" in e for e in validate_spec(spec)))

    def test_unknown_status_rejected(self):
        spec = {"candidate_id": "c", "version": "1", "hypothesis": "h", "risk": "r",
                "changes": [], "acceptance": {"equivalence": 1.0}, "status": "yolo"}
        self.assertTrue(any("status" in e for e in validate_spec(spec)))


if __name__ == "__main__":
    unittest.main()
