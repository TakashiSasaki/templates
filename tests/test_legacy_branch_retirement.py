from __future__ import annotations

import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SOURCE_LOCK = ROOT / "publication-sources.json"
LANGUAGE_POLICY = ROOT / "LANGUAGE.md"

ACTIVE_OPERATIONAL_FILES = (
    ".github/workflows/build-pages.yml",
    ".github/workflows/deploy-pages.yml",
    ".github/workflows/provider-coexistence.yml",
    "scripts/classify_provider_coexistence.py",
    "scripts/resolve_publication_sources.py",
    "scripts/validate_provider_coexistence.py",
    "scripts/generate_repository_trees_composition.py",
    "scripts/generate_repository_file_previews_composition.py",
    "scripts/generate_repository_browser.py",
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
        publications = source_lock["publications"]

        self.assertEqual(set(publications), {"composition", "policy"})
        for provider in ("composition", "policy"):
            with self.subTest(provider=provider):
                self.assertEqual(set(publications[provider]), {"revision"})
                self.assertRegex(
                    publications[provider]["revision"],
                    r"\A[0-9a-f]{40}\Z",
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
