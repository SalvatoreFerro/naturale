"""Specific, value-free errors must preserve the no-publication guarantees."""
import contextlib
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

try:
    from PIL import Image
except ImportError:
    Image = None

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("typed_images", ROOT / "skills/naturale/scripts/images.py")
images = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(images)


class SafeErrorContractTests(unittest.TestCase):
    def test_known_codes_never_echo_private_error_details(self):
        codes = ("unsupported_format", "extension_mismatch", "file_too_large", "too_many_pixels",
                 "multiframe_not_supported", "output_exists", "exiftool_too_old", "verification_failed")
        for code in codes:
            with self.subTest(code=code):
                result = images._safe_error(images.ImageError("PRIVATE /home/person/location GPS=37.6", code=code))
                self.assertEqual(result["code"], code)
                self.assertNotIn("PRIVATE", json.dumps(result))
                self.assertNotIn("/home/person", json.dumps(result))
                self.assertNotIn("37.6", json.dumps(result))


@unittest.skipUnless(Image is not None and images._exiftool_runtime.exiftool_report()["compatible"],
                     "Pillow and supported ExifTool required; older tools report exiftool_too_old")
class ImageFailureTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.source = self.base / "original.png"
        Image.new("RGB", (64, 48), (200, 80, 40)).save(self.source)
        self.output = self.base / "output.png"

    def assert_failure(self, source, code):
        original = source.read_bytes()
        with self.assertRaises(images.ImageError) as caught:
            images.clean_image(source, self.output)
        self.assertEqual(images._safe_error(caught.exception)["code"], code)
        self.assertEqual(source.read_bytes(), original)
        self.assertFalse(self.output.exists())
        self.assertFalse(Path(str(self.output) + ".report.json").exists())

    def test_unsupported_webp_and_extension_mismatch_are_specific(self):
        source = self.base / "PRIVATE-source.webp"
        Image.new("RGB", (8, 8)).save(source)
        self.assert_failure(source, "unsupported_format")
        disguised = self.base / "disguised.jpg"
        disguised.write_bytes(self.source.read_bytes())
        self.assert_failure(disguised, "extension_mismatch")

    def test_size_and_pixel_limits_have_distinct_codes(self):
        with patch.object(images, "MAX_FILE_BYTES", 1):
            self.assert_failure(self.source, "file_too_large")
        with patch.object(images, "MAX_PIXELS", 1):
            self.assert_failure(self.source, "too_many_pixels")

    def test_pillow_bomb_warning_and_error_are_too_many_pixels(self):
        for limit in (2000, 1024):
            with self.subTest(limit=limit), patch.object(Image, "MAX_IMAGE_PIXELS", limit):
                self.assert_failure(self.source, "too_many_pixels")

    def test_multiframe_is_specific(self):
        source = self.base / "animation.png"
        Image.new("RGB", (8, 8), "red").save(source, save_all=True,
                                             append_images=[Image.new("RGB", (8, 8), "blue")], duration=100)
        self.assert_failure(source, "multiframe_not_supported")

    def test_output_and_report_collisions_are_specific_and_preserved(self):
        for target in (self.output, Path(str(self.output) + ".report.json")):
            with self.subTest(target=target.name):
                target.write_bytes(b"DO NOT OVERWRITE")
                with self.assertRaises(images.ImageError) as caught:
                    images.clean_image(self.source, self.output)
                self.assertEqual(images._safe_error(caught.exception)["code"], "output_exists")
                self.assertEqual(target.read_bytes(), b"DO NOT OVERWRITE")
                target.unlink()
        existing = self.base / "report.json"
        existing.write_text("private existing report", encoding="utf-8")
        with self.assertRaises(images.ImageError) as caught:
            images._save_report({}, existing)
        self.assertEqual(images._safe_error(caught.exception)["code"], "output_exists")
        self.assertEqual(existing.read_text(), "private existing report")

    def test_verification_failure_has_code_and_publishes_nothing(self):
        original_snapshot = images._snapshot
        def tamper_snapshot(path):
            result = original_snapshot(path)
            if Path(path).name == "image.png":
                result["_pixels"] = "changed"
            return result
        with patch.object(images, "_snapshot", side_effect=tamper_snapshot):
            self.assert_failure(self.source, "verification_failed")

    def test_cli_summary_is_specific_and_full_details_are_explicit(self):
        source = self.base / "PRIVATE-source.webp"
        Image.new("RGB", (8, 8)).save(source)
        stdout, stderr = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
            status = images.main(["inspect", str(source)])
        self.assertEqual(status, 1)
        report = json.loads(stderr.getvalue())
        self.assertEqual(report["error"]["code"], "unsupported_format")
        self.assertNotIn("PRIVATE", stderr.getvalue())
        self.assertNotIn(str(self.base), stderr.getvalue())
        stderr = io.StringIO()
        private_error = images.ImageError("PRIVATE /home/person/filename", code="verification_failed")
        with patch.object(images, "inspect_image", side_effect=private_error), contextlib.redirect_stderr(stderr):
            status = images.main(["inspect", str(source), "--full-report"])
        self.assertEqual(status, 1)
        self.assertIn("PRIVATE /home/person/filename", json.loads(stderr.getvalue())["error"])


if __name__ == "__main__":
    unittest.main()
