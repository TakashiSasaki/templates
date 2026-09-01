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
CONSUMER_GUIDE_JA = ROOT / "translations" / "ja" / "docs" / "consumer-guide.md"
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
PRODUCT_EVIDENCE_EXAMPLE = (
    ROOT
    / "examples"
    / "onboarding"
    / "project-docs"
    / "implementation-evidence.product.json"
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
RELEASE_DESCRIPTOR = ROOT / "release" / "composition-installer.json"


def stable_toolchain_revision() -> str:
    descriptor = json.loads(RELEASE_DESCRIPTOR.read_text(encoding="utf-8"))
    toolchain = descriptor.get("toolchain")
    if not isinstance(toolchain, dict):
        raise AssertionError("stable release descriptor must declare toolchain")
    revision = toolchain.get("revision")
    if not isinstance(revision, str):
        raise AssertionError("stable release descriptor must declare toolchain revision")
    return revision


WEBSITE_REVISION = stable_toolchain_revision()


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

    def test_walkthrough_uses_stable_runner_without_revision_bridge(self) -> None:
        text = WALKTHROUGH.read_text(encoding="utf-8")
        self.assertIn("published stable Composition toolchain is Website-capable", text)
        shell_blocks = re.findall(r"```sh\n(.*?)\n```", text, flags=re.DOTALL)
        runner_commands = [block for block in shell_blocks if "scripts/run.py" in block]
        self.assertGreaterEqual(len(runner_commands), 7)
        for command in runner_commands:
            with self.subTest(command=command):
                self.assertNotIn("--revision", command)
        self.assertIn(
            f"Confirm the doctor output identifies `{WEBSITE_REVISION}` as the selected stable toolchain",
            text,
        )

    def test_stable_recipe_matches_every_optional_path_advertised_by_walkthrough(self) -> None:
        recipe_bytes = git_show_bytes(WEBSITE_REVISION, "recipes/website.json")
        current_recipe_bytes = (ROOT / "recipes" / "website.json").read_bytes()
        self.assertEqual(git_blob_sha(recipe_bytes), git_blob_sha(current_recipe_bytes))
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
            f"At stable toolchain revision `{WEBSITE_REVISION}`, the `website` recipe exposes exactly",
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

    def test_japanese_walkthrough_links_to_stable_install_anchor_and_product_asset(self) -> None:
        text = WALKTHROUGH_JA.read_text(encoding="utf-8")
        consumer_guide = CONSUMER_GUIDE_JA.read_text(encoding="utf-8")
        self.assertIn('<a id="composition-skill-install"></a>', consumer_guide)
        self.assertIn("(../consumer-guide.md#composition-skill-install)", text)
        self.assertNotIn("#install-and-run-the-composition-skill", text)

        match = re.search(
            r"\[published Project Docs product evidence example\]\(([^)]+)\)",
            text,
        )
        self.assertIsNotNone(match)
        assert match is not None
        linked_target = (WALKTHROUGH_JA.parent / match.group(1)).resolve()
        self.assertEqual(linked_target, PRODUCT_EVIDENCE_EXAMPLE.resolve())
        self.assertTrue(linked_target.is_file())

        publication = json.loads(
            (ROOT / "docs" / "publication-catalog.json").read_text(encoding="utf-8")
        )
        assets = {entry["source"]: entry["destination"] for entry in publication["assets"]}
        product_destination = assets[
            "examples/onboarding/project-docs/implementation-evidence.product.json"
        ]
        self.assertEqual(
            product_destination,
            "lifecycle/implementation-evidence/project-docs/implementation-evidence.product.json",
        )
        schema_destination = assets[
            "components/lifecycle.implementation-evidence/files/schemas"
        ]
        self.assertEqual(schema_destination, "lifecycle/implementation-evidence/schemas")
        evidence = json.loads(PRODUCT_EVIDENCE_EXAMPLE.read_text(encoding="utf-8"))
        published_schema = (
            ROOT / Path(product_destination).parent / evidence["$schema"]
        ).resolve()
        expected_published_schema = (
            ROOT / schema_destination / "implementation-evidence.schema.json"
        ).resolve()
        self.assertEqual(published_schema, expected_published_schema)

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
