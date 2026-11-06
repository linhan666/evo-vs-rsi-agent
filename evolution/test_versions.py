"""P5-05: one live version at a time, and a revert a person can actually run."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from versions import applied, current, load, next_version, record, rollback  # noqa: E402

PASSING_GATE = {"verdict": "pass", "blocking": [], "needs_human_number": []}
FAILING_GATE = {"verdict": "fail", "blocking": ["cost"], "needs_human_number": []}


def spec(name="c1"):
    return {"candidate_id": name,
            "changes": [{"type": "env", "key": "EVOVS_FEAT_JOBS", "value": "8"}],
            "rollback": "revert the default to '1' in featurize.py"}


class VersionLedgerTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.path = os.path.join(self.tmp.name, "versions.json")

    def test_a_failing_gate_cannot_be_recorded(self):
        with self.assertRaises(SystemExit):
            record(self.path, spec(), FAILING_GATE, git_sha="abc123", note="n")

    def test_force_records_and_marks_the_entry(self):
        entry = record(self.path, spec(), FAILING_GATE, git_sha="abc123", note="operator override", force=True)
        self.assertTrue(entry.get("forced"))
        self.assertEqual(current(load(self.path))["version"], "v1")

    def test_only_one_version_is_live(self):
        record(self.path, spec("c1"), PASSING_GATE, git_sha="a" * 40, note="first")
        record(self.path, spec("c2"), PASSING_GATE, git_sha="b" * 40, note="second")
        ledger = load(self.path)
        statuses = {item["candidate_id"]: item["status"] for item in ledger["entries"]}
        self.assertEqual(statuses, {"c1": "superseded", "c2": "active"})
        self.assertEqual(current(ledger)["candidate_id"], "c2")

    def test_versions_increment(self):
        self.assertEqual(next_version({"entries": []}), "v1")
        self.assertEqual(next_version({"entries": [{"version": "v7"}]}), "v8")

    def test_rollback_marks_and_returns_the_revert_text(self):
        record(self.path, spec(), PASSING_GATE, git_sha="a" * 40, note="n")
        entry = rollback(self.path, "v1")
        self.assertEqual(entry["status"], "rolled_back")
        self.assertIn("featurize.py", entry["rollback"])
        self.assertIsNone(current(load(self.path)))

    def test_rollback_twice_is_refused(self):
        record(self.path, spec(), PASSING_GATE, git_sha="a" * 40, note="n")
        rollback(self.path, "v1")
        with self.assertRaises(SystemExit):
            rollback(self.path, "v1")

    def test_the_gate_result_is_kept_with_the_version(self):
        record(self.path, spec(), {"verdict": "manual", "blocking": [], "needs_human_number": ["safety"]},
               git_sha="a" * 40, note="n", force=True)
        entry = load(self.path)["entries"][0]
        self.assertEqual(entry["gate"]["needs_human_number"], ["safety"])
        self.assertEqual(entry["change"]["key"], "EVOVS_FEAT_JOBS")


    def test_applied_means_ancestor_not_equality(self):
        # HEAD moves for unrelated reasons; the promoted change stays applied, so
        # "is this commit in history" is the question, not "is HEAD exactly this".
        import subprocess
        repo = os.path.join(self.tmp.name, "repo")
        os.makedirs(repo)
        env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@e",
               "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@e"}
        run = lambda *args: subprocess.run(args, cwd=repo, env=env, check=True, capture_output=True)
        run("git", "init", "-q")
        open(os.path.join(repo, "a.txt"), "w").write("a")
        run("git", "add", ".")
        run("git", "commit", "-q", "-m", "first")
        first = subprocess.run(["git", "rev-parse", "HEAD"], cwd=repo, capture_output=True,
                               text=True, check=True).stdout.strip()
        open(os.path.join(repo, "b.txt"), "w").write("b")
        run("git", "add", ".")
        run("git", "commit", "-q", "-m", "second")
        self.assertTrue(applied(first, repo))
        self.assertFalse(applied("0" * 40, repo))


if __name__ == "__main__":
    unittest.main()
