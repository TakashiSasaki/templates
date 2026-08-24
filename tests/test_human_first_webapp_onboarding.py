from __future__ import annotations

import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
WALKTHROUGH = ROOT / "docs" / "guides" / "webapp-product-walkthrough.md"
WALKTHROUGH_JA = ROOT / "translations" / "ja" / "docs" / "guides" / "webapp-product-walkthrough.md"
EXAMPLE_CONFIG = ROOT / "examples" / "onboarding" / "task-ledger" / "composition.json"
CONFIG_SCHEMA = ROOT / "schemas" / "composition-config.schema.json"
INSTALLER_RELEASE = ROOT / "release" / "composition-installer.json"


class HumanFirstWebappOnboardingTests(unittest.TestCase):
    def test_walkthrough_starts_at_zero_to_one_state(self) -> None:
        text = WALKTHROUGH.read_text(encoding="utf-8")
        headings = [
            "## 0. What this walkthrough will produce",
            "## 1. Create the separate product repository",
            "## 2. Check prerequisites",
            "## 3. Install Composition",
            "## 4. Create `composition.json`",
            "## 5. Inspect the repository",
            "## 6. Plan the initial materialization",
            "## 7. Review the plan",
            "## 8. Apply the scaffold",
            "## 9. Validate the scaffold",
            "## 10. Inspect the generated tree and editing boundary",
        ]
        positions = [text.index(heading) for heading in headings]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("separate product repository", text[: positions[-1]])
        self.assertIn("do not clone `takashisasaki/templates`", text.lower())

    def test_initial_commands_are_in_lifecycle_order_and_config_is_absolute(self) -> None:
        text = WALKTHROUGH.read_text(encoding="utf-8")
        inspect = text.index("  inspect\n", text.index("## 5."))
        plan = text.index("  plan --config /absolute/path/to/task-ledger/composition.json", text.index("## 6."))
        apply = text.index("  apply --config /absolute/path/to/task-ledger/composition.json", text.index("## 8."))
        validate = text.index("  validate\n", text.index("## 9."))
        self.assertLess(inspect, plan)
        self.assertLess(plan, apply)
        self.assertLess(apply, validate)
        self.assertIn("process current working directory", text)
        self.assertIn("Initial planning is read-only", text)

    def test_example_configuration_is_schema_valid(self) -> None:
        schema = json.loads(CONFIG_SCHEMA.read_text(encoding="utf-8"))
        config = json.loads(EXAMPLE_CONFIG.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        errors = list(Draft202012Validator(schema).iter_errors(config))
        self.assertEqual(errors, [])
        self.assertEqual(config["recipe"], "webapp")
        self.assertEqual(
            config["components"]["include"],
            ["capability.cli", "capability.runtime", "capability.service"],
        )

    def test_installer_command_tracks_stable_installer_release(self) -> None:
        release = json.loads(INSTALLER_RELEASE.read_text(encoding="utf-8"))
        installer = release["installer"]
        expected = (
            "https://raw.githubusercontent.com/"
            f"{installer['repository']}/{installer['revision']}/{installer['path']}"
        )
        self.assertIn(expected, WALKTHROUGH.read_text(encoding="utf-8"))

    def test_walkthrough_explains_concrete_ownership_and_product_boundary(self) -> None:
        text = WALKTHROUGH.read_text(encoding="utf-8")
        for expected in (
            "`README.md` | `seed`",
            "`contracts/manifest.json` | `generated`",
            "`schemas/*.schema.json` | `managed`",
            "`.template-composition/lock.json` | Composer state",
            "ordinary consumer content",
            "does **not** mean that Task Ledger is implemented",
            "Policy is a **separate authority**, not a Composition capability",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)

    def test_discoverability_entrypoints_prioritize_walkthrough(self) -> None:
        entrypoints = {
            ROOT / "README.md": ("Webapp product walkthrough", "## Lifecycle at a glance"),
            ROOT / "docs" / "index.md": ("Webapp product walkthrough", "## Composition architecture"),
            ROOT / "components" / "artifact.webapp-core" / "files" / "README.md": (
                "Webapp product walkthrough",
                "## What the Webapp recipe defines",
            ),
            ROOT / "components" / "artifact.webapp-core" / "files" / "docs" / "index.md": (
                "Webapp product walkthrough",
                "## Reference",
            ),
        }
        for path, (walkthrough, deeper) in entrypoints.items():
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text(encoding="utf-8")
                self.assertIn(walkthrough, text)
                self.assertLess(text.index(walkthrough), text.index(deeper))

    def test_japanese_walkthrough_keeps_zero_to_one_route(self) -> None:
        text = WALKTHROUGH_JA.read_text(encoding="utf-8")
        for expected in (
            "## 0. この walkthrough で何を作るか",
            "## 1. 別 product repository を作る",
            "## 3. Composition を install する",
            "## 4. `composition.json` を作る",
            "## 5. Repository を inspect する",
            "## 6. Initial materialization を plan する",
            "## 8. Scaffold を apply する",
            "## 9. Scaffold を validate する",
            "/absolute/path/to/task-ledger/composition.json",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)


if __name__ == "__main__":
    unittest.main()
