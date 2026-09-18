import json
from pathlib import Path
import re
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
        self.assertEqual(source["repository"], "TakashiSasaki/templates")
        self.assertEqual(source["schema_version"], 2)
        self.assertEqual(source["revision"], "9c2c538d5ee0b866379db40e5c24b29d60e155ba")
        self.assertEqual(source["path"], "repository-skills/land-templates-stack/SKILL.md")
        self.assertTrue(re.fullmatch(r"[0-9a-f]{40}", source["blob_sha"]))
        self.assertEqual(
            source["closure"],
            [
                {
                    "path": "repository-policy/stacked-pr-landing.md",
                    "blob_sha": "9761cdbcd21b0e8ba2f3eb2ffb306725a82f5eef",
                },
                {
                    "path": "repository-skills/land-templates-stack/scripts/plan_review_scope.py",
                    "blob_sha": "16c0907a19e3f8d339fe81e29f7b204e791fc781",
                },
            ],
        )
        # Modeling and Policy have independent histories.  Source retrieval
        # must verify this exact identity without requiring the Policy object
        # to be reachable from the Modeling checkout.
        landing = (ROOT / ".agents/skills/land-templates-stack/SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("does not authorize", landing)
        self.assertIn("same immutable", landing)
        self.assertNotIn("CI_DISCOVERY_MIN_OBSERVATION_MINUTES", landing)

    def test_modeling_review_route_separates_record_deltas_from_contract_changes(self):
        instructions = " ".join((ROOT / "AGENTS.md").read_text(encoding="utf-8").split())
        registration = " ".join(
            (ROOT / ".agents/skills/register-information-model/SKILL.md")
            .read_text(encoding="utf-8")
            .split()
        )
        for required in (
            "Adaptive review scope",
            "independent exact-head delta review",
            "Schema/profile meaning",
            "observed-versus-verified bytes",
            "external registration is not Integration/Site adoption",
            "valid completed",
            "independent review",
        ):
            with self.subTest(required=required):
                self.assertIn(required, instructions + " " + registration)
        self.assertNotIn("exactly one whole-stack", instructions)
        self.assertNotIn("Do not request per-member reviews as substitutes", instructions)


if __name__ == "__main__":
    unittest.main()
