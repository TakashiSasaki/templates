from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
WALKTHROUGH = ROOT / "docs" / "guides" / "webapp-product-walkthrough.md"
WALKTHROUGH_JA = ROOT / "translations" / "ja" / "docs" / "guides" / "webapp-product-walkthrough.md"
EXAMPLE_CONFIG = ROOT / "examples" / "onboarding" / "task-ledger" / "composition.json"
CONFIG_SCHEMA = ROOT / "schemas" / "composition-config.schema.json"
INSTALLER_RELEASE = ROOT / "release" / "composition-installer.json"
BROWSER_PROOF = ROOT / "examples" / "onboarding" / "task-ledger" / "browser_proof.py"
BROWSER_PROOF_REVISION = "d921437bfd1d7a53e7c238222b9e420c3d302a95"


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
        plan = text.index(
            "  plan --config /absolute/path/to/task-ledger/composition.json",
            text.index("## 6."),
        )
        apply = text.index(
            "  apply --config /absolute/path/to/task-ledger/composition.json",
            text.index("## 8."),
        )
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

    def test_product_verifier_is_created_before_first_execution(self) -> None:
        text = WALKTHROUGH.read_text(encoding="utf-8")
        creation = text.index("cat > scripts/verify.sh <<'SH'")
        execution = text.index("./scripts/verify.sh", creation + 1)
        self.assertLess(creation, execution)
        self.assertIn("Create `task_ledger/cli.py`", text[:execution])
        self.assertIn("Create `tests/test_task_ledger.py`", text[:execution])
        self.assertIn("chmod +x scripts/verify.sh", text[:execution])

    def test_reference_product_scope_and_browser_proof_boundary_are_truthful(self) -> None:
        text = WALKTHROUGH.read_text(encoding="utf-8")
        for expected in (
            "does not claim browser title editing",
            "API also supports title updates",
            "Optional task notes",
            "is **not** browser-level proof",
            "real positive and negative",
            "positive and negative `end-to-end-test` paths",
            "Do not relabel source inspection, HTTP reachability, or unit tests",
            "keep the evidence document in `template` mode",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)
        self.assertNotIn("browser UI for creating, listing, editing", text)

        japanese = WALKTHROUGH_JA.read_text(encoding="utf-8")
        for expected in (
            "completion requirement ではありません",
            "API は title update も提供します",
            "browser title editing を claim しません",
            "browser-level proofになりません",
            "実ブラウザを使う positive / negative",
            "positive/negative `end-to-end-test` path",
            "HTTP reachability、unit testをbrowser proofとして再分類",
            "evidence documentを `template` modeに保ちます",
            "`minWidthPx: 0`",
            "coverage-start sentinel",
            "実用上の最小幅は 320px",
            "sentinel と tested minimum の 320px は別の概念",
            "`[\\\"ready\\\", \\\"empty\\\", \\\"error\\\"]`",
            "`Could not load tasks.`",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, japanese)

    def test_real_browser_proof_is_immutable_and_runs_before_product_claim(self) -> None:
        text = WALKTHROUGH.read_text(encoding="utf-8")
        expected_url = (
            "https://raw.githubusercontent.com/TakashiSasaki/templates/"
            f"{BROWSER_PROOF_REVISION}/examples/onboarding/task-ledger/browser_proof.py"
        )
        self.assertIn(expected_url, text)
        self.assertIn("CHROMEWEBDRIVER", text)
        self.assertIn("CHROME_BINARY", text)
        self.assertIn('<h1 id="main-heading" tabindex="-1">Task Ledger</h1>', text)
        self.assertIn("genuine 200% browser page-scale", text)
        self.assertIn("unknown-route browser negative path", text)
        self.assertIn("python tests/test_task_ledger_browser.py", text)
        self.assertLess(
            text.index("python tests/test_task_ledger_browser.py"),
            text.index("## 13. Define and run authoritative product verification"),
        )
        browser_source = BROWSER_PROOF.read_text(encoding="utf-8")
        self.assertEqual(
            browser_source.count(
                "...['#main-heading', '#title', '#new-task button', '#status'].map("
            ),
            2,
        )
        self.assertEqual(
            browser_source.count("...document.querySelectorAll('#tasks li span, #tasks li button'),"),
            2,
        )
        self.assertIn('populated_narrow["labelsVisible"]', browser_source)
        self.assertIn("focus was not preserved on the replacement task action", browser_source)
        self.assertIn("delete did not move focus to the deterministic status-filter fallback", browser_source)
        self.assertIn("error state is not visibly rendered", browser_source)
        self.assertIn(
            "const controls = ['#main-heading', '#title', '#new-task button', '#status'];",
            browser_source,
        )
        compile(browser_source, str(BROWSER_PROOF), "exec")
        pinned = subprocess.run(
            [
                "git",
                "show",
                f"{BROWSER_PROOF_REVISION}:"
                "examples/onboarding/task-ledger/browser_proof.py",
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=True,
        )
        self.assertEqual(pinned.stdout, browser_source)

        japanese = WALKTHROUGH_JA.read_text(encoding="utf-8")
        for expected in (
            expected_url,
            "実ブラウザによる viewport / keyboard proof",
            "genuine 200% browser page-scale",
            "unknown routeのbrowser negative path",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, japanese)

    def test_discoverability_entrypoints_prioritize_first_use(self) -> None:
        entrypoints = {
            ROOT / "README.md": ("Webapp product walkthrough", "## Lifecycle at a glance"),
            ROOT / "docs" / "index.md": (
                "Webapp product walkthrough",
                "## Composition architecture",
            ),
            ROOT / "components" / "artifact.webapp-core" / "files" / "README.md": (
                "Webapp product walkthrough",
                "## What the Webapp recipe defines",
            ),
            ROOT
            / "components"
            / "artifact.webapp-core"
            / "files"
            / "docs"
            / "index.md": ("Web application overview", "## Reference"),
        }
        for path, (first_use, deeper) in entrypoints.items():
            with self.subTest(path=path.relative_to(ROOT)):
                text = path.read_text(encoding="utf-8")
                self.assertIn(first_use, text)
                self.assertLess(text.index(first_use), text.index(deeper))

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
