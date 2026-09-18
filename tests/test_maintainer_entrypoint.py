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


if __name__ == "__main__":
    unittest.main()
