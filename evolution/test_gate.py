"""P5-03: four gate classes, one verdict, and no silent passes."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from gate import evaluate  # noqa: E402

CLEAN_REPORT = {
    "equivalence_rate": 1.0,
    "featurize_time_ratio_max": 0.9,
    "best_speedup": 1.5,
    "steps": [{"tool_id": "rdkit.featurize", "exit_code": 0, "artifacts_total": 2, "artifacts_equal": 2,
               "mismatches": []}],
}

SPEED_SPEC = {
    "candidate_id": "c1",
    "acceptance": {"equivalence": 1.0, "max_time_ratio": 1.2, "min_speedup": 1.3},
}
CANARY_OK = {"state": "ok"}


def spec(**acceptance):
    return {"candidate_id": "c1", "acceptance": acceptance}


class GateTests(unittest.TestCase):
    def test_a_clean_candidate_passes_all_four(self):
        result = evaluate(SPEED_SPEC, CLEAN_REPORT, canary=CANARY_OK)
        self.assertEqual(result["verdict"], "pass")
        self.assertEqual({gate["gate"]: gate["status"] for gate in result["gates"]},
                         {"equivalence": "pass", "cost": "pass", "success": "pass",
                          "failure": "n/a", "quality": "n/a", "safety": "pass"})

    def test_a_failure_claim_needs_replayed_failures(self):
        claim = spec(equivalence=1.0, failures_in_replay=0)
        self.assertEqual(evaluate(claim, CLEAN_REPORT, canary=CANARY_OK)["verdict"], "fail")
        report = dict(CLEAN_REPORT, failures_replayed=4, failures_remaining=0)
        self.assertEqual(evaluate(claim, report, canary=CANARY_OK)["verdict"], "pass")
        still = dict(CLEAN_REPORT, failures_replayed=4, failures_remaining=2)
        result = evaluate(claim, still, canary=CANARY_OK)
        self.assertEqual(result["verdict"], "fail")
        self.assertIn("failure", result["blocking"])

    def test_a_report_that_replayed_nothing_cannot_claim_success(self):
        claim = spec(equivalence=1.0, failures_in_replay=0)
        result = evaluate(claim, dict(CLEAN_REPORT, failures_replayed=0, failures_remaining=0), canary=CANARY_OK)
        self.assertEqual(result["verdict"], "fail")

    def test_a_missed_speedup_blocks_even_when_everything_else_is_clean(self):
        report = dict(CLEAN_REPORT, best_speedup=1.05)
        result = evaluate(SPEED_SPEC, report, canary=CANARY_OK)
        self.assertEqual(result["verdict"], "fail")
        self.assertEqual(result["blocking"], ["cost"])

    def test_an_artifact_mismatch_fails_equivalence_and_success(self):
        report = dict(CLEAN_REPORT, equivalence_rate=0.5,
                      steps=[{"tool_id": "ml.train", "exit_code": 0, "artifacts_total": 2,
                              "artifacts_equal": 1, "mismatches": ["model.joblib: digest differs"]}])
        result = evaluate(SPEED_SPEC, report, canary=CANARY_OK)
        self.assertEqual(result["verdict"], "fail")
        self.assertEqual(sorted(result["blocking"]), ["equivalence", "success"])

    def test_a_non_zero_exit_is_a_success_failure(self):
        report = dict(CLEAN_REPORT, steps=[{"tool_id": "screening.rank", "exit_code": -9,
                                            "artifacts_total": 3, "artifacts_equal": 3, "mismatches": []}])
        result = evaluate(spec(equivalence=1.0), report, canary=CANARY_OK)
        self.assertEqual(result["verdict"], "fail")
        self.assertIn("success", result["blocking"])

    def test_metric_level_equivalence_cannot_be_read_as_a_pass(self):
        result = evaluate(spec(equivalence="not byte-comparable: feature space changes"), CLEAN_REPORT,
                          canary=CANARY_OK)
        self.assertEqual(result["verdict"], "manual")
        self.assertEqual(result["needs_human_number"], ["equivalence"])

    def test_a_quality_claim_without_metrics_stays_manual(self):
        result = evaluate(spec(equivalence=1.0, min_val_auroc=0.8), CLEAN_REPORT, canary=CANARY_OK)
        self.assertEqual(result["verdict"], "manual")
        self.assertEqual(result["needs_human_number"], ["quality"])

    def test_a_quality_claim_below_its_threshold_fails(self):
        result = evaluate(spec(equivalence=1.0, min_val_auroc=0.8), CLEAN_REPORT,
                          metrics={"auroc": 0.71}, canary=CANARY_OK)
        self.assertEqual(result["verdict"], "fail")
        self.assertIn("quality", result["blocking"])

    def test_cost_is_recomputed_when_an_old_report_omits_it(self):
        # Reports written before the gate existed carry no best_speedup; the verdict
        # must come from the step timings rather than fail on a missing field.
        report = {"equivalence_rate": 1.0,
                  "steps": [{"tool_id": "rdkit.featurize", "baseline_wall_seconds": 2.31,
                             "candidate_wall_seconds": 1.09, "exit_code": 0,
                             "artifacts_total": 2, "artifacts_equal": 2, "mismatches": []}]}
        result = evaluate(SPEED_SPEC, report, canary=CANARY_OK)
        self.assertEqual(result["verdict"], "pass")

    def test_a_failure_claim_is_judged_per_claimed_class(self):
        claim = spec(equivalence=1.0, failures_in_replay=0)
        claim["acceptance"]["failure_clusters"] = ["rdkit.featurize::missing_column:smiles"]
        report = dict(CLEAN_REPORT, failures_replayed=3, failures_remaining=2,
                      failures_by_class={
                          "rdkit.featurize::missing_column:smiles": {"replayed": 2, "remaining": 0},
                          "rdkit.featurize::FileNotFoundError": {"replayed": 1, "remaining": 2}})
        self.assertEqual(evaluate(claim, report, canary=CANARY_OK)["verdict"], "pass")

    def test_a_claimed_class_that_was_never_replayed_fails(self):
        claim = spec(equivalence=1.0, failures_in_replay=0)
        claim["acceptance"]["failure_clusters"] = ["rdkit.featurize::KeyError"]
        report = dict(CLEAN_REPORT, failures_replayed=2, failures_remaining=0,
                      failures_by_class={"rdkit.featurize::ValueError": {"replayed": 2, "remaining": 0}})
        result = evaluate(claim, report, canary=CANARY_OK)
        self.assertEqual(result["verdict"], "fail")
        self.assertIn("failure", result["blocking"])

    def test_a_replayed_failure_does_not_trip_the_success_gate(self):
        # Remediation candidates deliberately replay steps that used to fail; those
        # are the failure gate's business, not evidence that the success path broke.
        claim = spec(equivalence=1.0, failures_in_replay=0)
        claim["acceptance"]["failure_clusters"] = ["rdkit.featurize::missing_column:smiles"]
        report = dict(CLEAN_REPORT,
                      steps=[{"tool_id": "rdkit.featurize", "recorded_state": "SUCCEEDED", "exit_code": 0,
                              "artifacts_total": 2, "artifacts_equal": 2, "mismatches": []},
                             {"tool_id": "rdkit.featurize", "recorded_state": "FAILED", "exit_code": 1,
                              "artifacts_total": 0, "artifacts_equal": 0, "mismatches": []}],
                      failures_replayed=1, failures_remaining=0,
                      failures_by_class={"rdkit.featurize::missing_column:smiles": {"replayed": 1, "remaining": 0}})
        self.assertEqual(evaluate(claim, report, canary=CANARY_OK)["verdict"], "pass")

    def test_a_missing_canary_blocks_a_silent_pass(self):
        result = evaluate(SPEED_SPEC, CLEAN_REPORT)
        self.assertEqual(result["verdict"], "manual")
        self.assertEqual(result["needs_human_number"], ["safety"])

    def test_a_broken_canary_fails_safety(self):
        result = evaluate(SPEED_SPEC, CLEAN_REPORT, canary={"state": "error", "detail": "protected mode changed"})
        self.assertEqual(result["verdict"], "fail")
        self.assertIn("safety", result["blocking"])


if __name__ == "__main__":
    unittest.main()
