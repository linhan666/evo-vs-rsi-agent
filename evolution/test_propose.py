"""P4-04 hybrid: the rules decide what to propose, the LLM only phrases it."""
import json
import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from propose import (load_traces, main, mine_failures, mine_latency,  # noqa: E402
                     template_hypothesis, to_spec)
from spec import validate_spec  # noqa: E402


def write_trace(directory, name, exported_at, steps):
    trace = {"schema_version": "2", "ticket_dir": "/x", "exported_at": exported_at,
             "steps": steps}
    with open(os.path.join(directory, name + ".json"), "w", encoding="utf-8") as handle:
        json.dump(trace, handle)


def step(tool, seconds, *, state="SUCCEEDED", stderr=""):
    return {"job_id": "aaaaaaaaaaaa", "tool_id": tool, "state": state, "started_at": "2026-11-06T00:00:00Z",
            "argv": [], "wall_seconds": seconds, "exit_code": 0 if state == "SUCCEEDED" else 1,
            "error": "", "stderr_tail": stderr, "stdout_tail": "", "artifacts": []}


def heavy_workload(directory):
    """Two tickets that each screen twice: enough evidence for a latency claim."""
    for index in range(2):
        write_trace(directory, "t{}".format(index), "2026-11-0{}T00:00:00Z".format(index + 1),
                    [step("screening.rank", 80.0), step("screening.rank", 70.0), step("ml.train", 5.0)])


class MiningTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def test_a_failure_that_still_happens_is_mined_but_an_old_one_is_not(self):
        # The same class in two OLD traces only: recurrence alone is not enough,
        # because it may already be fixed — recency is the gate.
        for index in range(2):
            write_trace(self.tmp.name, "old{}".format(index), "2026-11-01T00:00:0{}Z".format(index),
                        [step("rdkit.featurize", 1.0, state="FAILED", stderr="ValueError: old bug\n")])
        for index in range(3):
            write_trace(self.tmp.name, "new{}".format(index), "2026-11-02T00:00:0{}Z".format(index),
                        [step("ml.train", 1.0, state="FAILED", stderr="KeyError: 'label'\n")])
        traces = load_traces(self.tmp.name)
        mined = mine_failures(traces, recent=3)
        keys = [item["cluster"] for item in mined]
        self.assertIn("ml.train::KeyError", keys)
        self.assertNotIn("rdkit.featurize::ValueError", keys)

    def test_only_the_wall_clock_owner_is_proposed(self):
        heavy_workload(self.tmp.name)
        mined = mine_latency(load_traces(self.tmp.name))
        self.assertEqual([item["tool_id"] for item in mined], ["screening.rank"])
        self.assertGreater(mined[0]["evidence"]["share"], 0.8)

    def test_a_single_ticket_cannot_speak_for_the_workload(self):
        # One ticket with many calls is still one observation; probe tickets look
        # exactly like this and must not generate a proposal.
        write_trace(self.tmp.name, "only", "2026-11-01T00:00:00Z",
                    [step("screening.rank", 80.0) for _ in range(6)])
        self.assertEqual(mine_latency(load_traces(self.tmp.name)), [])

    def test_a_cheap_corpus_proposes_nothing(self):
        write_trace(self.tmp.name, "t1", "2026-11-01T00:00:00Z",
                    [step("a.tool", 0.5), step("b.tool", 0.5)])
        self.assertEqual(mine_latency(load_traces(self.tmp.name)), [])

    def test_latency_evidence_names_its_window_and_caveat(self):
        heavy_workload(self.tmp.name)
        evidence = mine_latency(load_traces(self.tmp.name))[0]["evidence"]
        self.assertEqual(evidence["corpus_window"]["traces"], 2)
        self.assertIn("re-measure", evidence["caveat"])


class SpecTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        heavy_workload(self.tmp.name)

    def test_generated_spec_passes_the_intake_validator(self):
        opportunity = mine_latency(load_traces(self.tmp.name))[0]
        spec = to_spec(opportunity, None)
        self.assertEqual(validate_spec(spec), [])
        self.assertEqual(spec["acceptance"]["min_speedup"], 1.3)
        self.assertEqual(spec["changes"][0]["key"], "EVOVS_SCREEN_JOBS")

    def test_llm_wording_cannot_change_the_knob_or_the_acceptance(self):
        opportunity = mine_latency(load_traces(self.tmp.name))[0]
        spec = to_spec(opportunity, {"hypothesis": "h", "risk": "r"})
        self.assertEqual((spec["hypothesis"], spec["risk"]), ("h", "r"))
        self.assertEqual(spec["changes"], [opportunity["change"]])
        self.assertEqual(spec["acceptance"], opportunity["acceptance"])

    def test_template_names_the_measured_number(self):
        opportunity = mine_latency(load_traces(self.tmp.name))[0]
        self.assertIn("screening.rank", template_hypothesis(opportunity))
        self.assertIn("75.0", template_hypothesis(opportunity))  # 150s over 2 calls

    def test_emit_is_idempotent(self):
        out = os.path.join(self.tmp.name, "candidates")
        args = ["--traces-dir", self.tmp.name, "--out-dir", out, "--no-llm", "--emit"]
        self.assertEqual(main(args), 0)
        first = sorted(os.listdir(out))
        self.assertEqual(len(first), 1)
        self.assertEqual(main(args), 0)
        self.assertEqual(sorted(os.listdir(out)), first)


if __name__ == "__main__":
    unittest.main()
