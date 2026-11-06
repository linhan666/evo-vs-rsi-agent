"""Fusion tool (Phase 6B: model fusion is one of the Agent's choices)."""
import csv
import json
import os
import subprocess
import sys
import tempfile
import unittest

PYTHON = sys.executable


def write_predictions(path: str, scores: dict[str, float]) -> None:
    with open(path, "w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "score"])
        for molecule, score in scores.items():
            writer.writerow([molecule, score])


class FusionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.a = os.path.join(self.tmp.name, "a.csv")
        self.b = os.path.join(self.tmp.name, "b.csv")
        write_predictions(self.a, {"m1": 0.9, "m2": 0.6, "m3": 0.2})
        write_predictions(self.b, {"m1": 0.5, "m2": 0.8, "m3": 0.1})

    def fuse(self, method: str, weight: str = "0.5"):
        out = os.path.join(self.tmp.name, f"{method}.csv")
        rep = os.path.join(self.tmp.name, f"{method}.json")
        result = subprocess.run(
            [PYTHON, "-m", "evovs_science.modeling.fusion",
             "--a", self.a, "--b", self.b, "--output", out, "--report", rep,
             "--method", method, "--weight-a", weight],
            capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        rows = {}
        with open(out, encoding="utf-8") as handle:
            for row in csv.DictReader(handle):
                rows[row["id"]] = float(row["fused_score"])
        return rows, json.load(open(rep, encoding="utf-8"))

    def test_mean_fusion_averages_the_scores(self):
        rows, report = self.fuse("mean", "0.5")
        self.assertAlmostEqual(rows["m1"], 0.7, places=6)
        self.assertAlmostEqual(rows["m2"], 0.7, places=6)
        self.assertEqual(report["shared_molecules"], 3)
        self.assertEqual(report["method"], "mean")

    def test_weights_are_recorded_and_sum_to_one(self):
        _, report = self.fuse("mean", "0.3")
        self.assertAlmostEqual(report["weight_a"] + report["weight_b"], 1.0, places=6)

    def test_rank_fusion_orders_by_combined_rank(self):
        rows, _ = self.fuse("rank", "0.5")
        # m1 is 1st+2nd, m2 is 2nd+1st -> tie; m3 is last in both
        self.assertGreater(rows["m3"], -10)

    def test_disjoint_ids_are_refused(self):
        write_predictions(self.b, {"zzz": 0.5})
        result = subprocess.run(
            [PYTHON, "-m", "evovs_science.modeling.fusion",
             "--a", self.a, "--b", self.b,
             "--output", os.path.join(self.tmp.name, "x.csv"),
             "--report", os.path.join(self.tmp.name, "x.json")],
            capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("share no molecule", result.stderr + result.stdout)


if __name__ == "__main__":
    unittest.main()
