from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_LOCK = ROOT / "publication-sources.json"
DEPLOYMENT_STATE = ROOT / "deployment-state.json"

COMPOSITION_REVISION = "353ffd49279618a23efa1892d703e8f1de6c0c4a"
POLICY_REVISION = "46cfe5acbb91c1e4a6ece18dc2a429df3afa7268"

ACTIVE_OPERATIONAL_FILES = (
    ".github/workflows/build-pages.yml",
    ".github/workflows/deploy-pages.yml",
    "scripts/resolve_publication_sources.py",
    "scripts/generate_repository_trees_composition.py",
    "scripts/generate_repository_file_previews_composition.py",
    "scripts/generate_repository_browser_composition.py",
    "scripts/run_composition_navigation.py",
    "scripts/check_mobile_layout.py",
)

RETIRED_OPERATIONAL_PATTERNS = (
    "refs/heads/skill",
    "refs/heads/webapp",
    "skill_ref:",
    "webapp_ref:",
    "path: skill-source",
    "path: webapp-source",
    "--publication skill=",
    "--publication webapp=",
    "--provider skill=",
    "--provider webapp=",
    "--branch skill=",
    "--branch webapp=",
    "/repository-trees/skill/",
    "/repository-trees/webapp/",
)


class LegacyBranchRetirementTests(unittest.TestCase):
    def test_source_lock_uses_only_retirement_ready_authorities(self) -> None:
        source_lock = json.loads(SOURCE_LOCK.read_text(encoding="utf-8"))

        self.assertEqual(
            source_lock["publications"],
            {
                "composition": {"revision": COMPOSITION_REVISION},
                "policy": {"revision": POLICY_REVISION},
            },
        )

    def test_deployment_state_records_retirement_readiness(self) -> None:
        state = json.loads(DEPLOYMENT_STATE.read_text(encoding="utf-8"))

        self.assertEqual(state["locked_composition_revision"], COMPOSITION_REVISION)
        self.assertIn("retirement readiness completed", state["reason"])
        conditions = state["completed_conditions"]
        self.assertTrue(
            any(
                "legacy skill and webapp branch refs are historical-only" in condition
                for condition in conditions
            )
        )

    def test_active_site_operations_do_not_reintroduce_legacy_branches(self) -> None:
        for relative_path in ACTIVE_OPERATIONAL_FILES:
            path = ROOT / relative_path
            content = path.read_text(encoding="utf-8")
            for pattern in RETIRED_OPERATIONAL_PATTERNS:
                with self.subTest(path=relative_path, pattern=pattern):
                    self.assertNotIn(pattern, content)


if __name__ == "__main__":
    unittest.main()
