"""Test del criterio editoriale: nessuna valutazione o API simulata come reale."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("naturale_evaluate", ROOT / "scripts/evaluate.py")
evaluate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(evaluate)


class EvaluationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.cases = evaluate.validate_cases(ROOT / "evals/cases.jsonl")
        cls.heldout = [c for c, item in cls.cases.items() if item["split"] == "heldout"]

    def votes(self, preferences=None, critical=False):
        rows = []
        for i, case in enumerate(self.heldout):
            for reviewer in ("a", "b"):
                rows.append({"case_id": case, "reviewer_id": reviewer,
                             "preference": preferences[i] if preferences else "skill",
                             "critical_error": critical and not rows})
        return rows

    def aggregate(self, rows):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "votes.jsonl"
            path.write_text("\n".join(json.dumps(row) for row in rows), encoding="utf-8")
            return evaluate.aggregate_votes(path, self.cases)

    def test_dataset_is_complete_but_without_reviews_is_not_validated(self):
        self.assertEqual(len(self.cases), 80)
        result = evaluate.aggregate_votes(None, self.cases)
        self.assertEqual(result["status"], "not_validated")
        self.assertIsNone(result["skill_preference"])
        self.assertEqual(len(result["cases_needing_reviews"]), 40)

    def test_full_review_coverage_and_high_preference_pass(self):
        result = self.aggregate(self.votes())
        self.assertEqual(result["status"], "passed")
        self.assertEqual(result["n_ratings"], 80)
        self.assertEqual(result["n_cases"], 40)

    def test_ties_count_half_and_threshold_is_strict(self):
        result = self.aggregate(self.votes(["skill"] * 8 + ["tie"] * 32))
        self.assertAlmostEqual(result["skill_preference"], 0.6)
        self.assertEqual(result["status"], "not_validated")

    def test_one_critical_error_blocks_passing(self):
        result = self.aggregate(self.votes(critical=True))
        self.assertEqual(result["critical_errors"], 1)
        self.assertEqual(result["status"], "not_validated")

    def test_incomplete_coverage_blocks_passing(self):
        result = self.aggregate(self.votes()[:-1])
        self.assertEqual(result["status"], "not_validated")
        self.assertEqual(len(result["cases_needing_reviews"]), 1)

    def test_duplicate_reviewer_and_unknown_case_are_rejected(self):
        rows = self.votes()
        with self.assertRaises(evaluate.ValidationError):
            self.aggregate(rows + [rows[0]])
        rows[0] = {**rows[0], "case_id": "does-not-exist"}
        with self.assertRaises(evaluate.ValidationError):
            self.aggregate(rows)


if __name__ == "__main__":
    unittest.main()
