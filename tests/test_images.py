"""Behavior tests for the local image CLI; all images are temporary fixtures."""

from __future__ import annotations

import contextlib
from datetime import datetime, timedelta, timezone
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import shutil
import stat
import struct
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
import zlib

try:
    from PIL import Image, ImageCms
except ImportError:
    Image = ImageCms = None


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills" / "naturale" / "scripts" / "images.py"
EXIFTOOL = shutil.which("exiftool")
_MODULE = None


def images_module():
    global _MODULE
    if _MODULE is None:
        spec = importlib.util.spec_from_file_location("naturale_test_images", SCRIPT)
        if spec is None or spec.loader is None:
            raise AssertionError(f"Cannot load image module: {SCRIPT}")
        _MODULE = importlib.util.module_from_spec(spec)
        sys.modules[spec.name] = _MODULE
        spec.loader.exec_module(_MODULE)
    return _MODULE


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def contains_group(value, group):
    """Handle ExifTool reports with either flat or nested group dictionaries."""
    if not isinstance(value, dict):
        return False
    return any(
        group.lower() in key.lower() or contains_group(item, group)
        for key, item in value.items()
    )


@contextlib.contextmanager
def working_directory(path):
    old = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(old)


class ReportAssertions:
    def assert_report(self, report, operation, source, destination=None):
        self.assertEqual(report["schema_version"], "1.0")
        self.assertEqual(report["operation"], operation)
        for key, path in (("input", source), ("output", destination)):
            if path is None:
                self.assertIsNone(report[key])
                continue
            record = report[key]
            self.assertEqual(Path(record["path"]), Path(path).resolve())
            self.assertEqual(record["sha256"], sha256(path))
            self.assertIn(record["format"], {"PNG", "JPEG"})
            self.assertGreater(record["width"], 0)
            self.assertGreater(record["height"], 0)
        self.assertIsInstance(report["metadata"]["before"], dict)
        self.assertIsInstance(report["metadata"]["removed_groups"], list)
        for stage in ("before", "after"):
            details = report["c2pa"][stage]
            if stage == "after" and destination is None:
                self.assertIsNone(details)
                continue
            self.assertIn(
                details["embedded"],
                {"present", "not_found", "unreadable", "not_checked"},
            )
            self.assertIn(
                details["validation"],
                {"valid", "invalid", "not_checked", "unavailable"},
            )
            self.assertEqual(details["remote_manifest"], "not_fetched")
        self.assertEqual(report["invisible_watermark"], "not_checked")
        self.assertEqual(report["instagram_label"], "unknown")
        self.assertIsInstance(report["warnings"], list)


@unittest.skipUnless(Image is not None and EXIFTOOL, "Pillow and ExifTool required")
class LocalImageIntegrationTests(ReportAssertions, unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.tmp = Path(self.directory.name)
        self.images = images_module()

    def fixture(self, name="input.png", *, xmp=False, mode="RGB"):
        path = self.tmp / name
        fmt = "JPEG" if path.suffix.lower() in {".jpg", ".jpeg"} else "PNG"
        color = (55, 100, 180, 110) if mode == "RGBA" else (55, 100, 180)
        image = Image.new(mode, (43, 29), color)
        exif = Image.Exif()
        exif[0x0112] = 6
        exif[0x0131] = "Fixture generator retained in EXIF"
        profile = ImageCms.ImageCmsProfile(ImageCms.createProfile("sRGB")).tobytes()
        image.save(path, format=fmt, exif=exif, icc_profile=profile)
        if xmp:
            result = subprocess.run(
                [
                    EXIFTOOL,
                    "-config", "",
                    "-overwrite_original",
                    "-XMP:CreatorTool=AI fixture creator",
                    "-XMP-dc:Description=Description for cleanup test",
                    str(path),
                ],
                capture_output=True, text=True, check=False,
            )
            self.assertEqual(result.returncode, 0, result.stderr)
        return path

    def assert_same_image(self, before, after):
        with Image.open(before) as original, Image.open(after) as cleaned:
            original.load()
            cleaned.load()
            self.assertEqual(original.format, cleaned.format)
            self.assertEqual(original.mode, cleaned.mode)
            self.assertEqual(original.size, cleaned.size)
            self.assertEqual(original.tobytes(), cleaned.tobytes())
            self.assertEqual(original.info.get("icc_profile"), cleaned.info.get("icc_profile"))
            self.assertEqual(dict(original.getexif()), dict(cleaned.getexif()))

    def private_metadata(self, path):
        completed = subprocess.run([
            EXIFTOOL, "-config", "", "-overwrite_original",
            "-GPSLatitude=37.751", "-GPSLatitudeRef=N",
            "-GPSLongitude=14.9934", "-GPSLongitudeRef=E",
            "-EXIF:OwnerName=PRIVATE-OWNER", "-EXIF:SerialNumber=PRIVATE-SERIAL",
            "-EXIF:LensSerialNumber=PRIVATE-LENS", "-EXIF:CameraSerialNumber=PRIVATE-CAMERA",
            "-XMP-exif:GPSLatitude=37,45.06N", "-XMP-aux:OwnerName=PRIVATE-XMP-OWNER",
            "-XMP-aux:SerialNumber=PRIVATE-XMP-SERIAL", str(path),
        ], capture_output=True, text=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)

    def signed_fixture(self, private=False):
        """Create original C2PA credentials with ephemeral local keys, never fetched fixtures."""
        try:
            import c2pa
            from cryptography import x509
            from cryptography.hazmat.primitives import hashes, serialization
            from cryptography.hazmat.primitives.asymmetric import ec
            from cryptography.x509.oid import ExtendedKeyUsageOID, NameOID
        except ImportError:
            self.skipTest("Optional c2pa-python and cryptography required")
        if not hasattr(c2pa, "Context"):
            self.skipTest("A C2PA SDK with per-reader offline Context is required")
        now = datetime.now(timezone.utc)
        root_key = ec.generate_private_key(ec.SECP256R1())
        leaf_key = ec.generate_private_key(ec.SECP256R1())
        root_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Naturale test root")])
        leaf_name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "Naturale test signer")])
        root = (
            x509.CertificateBuilder()
            .subject_name(root_name).issuer_name(root_name)
            .public_key(root_key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=2))
            .add_extension(x509.BasicConstraints(ca=True, path_length=0), critical=True)
            .add_extension(x509.KeyUsage(False, False, False, False, False, True, True, False, False), critical=True)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(root_key.public_key()), critical=False)
            .sign(root_key, hashes.SHA256())
        )
        leaf = (
            x509.CertificateBuilder()
            .subject_name(leaf_name).issuer_name(root_name)
            .public_key(leaf_key.public_key()).serial_number(x509.random_serial_number())
            .not_valid_before(now - timedelta(days=1)).not_valid_after(now + timedelta(days=1))
            .add_extension(x509.BasicConstraints(ca=False, path_length=None), critical=True)
            .add_extension(x509.KeyUsage(True, True, False, False, False, False, False, False, False), critical=True)
            .add_extension(x509.ExtendedKeyUsage([ExtendedKeyUsageOID.EMAIL_PROTECTION]), critical=False)
            .add_extension(x509.AuthorityKeyIdentifier.from_issuer_public_key(root_key.public_key()), critical=False)
            .add_extension(x509.SubjectKeyIdentifier.from_public_key(leaf_key.public_key()), critical=False)
            .sign(root_key, hashes.SHA256())
        )
        chain = leaf.public_bytes(serialization.Encoding.PEM) + root.public_bytes(serialization.Encoding.PEM)
        private = leaf_key.private_bytes(
            serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
        )
        settings = c2pa.Settings()
        settings.update({
            "verify": {"remote_manifest_fetch": False, "ocsp_fetch": False},
            "builder": {"thumbnail": {"enabled": False}},
        })
        context = c2pa.Context(settings=settings)
        manifest = {
            "claim_generator_info": [{"name": "naturale-tests"}],
            "title": "Ephemeral local test fixture", "format": "image/png",
            "assertions": [{"label": "c2pa.actions", "data": {"actions": [{
                "action": "c2pa.created",
                "digitalSourceType": "http://cv.iptc.org/newscodes/digitalsourcetype/trainedAlgorithmicMedia",
            }]}}],
        }
        source = self.fixture("unsigned-for-signing.png")
        if private:
            self.private_metadata(source)
        signed = self.tmp / "signed.png"
        with c2pa.Signer.from_info(c2pa.C2paSignerInfo("es256", chain, private, None)) as signer:
            with c2pa.Builder(manifest, context=context) as builder:
                with source.open("rb") as original, signed.open("w+b") as destination:
                    builder.sign(signer, "image/png", original, destination)
        return signed

    def test_inspection_is_read_only_and_reports_unknown_detection(self):
        source = self.fixture(xmp=True)
        original = source.read_bytes()
        report = self.images.inspect_image(source)
        self.assert_report(report, "inspect", source)
        self.assertEqual(source.read_bytes(), original)
        self.assertTrue(contains_group(report["metadata"]["before"], "xmp"))
        self.assertIsNone(report["metadata"]["after"])
        self.assertIsNone(report["pixel_data_unchanged"])
        self.assertEqual(report["c2pa"]["before"]["validation"], "not_checked")
        self.assertEqual(sorted(p.name for p in self.tmp.iterdir()), [source.name])

    def test_clean_png_and_jpeg_removes_xmp_preserves_pixels_exif_and_icc(self):
        for suffix in (".png", ".jpg"):
            with self.subTest(suffix=suffix):
                source = self.fixture(f"source{suffix}", xmp=True)
                output = self.tmp / f"clean{suffix}"
                original_hash = sha256(source)
                report = self.images.clean_image(source, output)
                self.assert_report(report, "clean", source, output)
                self.assertEqual(sha256(source), original_hash)
                self.assertTrue(report["pixel_data_unchanged"])
                self.assertTrue(contains_group(report["metadata"]["before"], "xmp"))
                self.assertFalse(contains_group(report["metadata"]["after"], "xmp"))
                self.assertTrue(any("xmp" in group.lower() for group in report["metadata"]["removed_groups"]))
                self.assert_same_image(source, output)
                sidecar = Path(str(output) + ".report.json")
                self.assertEqual(json.loads(sidecar.read_text(encoding="utf-8")), report)

    def test_alpha_channel_is_preserved(self):
        source = self.fixture("alpha.png", xmp=True, mode="RGBA")
        output = self.tmp / "clean-alpha.png"
        self.images.clean_image(source, output)
        self.assert_same_image(source, output)

    def test_embedded_jumbf_container_is_removed_without_claiming_authenticity(self):
        source = self.fixture("embedded.png")

        def box(kind, payload):
            return struct.pack(">I", len(payload) + 8) + kind + payload

        # This is a JUMBF container, not a signed or trusted C2PA credential.
        description = bytes.fromhex("6332706100110010800000aa00389b71")
        description += b"\x03c2pa\x00"
        jumbf = box(b"jumb", box(b"jumd", description) + box(b"json", b'{"fixture":true}'))
        chunk = struct.pack(">I", len(jumbf)) + b"caBX" + jumbf
        chunk += struct.pack(">I", zlib.crc32(b"caBX" + jumbf) & 0xFFFFFFFF)
        data = source.read_bytes()
        # The first PNG chunk is IHDR: insert the ancillary JUMBF chunk after it.
        first_chunk_end = 8 + 12 + struct.unpack(">I", data[8:12])[0]
        source.write_bytes(data[:first_chunk_end] + chunk + data[first_chunk_end:])
        output = self.tmp / "without-jumbf.png"
        report = self.images.clean_image(source, output)
        self.assertIn(report["c2pa"]["before"]["embedded"], {"present", "unreadable"})
        self.assertEqual(report["c2pa"]["before"]["validation"], "not_checked")
        self.assertEqual(report["c2pa"]["after"]["embedded"], "not_found")
        self.assertFalse(contains_group(report["metadata"]["after"], "jumbf"))
        self.assertTrue(any("jumbf" in group.lower() for group in report["metadata"]["removed_groups"]))
        self.assert_same_image(source, output)

    def test_no_target_metadata_is_valid_noop(self):
        source = self.fixture()
        output = self.tmp / "clean.png"
        report = self.images.clean_image(source, output)
        self.assertEqual(report["metadata"]["removed_groups"], [])
        self.assertEqual(report["c2pa"]["after"]["embedded"], "not_found")
        self.assert_same_image(source, output)

    def test_existing_output_and_existing_sidecar_are_not_overwritten(self):
        source = self.fixture(xmp=True)
        for collision in ("output", "sidecar"):
            with self.subTest(collision=collision):
                output = self.tmp / f"{collision}.png"
                sidecar = Path(str(output) + ".report.json")
                existing = output if collision == "output" else sidecar
                existing.write_bytes(b"DO NOT OVERWRITE")
                with self.assertRaises(self.images.ImageError):
                    self.images.clean_image(source, output)
                self.assertEqual(existing.read_bytes(), b"DO NOT OVERWRITE")
                self.assertFalse(sidecar.exists() if collision == "output" else output.exists())

    def test_input_cannot_be_its_own_output(self):
        source = self.fixture(xmp=True)
        original = source.read_bytes()
        with self.assertRaises(self.images.ImageError):
            self.images.clean_image(source, source)
        self.assertEqual(source.read_bytes(), original)

    def test_unicode_and_option_like_input_filenames(self):
        for name in ("immagine è vulcano.png", "-overwrite_original.png"):
            with self.subTest(name=name):
                source = self.fixture(name, xmp=True)
                output = self.tmp / (source.stem + "-clean.png")
                with working_directory(self.tmp):
                    report = self.images.clean_image(Path(source.name), Path(output.name))
                self.assert_report(report, "clean", source, output)
                self.assertFalse(contains_group(report["metadata"]["after"], "xmp"))
                self.assert_same_image(source, output)

    def test_output_through_parent_alias_reports_canonical_path(self):
        source = self.fixture("source-with-alias.png", xmp=True)
        original = source.read_bytes()
        real_directory = self.tmp / "actual-output"
        real_directory.mkdir()
        alias = self.tmp / "output-alias"
        try:
            alias.symlink_to(real_directory, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Directory symlink creation unavailable")
        output = alias / "clean.png"
        report = self.images.clean_image(source, output)
        self.assert_report(report, "clean", source, output)
        self.assertEqual(Path(report["output"]["path"]), output.resolve())
        self.assertEqual(source.read_bytes(), original)
        self.assertTrue(alias.is_symlink())
        self.assertTrue((real_directory / "clean.png").is_file())
        self.assert_same_image(source, output)
        sidecar = Path(str(output) + ".report.json")
        self.assertEqual(json.loads(sidecar.read_text(encoding="utf-8")), report)

    def test_emoji_filename_and_parent_are_not_passed_to_exiftool_arguments(self):
        prepared = self.fixture("prepared-for-unicode.png", xmp=True)
        self.private_metadata(prepared)
        folder = self.tmp / "cartella riservata è 🌋"
        folder.mkdir()
        source = folder / "foto proprietà 🌈.png"
        prepared.replace(source)
        original = source.read_bytes()
        calls = []
        real_run = subprocess.run

        def ascii_arguments(command, *args, **kwargs):
            self.assertTrue(all(str(argument).isascii() for argument in command[1:]), command[1:])
            if command[-1] == "-":
                self.assertIsNotNone(kwargs.get("stdin"))
                self.assertFalse(kwargs["stdin"].closed)
            else:
                self.assertIsNotNone(kwargs.get("cwd"))
                self.assertEqual(Path(command[-1]).name, command[-1])
                if "-TagsFromFile" in command:
                    tag_source = command[command.index("-TagsFromFile") + 1]
                    self.assertTrue(tag_source.startswith("original."))
                    self.assertTrue((Path(kwargs["cwd"]) / tag_source).is_file())
            calls.append(command)
            return real_run(command, *args, **kwargs)

        with patch.object(self.images.subprocess, "run", side_effect=ascii_arguments):
            inspection = self.images.inspect_image(source)
            self.assertEqual(inspection["metadata"]["before"]["SourceFile"], str(source.resolve()))
            for profile in ("provenance", "privacy"):
                output = folder / ("copia 🌋 " + profile + ".png")
                report = self.images.clean_image(source, output, profile=profile)
                self.assert_report(report, "clean", source, output)
                self.assertEqual(report["metadata"]["after"]["SourceFile"], str(output.resolve()))
                self.assertTrue(report["pixel_data_unchanged"])
                if profile == "privacy":
                    self.assertFalse(self.images._privacy_targets(report["metadata"]["after"]))
                else:
                    self.assertFalse(self.images._groups(report["metadata"]["after"]))
        self.assertEqual(source.read_bytes(), original)
        self.assertTrue(any("-TagsFromFile" in command for command in calls))
        self.assertTrue(any(command[-1] == "-" for command in calls))

    def test_emoji_signed_image_preserves_jumbf_through_binary_stdin(self):
        prepared = self.signed_fixture(private=True)
        folder = self.tmp / "credenziali 🔏"
        folder.mkdir()
        source = folder / "origine 🌋.png"
        prepared.replace(source)
        output = folder / "copia privata 🌈.png"
        original = source.read_bytes()
        report = self.images.clean_image(source, output, profile="privacy")
        self.assertTrue(report["c2pa_container_unchanged"])
        self.assertEqual(report["c2pa"]["after"]["embedded"], "present")
        self.assertEqual(self.images._jumbf_digest(source, required=True),
                         self.images._jumbf_digest(output, required=True))
        self.assertEqual(source.read_bytes(), original)

    def test_actual_format_and_extension_must_match(self):
        source = self.fixture("actual.jpg")
        mismatch = self.tmp / "disguised.png"
        mismatch.write_bytes(source.read_bytes())
        with self.assertRaises(self.images.ImageError):
            self.images.inspect_image(mismatch)

    def test_output_extension_cannot_request_silent_format_conversion(self):
        source = self.fixture("source.png")
        output = self.tmp / "wrong-format.jpg"
        with self.assertRaises(self.images.ImageError):
            self.images.clean_image(source, output)
        self.assertFalse(output.exists())

    def test_unsupported_formats_and_corrupt_files_are_rejected(self):
        unsupported = self.tmp / "image.gif"
        Image.new("RGB", (4, 4)).save(unsupported)
        corrupt = self.tmp / "broken.png"
        corrupt.write_bytes(b"\x89PNG\r\n\x1a\ntruncated image")
        for source in (unsupported, corrupt, self.tmp / "missing.png"):
            with self.subTest(source=source.name):
                with self.assertRaises(self.images.ImageError):
                    self.images.inspect_image(source)

    def test_animated_png_is_rejected(self):
        source = self.tmp / "animation.png"
        first = Image.new("RGB", (8, 8), "red")
        second = Image.new("RGB", (8, 8), "blue")
        first.save(source, save_all=True, append_images=[second], duration=100, loop=0)
        with self.assertRaises(self.images.ImageError):
            self.images.inspect_image(source)

    def test_cli_inspect_and_clean_emit_json(self):
        source = self.fixture("cli.png", xmp=True)
        output = self.tmp / "cli-clean.png"
        for arguments, operation in (
            (["inspect", str(source), "--full-report"], "inspect"),
            (["clean", str(source), "--output", str(output), "--full-report"], "clean"),
        ):
            with self.subTest(operation=operation):
                completed = subprocess.run(
                    [sys.executable, str(SCRIPT), *arguments],
                    capture_output=True, text=True, check=False,
                )
                self.assertEqual(completed.returncode, 0, completed.stderr)
                report = json.loads(completed.stdout)
                self.assert_report(report, operation, source, output if operation == "clean" else None)

    def test_optional_c2pa_adapter_disables_remote_manifest_and_ocsp_fetch(self):
        source = self.fixture("offline.png")
        configured = {}
        readers = []

        class Settings:
            def update(self, values):
                configured.update(values)

        class Context:
            def __init__(self, settings=None):
                self.settings = settings

        class Reader:
            def __init__(inner, path, context=None):
                self.assertIsNotNone(context)
                self.assertIs(configured["verify"]["remote_manifest_fetch"], False)
                self.assertIs(configured["verify"]["ocsp_fetch"], False)
                readers.append(path)

            def __enter__(inner):
                return inner

            def __exit__(inner, *_):
                return False

            def json(inner):
                return '{"validation_status": []}'

        sdk = SimpleNamespace(Settings=Settings, Context=Context, Reader=Reader)
        real_import = self.images.importlib.import_module

        def import_sdk(name, *args, **kwargs):
            return sdk if name == "c2pa" else real_import(name, *args, **kwargs)

        with patch.object(self.images.importlib, "import_module", side_effect=import_sdk):
            report = self.images.inspect_image(source, validate_c2pa=True)
        self.assertEqual(readers, [str(source.resolve())])
        self.assertEqual(report["c2pa"]["before"]["remote_manifest"], "not_fetched")

    def test_real_optional_sdk_on_unsigned_image_does_not_claim_valid_signature(self):
        try:
            import c2pa  # noqa: F401 - this test requires the optional real SDK
        except ImportError:
            self.skipTest("Optional c2pa-python required")
        source = self.fixture("unsigned.png")
        report = self.images.inspect_image(source, validate_c2pa=True)
        self.assertEqual(report["c2pa"]["before"]["embedded"], "not_found")
        self.assertEqual(report["c2pa"]["before"]["validation"], "not_checked")
        self.assertEqual(report["c2pa"]["before"]["remote_manifest"], "not_fetched")

    def test_real_signed_c2pa_is_valid_but_not_implicitly_trusted_and_can_be_cleaned(self):
        source = self.signed_fixture()
        output = self.tmp / "signed-clean.png"
        report = self.images.clean_image(source, output, validate_c2pa=True)
        self.assertEqual(report["c2pa"]["before"]["embedded"], "present")
        self.assertEqual(report["c2pa"]["before"]["validation"], "valid")
        self.assertNotEqual(report["c2pa"]["before"].get("signer_trust"), "trusted")
        self.assertEqual(report["c2pa"]["after"]["embedded"], "not_found")
        self.assertEqual(report["c2pa"]["after"]["validation"], "not_checked")
        self.assert_same_image(source, output)

    def test_real_c2pa_hash_mismatch_is_invalid_although_png_still_decodes(self):
        source = self.signed_fixture()
        data = source.read_bytes()
        chunks = []
        offset = 8
        while offset < len(data):
            size = struct.unpack(">I", data[offset:offset + 4])[0]
            kind = data[offset + 4:offset + 8]
            payload = data[offset + 8:offset + 8 + size]
            chunks.append((kind, payload))
            offset += size + 12
        pixels = bytearray(zlib.decompress(b"".join(payload for kind, payload in chunks if kind == b"IDAT")))
        pixels[1] ^= 1
        replacement = zlib.compress(pixels)
        rebuilt = bytearray(data[:8])
        replaced = False
        for kind, payload in chunks:
            if kind == b"IDAT":
                if replaced:
                    continue
                payload = replacement
                replaced = True
            rebuilt.extend(struct.pack(">I", len(payload)) + kind + payload)
            rebuilt.extend(struct.pack(">I", zlib.crc32(kind + payload) & 0xFFFFFFFF))
        tampered = self.tmp / "tampered.png"
        tampered.write_bytes(rebuilt)
        with Image.open(tampered) as readable:
            readable.load()
        report = self.images.inspect_image(tampered, validate_c2pa=True)
        self.assertEqual(report["c2pa"]["before"]["embedded"], "present")
        self.assertEqual(report["c2pa"]["before"]["validation"], "invalid")
        self.assertEqual(report["c2pa"]["before"]["remote_manifest"], "not_fetched")

    def test_missing_optional_c2pa_dependency_does_not_break_inspection(self):
        source = self.fixture("without-sdk.png")
        real_import = self.images.importlib.import_module

        def without_sdk(name, *args, **kwargs):
            if name == "c2pa":
                raise ImportError("Optional SDK intentionally unavailable")
            return real_import(name, *args, **kwargs)

        with patch.object(self.images.importlib, "import_module", side_effect=without_sdk):
            report = self.images.inspect_image(source, validate_c2pa=True)
        self.assertEqual(report["c2pa"]["before"]["validation"], "unavailable")
        self.assertTrue(report["warnings"])

    def test_incomplete_sdk_results_cannot_imply_a_valid_signature(self):
        source = self.fixture("incomplete-c2pa-report.png")
        real_import = self.images.importlib.import_module
        for response in ({}, {"validation_state": "Valid", "active_manifest": "missing", "manifests": {}}):
            with self.subTest(response=response):
                settings = MagicMock()
                reader = MagicMock()
                reader.return_value.__enter__.return_value.json.return_value = json.dumps(response)
                sdk = SimpleNamespace(Settings=lambda: settings, Context=lambda settings: object(), Reader=reader)

                def import_sdk(name, *args, **kwargs):
                    return sdk if name == "c2pa" else real_import(name, *args, **kwargs)

                with patch.object(self.images.importlib, "import_module", side_effect=import_sdk):
                    report = self.images.inspect_image(source, validate_c2pa=True)
                self.assertEqual(report["c2pa"]["before"]["validation"], "not_checked")

    @unittest.skipUnless(os.name == "posix", "Unix file permissions")
    def test_published_image_and_report_are_private_to_the_user(self):
        source = self.fixture("private-input.png", xmp=True)
        output = self.tmp / "private-output.png"
        previous_umask = os.umask(0)
        try:
            self.images.clean_image(source, output)
        finally:
            os.umask(previous_umask)
        self.assertEqual(stat.S_IMODE(output.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(Path(str(output) + ".report.json").stat().st_mode), 0o600)

    def test_exiftool_write_failure_publishes_nothing(self):
        source = self.fixture("write-fails.png", xmp=True)
        output = self.tmp / "must-not-exist.png"
        original = source.read_bytes()
        real_run = subprocess.run

        def fail_write(command, *args, **kwargs):
            if "-XMP:all=" in command:
                return subprocess.CompletedProcess(command, 1, "", "Simulated write failure")
            return real_run(command, *args, **kwargs)

        with patch.object(self.images.subprocess, "run", side_effect=fail_write):
            with self.assertRaises(self.images.ImageError):
                self.images.clean_image(source, output)
        self.assertEqual(source.read_bytes(), original)
        self.assertFalse(output.exists())
        self.assertFalse(Path(str(output) + ".report.json").exists())
        self.assertEqual(sorted(self.tmp.iterdir()), [source])

    def test_pixel_verification_failure_publishes_nothing(self):
        source = self.fixture("verify-fails.png", xmp=True)
        output = self.tmp / "must-not-be-published.png"
        original = source.read_bytes()
        real_run = subprocess.run

        def corrupt_after_write(command, *args, **kwargs):
            result = real_run(command, *args, **kwargs)
            if "-XMP:all=" in command and result.returncode == 0:
                temporary = Path(kwargs.get("cwd", Path.cwd())) / command[-1]
                with Image.open(temporary) as image:
                    image.load()
                    image.putpixel((0, 0), (255, 0, 0))
                    image.save(temporary)
            return result

        with patch.object(self.images.subprocess, "run", side_effect=corrupt_after_write):
            with self.assertRaises(self.images.ImageError):
                self.images.clean_image(source, output)
        self.assertEqual(source.read_bytes(), original)
        self.assertFalse(output.exists())
        self.assertFalse(Path(str(output) + ".report.json").exists())
        self.assertEqual(sorted(self.tmp.iterdir()), [source])

    def test_privacy_removes_only_selected_identifiers_and_preserves_rendering(self):
        for suffix in (".png", ".jpg"):
            with self.subTest(suffix=suffix):
                source = self.fixture("personal" + suffix, xmp=True)
                self.private_metadata(source)
                original = source.read_bytes()
                output = self.tmp / ("privacy-copy" + suffix)
                report = self.images.clean_image(source, output, profile="privacy")
                self.assertEqual(source.read_bytes(), original)
                self.assertTrue(self.images._privacy_targets(report["metadata"]["before"]))
                self.assertFalse(self.images._privacy_targets(report["metadata"]["after"]))
                self.assertTrue(report["metadata"]["removed_tags"])
                self.assertIn("GPS", report["metadata"]["removed_groups"])
                self.assertEqual(report["metadata"]["after"]["XMP-xmp:CreatorTool"], "AI fixture creator")
                with Image.open(source) as before, Image.open(output) as after:
                    self.assertEqual(before.tobytes(), after.tobytes())
                    self.assertEqual(before.info["icc_profile"], after.info["icc_profile"])
                    self.assertEqual(after.getexif()[0x0112], 6)
                    self.assertEqual(after.getexif()[0x0131], before.getexif()[0x0131])
                    self.assertEqual(self.images._exif_without_private(self.images._exif_snapshot(before)),
                                     self.images._exif_snapshot(after))

    def test_privacy_preserves_signed_c2pa_container_and_reports_limitations(self):
        source = self.signed_fixture(private=True)
        original = source.read_bytes()
        output = self.tmp / "signed-privacy.png"
        report = self.images.clean_image(source, output, validate_c2pa=True, profile="privacy")
        self.assertEqual(source.read_bytes(), original)
        self.assertEqual(report["c2pa"]["before"]["validation"], "valid")
        self.assertEqual(report["c2pa"]["after"]["embedded"], "present")
        self.assertTrue(report["c2pa_container_unchanged"])
        self.assertEqual(self.images._jumbf_digest(source), self.images._jumbf_digest(output))
        self.assertFalse(self.images._privacy_targets(report["metadata"]["after"]))
        summary = self.images.summarize_report(report)
        self.assertIn("retained_credentials_may_contain_personal_data", summary["warnings"])
        self.assertIn("c2pa_may_be_invalidated", summary["warnings"])
        self.assertIn("targeted_privacy_cleanup_not_anonymization", summary["warnings"])

    def test_privacy_refuses_to_certify_preservation_when_jumbf_extraction_is_empty(self):
        source = self.signed_fixture(private=True)
        output = self.tmp / "unverifiable-privacy.png"
        original = source.read_bytes()
        real_run = subprocess.run

        def omit_binary_data(command, *args, **kwargs):
            if "-b" in command and "-JUMBF" in command:
                return subprocess.CompletedProcess(command, 0, b"", b"")
            return real_run(command, *args, **kwargs)

        with patch.object(self.images.subprocess, "run", side_effect=omit_binary_data):
            with self.assertRaises(self.images.ImageError):
                self.images.clean_image(source, output, profile="privacy")
        self.assertEqual(source.read_bytes(), original)
        self.assertFalse(output.exists())
        self.assertFalse(Path(str(output) + ".report.json").exists())

    def test_default_cli_summary_hides_values_paths_and_raw_sdk_warnings(self):
        source = self.fixture("personal-values.png", xmp=True)
        self.private_metadata(source)
        completed = subprocess.run([sys.executable, str(SCRIPT), "inspect", str(source)],
                                   capture_output=True, text=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        summary = json.loads(completed.stdout)
        self.assertEqual(summary["detail"], "summary")
        self.assertEqual(summary["input"]["name"], source.name)
        for sensitive in ("PRIVATE-OWNER", "PRIVATE-SERIAL", "37.751", str(self.tmp), "sha256"):
            self.assertNotIn(sensitive, completed.stdout)
        full = self.images.inspect_image(source)
        full["c2pa"]["before"]["validation_details"] = {"claim": "SENSITIVE-CLAIM"}
        full["warnings"].append("PRIVATE-RAW-WARNING " + str(self.tmp))
        shown = json.dumps(self.images.summarize_report(full))
        self.assertNotIn("SENSITIVE-CLAIM", shown)
        self.assertNotIn("PRIVATE-RAW-WARNING", shown)

    def test_inspect_can_save_full_local_report_without_exposing_values(self):
        source = self.fixture("save-report.png", xmp=True)
        self.private_metadata(source)
        report_path = self.tmp / "private-report.json"
        completed = subprocess.run([sys.executable, str(SCRIPT), "inspect", str(source),
                                    "--report", str(report_path)], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        self.assertEqual(json.loads(completed.stdout)["report_file"], report_path.name)
        self.assertNotIn("PRIVATE-OWNER", completed.stdout)
        self.assertIn("PRIVATE-OWNER", report_path.read_text())
        if os.name == "posix":
            self.assertEqual(stat.S_IMODE(report_path.stat().st_mode), 0o600)
        original_report = report_path.read_bytes()
        repeated = subprocess.run([sys.executable, str(SCRIPT), "inspect", str(source),
                                   "--report", str(report_path)], capture_output=True, text=True)
        self.assertNotEqual(repeated.returncode, 0)
        self.assertEqual(report_path.read_bytes(), original_report)
        self.assertNotIn(str(self.tmp), repeated.stderr)

    def test_default_clean_summary_keeps_full_sidecar_local(self):
        source = self.fixture("summary-clean.png", xmp=True)
        self.private_metadata(source)
        output = self.tmp / "summary-copy.png"
        completed = subprocess.run([sys.executable, str(SCRIPT), "clean", str(source),
                                    "--output", str(output), "--profile", "privacy"],
                                   capture_output=True, text=True, check=False)
        self.assertEqual(completed.returncode, 0, completed.stderr)
        summary = json.loads(completed.stdout)
        self.assertEqual(summary["profile"], "privacy")
        self.assertNotIn("PRIVATE-OWNER", completed.stdout)
        self.assertNotIn(str(self.tmp), completed.stdout)
        full = json.loads(Path(str(output) + ".report.json").read_text())
        self.assertEqual(full["metadata"]["before"]["ExifIFD:OwnerName"], "PRIVATE-OWNER")

    def test_batch_continues_after_corrupt_files_and_skips_nested_images(self):
        inputs = self.tmp / "inputs"
        inputs.mkdir()
        output = self.tmp / "copies"
        a = self.fixture("inputs/a.jpg", xmp=True)
        b = self.fixture("inputs/b.png", xmp=True)
        (inputs / "broken.png").write_bytes(b"not a png")
        (inputs / "notes.txt").write_text("not an image")
        (inputs / "nested").mkdir()
        self.fixture("inputs/nested/hidden.png", xmp=True)
        original = {p.name: sha256(p) for p in (a, b)}
        report = self.images.batch_images(inputs, output)
        self.assertEqual(report["total"], 3)
        self.assertEqual(report["success"], 2)
        self.assertEqual(report["failed"], 1)
        self.assertEqual([r["input_name"] for r in report["results"]], ["a.jpg", "b.png", "broken.png"])
        self.assertFalse((output / "hidden-clean.png").exists())
        self.assertTrue((output / "a-clean.jpg").exists())
        self.assertTrue((output / "b-clean.png.report.json").exists())
        self.assertNotIn(str(self.tmp), json.dumps(report))
        for p in (a, b):
            self.assertEqual(sha256(p), original[p.name])

    def test_batch_dry_run_creates_no_output_and_collisions_are_not_overwritten(self):
        inputs = self.tmp / "source-folder"
        inputs.mkdir()
        self.fixture("source-folder/a.png", xmp=True)
        self.fixture("source-folder/b.png", xmp=True)
        self.private_metadata(inputs / "a.png")
        output = self.tmp / "planned-folder"
        report = self.images.batch_images(inputs, output, profile="privacy", dry_run=True)
        self.assertEqual(report["planned"], 2)
        self.assertFalse(output.exists())
        self.assertEqual(report["results"][0]["plan"]["profile"], "privacy")
        self.assertGreater(report["results"][0]["plan"]["targeted_tag_count"], 0)
        self.assertIn("GPS", report["results"][0]["plan"]["groups_to_remove"])
        output.mkdir()
        existing = output / "a-privacy.png"
        existing.write_bytes(b"preexisting output")
        report = self.images.batch_images(inputs, output, profile="privacy")
        self.assertEqual(report["failed"], 1)
        self.assertEqual(report["success"], 1)
        self.assertEqual(existing.read_bytes(), b"preexisting output")

    def test_batch_refuses_symlink_files_without_reading_their_targets(self):
        inputs = self.tmp / "links"
        inputs.mkdir()
        outside = self.fixture("outside.png", xmp=True)
        linked = inputs / "linked.png"
        try:
            linked.symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation unavailable")
        original = outside.read_bytes()
        report = self.images.batch_images(inputs, self.tmp / "link-results")
        self.assertEqual(report["failed"], 1)
        self.assertEqual(report["success"], 0)
        self.assertEqual(outside.read_bytes(), original)
        self.assertNotIn(str(outside), json.dumps(report))

    def test_batch_cli_returns_failure_when_one_file_fails_without_raw_error_paths(self):
        inputs = self.tmp / "mixed-cli"
        inputs.mkdir()
        self.fixture("mixed-cli/good.png", xmp=True)
        (inputs / "bad.png").write_bytes(b"broken")
        completed = subprocess.run([sys.executable, str(SCRIPT), "batch", str(inputs),
                                    "--output-dir", str(self.tmp / "mixed-results")],
                                   capture_output=True, text=True, check=False)
        self.assertEqual(completed.returncode, 1, completed.stderr)
        result = json.loads(completed.stdout)
        self.assertEqual(result["success"], 1)
        self.assertEqual(result["failed"], 1)
        self.assertNotIn(str(self.tmp), completed.stdout)
        self.assertNotIn("Traceback", completed.stdout + completed.stderr)


class ImageDependencyAndCliTests(unittest.TestCase):
    def test_missing_publish_source_does_not_reserve_an_empty_destination(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "missing-source.png"
            destination = Path(directory) / "no-residue.png"
            with self.assertRaises(OSError):
                images_module()._publish_exclusive(source, destination)
            self.assertFalse(destination.exists())

    def test_missing_exiftool_is_a_clear_cli_error(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "input.png"
            if Image is None:
                self.skipTest("Pillow required to create test image")
            Image.new("RGB", (3, 3)).save(source)
            env = dict(os.environ, PATH="")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), "inspect", str(source)],
                capture_output=True, text=True, env=env, check=False,
            )
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("exiftool", result.stderr.lower())
            self.assertNotIn("Traceback", result.stderr)

    def test_cli_usage_error_is_not_a_python_traceback(self):
        result = subprocess.run(
            [sys.executable, str(SCRIPT), "clean"],
            capture_output=True, text=True, check=False,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
