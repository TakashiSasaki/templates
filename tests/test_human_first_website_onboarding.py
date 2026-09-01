from __future__ import annotations

import hashlib
import json
import re
import subprocess
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
WALKTHROUGH = ROOT / "docs" / "guides" / "website-product-walkthrough.md"
WALKTHROUGH_JA = (
    ROOT / "translations" / "ja" / "docs" / "guides" / "website-product-walkthrough.md"
)
SELECTION_JA = (
    ROOT / "translations" / "ja" / "docs" / "guides" / "website-webapp-selection.md"
)
CATALOG_JA = ROOT / "translations" / "ja" / "catalog" / "README.md"
EXAMPLE_CONFIG = ROOT / "examples" / "onboarding" / "project-docs" / "composition.json"
PLANNING_EVIDENCE_EXAMPLE = (
    ROOT
    / "examples"
    / "onboarding"
    / "project-docs"
    / "implementation-evidence.planning.json"
)
CONFIG_SCHEMA = ROOT / "schemas" / "composition-config.schema.json"
EVIDENCE_SCHEMA = (
    ROOT
    / "components"
    / "lifecycle.implementation-evidence"
    / "files"
    / "schemas"
    / "implementation-evidence.schema.json"
)
WEBSITE_REVISION = "ca8b8bc9091c6c199224cd9b66c9a59229f1b6ac"
PINNED_WEBSITE_RECIPE_BLOB_SHA = "f22f44ecee7b8e7b5c039be71e818cd5e8bd5840"


def git_blob_sha(data: bytes) -> str:
    return hashlib.sha1(f"blob {len(data)}\0".encode() + data).hexdigest()


def git_show_bytes(revision: str, path: str) -> bytes:
    return subprocess.check_output(
        ["git", "show", f"{revision}:{path}"],
        cwd=ROOT,
    )


class HumanFirstWebsiteOnboardingTests(unittest.TestCase):
    def test_walkthrough_has_ordered_zero_to_one_lifecycle(self) -> None:
        text = WALKTHROUGH.read_text(encoding="utf-8")
        markers = [
            "**Doctor**",
            "**Inspect**",
            "**Plan**",
            "**Review**",
            "**Apply**",
            "**Validate scaffold**",
            "**Define Website contract**",
            "**Define planning evidence**",
            "**Checkpoint planning**",
            "**Implement content and presentation**",
            "**Run product and browser proof**",
            "**Populate and validate product evidence**",
            "**Checkpoint product**",
            "**Optional capabilities**",
            "**Evaluate release readiness**",
        ]
        section = text.index("## Completion path at a glance")
        positions = [text.index(marker, section) for marker in markers]
        self.assertEqual(positions, sorted(positions))
        self.assertIn("scaffold validity is not product completion", text)
        self.assertIn("deferred required browser proof", text)

    def test_walkthrough_selects_website_by_product_identity(self) -> None:
        text = WALKTHROUGH.read_text(encoding="utf-8")
        self.assertIn('"recipe": "website"', text)
        self.assertIn("content/document-oriented", text)
        self.assertIn("Static output does not make this choice", text)
        self.assertIn("Do not directly include `foundation.web`", text)
        self.assertIn("`artifact.website-core`", text)
        self.assertIn("transitive `foundation.web`", text)
        self.assertIn(
            "**not** `artifact.webapp-core`, `capability.pwa`, or `capability.runtime`",
            text,
        )

    def test_walkthrough_pins_every_runner_invocation_to_one_revision(self) -> None:
        text = WALKTHROUGH.read_text(encoding="utf-8")
        self.assertIn(
            "currently published skill's stable runtime manifest predates the `website` recipe",
            text,
        )
        shell_blocks = re.findall(r"```sh\n(.*?)\n```", text, flags=re.DOTALL)
        runner_commands = [block for block in shell_blocks if "scripts/run.py" in block]
        self.assertGreaterEqual(len(runner_commands), 7)
        for command in runner_commands:
            with self.subTest(command=command):
                self.assertEqual(command.count("--revision"), 1)
                self.assertIn(f"--revision {WEBSITE_REVISION}", command)
        self.assertNotIn("--revision 98e38718abef02f4e1ffdd864764b77dcc2d4375", text)
        self.assertNotIn("--revision 379073f376ce1de80948abd2e92d5560b573e7e6", text)
        self.assertIn(
            f"Confirm the doctor output identifies `{WEBSITE_REVISION}` as the selected toolchain",
            text,
        )

    def test_pinned_recipe_matches_every_optional_path_advertised_by_walkthrough(self) -> None:
        recipe_bytes = git_show_bytes(WEBSITE_REVISION, "recipes/website.json")
        self.assertEqual(git_blob_sha(recipe_bytes), PINNED_WEBSITE_RECIPE_BLOB_SHA)
        recipe = json.loads(recipe_bytes)
        text = WALKTHROUGH.read_text(encoding="utf-8")
        start = text.index("## 14. Optional")
        end = text.index("## 15. Execute release-readiness evaluation")
        optional_section = text[start:end]
        advertised = set(
            re.findall(r"`((?:capability|lifecycle)\.[a-z0-9.-]+)`", optional_section)
        )
        self.assertEqual(advertised, set(recipe["optional_components"]))
        self.assertIn(
            f"At immutable revision `{WEBSITE_REVISION}`, the `website` recipe exposes exactly",
            optional_section,
        )

    def test_website_contract_boundary_does_not_reintroduce_webapp_semantics(self) -> None:
        text = WALKTHROUGH.read_text(encoding="utf-8")
        for required in (
            "`contracts/browser-identity.json`",
            "`contracts/routes.json`",
            "`contracts/viewports.json`",
            "`contracts/site-structure.json`",
            "`contracts/document-metadata.json`",
            "`contracts/site-discovery.json`",
        ):
            self.assertIn(required, text)
        for private in (
            "`contracts/application-routes.json`",
            "`contracts/surfaces.json`",
            "`contracts/ui-states.json`",
        ):
            self.assertIn(private, text)
        self.assertIn("Project Docs does **not** need Webapp-private", text)

    def test_planning_evidence_example_is_schema_valid_and_explicitly_used(self) -> None:
        schema = json.loads(EVIDENCE_SCHEMA.read_text(encoding="utf-8"))
        evidence = json.loads(PLANNING_EVIDENCE_EXAMPLE.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(evidence)), [])
        self.assertEqual(evidence["mode"], "planning")
        self.assertGreaterEqual(len(evidence["requirements"]), 1)
        text = WALKTHROUGH.read_text(encoding="utf-8")
        self.assertIn("implementation-evidence.planning.json", text)
        self.assertIn('"id": "WEBSITE-BROWSER"', text)
        self.assertIn('"id": "WEBSITE-DISCOVERY"', text)
        self.assertIn("every target derived from the current contracts is covered", text)

    def test_checkpoint_lifecycle_is_mandatory_and_precedes_implementation(self) -> None:
        text = WALKTHROUGH.read_text(encoding="utf-8")
        planning = text.index("## 9. Validate planning and create the mandatory planning checkpoint")
        implementation = text.index("## 10. Implement the Website in consumer-owned files")
        product_checkpoint = text.index(
            "## 13. Create the mandatory product checkpoint and revalidate"
        )
        self.assertLess(planning, implementation)
        self.assertLess(implementation, product_checkpoint)
        self.assertIn(
            "transitively requires `lifecycle.lifecycle-checkpoints`",
            text,
        )
        self.assertIn("Do not start implementation until that planning checkpoint", text)
        self.assertIn("`lifecycle.next_actions`", text)
        self.assertIn("`next_action_command.argv`", text)
        self.assertIn("closed planning-to-product lifecycle state", text)

    def test_seeded_product_identity_and_favicon_are_explicitly_replaced_or_materialized(self) -> None:
        text = WALKTHROUGH.read_text(encoding="utf-8")
        self.assertIn("favicon.svg\nassets/site.css", text)
        self.assertIn(
            "seeded `contracts/browser-identity.json` declares `favicon.svg`",
            text,
        )
        self.assertIn(
            "Either create a truthful `favicon.svg` at the declared location",
            text,
        )
        self.assertIn(
            "set `siteName` to the actual product name `Project Docs`",
            text,
        )
        self.assertIn('seeded `siteName: "Website"` is a scaffold placeholder', text)
        self.assertIn('`siteName: "Project Docs"` rather than the seeded placeholder', text)

    def test_browser_proof_boundary_is_explicit_and_fail_closed(self) -> None:
        text = WALKTHROUGH.read_text(encoding="utf-8")
        for expected in (
            "real browser-backed positive and negative proof",
            "Source inspection, successful HTTP fetches, unit tests, or contract declarations alone are **not** browser-backed proof",
            "mark it deferred and keep release readiness `NOT READY`",
            "execution capabilities include `browser`",
            "link every record from the stable requirement that owns its declared target",
            "every linked record at least one valid `releaseGateIds` entry",
            "`lifecycle.next_actions`",
            "`next_action_command.argv`",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)

    def test_release_readiness_is_an_executed_machine_action_not_a_prose_claim(self) -> None:
        text = WALKTHROUGH.read_text(encoding="utf-8")
        product_checkpoint = text.index("## 13. Create the mandatory product checkpoint and revalidate")
        readiness = text.index("## 15. Execute release-readiness evaluation")
        completion = text.index("## 16. Completion criteria")
        self.assertLess(product_checkpoint, readiness)
        self.assertLess(readiness, completion)
        for expected in (
            "`check-release-readiness`",
            "complete `next_action_command.argv`",
            "`release_readiness` field as authoritative",
            "`ready` means there are no blocking conditions",
            "`not-ready` means at least one blocking condition remains",
            "provider/action execution failure is an operational failure",
            "has actually been executed and its structured result recorded",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)

    def test_example_configuration_is_schema_valid_and_minimal(self) -> None:
        schema = json.loads(CONFIG_SCHEMA.read_text(encoding="utf-8"))
        config = json.loads(EXAMPLE_CONFIG.read_text(encoding="utf-8"))
        Draft202012Validator.check_schema(schema)
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(config)), [])
        self.assertEqual(config["recipe"], "website")
        self.assertEqual(config["components"], {"include": [], "exclude": []})

    def test_selection_and_documentation_entrypoints_expose_website_onboarding(self) -> None:
        docs_index = (ROOT / "docs" / "index.md").read_text(encoding="utf-8")
        catalog = (ROOT / "catalog" / "README.md").read_text(encoding="utf-8")
        selection = (
            ROOT / "docs" / "guides" / "website-webapp-selection.md"
        ).read_text(encoding="utf-8")
        self.assertIn("Website product walkthrough", docs_index)
        self.assertIn("website-product-walkthrough.md", docs_index)
        self.assertIn("Website product walkthrough", catalog)
        self.assertIn("website-product-walkthrough.md", catalog)
        self.assertIn(
            "Website or Web application guide", WALKTHROUGH.read_text(encoding="utf-8")
        )
        self.assertIn("`website`", selection)
        self.assertIn("`webapp`", selection)

    def test_japanese_reader_links_stay_within_the_japanese_derivative_tree(self) -> None:
        catalog = CATALOG_JA.read_text(encoding="utf-8")
        selection = SELECTION_JA.read_text(encoding="utf-8")
        self.assertIn("(../docs/guides/website-webapp-selection.md)", catalog)
        self.assertIn("(../docs/guides/website-product-walkthrough.md)", catalog)
        self.assertIn("(../docs/guides/composition-concepts.md)", catalog)
        self.assertNotIn("(../../docs/guides/website-webapp-selection.md)", catalog)
        self.assertNotIn("(../../docs/guides/website-product-walkthrough.md)", catalog)
        self.assertIn("(../../catalog/README.md)", selection)
        self.assertNotIn("(../../../catalog/README.md)", selection)

    def test_publication_and_translation_authorities_include_new_reader_paths(self) -> None:
        publication = json.loads(
            (ROOT / "docs" / "publication-catalog.json").read_text(encoding="utf-8")
        )
        published = {entry["source"] for entry in publication["documents"]}
        self.assertIn("docs/guides/website-webapp-selection.md", published)
        self.assertIn("docs/guides/website-product-walkthrough.md", published)

        manifest = json.loads(
            (ROOT / "translations" / "manifest.json").read_text(encoding="utf-8")
        )
        translated = {
            entry["canonical"]: entry for entry in manifest["translations"]
        }
        self.assertEqual(
            translated["docs/guides/website-product-walkthrough.md"]["translation"],
            "translations/ja/docs/guides/website-product-walkthrough.md",
        )
        self.assertEqual(
            translated["docs/guides/website-product-walkthrough.md"]["canonical_blob_sha"],
            git_blob_sha(WALKTHROUGH.read_bytes()),
        )
        self.assertEqual(
            translated["docs/guides/website-webapp-selection.md"]["translation"],
            "translations/ja/docs/guides/website-webapp-selection.md",
        )

    def test_japanese_walkthrough_preserves_core_boundaries(self) -> None:
        text = WALKTHROUGH_JA.read_text(encoding="utf-8")
        for expected in (
            "参考訳（非正本）",
            "## Completion path at a glance",
            '"recipe": "website"',
            "scaffold validity は product completion ではない",
            "`artifact.website-core`",
            "transitive `foundation.web`",
            WEBSITE_REVISION,
            "implementation-evidence.planning.json",
            '"id": "WEBSITE-BROWSER"',
            '"id": "WEBSITE-DISCOVERY"',
            "mandatory planning checkpoint",
            "Mandatory product checkpoint",
            "favicon.svg",
            '`siteName` を実際の product 名 `Project Docs`',
            "browser-backed proof になりません",
            "PWA は cross-cutting capability",
            "`check-release-readiness`",
            "`release_readiness` field",
            "`not-ready`",
        ):
            with self.subTest(expected=expected):
                self.assertIn(expected, text)


if __name__ == "__main__":
    unittest.main()
