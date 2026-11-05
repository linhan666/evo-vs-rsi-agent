"""Contract tests for the Phase 0 job schema. Standard library only."""

from __future__ import annotations

import unittest

from evovs_science.schemas import (
    SCHEMA_VERSION,
    JobResult,
    SchemaError,
    Usage,
    is_terminal,
    job_result_to_dict,
    job_spec_from_dict,
)


def valid_payload() -> dict:
    return {
        "schema_version": SCHEMA_VERSION,
        "ticket_id": "mor_bind_001",
        "experiment_id": "exp_012",
        "tool_id": "rdkit.featurize",
        "workspace_id": "ws_mor_bind_001",
        "argv": ["python3", "-m", "evovs_science.cli", "version"],
        "input_artifacts": ["artifact_library_100k"],
        "output_prefix": "runs/mor_bind_001/features",
        "resources": {
            "max_cpu_cores": 4,
            "max_gpu_count": 0,
            "max_wall_seconds": 900,
            "max_memory_gb": 8,
        },
        "idempotency_key": "sha256:deadbeef",
    }


class JobSpecTests(unittest.TestCase):
    def test_valid_spec_roundtrip(self) -> None:
        spec = job_spec_from_dict(valid_payload())
        self.assertEqual(spec.ticket_id, "mor_bind_001")
        self.assertIsInstance(spec.argv, tuple)
        self.assertEqual(spec.resources.max_gpu_count, 0)
        self.assertIsNone(spec.environment_ref)

    def test_rejects_wrong_schema_version(self) -> None:
        payload = valid_payload()
        payload["schema_version"] = "2"
        with self.assertRaises(SchemaError):
            job_spec_from_dict(payload)

    def test_rejects_argv_as_shell_string(self) -> None:
        payload = valid_payload()
        payload["argv"] = "python3 train.py --target MOR"
        with self.assertRaises(SchemaError):
            job_spec_from_dict(payload)

    def test_rejects_empty_argv(self) -> None:
        payload = valid_payload()
        payload["argv"] = []
        with self.assertRaises(SchemaError):
            job_spec_from_dict(payload)

    def test_rejects_missing_idempotency_key(self) -> None:
        payload = valid_payload()
        del payload["idempotency_key"]
        with self.assertRaises(SchemaError):
            job_spec_from_dict(payload)

    def test_rejects_negative_gpu_or_zero_cpu(self) -> None:
        negative_gpu = valid_payload()
        negative_gpu["resources"]["max_gpu_count"] = -1
        with self.assertRaises(SchemaError):
            job_spec_from_dict(negative_gpu)

        zero_cpu = valid_payload()
        zero_cpu["resources"]["max_cpu_cores"] = 0
        with self.assertRaises(SchemaError):
            job_spec_from_dict(zero_cpu)

    def test_bool_is_not_an_integer_resource(self) -> None:
        payload = valid_payload()
        payload["resources"]["max_cpu_cores"] = True
        with self.assertRaises(SchemaError):
            job_spec_from_dict(payload)


class JobResultTests(unittest.TestCase):
    def test_serialise_omits_absent_fields(self) -> None:
        payload = job_result_to_dict(JobResult(job_id="job_098", state="RUNNING"))
        self.assertEqual(payload["state"], "RUNNING")
        self.assertNotIn("exit_code", payload)
        self.assertEqual(payload["output_artifacts"], [])

    def test_rejects_unknown_state(self) -> None:
        with self.assertRaises(SchemaError):
            job_result_to_dict(JobResult(job_id="job_098", state="DONE"))

    def test_terminal_classification(self) -> None:
        self.assertTrue(is_terminal("SUCCEEDED"))
        self.assertTrue(is_terminal("TIMED_OUT"))
        self.assertFalse(is_terminal("RUNNING"))
        with self.assertRaises(SchemaError):
            is_terminal("UNKNOWN")

    def test_usage_serialised(self) -> None:
        result = JobResult(
            job_id="job_098",
            state="SUCCEEDED",
            exit_code=0,
            output_artifacts=("artifact_metrics_012",),
            usage=Usage(cpu_seconds=85.0, gpu_seconds=0.0, max_rss_mb=512.0),
        )
        payload = job_result_to_dict(result)
        self.assertEqual(payload["usage"]["cpu_seconds"], 85.0)
        self.assertEqual(payload["output_artifacts"], ["artifact_metrics_012"])


if __name__ == "__main__":
    unittest.main()
