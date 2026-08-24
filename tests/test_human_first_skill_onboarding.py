from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
WALKTHROUGH = ROOT / "docs" / "guides" / "skill-first-use-walkthrough.md"
WALKTHROUGH_JA = ROOT / "translations" / "ja" / "docs" / "guides" / "skill-first-use-walkthrough.md"
EXAMPLE_CONFIG = ROOT / "examples" / "onboarding" / "release-note-helper" / "composition.json"
CONFIG_SCHEMA = ROOT / "schemas" / "composition-config.schema.json"
INSTALLER_RELEASE = ROOT / "release" / "composition-installer.json"
PUBLICATION_CATALOG = ROOT / "docs" / "publication-catalog.json"


class HumanFirstSkillOnboardingTests(unittest.TestCase):
    def test_walkthrough_is_zero_to_one_and_lifecycle_ordered(self) -> None:
        text = WALKTHROUGH.read_text(encoding="utf-8")
        headings = [
            "## 0. What this walkthrough will produce",
            "## 1. Create the product repository",
            "## 2. Check prerequisites",
            "## 3. Install Composition",
            "## 4. Create `composition.json`",
            "## 5. Inspect",
            "## 6. Plan and review",
            "## 7. Apply",
            "## 8. Validate the scaffold",
            "## 9. Know exactly what you may edit",
            "## 10. Turn `SKILL.md` into Release Note Helper",
            "## 11. Add a real consumer-owned resource",
            "## 12. Validate the concrete Skill",
        ]
        positions = [text.index(heading) for heading in headings]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("separate consumer repository", text[: positions[1]])
        self.assertIn("Planning is read-only", text)
        self.assertIn("process current working directory", text)

    def test_example_configuration_is_minimal_and_schema_valid(self) -> None:
        schema = json.loads(CONFIG_SCHEMA.read_text(encoding="utf-8"))
        config = json.loads(EXAMPLE_CONFIG.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(config)), [])
        self.assertEqual(config["recipe"], "skill")
        self.assertEqual(config["components"], {"include": [], "exclude": []})

    def test_installer_pin_matches_release_metadata(self) -> None:
        release = json.loads(INSTALLER_RELEASE.read_text(encoding="utf-8"))
        installer = release["installer"]
        expected = (
            "https://raw.githubusercontent.com/"
            f"{installer['repository']}/{installer['revision']}/{installer['path']}"
        )
        self.assertIn(expected, WALKTHROUGH.read_text(encoding="utf-8"))

    def test_walkthrough_has_concrete_skill_ownership_and_completion_boundary(self) -> None:
        text = WALKTHROUGH.read_text(encoding="utf-8")
        for expected in (
            "`SKILL.md` | `seed`",
            "`.github/workflows/validate-skill.yml` | `managed`",
            "`.github/scripts/validate_skill.py` | `managed`",
            "new `references/`, `assets/`, or `scripts/` files | ordinary consumer content",
            "does **not** mean Release Note Helper is an operational Skill",
            "Selected profiles: knowledge-augmented",
            "references/release-note-style.md",
            "Policy is independent from Composition",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)

    def test_skill_entrypoints_point_to_walkthrough_before_reference(self) -> None:
        for path, reference_heading in (
            (ROOT / "components" / "artifact.skill-core" / "files" / "README.md", "## Artifact model"),
            (ROOT / "components" / "artifact.skill-core" / "files" / "docs" / "index.md", "## Reference"),
        ):
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text(encoding="utf-8")
                self.assertIn("skill-first-use-walkthrough.md", text)
                self.assertLess(text.index("skill-first-use-walkthrough.md"), text.index(reference_heading))

    def test_publication_catalog_contains_canonical_skill_walkthrough(self) -> None:
        catalog = json.loads(PUBLICATION_CATALOG.read_text(encoding="utf-8"))
        matches = [
            item
            for item in catalog["documents"]
            if item["id"] == "skill-first-use-walkthrough"
        ]
        self.assertEqual(
            matches,
            [
                {
                    "id": "skill-first-use-walkthrough",
                    "source": "docs/guides/skill-first-use-walkthrough.md",
                    "optional": False,
                    "home": False,
                }
            ],
        )

    def test_japanese_walkthrough_preserves_first_use_path(self) -> None:
        text = WALKTHROUGH_JA.read_text(encoding="utf-8")
        for expected in (
            "## 0. この walkthrough で何を作るか",
            "## 3. Composition を install する",
            "## 4. `composition.json` を作る",
            "## 5. Inspect",
            "## 6. Plan と review",
            "## 7. Apply",
            "## 8. Scaffold を validate する",
            "Selected profiles: knowledge-augmented",
            "references/release-note-style.md",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)


if __name__ == "__main__":
    unittest.main()
