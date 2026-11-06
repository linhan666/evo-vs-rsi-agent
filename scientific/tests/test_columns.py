"""Pre-flight column resolution (candidates 27384f and its ml.train sibling)."""
import os
import tempfile
import unittest

from evovs_science.chemistry.featurize import check_input_file, resolve_columns  # noqa: F401
from evovs_science.modeling.train import read_labels  # noqa: F401


class ColumnResolutionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)

    def write(self, header, row="CHEMBL1,CCO,1"):
        path = os.path.join(self.tmp.name, "data.csv")
        with open(path, "w", encoding="utf-8") as handle:
            handle.write(header + "\n" + row + "\n")
        return path

    def test_an_exact_name_is_left_alone(self):
        path = self.write("id,smiles")
        columns = resolve_columns(path, {"id": "id", "smiles": "smiles"})
        self.assertEqual((columns["id"], columns["smiles"]), ("id", "smiles"))
        self.assertEqual(columns["resolved"], {})

    def test_a_chembl_header_resolves_through_the_alias(self):
        path = self.write("molecule_chembl_id,canonical_smiles,standard_type")
        columns = resolve_columns(path, {"id": "id", "smiles": "smiles"})
        self.assertEqual((columns["id"], columns["smiles"]), ("molecule_chembl_id", "canonical_smiles"))
        self.assertEqual(columns["resolved"], {"id": "molecule_chembl_id", "smiles": "canonical_smiles"})

    def test_an_unknown_smiles_column_fails_with_the_columns_that_exist(self):
        path = self.write("compound,structure_smiles_v2")
        with self.assertRaises(SystemExit) as caught:
            resolve_columns(path, {"id": "id", "smiles": "smiles"})
        self.assertIn("structure_smiles_v2", str(caught.exception))

    def test_a_missing_id_column_is_tolerated_by_featurize(self):
        path = self.write("smiles")
        columns = resolve_columns(path, {"id": "id", "smiles": "smiles"})
        self.assertNotIn("id", columns)
        self.assertEqual(columns["smiles"], "smiles")

    def test_ml_train_resolves_the_id_it_never_named(self):
        # The corpus failure: `--label-id-column id` against a table that names it
        # `molecule_chembl_id`. Twelve retries said "needs 'id' and 'label' columns".
        path = self.write("molecule_chembl_id,label", row="CHEMBL1,1")
        resolved: dict = {}
        labels, _ = read_labels(path, "id", "label", resolved)
        self.assertEqual(labels, {"CHEMBL1": 1})
        self.assertEqual(resolved, {"id": "molecule_chembl_id"})

    def test_a_missing_file_fails_before_any_work(self):
        with self.assertRaises(SystemExit) as caught:
            check_input_file(os.path.join(self.tmp.name, "nope.csv"))
        self.assertIn("no such input file", str(caught.exception))

    def test_a_directory_is_not_an_input(self):
        with self.assertRaises(SystemExit) as caught:
            check_input_file(self.tmp.name)
        self.assertIn("is a directory", str(caught.exception))


if __name__ == "__main__":
    unittest.main()
