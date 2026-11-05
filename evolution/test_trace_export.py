"""D-1 regression: failed steps must carry the text the tool actually printed."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from failure_clusters import error_class, last_meaningful_line  # noqa: E402
from trace_export import export  # noqa: E402


def make_job(root, job_id, *, state, exit_code, error="", stderr="", stdout=""):
    job_dir = os.path.join(root, ".jobs", job_id)
    os.makedirs(job_dir, exist_ok=True)
    record = {
        "job_id": job_id,
        "tool_id": "rdkit.featurize",
        "state": state,
        "started_at": "2026-11-06T00:00:0{}Z".format(job_id[-1]),
        "argv": ["python", "-m", "evovs_science.chemistry.featurize"],
        "usage": {"wall_seconds": 0.1},
        "exit_code": exit_code,
        "error": error,
        "artifacts": [],
    }
    with open(os.path.join(job_dir, "result.json"), "w", encoding="utf-8") as handle:
        json.dump(record, handle)
    if stderr:
        with open(os.path.join(job_dir, "stderr.log"), "w", encoding="utf-8") as handle:
            handle.write(stderr)
    if stdout:
        with open(os.path.join(job_dir, "stdout.log"), "w", encoding="utf-8") as handle:
            handle.write(stdout)


class TraceExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_failed_step_keeps_stderr_tail(self):
        make_job(self.tmp.name, "j1", state="FAILED", exit_code=1,
                 stderr="Traceback (most recent call last):\n  ...\nFileNotFoundError: no such file: /x/y.csv\n")
        steps = export(self.tmp.name)["steps"]
        self.assertEqual(len(steps), 1)
        self.assertEqual(steps[0]["error"], "")
        self.assertIn("FileNotFoundError", steps[0]["stderr_tail"])
        self.assertEqual(steps[0]["stdout_tail"], "")

    def test_failed_step_falls_back_to_stdout_when_stderr_is_silent(self):
        make_job(self.tmp.name, "j2", state="FAILED", exit_code=2,
                 stdout="usage error: --model must be a file\n")
        step = export(self.tmp.name)["steps"][0]
        self.assertEqual(step["stderr_tail"], "")
        self.assertIn("usage error", step["stdout_tail"])

    def test_successful_step_keeps_no_stdout_noise(self):
        make_job(self.tmp.name, "j3", state="SUCCEEDED", exit_code=0,
                 stdout='{"rows": 2790}'.ljust(4000, " "))
        step = export(self.tmp.name)["steps"][0]
        self.assertEqual(step["stdout_tail"], "")

    def test_tail_is_bounded(self):
        make_job(self.tmp.name, "j4", state="FAILED", exit_code=1, stderr="x" * 5000 + "\nboom\n")
        step = export(self.tmp.name)["steps"][0]
        self.assertLessEqual(len(step["stderr_tail"]), 1200)
        self.assertTrue(step["stderr_tail"].endswith("boom"))

    def test_schema_version_bumped_for_the_new_fields(self):
        make_job(self.tmp.name, "j5", state="SUCCEEDED", exit_code=0)
        self.assertEqual(export(self.tmp.name)["schema_version"], "2")


class ErrorClassTests(unittest.TestCase):
    def test_structured_error_wins(self):
        self.assertEqual(error_class("JSONDecodeError: bad", "ValueError: x", 1), "JSONDecodeError")

    def test_traceback_tail_is_parsed(self):
        tail = "Traceback (most recent call last):\n  File \"a.py\", line 1\nKeyError: 'label'\n"
        self.assertEqual(error_class("", tail, 1), "KeyError")

    def test_exit_code_when_nothing_recorded(self):
        self.assertEqual(error_class("", "", 2), "exit_2")

    def test_missing_column_is_a_named_class(self):
        tail = ("/home/u/proj/scientific/.artifacts/chembl/oprm1/ki/dataset.csv has no 'smiles' column; "
                "found ['molecule_chembl_id', 'canonical_smiles']")
        self.assertEqual(error_class("", tail, 1), "missing_column:smiles")

    def test_unclassified_message_does_not_leak_absolute_paths(self):
        tail = "/home/u/proj/data/x.csv looks empty"
        self.assertEqual(error_class("", tail, 1), "<path> looks empty")

    def test_last_meaningful_line_skips_blank_tail(self):
        self.assertEqual(last_meaningful_line("a\n\nb\n\n"), "b")


if __name__ == "__main__":
    unittest.main()
