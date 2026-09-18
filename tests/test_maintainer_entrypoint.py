import json
import re
from pathlib import Path
import unittest


ROOT = Path(__file__).resolve().parents[1]


class MaintainerEntrypointTests(unittest.TestCase):
    def test_composition_route_keeps_consumer_and_authority_paths_distinct(self):
        readme = (ROOT / "README.md").read_text(encoding="utf-8")
        for required in (
            "Using Composition",
            "Maintain the Composition authority in `templates`",
            "maintainer onboarding guide",
            "checked-out branch is `composition`",
            "generated/",
            "python3 scripts/run_composition_preflight.py fast",
            "full immutable SHAs",
            "Integration",
            "Site adoption",
            "Policy Work ledger",
        ):
            with self.subTest(required=required):
                self.assertIn(required, readme)

    def test_composition_maintainer_references_are_local_and_real(self):
        for relative in (
            "AGENTS.md",
            "components",
            "recipes",
            "generated",
            "scripts/run_composition_preflight.py",
        ):
            with self.subTest(relative=relative):
                self.assertTrue((ROOT / relative).exists())

    def test_maintainer_landing_route_uses_the_frozen_policy_snapshot(self):
        source_path = ROOT / ".agents/skills/land-templates-stack/source.json"
        source = json.loads(source_path.read_text(encoding="utf-8"))
        self.assertEqual(source["schema_version"], 1)
        self.assertEqual(source["kind"], "repository-maintainer-skill-reference")
        self.assertEqual(source["repository"], "TakashiSasaki/templates")
        self.assertEqual(source["revision"], "5af977020fca701bcf6b7fb7ce12ca077b2d7220")
        self.assertEqual(source["path"], "repository-skills/land-templates-stack/SKILL.md")
        self.assertTrue(re.fullmatch(r"[0-9a-f]{40}", source["revision"]))
        self.assertTrue(re.fullmatch(r"[0-9a-f]{40}", source["blob_sha"]))
        # Authority histories are intentionally independent.  The consumer
        # checkout need not contain the Policy commit object; the immutable
        # source verifier retrieves or uses that exact snapshot separately.
        skill = (ROOT / ".agents/skills/land-templates-stack/SKILL.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("does not reproduce landing", skill)
        self.assertIn("human-controlled boundary", skill)


if __name__ == "__main__":
    unittest.main()
