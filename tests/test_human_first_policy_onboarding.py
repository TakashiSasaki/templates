from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
GETTING_STARTED = ROOT / "docs" / "getting-started.md"
GETTING_STARTED_JA = ROOT / "translations" / "ja" / "docs" / "getting-started.md"
INSTALLER_RELEASE = ROOT / "release" / "skill-installer.json"


class HumanFirstPolicyOnboardingTests(unittest.TestCase):
    def test_first_dry_run_precedes_trust_reference_details(self) -> None:
        text = GETTING_STARTED.read_text(encoding="utf-8")
        inspect = text.index("## 3. Inspect the repository with a dry run")
        trust = text.index("## Trust and runtime details")
        self.assertLess(inspect, trust)
        self.assertIn("Bootstrap without `--apply` is a dry run", text[:trust])
        self.assertIn("You do not select an `init` or `adopt` route manually", text[:trust])

    def test_fresh_and_migration_routes_are_explicit(self) -> None:
        text = GETTING_STARTED.read_text(encoding="utf-8")
        for expected in (
            "`unmanaged-empty` — no existing instructions; use **fresh adoption**",
            "`unmanaged-existing` — existing instructions or policy are present; use **migration adoption**",
            "## 4A. Fresh adoption",
            "## 4B. Migration adoption",
            "The existing primary instruction is **not replaced**",
            "adopt preview",
            "adopt finalize --apply",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)

    def test_human_owned_and_managed_boundaries_are_explicit(self) -> None:
        text = GETTING_STARTED.read_text(encoding="utf-8")
        self.assertIn("`.agent-policy.yml` is human-owned configuration", text)
        self.assertIn("`policy/project.md` is human-owned product-specific policy input", text)
        self.assertIn("`.agent-policy.lock`, rendered `AGENTS.md`, and generated validation skills are tool-managed", text)

    def test_managed_first_use_loop_is_render_validate_check(self) -> None:
        text = GETTING_STARTED.read_text(encoding="utf-8")
        section = text[text.index("## 6. Render, validate, and check a managed repository"):text.index("## Trust and runtime details")]
        render = section.index(" render\n")
        validate = section.index(" validate\n")
        check = section.index(" check\n")
        self.assertLess(render, validate)
        self.assertLess(validate, check)

    def test_installer_command_tracks_release_metadata(self) -> None:
        release = json.loads(INSTALLER_RELEASE.read_text(encoding="utf-8"))
        installer = release["installer"]
        expected = (
            "https://raw.githubusercontent.com/"
            f"{installer['repository']}/{installer['revision']}/{installer['path']}"
        )
        self.assertIn(expected, GETTING_STARTED.read_text(encoding="utf-8"))

    def test_japanese_translation_keeps_same_first_use_route(self) -> None:
        text = GETTING_STARTED_JA.read_text(encoding="utf-8")
        for expected in (
            "## 3. Dry run で repository を inspect する",
            "`unmanaged-empty`",
            "`unmanaged-existing`",
            "## 4A. Fresh adoption",
            "## 4B. Migration adoption",
            "render → validate → check",
            "## Trust and runtime details",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)


if __name__ == "__main__":
    unittest.main()
