"""Installer tests use a temporary home; never install into the real account."""
from __future__ import annotations

import importlib.util
import json
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
        self.base = Path(self.directory.name).resolve()
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

    def new_version(self, version="0.2.0", text="Nuove regole"):
        (self.source / "VERSION").write_text(version + "\n", encoding="utf-8")
        (self.source / "references/editorial.md").write_text(text, encoding="utf-8")

    def test_receipt_contains_version_hashes_and_no_private_paths(self):
        self.new_version()
        installer.install(self.source, ["codex"], self.home)
        path = self.target("codex") / installer.RECEIPT
        receipt = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual(receipt["schema_version"], "1.0")
        self.assertEqual(receipt["version"], "0.2.0")
        self.assertEqual(receipt["files"], installer._hashes(installer._manifest(self.source)))
        self.assertNotIn(str(self.home), path.read_text())
        if os.name == "posix":
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_update_keeps_complete_backup_and_rollback_keeps_newer_backup(self):
        installer.install(self.source, ["codex"], self.home)
        old = installer._manifest(self.target("codex"))
        cache = self.target("codex") / "scripts/__pycache__"
        cache.mkdir()
        (cache / "old.pyc").write_bytes(b"old cache")
        self.new_version()
        result = installer.install(self.source, ["codex"], self.home, update=True)[0]
        self.assertEqual(result["status"], "updated")
        backup = Path(result["backup_path"])
        self.assertEqual(installer._manifest(backup / "skill"), old)
        self.assertTrue((backup / "skill/scripts/__pycache__/old.pyc").is_file())
        self.assertEqual(installer._manifest(self.target("codex")), installer._manifest(self.source))
        restored = installer.rollback(backup, "codex", home=self.home)
        self.assertEqual(restored["status"], "rolled_back")
        self.assertEqual(installer._manifest(self.target("codex")), old)
        self.assertEqual(installer._manifest(Path(restored["backup_path"]) / "skill"), installer._manifest(self.source))
        self.assertTrue(backup.is_dir(), "Rollback must not consume the user's selected backup")

    def test_update_and_rollback_dry_run_do_not_write(self):
        installer.install(self.source, ["claude"], self.home)
        old = installer._manifest(self.target("claude"))
        self.new_version()
        result = installer.install(self.source, ["claude"], self.home, update=True, dry_run=True)[0]
        self.assertEqual(result["status"], "would_update")
        self.assertFalse((self.home / ".naturale").exists())
        self.assertEqual(installer._manifest(self.target("claude")), old)
        updated = installer.install(self.source, ["claude"], self.home, update=True)[0]
        before = sorted((self.home / ".naturale/backups/claude").iterdir())
        restored = installer.rollback(updated["backup_path"], "claude", self.home, dry_run=True)
        self.assertEqual(restored["status"], "would_rollback")
        self.assertEqual(sorted((self.home / ".naturale/backups/claude").iterdir()), before)
        self.assertEqual(installer._manifest(self.target("claude")), installer._manifest(self.source))

    def test_update_refuses_modified_managed_files_and_extra_personal_files(self):
        installer.install(self.source, ["codex"], self.home)
        self.new_version()
        target = self.target("codex")
        original = (target / "references/editorial.md").read_bytes()
        (target / "references/editorial.md").write_bytes(b"Personal customization")
        with self.assertRaises(installer.InstallError):
            installer.install(self.source, ["codex"], self.home, update=True)
        self.assertEqual((target / "references/editorial.md").read_bytes(), b"Personal customization")
        (target / "references/editorial.md").write_bytes(original)
        (target / "my-notes.txt").write_text("Do not lose this")
        with self.assertRaises(installer.InstallError):
            installer.install(self.source, ["codex"], self.home, update=True)
        self.assertEqual((target / "my-notes.txt").read_text(), "Do not lose this")
        self.assertFalse((self.home / ".naturale").exists())

    def test_update_refuses_legacy_installation_without_receipt(self):
        installer.install(self.source, ["codex"], self.home)
        (self.target("codex") / installer.RECEIPT).unlink()
        old = installer._manifest(self.target("codex"))
        self.new_version()
        with self.assertRaises(installer.InstallError):
            installer.install(self.source, ["codex"], self.home, update=True)
        self.assertEqual(installer._manifest(self.target("codex")), old)

    def test_update_refuses_embedded_venv_without_moving_anything(self):
        installer.install(self.source, ["codex"], self.home)
        runtime = self.target("codex") / ".venv"
        runtime.mkdir()
        (runtime / "data").write_text("runtime data")
        self.new_version()
        with self.assertRaises(installer.InstallError):
            installer.install(self.source, ["codex"], self.home, update=True)
        self.assertEqual((runtime / "data").read_text(), "runtime data")
        self.assertFalse((self.home / ".naturale").exists())

    def test_update_preflights_both_hosts_before_changes(self):
        installer.install(self.source, ["claude", "codex"], self.home)
        old = installer._manifest(self.target("claude"))
        (self.target("codex") / "private-note").write_text("keep")
        self.new_version()
        with self.assertRaises(installer.InstallError):
            installer.install(self.source, ["claude", "codex"], self.home, update=True)
        self.assertEqual(installer._manifest(self.target("claude")), old)
        self.assertFalse((self.home / ".naturale").exists())

    def test_update_failure_restores_both_previous_versions(self):
        installer.install(self.source, ["claude", "codex"], self.home)
        original = {host: installer._manifest(self.target(host)) for host in ("claude", "codex")}
        self.new_version()
        real_write = installer._write_exclusive
        calls = []

        def write(destination, files):
            calls.append(destination)
            if len(calls) == 2:
                raise OSError("Simulated second host failure")
            real_write(destination, files)

        with patch.object(installer, "_write_exclusive", side_effect=write):
            with self.assertRaises(installer.InstallError):
                installer.install(self.source, ["claude", "codex"], self.home, update=True)
        for host in ("claude", "codex"):
            self.assertEqual(installer._manifest(self.target(host)), original[host])
            installer._managed(self.target(host))

    def test_rollback_preserves_personal_file_added_to_completed_host_during_update(self):
        installer.install(self.source, ["claude", "codex"], self.home)
        old_claude = installer._manifest(self.target("claude"))
        old_codex = installer._manifest(self.target("codex"))
        self.new_version()
        real_write = installer._write_exclusive
        calls = []

        def write(destination, files):
            calls.append(destination)
            if len(calls) == 2:
                (self.target("claude") / "personal-note.txt").write_text("Never discard this concurrent note")
                raise OSError("Second host failed after a concurrent first-host edit")
            real_write(destination, files)

        with patch.object(installer, "_write_exclusive", side_effect=write):
            with self.assertRaises(installer.InstallError) as context:
                installer.install(self.source, ["claude", "codex"], self.home, update=True)
        self.assertIn("modifiche concorrenti", str(context.exception))
        self.assertEqual((self.target("claude") / "personal-note.txt").read_text(), "Never discard this concurrent note")
        backups = list((self.home / ".naturale/backups/claude").iterdir())
        self.assertEqual(len(backups), 1)
        self.assertEqual(installer._manifest(backups[0] / "skill"), old_claude)
        self.assertEqual(installer._manifest(self.target("codex")), old_codex)

    def test_failed_partial_update_keeps_unknown_new_data_and_original_backup(self):
        installer.install(self.source, ["codex"], self.home)
        original = installer._manifest(self.target("codex"))
        self.new_version()

        def write(destination, files):
            (destination / "private-note.txt").write_text("Do not delete a partially installed copy's personal data")
            raise OSError("Failure before package copy completed")

        with patch.object(installer, "_write_exclusive", side_effect=write):
            with self.assertRaises(installer.InstallError):
                installer.install(self.source, ["codex"], self.home, update=True)
        self.assertIn("personal data", (self.target("codex") / "private-note.txt").read_text())
        backups = list((self.home / ".naturale/backups/codex").iterdir())
        self.assertEqual(len(backups), 1)
        self.assertEqual(installer._manifest(backups[0] / "skill"), original)

    def test_rollback_refuses_backup_outside_store_and_modified_current(self):
        installer.install(self.source, ["codex"], self.home)
        self.new_version()
        result = installer.install(self.source, ["codex"], self.home, update=True)[0]
        with self.assertRaises(installer.InstallError):
            installer.rollback(self.source, "codex", self.home)
        with self.assertRaises(installer.InstallError):
            installer.rollback(result["backup_path"], "both", self.home)
        (self.target("codex") / "personal.txt").write_text("keep")
        with self.assertRaises(installer.InstallError):
            installer.rollback(result["backup_path"], "codex", self.home)
        self.assertEqual((self.target("codex") / "personal.txt").read_text(), "keep")

    def test_invalid_receipt_does_not_authorize_update(self):
        installer.install(self.source, ["codex"], self.home)
        receipt = self.target("codex") / installer.RECEIPT
        receipt.write_text('{"schema_version":"1.0","version":"0.1.0","files":{"../private":"' + "0" * 64 + '"}}')
        old = installer._manifest(self.target("codex"))
        self.new_version()
        with self.assertRaises(installer.InstallError):
            installer.install(self.source, ["codex"], self.home, update=True)
        self.assertEqual(installer._manifest(self.target("codex")), old)

    def test_receipt_with_invalid_unicode_version_is_a_controlled_error(self):
        installer.install(self.source, ["codex"], self.home)
        path = self.target("codex") / installer.RECEIPT
        data = json.loads(path.read_text(encoding="utf-8"))
        data["version"] = chr(0xD800)
        path.write_text(json.dumps(data), encoding="utf-8")
        with self.assertRaises(installer.InstallError):
            installer._receipt(self.target("codex"))

    @unittest.skipUnless(hasattr(os, "mkfifo"), "Unix FIFO required")
    def test_fifo_receipt_is_rejected_without_blocking(self):
        installer.install(self.source, ["codex"], self.home)
        path = self.target("codex") / installer.RECEIPT
        path.unlink()
        os.mkfifo(path)
        code = (
            "import importlib.util,sys; "
            "s=importlib.util.spec_from_file_location('installer',sys.argv[1]); "
            "m=importlib.util.module_from_spec(s);s.loader.exec_module(m); "
            "m._receipt(m.Path(sys.argv[2]))"
        )
        result = subprocess.run(
            [sys.executable, "-c", code, str(ROOT / "scripts/install.py"), str(self.target("codex"))],
            capture_output=True, text=True, timeout=3,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("InstallError", result.stderr)

    def test_tampered_backup_is_not_restored(self):
        installer.install(self.source, ["codex"], self.home)
        self.new_version()
        result = installer.install(self.source, ["codex"], self.home, update=True)[0]
        backup = Path(result["backup_path"])
        (backup / "skill/scripts/images.py").write_text("# changed after backup")
        current = installer._manifest(self.target("codex"))
        with self.assertRaises(installer.InstallError):
            installer.rollback(backup, "codex", self.home)
        self.assertEqual(installer._manifest(self.target("codex")), current)

    def test_concurrent_update_destination_is_preserved_with_original_in_backup(self):
        installer.install(self.source, ["codex"], self.home)
        target = self.target("codex")
        old = installer._manifest(target)
        self.new_version()
        real_mkdir = Path.mkdir
        collided = []

        def mkdir(path, *args, **kwargs):
            if path == target and not path.exists() and not collided:
                collided.append(path)
                real_mkdir(path)
                (path / "concurrent.txt").write_text("another installation")
            return real_mkdir(path, *args, **kwargs)

        with patch.object(Path, "mkdir", new=mkdir):
            with self.assertRaises(installer.InstallError):
                installer.install(self.source, ["codex"], self.home, update=True)
        self.assertEqual((target / "concurrent.txt").read_text(), "another installation")
        backups = list((self.home / ".naturale/backups/codex").iterdir())
        self.assertEqual(len(backups), 1)
        self.assertEqual(installer._manifest(backups[0] / "skill"), old)

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
