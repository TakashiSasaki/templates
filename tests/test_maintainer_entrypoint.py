from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class MaintainerEntrypointTests(unittest.TestCase):
    def test_modeling_maintainer_route_separates_sources_from_publication(self):
        readme = " ".join((ROOT / "README.md").read_text(encoding="utf-8").split())
        for required in (
            "Maintain this authority in `templates`",
            "maintainer onboarding guide",
            "AUTHORITY.md",
            "AGENTS.md",
            "docs/intake.md",
            ".agents/skills/register-information-model/SKILL.md",
            "records/",
            "CATALOG.md",
            "catalog.json",
            "docs/resources/",
            "python3 tools/catalog.py generate",
            "python3 tools/qualify.py",
            "immutable full SHA",
            "Work ledger",
            "does not register an Integration",
        ):
            with self.subTest(required=required):
                self.assertIn(required, readme)

    def test_existing_registration_skill_remains_the_only_local_skill_route(self):
        skill = (ROOT / ".agents/skills/register-information-model/SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("## Read before editing", skill)
        self.assertIn("## Validate before requesting CI", skill)
        self.assertIn("Do not merge or enable Integration/Site adoption without authorization", skill)


if __name__ == "__main__":
    unittest.main()
