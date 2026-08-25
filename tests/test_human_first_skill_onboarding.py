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
            "## 12. Check concrete completion, then validate the Skill",
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
            "active seed destination is still part of the resolved Composition state",
            "Selected profiles: knowledge-augmented",
            "references/release-note-style.md",
            "Selected profiles: template-scaffold",
            "explicit consumer gate checks **concrete completion**",
            "Policy is independent from Composition",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)

    def test_concrete_completion_gate_precedes_structural_validation(self) -> None:
        text = WALKTHROUGH.read_text(encoding="utf-8")
        section = text[text.index("## 12.") : text.index("## 13.")]
        sentinel_check = section.index("grep -q 'Selected profiles: template-scaffold'")
        todo_check = section.index("grep -q '\\bTODO\\b'")
        skill_validation = section.index("python .github/scripts/validate_skill.py .")
        composition_validation = section.index(
            "python /absolute/path/to/agent-skills/composition/scripts/run.py"
        )
        self.assertLess(sentinel_check, skill_validation)
        self.assertLess(todo_check, skill_validation)
        self.assertLess(skill_validation, composition_validation)
        self.assertIn("validator intentionally accepts the initial `template-scaffold`", text)

    def test_skill_entrypoints_prioritize_first_use_before_reference(self) -> None:
        overview = (
            ROOT / "components" / "artifact.skill-core" / "files" / "README.md"
        ).read_text(encoding="utf-8")
        self.assertIn("/composition/use/skill-first-use-walkthrough/", overview)
        self.assertLess(
            overview.index("/composition/use/skill-first-use-walkthrough/"),
            overview.index("## Artifact model"),
        )

        index = (
            ROOT / "components" / "artifact.skill-core" / "files" / "docs" / "index.md"
        ).read_text(encoding="utf-8")
        self.assertIn("[Skill overview](../README.md)", index)
        self.assertLess(index.index("[Skill overview]"), index.index("## Reference"))

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
