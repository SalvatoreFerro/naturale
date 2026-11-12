"""Installer tests use a temporary home; never install into the real account."""
from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("naturale_install", ROOT / "scripts/install.py")
installer = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(installer)


class InstallerTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.home = self.base / "home"
        self.home.mkdir()
        self.source = self.base / "source"
        (self.source / "references").mkdir(parents=True)
        (self.source / "scripts").mkdir()
        (self.source / "SKILL.md").write_text(
            '---\nname: naturale\ndescription: "Test locale"\n---\n\n[Regole](references/editorial.md)\n', encoding="utf-8"
        )
        for relative, text in {
            "LICENSE": "MIT test", "INSTALL.md": "Istruzioni", "requirements.txt": "Pillow>=11,<13\n",
            "references/editorial.md": "Regole", "scripts/images.py": "# test locale\n",
        }.items():
            (self.source / relative).write_text(text, encoding="utf-8")

    def target(self, host):
        return self.home / installer.HOSTS[host] / "skills" / "naturale"

    def test_installs_both_and_copies_required_files(self):
        results = installer.install(self.source, ["claude", "codex"], self.home)
        self.assertEqual([r["status"] for r in results], ["installed", "installed"])
        expected = installer._manifest(self.source)
        for host in ("claude", "codex"):
            self.assertEqual(installer._manifest(self.target(host)), expected)

    def test_real_repository_skill_passes_validation(self):
        files = installer._validate_source(ROOT / "skills/naturale")
        self.assertIn("SKILL.md", files)
        self.assertIn("references/images.md", files)

    def test_dry_run_does_not_create_any_home_entries(self):
        results = installer.install(self.source, ["codex", "claude"], self.home, dry_run=True)
        self.assertTrue(all(r["status"] == "would_install" for r in results))
        self.assertEqual(list(self.home.iterdir()), [])

    def test_identical_installation_is_idempotent(self):
        installer.install(self.source, ["codex"], self.home)
        skill = self.target("codex") / "SKILL.md"
        timestamp = skill.stat().st_mtime_ns
        results = installer.install(self.source, ["codex"], self.home)
        self.assertEqual(results[0]["status"], "already_installed")
        self.assertEqual(skill.stat().st_mtime_ns, timestamp)

    def test_conflict_in_second_host_prevents_all_changes(self):
        target = self.target("codex")
        target.mkdir(parents=True)
        (target / "mine.txt").write_text("keep me")
        with self.assertRaises(installer.InstallError):
            installer.install(self.source, ["claude", "codex"], self.home)
        self.assertFalse((self.home / ".claude").exists())
        self.assertEqual((target / "mine.txt").read_text(), "keep me")

    def test_modified_installation_is_never_overwritten(self):
        installer.install(self.source, ["claude"], self.home)
        skill = self.target("claude") / "SKILL.md"
        skill.write_text("My changes", encoding="utf-8")
        with self.assertRaises(installer.InstallError):
            installer.install(self.source, ["claude"], self.home)
        self.assertEqual(skill.read_text(), "My changes")

    def test_runtime_caches_are_not_installed_and_do_not_break_idempotence(self):
        cache = self.source / "scripts/__pycache__"
        cache.mkdir()
        (cache / "x.pyc").write_bytes(b"bytecode")
        installer.install(self.source, ["codex"], self.home)
        self.assertFalse((self.target("codex") / "scripts/__pycache__").exists())
        runtime = self.target("codex") / ".venv"
        runtime.mkdir()
        (runtime / "somefile").write_text("runtime")
        result = installer.install(self.source, ["codex"], self.home)
        self.assertEqual(result[0]["status"], "already_installed")

    def test_missing_required_source_or_reference_is_rejected(self):
        for mode in ("required", "reference"):
            with self.subTest(mode=mode):
                if mode == "required":
                    (self.source / "LICENSE").unlink()
                else:
                    (self.source / "LICENSE").write_text("MIT")
                    (self.source / "references/editorial.md").unlink()
                with self.assertRaises(installer.InstallError):
                    installer.install(self.source, ["codex"], self.home)
                self.assertEqual(list(self.home.iterdir()), [])

    def test_source_reference_cannot_escape_package(self):
        (self.base / "private.txt").write_text("private")
        with (self.source / "SKILL.md").open("a") as stream:
            stream.write("\n[Outside](../private.txt)\n")
        with self.assertRaises(installer.InstallError):
            installer.install(self.source, ["codex"], self.home)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_failure_on_second_copy_rolls_back_only_new_installations(self):
        original = installer._write_exclusive
        calls = []

        def copy(destination, files):
            calls.append(destination)
            if len(calls) == 2:
                raise OSError("Simulated failure")
            return original(destination, files)

        with patch.object(installer, "_write_exclusive", side_effect=copy):
            with self.assertRaises(installer.InstallError):
                installer.install(self.source, ["claude", "codex"], self.home)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_preexisting_identical_host_survives_failure_of_new_host(self):
        installer.install(self.source, ["claude"], self.home)
        with patch.object(installer, "_write_exclusive", side_effect=OSError("Simulated failure")):
            with self.assertRaises(installer.InstallError):
                installer.install(self.source, ["claude", "codex"], self.home)
        self.assertEqual(installer._manifest(self.target("claude")), installer._manifest(self.source))
        self.assertFalse(self.target("codex").exists())

    def test_destination_symlink_is_rejected(self):
        target = self.target("codex")
        target.parent.mkdir(parents=True)
        outside = self.base / "outside"
        outside.mkdir()
        try:
            target.symlink_to(outside, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation unavailable")
        with self.assertRaises(installer.InstallError):
            installer.install(self.source, ["codex"], self.home)
        self.assertEqual(list(outside.iterdir()), [])

    def test_source_symlink_is_rejected(self):
        outside = self.base / "private"
        outside.write_text("never copy")
        try:
            (self.source / "private").symlink_to(outside)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation unavailable")
        with self.assertRaises(installer.InstallError):
            installer.install(self.source, ["codex"], self.home)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_racing_destination_is_never_overwritten_or_deleted(self):
        original = installer._check_ancestors
        checks = []

        def check(home, destination):
            original(home, destination)
            checks.append(destination)
            if len(checks) == 2:
                destination.mkdir(parents=True)
                (destination / "concurrent.txt").write_text("concurrent installation")

        with patch.object(installer, "_check_ancestors", side_effect=check):
            with self.assertRaises(installer.InstallError):
                installer.install(self.source, ["codex"], self.home)
        self.assertEqual((self.target("codex") / "concurrent.txt").read_text(), "concurrent installation")

    @unittest.skipUnless(hasattr(os, "mkfifo"), "Unix FIFO required")
    def test_fifo_in_source_is_rejected_without_blocking(self):
        os.mkfifo(self.source / "not-a-regular-file")
        code = (
            "import importlib.util,sys; "
            "s=importlib.util.spec_from_file_location('installer',sys.argv[1]); "
            "m=importlib.util.module_from_spec(s);s.loader.exec_module(m); "
            "m._manifest(m.Path(sys.argv[2]))"
        )
        result = subprocess.run(
            [sys.executable, "-c", code, str(ROOT / "scripts/install.py"), str(self.source)],
            capture_output=True, text=True, timeout=3,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("File non regolare", result.stderr)
        self.assertEqual(list(self.home.iterdir()), [])

    def test_cli_requires_explicit_host_and_help_is_read_only(self):
        result = subprocess.run([sys.executable, str(ROOT / "scripts/install.py"), "--help"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0)
        self.assertIn("--host", result.stdout)
        missing = subprocess.run([sys.executable, str(ROOT / "scripts/install.py"), "--dry-run"], capture_output=True, text=True)
        self.assertEqual(missing.returncode, 2)


if __name__ == "__main__":
    unittest.main()
