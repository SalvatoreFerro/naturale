"""Read-only diagnostics use only synthetic installations and mocked tools."""
from __future__ import annotations

from contextlib import redirect_stdout
import importlib.util
import io
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("naturale_doctor", ROOT / "scripts/doctor.py")
diagnostics = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diagnostics)


class DoctorTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.home = Path(self.directory.name)
        self.versions = {"Pillow": "12.3.0", "c2pa-python": "0.38.1"}
        self.package_patch = patch.object(diagnostics.metadata, "version", side_effect=self.package_version)
        self.which_patch = patch.object(diagnostics.shutil, "which", return_value="/private/local/exiftool")
        self.run_patch = patch.object(diagnostics.subprocess, "run", return_value=subprocess.CompletedProcess([], 0, "13.63\n", ""))
        self.package_patch.start()
        self.which_patch.start()
        self.run_mock = self.run_patch.start()
        self.addCleanup(self.package_patch.stop)
        self.addCleanup(self.which_patch.stop)
        self.addCleanup(self.run_patch.stop)

    def package_version(self, name):
        if name not in self.versions:
            raise diagnostics.metadata.PackageNotFoundError(name)
        return self.versions[name]

    def install(self, host="codex", version="0.2.0"):
        skill = self.home / diagnostics.HOSTS[host] / "skills/naturale"
        (skill / "references").mkdir(parents=True)
        (skill / "SKILL.md").write_text(
            '---\nname: naturale\ndescription: "Test"\n---\n[Regole](references/rules.md)\n', encoding="utf-8"
        )
        (skill / "references/rules.md").write_text("Regole", encoding="utf-8")
        if version is not None:
            (skill / "VERSION").write_text(version + "\n", encoding="utf-8")
        return skill

    def test_one_valid_host_is_ready_and_optional_sdk_is_not_required(self):
        self.install()
        self.versions.pop("c2pa-python")
        report = diagnostics.doctor(home=self.home)
        self.assertTrue(report["ready"])
        self.assertTrue(report["images_ready"])
        self.assertFalse(report["dependencies"]["c2pa"]["available"])
        self.assertTrue(report["dependencies"]["c2pa"]["optional"])
        by_host = {item["host"]: item for item in report["hosts"]}
        self.assertTrue(by_host["codex"]["text_ready"])
        self.assertFalse(by_host["claude"]["text_ready"])
        self.assertEqual(by_host["codex"]["version"], "0.2.0")

    def test_absent_images_dependencies_do_not_block_text_skill(self):
        self.install()
        self.versions.pop("Pillow")
        with patch.object(diagnostics.shutil, "which", return_value=None):
            report = diagnostics.doctor("codex", self.home)
        self.assertTrue(report["ready"])
        self.assertFalse(report["images_ready"])
        self.assertFalse(report["dependencies"]["pillow"]["available"])
        self.assertEqual(report["dependencies"]["exiftool"]["problem"], "not_found")

    def test_unsupported_pillow_version_is_flagged(self):
        self.install()
        self.versions["Pillow"] = "13.0.0"
        report = diagnostics.doctor("codex", self.home)
        self.assertTrue(report["ready"])
        self.assertFalse(report["images_ready"])
        self.assertFalse(report["dependencies"]["pillow"]["compatible"])

    def test_empty_home_is_not_ready_and_auto_checks_both(self):
        report = diagnostics.doctor("auto", self.home)
        self.assertFalse(report["ready"])
        self.assertEqual({host["host"] for host in report["hosts"]}, {"claude", "codex"})
        self.assertTrue(all(host["missing"] == ["skill_not_installed"] for host in report["hosts"]))

    def test_auto_selects_existing_installation(self):
        self.install("claude", version=None)
        report = diagnostics.doctor("auto", self.home)
        self.assertEqual([host["host"] for host in report["hosts"]], ["claude"])
        self.assertEqual(report["hosts"][0]["version"], "0.1.0")

    def test_missing_or_escaping_reference_is_not_ready(self):
        skill = self.install()
        (skill / "references/rules.md").unlink()
        self.assertIn("missing_reference", diagnostics.doctor("codex", self.home)["hosts"][0]["missing"])
        with (skill / "SKILL.md").open("a", encoding="utf-8") as stream:
            stream.write("[Privato](../../outside.md)\n")
        self.assertIn("unsafe_reference", diagnostics.doctor("codex", self.home)["hosts"][0]["missing"])

    def test_invalid_entrypoint_and_version_are_reported(self):
        skill = self.install()
        (skill / "SKILL.md").write_text("# No frontmatter\n", encoding="utf-8")
        (skill / "VERSION").write_text("/private/secret-directory\n", encoding="utf-8")
        host = diagnostics.doctor("codex", self.home)["hosts"][0]
        self.assertFalse(host["text_ready"])
        self.assertIsNone(host["version"])
        self.assertIn("invalid_skill_name", host["missing"])
        self.assertIn("invalid_version", host["missing"])

    def test_malformed_reference_is_reported_without_exception(self):
        skill = self.install()
        with (skill / "SKILL.md").open("a", encoding="utf-8") as stream:
            stream.write("[Invalid](http://[invalid)\n")
        report = diagnostics.doctor("codex", self.home)
        self.assertFalse(report["ready"])
        self.assertIn("unsafe_reference", report["hosts"][0]["missing"])

    def test_receipt_is_optional_and_raw_content_is_not_returned(self):
        skill = self.install()
        receipt = skill / ".naturale-install.json"
        receipt.write_text('{"schema_version":"1.0","private_path":"never-disclose"}', encoding="utf-8")
        report = diagnostics.doctor("codex", self.home)
        self.assertEqual(report["hosts"][0]["receipt"], "present")
        self.assertNotIn("never-disclose", json.dumps(report))
        receipt.write_text("not JSON", encoding="utf-8")
        report = diagnostics.doctor("codex", self.home)
        self.assertTrue(report["ready"])
        self.assertEqual(report["hosts"][0]["receipt"], "unreadable")

    def test_exiftool_uses_empty_config_and_never_leaks_errors_or_executable_path(self):
        self.install()
        self.run_mock.return_value = subprocess.CompletedProcess([], 1, "", "secret /private/tool/filename token")
        report = diagnostics.doctor("codex", self.home)
        command = self.run_mock.call_args.args[0]
        self.assertEqual(command, ["/private/local/exiftool", "-config", "", "-ver"])
        self.assertFalse(self.run_mock.call_args.kwargs["shell"])
        self.assertFalse(report["images_ready"])
        encoded = json.dumps(report)
        self.assertNotIn("secret", encoded)
        self.assertNotIn("/private", encoded)
        self.assertNotIn(str(self.home), encoded)

    def test_exiftool_timeout_is_reported_without_raising_or_leaking_command(self):
        self.install()
        self.run_mock.side_effect = subprocess.TimeoutExpired(["/private/local/exiftool"], 10)
        report = diagnostics.doctor("codex", self.home)
        self.assertEqual(report["dependencies"]["exiftool"]["problem"], "not_executable_or_timeout")
        self.assertNotIn("/private", json.dumps(report))

    def test_diagnosis_does_not_create_or_change_files(self):
        self.install()
        before = {path.relative_to(self.home).as_posix(): path.read_bytes()
                  for path in self.home.rglob("*") if path.is_file()}
        diagnostics.doctor(home=self.home)
        after = {path.relative_to(self.home).as_posix(): path.read_bytes()
                 for path in self.home.rglob("*") if path.is_file()}
        self.assertEqual(before, after)

    def test_unreadable_installation_does_not_leak_error_paths(self):
        self.install()
        with patch.object(diagnostics, "_host_report", side_effect=PermissionError("secret /private/data")):
            report = diagnostics.doctor("codex", self.home)
        self.assertFalse(report["ready"])
        self.assertEqual(report["hosts"][0]["missing"], ["installation_unreadable"])
        self.assertNotIn("secret", json.dumps(report))

    def test_cli_exit_code_tracks_text_readiness(self):
        self.install("codex")
        with patch.object(diagnostics.Path, "home", return_value=self.home), redirect_stdout(io.StringIO()) as out:
            self.assertEqual(diagnostics.main(["--host", "codex"]), 0)
        self.assertTrue(json.loads(out.getvalue())["ready"])
        with patch.object(diagnostics.Path, "home", return_value=self.home), redirect_stdout(io.StringIO()):
            self.assertEqual(diagnostics.main(["--host", "claude"]), 1)

    def test_old_python_is_flagged_without_mutation(self):
        self.install()
        with patch.object(diagnostics.sys, "version_info", (3, 10, 14)):
            report = diagnostics.doctor("codex", self.home)
        self.assertFalse(report["python"]["supported"])
        self.assertFalse(report["ready"])

    def test_symlink_installation_is_not_followed(self):
        target = self.home / ".agents/skills/naturale"
        target.parent.mkdir(parents=True)
        elsewhere = self.home / "elsewhere"
        elsewhere.mkdir()
        try:
            target.symlink_to(elsewhere, target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest("Symlink creation unavailable")
        report = diagnostics.doctor("codex", self.home)
        self.assertFalse(report["ready"])
        self.assertEqual(report["hosts"][0]["missing"], ["unsafe_installation"])


if __name__ == "__main__":
    unittest.main()
