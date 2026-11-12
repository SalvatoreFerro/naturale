"""CLI JSON remains UTF-8 even when a Windows-style pipe encoding is selected."""
import json
import importlib.util
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
_runtime_spec = importlib.util.spec_from_file_location("unicode_exiftool_runtime", ROOT / "skills/naturale/scripts/exiftool_runtime.py")
_runtime = importlib.util.module_from_spec(_runtime_spec)
_runtime_spec.loader.exec_module(_runtime)


class UnicodeCliTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.base = Path(self.tmp.name).resolve()
        self.environment = {**os.environ, "PYTHONIOENCODING": "cp1252"}

    def run_cli(self, relative, *args):
        return subprocess.run(
            [sys.executable, str(ROOT / relative), *map(str, args)],
            env=self.environment, capture_output=True, encoding="utf-8", timeout=30,
        )

    def test_profile_cli_preserves_unicode_outside_legacy_encoding(self):
        profile = {"register": "cordiale 😀", "conciseness": "più breve"}
        source = self.base / "profilo.json"
        source.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
        result = self.run_cli("skills/naturale/scripts/text.py", "profiles", "create", "lavoro",
                              "--from-json", source, "--directory", self.base / "profiles")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["register"], profile["register"])

    def test_diff_and_audit_cli_are_utf8(self):
        source, revision = self.base / "source.txt", self.base / "revision.txt"
        source.write_text("Potremmo consegnare 12 unità 😀.", encoding="utf-8")
        revision.write_text("Consegneremo 13 unità 😀.", encoding="utf-8")
        result = self.run_cli("skills/naturale/scripts/text.py", "audit", "--source", source,
                              "--revision", revision, "--diff")
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertIn("unità 😀", json.loads(result.stdout)["diff"])

    def test_evaluation_error_json_handles_unicode_paths(self):
        result = self.run_cli("scripts/evaluate.py", "--validate-cases", self.base / "assente-😀.jsonl")
        self.assertEqual(result.returncode, 2, result.stderr)
        self.assertIn("😀", json.loads(result.stderr)["error"])

    @unittest.skipUnless(_runtime.exiftool_report()["compatible"], "Supported ExifTool required; exiftool_too_old otherwise")
    def test_image_summary_preserves_unicode_basename(self):
        from PIL import Image
        source = self.base / "foto-😀.png"
        Image.new("RGB", (4, 4), "red").save(source)
        result = self.run_cli("skills/naturale/scripts/images.py", "inspect", source)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["input"]["name"], source.name)


if __name__ == "__main__":
    unittest.main()
