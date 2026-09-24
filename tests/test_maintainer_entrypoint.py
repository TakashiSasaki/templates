import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MaintainerEntrypointTests(unittest.TestCase):
    def test_policy_route_identifies_source_and_generated_outputs(self):
        readme = " ".join((ROOT / "README.md").read_text(encoding="utf-8").split())
        for required in (
            "Maintain the Policy authority in `templates`",
            "adoption commands above are for a separate product repository",
            "maintainer onboarding guide",
            "checked-out branch is `policy`",
            ".agent-policy.yml",
            "repository-policy/",
            "AGENTS.md",
            ".review-authority/review-policy.md",
            ".agent-policy.lock",
            "5ad8b0d89a7778beb98aa5794ef6aa58dca30ab5",
            "python -m pytest",
            "Work-ledger",
            "does not own Composition, Integration, Site, or Pages",
        ):
            with self.subTest(required=required):
                self.assertIn(required, readme)

    def test_policy_maintainer_route_points_to_real_local_sources(self):
        for relative in (
            "AGENTS.md",
            ".agent-policy.yml",
            ".agent-policy.lock",
            "repository-policy/maintainer-validation.md",
            "skills/orchestrate-repository-change/SKILL.md",
        ):
            with self.subTest(relative=relative):
                self.assertTrue((ROOT / relative).is_file())


if __name__ == "__main__":
    unittest.main()
