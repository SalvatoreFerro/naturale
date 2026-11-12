"""Portable, dependency-free contract for the optional Claude plugin package."""
from pathlib import Path
import json
import unittest


ROOT = Path(__file__).resolve().parents[1]
PLUGIN_DIRECTORY = ROOT / ".claude-plugin"


class ClaudePluginContractTests(unittest.TestCase):
    def load(self, name):
        path = PLUGIN_DIRECTORY / name
        self.assertTrue(path.is_file(), f"Missing plugin metadata: {path.name}")
        return json.loads(path.read_text(encoding="utf-8"))

    def test_plugin_has_explicit_identity_version_and_license(self):
        plugin = self.load("plugin.json")
        self.assertEqual(plugin["name"], "naturale")
        self.assertRegex(plugin["version"], r"^\d+\.\d+\.\d+$")
        self.assertEqual(plugin["version"], "0.2.1")
        self.assertEqual(plugin["license"], "MIT")
        self.assertEqual(plugin["author"]["name"], "SalvatoreFerro")
        self.assertTrue(plugin["description"].strip())
        self.assertEqual(plugin["repository"], "https://github.com/SalvatoreFerro/naturale")

    def test_marketplace_source_is_the_repository_root(self):
        marketplace = self.load("marketplace.json")
        self.assertEqual(marketplace["name"], "naturale-marketplace")
        self.assertTrue(marketplace["description"].strip())
        self.assertEqual(marketplace["owner"], {"name": "SalvatoreFerro"})
        self.assertEqual(len(marketplace["plugins"]), 1)
        entry = marketplace["plugins"][0]
        self.assertEqual(entry["name"], self.load("plugin.json")["name"])
        self.assertEqual(entry["source"], "./")
        self.assertEqual((ROOT / entry["source"]).resolve(), ROOT.resolve())

    def test_package_uses_the_existing_skill_and_has_no_services_or_hooks(self):
        plugin = self.load("plugin.json")
        allowed = {"name", "version", "description", "author", "repository", "license"}
        self.assertLessEqual(set(plugin), allowed)
        self.assertTrue((ROOT / "skills/naturale/SKILL.md").is_file())
        for path in (ROOT / ".mcp.json", ROOT / ".lsp.json", ROOT / "hooks/hooks.json"):
            self.assertFalse(path.exists(), f"Unexpected runtime service or hook: {path.name}")

    def test_readme_documents_both_installation_routes_without_replacing_codex(self):
        text = (ROOT / "README.md").read_text(encoding="utf-8")
        self.assertIn("/plugin install naturale --marketplace SalvatoreFerro/naturale", text)
        self.assertIn("claude plugin marketplace add SalvatoreFerro/naturale", text)
        self.assertIn("claude plugin install naturale@naturale-marketplace", text)
        self.assertIn("/naturale:naturale", text)
        self.assertIn("2.1.275", text)
        self.assertIn("claude plugin validate .", text)
        self.assertIn("claude plugin list", text)
        self.assertRegex(text, r"plugin[^\n]+manuale|manuale[^\n]+plugin")
        self.assertIn('python3 scripts/install.py --host codex', text)


if __name__ == "__main__":
    unittest.main()
