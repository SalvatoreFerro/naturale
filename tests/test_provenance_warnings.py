"""Retained information must be reported without silently broadening cleanup."""
import importlib.util
import json
from pathlib import Path
import tempfile
import unittest

try:
    from PIL import Image
    from PIL.PngImagePlugin import PngInfo
except ImportError:
    Image = None

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("warnings_images", ROOT / "skills/naturale/scripts/images.py")
images = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(images)


@unittest.skipUnless(Image is not None and images._exiftool_runtime.exiftool_report()["compatible"],
                     "Pillow and supported ExifTool required; old tools fail with exiftool_too_old")
class ProvenanceWarningTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()

    def assert_warning(self, report, code):
        self.assertIn(code, report["warnings"])
        self.assertIn(code, images.summarize_report(report)["warnings"])

    def test_plain_png_reports_nothing_removed(self):
        source, output = self.base / "plain.png", self.base / "plain-clean.png"
        Image.new("RGB", (64, 48)).save(source)
        original = source.read_bytes()
        report = images.clean_image(source, output)
        self.assert_warning(report, "nothing_removed")
        self.assertEqual(report["metadata"]["removed_groups"], [])
        self.assertEqual(source.read_bytes(), original)
        self.assertNotIn("generation_text_retained", report["warnings"])

    def test_all_png_text_encodings_are_retained_and_reported(self):
        variants = (("parameters", "text", False), ("prompt", "text", True),
                    ("workflow", "itxt", False), ("Description", "itxt", True),
                    ("Comment", "text", False), ("arbitrary-encoder-key", "text", True))
        for index, (key, kind, compressed) in enumerate(variants):
            with self.subTest(key=key, compressed=compressed):
                source, output = self.base / f"text{index}.png", self.base / f"text{index}-clean.png"
                info = PngInfo()
                value = "prompt di prova, Steps: 30, Seed: 12345, Model: sdxl"
                if kind == "itxt":
                    info.add_itxt(key, value, zip=compressed)
                else:
                    info.add_text(key, value, zip=compressed)
                Image.new("RGB", (64, 48)).save(source, pnginfo=info)
                original = source.read_bytes()
                report = images.clean_image(source, output)
                self.assert_warning(report, "generation_text_retained")
                self.assert_warning(report, "nothing_removed")
                with Image.open(output) as image:
                    self.assertEqual(image.text[key], value)
                self.assertEqual(source.read_bytes(), original)
                self.assertNotIn(value, json.dumps(images.summarize_report(report)))
                self.assertNotIn("12345", json.dumps(images.summarize_report(report)))

    def test_jpeg_comment_is_retained_and_reported(self):
        source, output = self.base / "comment.jpg", self.base / "comment-clean.jpg"
        Image.new("RGB", (64, 48)).save(source)
        images._exiftool("-overwrite_original", "-Comment=private prompt, seed 12345", source.name, cwd=self.base)
        report = images.clean_image(source, output)
        self.assert_warning(report, "generation_text_retained")
        self.assertEqual(report["metadata"]["after"]["File:Comment"], "private prompt, seed 12345")
        self.assertNotIn("private prompt", json.dumps(images.summarize_report(report)))

    def test_xmp_removal_reports_retained_gps_without_noop_warning(self):
        source, output = self.base / "gps.jpg", self.base / "gps-clean.jpg"
        Image.new("RGB", (64, 48)).save(source)
        images._exiftool("-overwrite_original", "-XMP:CreatorTool=fixture", "-GPSLatitude=37.6",
                         "-GPSLatitudeRef=N", "-GPSLongitude=15.0", "-GPSLongitudeRef=E", source.name, cwd=self.base)
        report = images.clean_image(source, output)
        self.assert_warning(report, "gps_retained")
        self.assertIn("XMP", report["metadata"]["removed_groups"])
        self.assertTrue(any(key.startswith("GPS:") for key in report["metadata"]["after"]))
        self.assertNotIn("nothing_removed", report["warnings"])
        summary = json.dumps(images.summarize_report(report))
        self.assertNotIn("37.6", summary)
        self.assertNotIn("15.0", summary)


if __name__ == "__main__":
    unittest.main()
