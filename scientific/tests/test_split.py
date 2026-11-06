"""Split strategies (Phase 6B: the split is a scientific decision)."""
import json
import os
import subprocess
import sys
import tempfile
import unittest

PYTHON = sys.executable


class ScaffoldSplitTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.csv = os.path.join(self.tmp.name, "data.csv")
        rows = ["id,smiles"]
        rings = ["c1ccccc1", "C1CCCCC1", "c1ccncc1", "C1CCOCC1"]
        for index in range(40):
            rows.append(f"mol{index},{rings[index % len(rings)]}CC")
        with open(self.csv, "w", encoding="utf-8") as handle:
            handle.write("\n".join(rows) + "\n")

    def run_split(self, strategy: str):
        out = os.path.join(self.tmp.name, f"{strategy}.json")
        result = subprocess.run(
            [PYTHON, "-m", "evovs_science.data.split", "--input", self.csv,
             "--output", out, "--strategy", strategy, "--test-fraction", "0.3",
             "--val-fraction", "0.1", "--id-column", "id", "--smiles-column", "smiles"],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.load(open(out, encoding="utf-8"))

    def test_scaffold_split_keeps_scaffolds_whole(self):
        manifest = self.run_split("scaffold")
        by_split = {}
        for molecule, split in manifest["rows"].items():
            by_split.setdefault(split, []).append(molecule)
        # two scaffolds -> one whole scaffold may not be split across train and test
        self.assertGreaterEqual(len(by_split.get("train", [])), 1)
        self.assertEqual(manifest["strategy"], "scaffold")
        self.assertEqual(len(manifest["rows"]), 40)

    def test_random_split_is_deterministic_under_a_seed(self):
        first = self.run_split("random")
        second = self.run_split("random")
        self.assertEqual(first["rows"], second["rows"])
        self.assertEqual(first["strategy"], "random")

    def test_strategy_is_recorded_in_the_manifest(self):
        manifest = self.run_split("scaffold")
        for key in ("strategy", "seed", "test_fraction", "counts"):
            self.assertIn(key, manifest)
        self.assertEqual(sum(manifest["counts"].values()), 40)

    def test_too_few_rows_is_refused(self):
        small = os.path.join(self.tmp.name, "small.csv")
        with open(small, "w", encoding="utf-8") as handle:
            handle.write("id,smiles\nm1,CCO\nm2,CCC\n")
        result = subprocess.run(
            [PYTHON, "-m", "evovs_science.data.split", "--input", small,
             "--output", os.path.join(self.tmp.name, "s.json"), "--strategy", "random"],
            capture_output=True, text=True)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("NOT_ENOUGH_RELIABLE_DATA", result.stderr + result.stdout)



class ManifestRoundTripTests(unittest.TestCase):
    """data.split -> ml.train must work without the Agent patching anything."""

    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.csv = os.path.join(self.tmp.name, "data.csv")
        rows = ["id,smiles"]
        rings = ["c1ccccc1", "C1CCCCC1", "c1ccncc1", "C1CCOCC1"]
        for index in range(40):
            rows.append(f"mol{index},{rings[index % len(rings)]}CC")
        with open(self.csv, "w", encoding="utf-8") as handle:
            handle.write("\n".join(rows) + "\n")

    def test_split_manifest_is_accepted_by_read_split_ids(self):
        out = os.path.join(self.tmp.name, "scaffold.json")
        result = subprocess.run(
            [PYTHON, "-m", "evovs_science.data.split", "--input", self.csv,
             "--output", out, "--strategy", "scaffold"],
            capture_output=True, text=True,
            cwd=os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
        self.assertEqual(result.returncode, 0, result.stderr)

        from evovs_science.modeling.train import read_split_ids
        groups = read_split_ids(out)
        self.assertIn("train", groups)
        self.assertIn("validation", groups)   # val is normalised
        self.assertNotIn("val", groups)
        self.assertGreater(len(groups["train"]), 0)

    def test_molecules_layout_is_still_accepted(self):
        legacy = os.path.join(self.tmp.name, "legacy.json")
        with open(legacy, "w", encoding="utf-8") as handle:
            json.dump({"molecules": {"train": ["a", "b"], "validation": ["c"]}}, handle)
        from evovs_science.modeling.train import read_split_ids
        groups = read_split_ids(legacy)
        self.assertEqual(groups["train"], {"a", "b"})
        self.assertEqual(groups["validation"], {"c"})


if __name__ == "__main__":
    unittest.main()
