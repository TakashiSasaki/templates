import json
from pathlib import Path
import re
import subprocess
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

    def test_maintainer_landing_route_preserves_modeling_boundaries(self):
        source = json.loads(
            (ROOT / ".agents/skills/land-templates-stack/source.json").read_text(
                encoding="utf-8"
            )
        )
        self.assertEqual(source["kind"], "repository-maintainer-skill-reference")
        self.assertEqual(source["revision"], "5af977020fca701bcf6b7fb7ce12ca077b2d7220")
        self.assertTrue(re.fullmatch(r"[0-9a-f]{40}", source["blob_sha"]))
        self.assertEqual(
            subprocess.check_output(
                ["git", "rev-parse", f"{source['revision']}:{source['path']}"],
                cwd=ROOT,
                text=True,
            ).strip(),
            source["blob_sha"],
        )
        landing = (ROOT / ".agents/skills/land-templates-stack/SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("does not authorize", landing)
        self.assertIn("same immutable", landing)
        self.assertNotIn("CI_DISCOVERY_MIN_OBSERVATION_MINUTES", landing)


if __name__ == "__main__":
    unittest.main()
