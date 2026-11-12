"""Dependency maintenance must preserve the CI trust and support boundaries."""
from pathlib import Path
import re
import tomllib
import unittest

ROOT = Path(__file__).resolve().parents[1]


class CIPolicyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.workflow = (ROOT / ".github/workflows/ci.yml").read_text(encoding="utf-8")

    def test_official_actions_use_reviewed_immutable_pins(self):
        expected = {
            "checkout": "3d3c42e5aac5ba805825da76410c181273ba90b1",
            "setup-python": "6d4fd22b20465ccc0f7354476588e8df7c9ca0e0",
        }
        for action, pin in expected.items():
            with self.subTest(action=action):
                references = re.findall(r"uses: actions/" + action + r"@([^\s#]+)", self.workflow)
                self.assertTrue(references, f"Missing official action: {action}")
                self.assertEqual(set(references), {pin})

    def test_checkouts_do_not_persist_repository_credentials(self):
        steps = re.split(r"(?m)^      - ", self.workflow)[1:]
        checkouts = [step for step in steps if re.search(r"uses: actions/checkout@", step)]
        self.assertGreaterEqual(len(checkouts), 2, "Both project and ExifTool source need checkout")
        for step in checkouts:
            with self.subTest(step=step.splitlines()[0]):
                self.assertRegex(step, r"(?m)^          persist-credentials: false[ \t]*$")

    def test_workflow_token_has_only_contents_read_permission(self):
        declarations = re.findall(r"(?m)^[ \t]*permissions:", self.workflow)
        self.assertEqual(len(declarations), 1, "Job overrides must not widen the default token")
        permissions = re.search(r"(?ms)^permissions:\n(.*?)(?=^[^\s#]|\Z)", self.workflow)
        self.assertIsNotNone(permissions)
        self.assertEqual(permissions.group(1).strip(), "contents: read")

    def test_pillow_support_bound_remains_consistent_and_below_13(self):
        project = tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        project_pillow = [item for item in project["project"]["dependencies"] if item.startswith("Pillow")]
        requirements = (ROOT / "skills/naturale/requirements.txt").read_text(encoding="utf-8")
        skill_pillow = [item.strip() for item in requirements.splitlines() if item.strip().startswith("Pillow")]
        self.assertEqual(project_pillow, ["Pillow>=11,<13"])
        self.assertEqual(skill_pillow, project_pillow)
