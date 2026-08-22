from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_LOCK = ROOT / "publication-sources.json"
DEPLOYMENT_STATE = ROOT / "deployment-state.json"
LANGUAGE_POLICY = ROOT / "LANGUAGE.md"

COMPOSITION_REVISION = "72324eca6ec17f3b64cb967e2d2630c7f88eec1b"
POLICY_REVISION = "3388f2df6c59cf2466b114cc236dd1b512349dc7"
SKILL_ARCHIVE_REVISION = "b8b735dbe525ca76316fec445cdce43db02a955e"
WEBAPP_ARCHIVE_REVISION = "fa269e1310a37ad46f3644ed4f46954a815380ec"

ACTIVE_OPERATIONAL_FILES = (
    ".github/workflows/build-pages.yml",
    ".github/workflows/deploy-pages.yml",
    ".github/workflows/provider-coexistence.yml",
    "scripts/resolve_publication_sources.py",
    "scripts/validate_provider_coexistence.py",
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
    def test_source_lock_uses_only_active_external_authorities(self) -> None:
        source_lock = json.loads(SOURCE_LOCK.read_text(encoding="utf-8"))

        self.assertEqual(
            source_lock["publications"],
            {
                "composition": {"revision": COMPOSITION_REVISION},
                "policy": {"revision": POLICY_REVISION},
            },
        )

    def test_deployment_state_records_completed_retirement(self) -> None:
        state = json.loads(DEPLOYMENT_STATE.read_text(encoding="utf-8"))

        self.assertEqual(state["locked_composition_revision"], COMPOSITION_REVISION)
        self.assertIn("branch retirement", state["reason"])
        conditions = state["completed_conditions"]
        retirement_condition = next(
            condition
            for condition in conditions
            if "legacy skill and webapp branch refs are deleted" in condition
        )
        self.assertIn("archive/skill-final", retirement_condition)
        self.assertIn(SKILL_ARCHIVE_REVISION, retirement_condition)
        self.assertIn("archive/webapp-final", retirement_condition)
        self.assertIn(WEBAPP_ARCHIVE_REVISION, retirement_condition)
        self.assertTrue(
            any(
                "active canonical authorities are site, policy, and composition" in condition
                for condition in conditions
            )
        )
        lifecycle_boundary = next(
            condition
            for condition in conditions
            if "Composer lifecycle semantics are owned by the composition authority"
            in condition
        )
        self.assertIn("outside this Site migration-state record", lifecycle_boundary)
        self.assertTrue(
            any(
                "validates Policy–Composition coexistence" in condition
                and "without becoming a consumer-state management authority" in condition
                for condition in conditions
            )
        )
        self.assertFalse(
            any("future Composition work" in condition for condition in conditions)
        )

    def test_language_policy_uses_current_authority_and_translation_ownership(self) -> None:
        policy = LANGUAGE_POLICY.read_text(encoding="utf-8")

        self.assertIn(
            "current `site`, `policy`, and `composition` authority branches",
            policy,
        )
        self.assertIn(
            "The authority that owns a canonical document also owns its translation files",
            policy,
        )
        self.assertIn(
            "the `policy` and `composition` branches therefore own translations",
            policy,
        )
        self.assertIn(
            "`site` does not maintain independent copies of those translations",
            policy,
        )
        self.assertIn("translations/ja/README.md", policy)

    def test_active_site_operations_do_not_reintroduce_legacy_branches(self) -> None:
        for relative_path in ACTIVE_OPERATIONAL_FILES:
            path = ROOT / relative_path
            content = path.read_text(encoding="utf-8")
            for pattern in RETIRED_OPERATIONAL_PATTERNS:
                with self.subTest(path=relative_path, pattern=pattern):
                    self.assertNotIn(pattern, content)


if __name__ == "__main__":
    unittest.main()
