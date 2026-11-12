"""Home aliases are allowed; links in profile storage are not followed."""
from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "naturale_profile_paths", ROOT / "skills/naturale/scripts/text.py"
)
text = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(text)


class ProfilePathTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name).resolve()
        self.home = self.base / "real-home"
        self.home.mkdir()
        self.alias = self.base / "home-link"
        self.symlink(self.alias, self.home)
        self.profile = {"register": "professionale", "conciseness": "breve"}

    def symlink(self, link, target, directory=True):
        try:
            link.symlink_to(target, target_is_directory=directory)
        except (OSError, NotImplementedError):
            self.skipTest("Symlinks unavailable")

    def test_default_home_alias_supports_canonical_storage_and_round_trip(self):
        directory = self.home / ".naturale" / "profiles"
        with patch.object(Path, "home", return_value=self.alias):
            self.assertEqual(text._profile_directory(), directory)
            profile = text.create_profile("lavoro", self.profile)
            self.assertEqual(text.show_profile("lavoro"), profile)
            self.assertEqual(text.list_profiles()[0]["name"], "lavoro")
            self.assertTrue((directory / "lavoro.json").is_file())
            self.assertEqual(text.delete_profile("lavoro"), {"deleted": "lavoro"})
            self.assertEqual(text.list_profiles(), [])

    def test_explicit_directory_accepts_parent_alias_and_returns_canonical_path(self):
        directory = self.alias / "private" / "profiles"
        expected = self.home / "private" / "profiles"
        self.assertEqual(text._profile_directory(directory), expected)
        profile = text.create_profile("lavoro", self.profile, directory)
        self.assertEqual(text.show_profile("lavoro", directory), profile)
        self.assertTrue((expected / "lavoro.json").is_file())

    def test_reads_through_home_alias_do_not_create_missing_storage(self):
        with patch.object(Path, "home", return_value=self.alias):
            self.assertEqual(text.list_profiles(), [])
            with self.assertRaises(text.TextError):
                text.show_profile("lavoro")
        self.assertFalse((self.home / ".naturale").exists())

    def test_default_rejects_naturale_symlink_below_resolved_home(self):
        outside = self.base / "outside"
        outside.mkdir()
        self.symlink(self.home / ".naturale", outside)
        with patch.object(Path, "home", return_value=self.alias):
            with self.assertRaisesRegex(text.TextError, "Collegamento simbolico"):
                text.create_profile("lavoro", self.profile)
        self.assertEqual(list(outside.iterdir()), [])

    def test_default_rejects_profiles_symlink_below_resolved_home(self):
        outside = self.base / "outside"
        outside.mkdir()
        (self.home / ".naturale").mkdir()
        self.symlink(self.home / ".naturale" / "profiles", outside)
        with patch.object(Path, "home", return_value=self.alias):
            with self.assertRaisesRegex(text.TextError, "Collegamento simbolico"):
                text.create_profile("lavoro", self.profile)
        self.assertEqual(list(outside.iterdir()), [])

    def test_explicit_directory_rejects_final_store_link_even_with_parent_alias(self):
        outside = self.base / "outside"
        outside.mkdir()
        self.symlink(self.home / "profiles", outside)
        with self.assertRaisesRegex(text.TextError, "Collegamento simbolico"):
            text.create_profile("lavoro", self.profile, self.alias / "profiles")
        self.assertEqual(list(outside.iterdir()), [])

    def test_home_alias_never_overwrites_an_existing_profile(self):
        directory = self.home / ".naturale" / "profiles"
        text.create_profile("lavoro", self.profile, directory)
        original = (directory / "lavoro.json").read_bytes()
        with patch.object(Path, "home", return_value=self.alias):
            with self.assertRaisesRegex(text.TextError, "non viene sovrascritto"):
                text.create_profile("lavoro", {**self.profile, "register": "altro"})
        self.assertEqual((directory / "lavoro.json").read_bytes(), original)

    def test_home_alias_never_reads_replaces_or_deletes_a_final_profile_link(self):
        directory = self.home / ".naturale" / "profiles"
        directory.mkdir(parents=True)
        outside = self.base / "outside.json"
        outside.write_text(json.dumps(self.profile), encoding="utf-8")
        original = outside.read_bytes()
        final_link = directory / "lavoro.json"
        self.symlink(final_link, outside, directory=False)
        with patch.object(Path, "home", return_value=self.alias):
            for operation in (
                lambda: text.show_profile("lavoro"),
                lambda: text.create_profile("lavoro", self.profile),
                lambda: text.delete_profile("lavoro"),
            ):
                with self.subTest(operation=operation):
                    with self.assertRaises(text.TextError):
                        operation()
        self.assertTrue(final_link.is_symlink())
        self.assertEqual(outside.read_bytes(), original)
