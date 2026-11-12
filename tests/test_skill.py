"""Check the portable Agent Skills contract without third-party YAML parsers."""

from pathlib import Path
import re
import unittest


ROOT = Path(__file__).resolve().parents[1]
SKILL_DIRECTORY = ROOT / "skills" / "naturale"
SKILL = SKILL_DIRECTORY / "SKILL.md"


class SkillContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.text = SKILL.read_text(encoding="utf-8")

    def test_frontmatter_has_portable_name_and_description(self):
        match = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|\Z)", self.text, re.S)
        self.assertIsNotNone(match, "SKILL.md must start with YAML frontmatter")
        frontmatter = match.group(1)
        name = re.search(r"(?m)^name:\s*['\"]?([a-z0-9-]+)['\"]?\s*$", frontmatter)
        self.assertIsNotNone(name)
        self.assertEqual(name.group(1), SKILL_DIRECTORY.name)
        self.assertLessEqual(len(name.group(1)), 64)
        self.assertRegex(name.group(1), r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
        description = re.search(r"(?m)^description:\s*(\S.*)$", frontmatter)
        self.assertIsNotNone(description, "A nonempty description is required")

    def test_relative_markdown_references_resolve_inside_skill(self):
        references = re.findall(r"\[[^\]]+\]\(([^)]+)\)", self.text)
        local = []
        for target in references:
            target = target.strip().split(" ", 1)[0].strip("<>")
            if re.match(r"[a-zA-Z][a-zA-Z0-9+.-]*:", target) or target.startswith("#"):
                continue
            target = target.split("#", 1)[0]
            if not target:
                continue
            local.append(target)
            resolved = (SKILL_DIRECTORY / target).resolve()
            self.assertTrue(resolved.is_relative_to(SKILL_DIRECTORY.resolve()), target)
            self.assertTrue(resolved.exists(), f"Missing skill reference: {target}")
        self.assertTrue(local, "Use explicit links to the skill's local references")

    def test_description_is_short_and_focuses_on_supported_operations(self):
        frontmatter = self.text.split("---", 2)[1]
        description = re.search(r"(?m)^description:\s*(\S.*)$", frontmatter)
        self.assertIsNotNone(description)
        value = description.group(1).strip()
        if value.startswith(('"', "'")) and value[-1] == value[0]:
            value = value[1:-1]
        with self.subTest(requirement="Claude app character limit"):
            self.assertLessEqual(len(value), 200)
        for word in ("rilevator", "detector", "instagram"):
            with self.subTest(unwanted_description_term=word):
                self.assertNotIn(word, value.casefold())

    def test_image_and_detector_limits_remain_in_skill_body(self):
        body = self.text.split("---", 2)[-1]
        self.assertIn("I punteggi dei detector non sono un obiettivo né una prova di qualità.", body)
        self.assertIn("Watermark invisibili", body)
        self.assertIn("l'eventuale etichettatura resta sconosciuta", body)
        self.assertIn("Non ritoccare i pixel per tentare di rimuovere watermark invisibili.", body)

    def test_image_script_exists_and_has_no_external_runtime_requirement(self):
        script = SKILL_DIRECTORY / "scripts" / "images.py"
        self.assertTrue(script.is_file())
        self.assertFalse((SKILL_DIRECTORY / "ai-plugin.json").exists())

    def test_portable_skill_is_not_an_entire_document_in_frontmatter(self):
        self.assertLess(len(self.text.splitlines()), 500)
        self.assertGreater(len(self.text.split("---", 2)[-1].strip()), 100)


if __name__ == "__main__":
    unittest.main()
