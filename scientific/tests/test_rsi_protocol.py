"""Portable state-machine tests. Execute only on the authorized project server."""
import unittest

from evovs_science.rsi.protocol import (
    ProtocolError, attest_frozen, begin_deep_target, begin_wave, canonical_hash,
    commit_wave, create_run, freeze_for_test, register_harness_promotion,
    submit_focused_practice, submit_target_attempt, submit_wave_result,
)

ZERO = "0" * 64
ONE = "1" * 64
TWO = "2" * 64
THREE = "3" * 64
FOUR = "4" * 64


def receipt(verdict="PASS", scope="practice", actor="actor-1", verifier="verifier-2"):
    return {
        "verification": {
            "verdict": verdict,
            "actor_id": actor,
            "verifier_id": verifier,
            "actor_artifact_sha256": ONE,
            "verified_artifact_sha256": ONE,
            "report_sha256": TWO,
            "evidence_scope": scope,
        },
        "lessons": [{
            "claim": "An empirical observation, not a general law",
            "applicability": "Only this synthetic rehearsal",
            "limitations": "Unknown transfer performance",
        }],
    }


def run(arm="R"):
    return create_run("rehearsal", arm=arm, search_space_sha256=ZERO,
                      data_manifest_sha256=ONE, harness_sha256=TWO)


def project(name):
    return {"id": name, "target": "MOR", "objective": "rehearse a local split",
            "rationale": "broaden algorithm coverage"}


def complete_brs(state):
    state = begin_wave(state, [project("p1"), project("p2")])
    state = submit_wave_result(state, "p1", receipt("PASS"))
    state = submit_wave_result(state, "p2", receipt("FAIL"))
    return commit_wave(state)


class ProtocolTests(unittest.TestCase):
    def test_hash_is_canonical(self):
        self.assertEqual(canonical_hash({"a": 1, "b": 2}),
                         canonical_hash({"b": 2, "a": 1}))

    def test_brs_wave_is_a_barrier_and_memory_is_ordered(self):
        state = begin_wave(run(), [project("p1"), project("p2")])
        start_sha = state["memory_sha256"]
        state = submit_wave_result(state, "p2", receipt("FAIL"))
        self.assertEqual(state["memory_sha256"], start_sha)
        with self.assertRaises(ProtocolError):
            commit_wave(state)
        state = submit_wave_result(state, "p1", receipt("PASS"))
        self.assertEqual(state["wave"]["projects"][0]["memory_before_sha256"], start_sha)
        state = commit_wave(state)
        self.assertEqual([x["source_id"] for x in state["memory"]], ["p1", "p2"])
        self.assertEqual([x["terminal_outcome"] for x in state["memory"]],
                         ["PASS", "FAIL"])
        self.assertEqual(state["wave_history"][0]["memory_before_sha256"], start_sha)

    def test_infrastructure_failure_blocks_publication(self):
        state = begin_wave(run(), [project("p1")])
        bad = receipt("INFRA_ERROR")
        bad["lessons"] = []
        state = submit_wave_result(state, "p1", bad)
        with self.assertRaises(ProtocolError):
            commit_wave(state)

    def test_verifier_independence_and_artifact_hash(self):
        state = begin_wave(run(), [project("p1")])
        with self.assertRaises(ProtocolError):
            submit_wave_result(state, "p1", receipt(actor="same", verifier="same"))
        bad = receipt()
        bad["verification"]["verified_artifact_sha256"] = THREE
        with self.assertRaises(ProtocolError):
            submit_wave_result(state, "p1", bad)

    def test_unresolved_cannot_be_used_as_learning(self):
        state = begin_wave(run(), [project("p1")])
        with self.assertRaises(ProtocolError):
            submit_wave_result(state, "p1", receipt("UNRESOLVED"))

    def test_a_arm_has_no_memory_but_m_arm_has_learning(self):
        a = complete_brs(run("A"))
        m = complete_brs(run("M"))
        self.assertEqual(a["memory"], [])
        self.assertEqual(len(m["memory"]), 2)
        self.assertEqual(a["memory_sha256"], canonical_hash([]))

    def test_deep_failure_practice_and_mandatory_retrial(self):
        state = begin_deep_target(complete_brs(run()), "heldout-development-target")
        state = submit_target_attempt(state, receipt("FAIL", "train_validation"))
        with self.assertRaises(ProtocolError):
            freeze_for_test(state)
        with self.assertRaises(ProtocolError):
            submit_target_attempt(state, receipt("PASS", "train_validation"))
        state = submit_focused_practice(state, "fix-small-minority", receipt("PASS"))
        with self.assertRaises(ProtocolError):
            freeze_for_test(state)
        state = submit_target_attempt(state, receipt("PASS", "train_validation"))
        state = freeze_for_test(state)
        self.assertEqual(state["phase"], "TEST")
        self.assertEqual(state["frozen_sha256"], state["memory_sha256"])
        attest_frozen(state, expected_sha256=state["frozen_sha256"],
                      search_space_sha256=ZERO, harness_sha256=TWO)
        with self.assertRaises(ProtocolError):
            begin_wave(state, [project("late")])
        with self.assertRaises(ProtocolError):
            submit_focused_practice(state, "late", receipt("PASS"))

    def test_harness_promotion_requires_r_and_outside_wave(self):
        with self.assertRaises(ProtocolError):
            register_harness_promotion(run("M"), candidate_id="p", gate_report_sha256=THREE,
                                       operator_id="operator", new_harness_sha256=FOUR)
        wave = begin_wave(run(), [project("p1")])
        with self.assertRaises(ProtocolError):
            register_harness_promotion(wave, candidate_id="p",
                                       gate_report_sha256=THREE,
                                       operator_id="operator", new_harness_sha256=FOUR)
        promoted = register_harness_promotion(run(), candidate_id="fix",
                                               gate_report_sha256=THREE,
                                               operator_id="operator", new_harness_sha256=FOUR)
        self.assertEqual(promoted["harness_sha256"], FOUR)
        self.assertEqual(promoted["protocol_history"][0]["event"],
                         "operator_approved_promotion")

    def test_tampered_memory_cannot_pass_frozen_attestation(self):
        state = begin_deep_target(complete_brs(run()), "target")
        state = submit_target_attempt(state, receipt("PASS", "train_validation"))
        frozen = freeze_for_test(state)
        frozen["memory"].append({"forbidden": "changed after freeze"})
        with self.assertRaises(ProtocolError):
            attest_frozen(frozen, expected_sha256=state["memory_sha256"],
                          search_space_sha256=ZERO, harness_sha256=TWO)


if __name__ == "__main__":
    unittest.main()
