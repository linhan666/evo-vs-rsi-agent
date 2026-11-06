"""P5-04: fixed profiles, a real frontier, and gated candidates kept out of both."""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from pareto import evaluate, frontier, rank  # noqa: E402

ENTRIES = [
    {"candidate_id": "fast-cheap", "quality": 0.001, "cost": 3.0, "gates_ok": True},
    {"candidate_id": "accurate", "quality": 0.02, "cost": 1.1, "gates_ok": True},
    {"candidate_id": "middle", "quality": 0.008, "cost": 1.8, "gates_ok": True},
    # beaten by "middle" on both axes, so it must not appear on any front
    {"candidate_id": "worse-than-middle", "quality": 0.005, "cost": 1.5, "gates_ok": True},
    {"candidate_id": "blocked", "quality": 0.5, "cost": 9.0, "gates_ok": False},
]


class ParetoTests(unittest.TestCase):
    def test_the_profile_decides_the_winner(self):
        self.assertEqual(rank(ENTRIES, "lite")[0]["candidate_id"], "fast-cheap")
        self.assertEqual(rank(ENTRIES, "heavy")[0]["candidate_id"], "accurate")
        self.assertEqual(rank(ENTRIES, "balanced")[0]["candidate_id"], "fast-cheap")

    def test_a_dominated_candidate_stays_off_the_front(self):
        ids = [item["candidate_id"] for item in frontier(ENTRIES)]
        self.assertEqual(ids, ["accurate", "middle", "fast-cheap"])  # sorted by quality, no dominator pair
        self.assertNotIn("worse-than-middle", ids)

    def test_a_gate_blocked_candidate_never_ranks_or_fronts(self):
        self.assertNotIn("blocked", [item["candidate_id"] for item in rank(ENTRIES, "heavy")])
        self.assertNotIn("blocked", [item["candidate_id"] for item in frontier(ENTRIES)])
        self.assertEqual(evaluate(ENTRIES)["blocked_by_gate"], ["blocked"])

    def test_a_single_candidate_is_not_punished_for_being_alone(self):
        one = [{"candidate_id": "only", "quality": 0.0, "cost": 0.0, "gates_ok": True}]
        self.assertEqual(rank(one, "balanced")[0]["score"], 1.0)
        self.assertEqual([item["candidate_id"] for item in frontier(one)], ["only"])

    def test_every_profile_is_reported(self):
        result = evaluate(ENTRIES)
        self.assertEqual(set(result["profiles"]), {"lite", "balanced", "heavy"})
        for name in result["profiles"]:
            self.assertEqual(len(result["profiles"][name]), 4)  # blocked excluded


if __name__ == "__main__":
    unittest.main()
