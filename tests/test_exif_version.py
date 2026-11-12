"""The oldest supported ExifTool must be enforced before image publication."""
import importlib.util
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


doctor = load("version_doctor", "scripts/doctor.py")
images = load("version_images", "skills/naturale/scripts/images.py")


class ExifVersionTests(unittest.TestCase):
    def test_doctor_distinguishes_present_from_compatible(self):
        for version, compatible in (("12.76", False), ("13.59", False), ("13.60", True), ("13.63", True)):
            with self.subTest(version=version):
                with patch.object(doctor.shutil, "which", return_value="exiftool"), patch.object(
                        doctor.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, version + "\n", "")):
                    report = doctor._exiftool_report()
                self.assertTrue(report["available"])
                self.assertIs(report["compatible"], compatible)
                self.assertEqual(report["minimum_version"], "13.60")
                self.assertEqual(report["problem"], None if compatible else "exiftool_too_old")

    def test_doctor_never_marks_old_tool_images_ready(self):
        with tempfile.TemporaryDirectory() as directory:
            with patch.object(doctor.shutil, "which", return_value="exiftool"), patch.object(
                    doctor.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "12.76\n", "")), patch.object(
                    doctor.metadata, "version", return_value="12.3.0"):
                report = doctor.doctor(home=directory)
            self.assertFalse(report["images_ready"])
            self.assertEqual(report["dependencies"]["exiftool"]["problem"], "exiftool_too_old")

    def test_old_tool_fails_before_reading_or_publishing_anything(self):
        with tempfile.TemporaryDirectory() as directory:
            source, output = Path(directory) / "input.png", Path(directory) / "output.png"
            source.write_bytes(b"not even decoded with unsupported tooling")
            with patch.object(images.shutil, "which", return_value="exiftool"), patch.object(
                    images.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "12.76\n", "")):
                for operation in (lambda: images.inspect_image(source), lambda: images.clean_image(source, output),
                                  lambda: images.batch_images(directory, Path(directory) / "out")):
                    with self.subTest(operation=operation):
                        with self.assertRaises(images.ImageError) as caught:
                            operation()
                        self.assertEqual(images._safe_error(caught.exception)["code"], "exiftool_too_old")
            self.assertEqual(source.read_bytes(), b"not even decoded with unsupported tooling")
            self.assertEqual(sorted(p.name for p in Path(directory).iterdir()), ["input.png"])

    def test_minimum_is_defined_in_one_shared_runtime_module(self):
        runtime = load("shared_runtime", "skills/naturale/scripts/exiftool_runtime.py")
        self.assertEqual(runtime.MIN_EXIFTOOL_VERSION, (13, 60))
        self.assertEqual(images._exiftool_runtime.__file__, doctor._exiftool_runtime.__file__)


if __name__ == "__main__":
    unittest.main()
