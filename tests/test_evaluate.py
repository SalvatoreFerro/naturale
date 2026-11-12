"""Test del criterio editoriale: nessuna valutazione o API simulata come reale."""
import copy
import importlib.util
import json
import os
import stat
import subprocess
import sys
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

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


class ExtendedEvaluationTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.tmp = Path(self.directory.name)
        source = evaluate.validate_cases(ROOT / "evals/cases.jsonl")
        self.example = copy.deepcopy(next(item for item in source.values() if item["split"] == "heldout"))

    def dataset(self, count=2, provenance=None):
        rows = []
        for number in range(count):
            row = copy.deepcopy(self.example)
            row["id"] = f"case-{number:02d}"
            if provenance is not None:
                row["provenance"] = provenance
            rows.append(row)
        path = self.tmp / "cases.jsonl"
        self.write_jsonl(path, rows)
        return path

    def write_jsonl(self, path, rows):
        path.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows), encoding="utf-8")

    def pairs(self, cases):
        path = self.tmp / "pairs.jsonl"
        self.write_jsonl(path, [{"case_id": key, "model": "example-model-2026-11", "skill_version": "0.2.0",
                                 "skill_output": f"Testo A per {key}", "baseline_output": f"Testo B per {key}"}
                                for key in cases])
        return path

    def test_general_format_is_independent_of_the_80_case_pilot(self):
        path = self.dataset(2, {"kind": "synthetic"})
        cases = evaluate.validate_cases(path)
        self.assertEqual(len(cases), 2)
        with self.assertRaises(evaluate.ValidationError):
            evaluate.validate_cases(path, pilot=True)
        original = evaluate.validate_cases(ROOT / "evals/cases.jsonl", pilot=True)
        self.assertEqual(len(original), 80)

    def test_human_data_requires_explicit_consent_and_anonymization_declarations(self):
        valid = {"kind": "human_authorized", "consent": "confirmed", "anonymized": True}
        cases = evaluate.validate_cases(self.dataset(1, valid))
        self.assertEqual(cases["case-00"]["provenance"], valid)
        for invalid in ({"kind": "human_authorized"}, {**valid, "anonymized": False},
                        {"kind": "synthetic", "consent": "confirmed"}):
            with self.subTest(invalid=invalid):
                with self.assertRaises(evaluate.ValidationError):
                    evaluate.validate_cases(self.dataset(1, invalid))

    def test_small_sample_does_not_pass_even_with_unanimous_complete_reviews(self):
        cases = evaluate.validate_cases(self.dataset(2))
        path = self.tmp / "votes.jsonl"
        self.write_jsonl(path, [{"case_id": key, "reviewer_id": reviewer, "preference": "skill", "critical_error": False}
                                for key in cases for reviewer in ("one", "two")])
        result = evaluate.aggregate_votes(path, cases)
        self.assertEqual(result["case_mean_preference"], 1)
        self.assertFalse(result["sample_sufficient"])
        self.assertEqual(result["status"], "not_validated")

    def test_case_means_prevent_one_heavily_reviewed_case_from_dominating(self):
        cases = evaluate.validate_cases(self.dataset(40))
        rows = []
        for index, key in enumerate(cases):
            for reviewer in range(200 if index == 0 else 2):
                rows.append({"case_id": key, "reviewer_id": str(reviewer),
                             "preference": "skill" if index == 0 else "baseline", "critical_error": False})
        path = self.tmp / "votes.jsonl"
        self.write_jsonl(path, rows)
        result = evaluate.aggregate_votes(path, cases)
        self.assertGreater(result["vote_weighted_preference"], 0.60)
        self.assertEqual(result["case_mean_preference"], 1 / 40)
        self.assertEqual(result["status"], "not_validated")

    def test_blind_packets_are_balanced_reproducible_and_exclude_model_labels(self):
        cases = evaluate.validate_cases(self.dataset(4))
        pairs = self.pairs(cases)
        first, second = self.tmp / "one", self.tmp / "two"
        evaluate.prepare_comparison(pairs, cases, first, seed=42)
        evaluate.prepare_comparison(pairs, cases, second, seed=42)
        self.assertEqual((first / "packets.jsonl").read_bytes(), (second / "packets.jsonl").read_bytes())
        packets = [item for _, item in evaluate.read_jsonl(first / "packets.jsonl")]
        mapping = json.loads((first / "mapping-private.json").read_text())["mapping"]
        self.assertEqual(sum(item["labels"]["A"] == "skill" for item in mapping), 2)
        for packet in packets:
            self.assertEqual(set(packet), {"case_id", "instruction", "text", "A", "B", "checks"})
        self.assertEqual({item["model"] for item in mapping}, {"example-model-2026-11"})
        self.assertTrue(all(item["skill_version"] == "0.2.0" for item in mapping))

    def test_comparison_requires_complete_heldout_coverage_before_writing(self):
        cases = evaluate.validate_cases(self.dataset(2))
        pairs = self.pairs(dict(list(cases.items())[:1]))
        output = self.tmp / "comparison"
        with self.assertRaises(evaluate.ValidationError):
            evaluate.prepare_comparison(pairs, cases, output)
        self.assertFalse(output.exists())

    def test_comparison_rejects_mixed_model_versions(self):
        cases = evaluate.validate_cases(self.dataset(2))
        pairs = self.pairs(cases)
        rows = [item for _, item in evaluate.read_jsonl(pairs)]
        rows[0]["model"] = "a-different-model-version"
        self.write_jsonl(pairs, rows)
        output = self.tmp / "comparison"
        with self.assertRaises(evaluate.ValidationError):
            evaluate.prepare_comparison(pairs, cases, output)
        self.assertFalse(output.exists())

    def test_comparison_never_overwrites_existing_directory(self):
        cases = evaluate.validate_cases(self.dataset())
        output = self.tmp / "comparison"
        output.mkdir()
        sentinel = output / "private.txt"
        sentinel.write_text("keep")
        with self.assertRaises(evaluate.ValidationError):
            evaluate.prepare_comparison(self.pairs(cases), cases, output)
        self.assertEqual(sentinel.read_text(), "keep")
        self.assertEqual(list(output.iterdir()), [sentinel])

    def test_failed_comparison_write_removes_only_its_new_directory(self):
        cases = evaluate.validate_cases(self.dataset())
        pairs = self.pairs(cases)
        output = self.tmp / "comparison"
        original = evaluate._write_private
        calls = []

        def fail_second(path, text):
            calls.append(path)
            if len(calls) == 2:
                raise OSError("Simulated disk error")
            original(path, text)

        with patch.object(evaluate, "_write_private", side_effect=fail_second):
            with self.assertRaises(OSError):
                evaluate.prepare_comparison(pairs, cases, output)
        self.assertFalse(output.exists())
        self.assertTrue(pairs.exists())

    @unittest.skipUnless(os.name == "posix", "Unix permissions")
    def test_review_packets_and_private_mapping_are_private_files(self):
        cases = evaluate.validate_cases(self.dataset())
        output = self.tmp / "comparison"
        evaluate.prepare_comparison(self.pairs(cases), cases, output)
        self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o700)
        for name in ("packets.jsonl", "mapping-private.json"):
            self.assertEqual(stat.S_IMODE((output / name).stat().st_mode), 0o600)

    def test_jsonl_template_is_synthetic_and_not_presented_as_human_data(self):
        cases = evaluate.validate_cases(ROOT / "evals/real-world-template.jsonl")
        self.assertTrue(all(item["provenance"] == {"kind": "synthetic"} for item in cases.values()))
        self.assertEqual(evaluate.aggregate_votes(None, cases)["status"], "not_validated")

    def test_jsonl_accepts_utf8_bom_and_limits_reads(self):
        path = self.dataset(1)
        path.write_bytes(b"\xef\xbb\xbf" + path.read_bytes())
        self.assertEqual(len(evaluate.validate_cases(path)), 1)
        with patch.object(evaluate, "MAX_JSONL_BYTES", 16):
            with self.assertRaises(evaluate.ValidationError):
                evaluate.read_jsonl(path)

    def test_unicode_separators_inside_json_strings_are_not_record_boundaries(self):
        path = self.dataset(1)
        rows = [item for _, item in evaluate.read_jsonl(path)]
        rows[0]["text"] = "Nota\u2028aggiuntiva\u0085 " + rows[0]["text"]
        self.write_jsonl(path, rows)
        cases = evaluate.validate_cases(path)
        self.assertIn("\u2028", cases["case-00"]["text"])

    def test_jsonl_rejects_symlinks(self):
        path = self.dataset(1)
        link = self.tmp / "linked.jsonl"
        try:
            link.symlink_to(path)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation unavailable")
        with self.assertRaises(evaluate.ValidationError):
            evaluate.read_jsonl(link)

    @unittest.skipUnless(hasattr(os, "mkfifo"), "Unix FIFO required")
    def test_jsonl_rejects_fifo_without_blocking(self):
        path = self.tmp / "pipe.jsonl"
        os.mkfifo(path)
        code = (
            "import importlib.util,sys; "
            "s=importlib.util.spec_from_file_location('evaluation',sys.argv[1]); "
            "m=importlib.util.module_from_spec(s);s.loader.exec_module(m); "
            "m.read_jsonl(sys.argv[2])"
        )
        result = subprocess.run([sys.executable, "-c", code, str(ROOT / "scripts/evaluate.py"), str(path)],
                                capture_output=True, text=True, timeout=3)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("regular file", result.stderr)


if __name__ == "__main__":
    unittest.main()
