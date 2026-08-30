from __future__ import annotations

import copy
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from scripts.assemble_publications import load_manifest
from scripts.materialize_publication_staging import (
    PublicationStagingError,
    materialize,
)
from scripts.prepare_repository_tree_publication import augment_manifest
from scripts.reader_navigation_locales import load_overlays


ROOT = Path(__file__).resolve().parents[1]
FUTURE_ID = "future-policy-page"
FUTURE_TITLE = "Future policy page"
FUTURE_DESTINATION = "policy/future-policy-page.md"
FUTURE_LOCALIZED = "将来の Policy ページ"


def _copy_inputs(destination: Path) -> None:
    for name in (
        "publication-staging.json",
        "site-manifest.json",
        "reader-navigation-locales.json",
    ):
        shutil.copy2(ROOT / name, destination / name)


def _configure_future_mapping(site_root: Path) -> None:
    staging_path = site_root / "publication-staging.json"
    staging = json.loads(staging_path.read_text(encoding="utf-8"))
    staging["mappings"][0] = {
        "id": FUTURE_ID,
        "publication": "policy",
        "document": FUTURE_ID,
        "title": FUTURE_TITLE,
        "destination": FUTURE_DESTINATION,
        "insert_after": {
            "publication": "policy",
            "document": "getting-started",
        },
        "localizations": [
            {
                "language": "ja",
                "label_id": FUTURE_ID,
                "localized": FUTURE_LOCALIZED,
            }
        ],
    }
    staging_path.write_text(
        json.dumps(staging, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _pages(nodes):
    for node in nodes:
        if "children" in node:
            yield from _pages(node["children"])
        else:
            yield node


def _prepared_navigation(site_root: Path):
    manifest_path = site_root / "site-manifest.json"
    load_manifest(manifest_path)
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    return augment_manifest(manifest)["navigation"]


class PublicationStagingMaterializationTests(unittest.TestCase):
    def test_future_mapping_materializes_without_changing_active_authority(self) -> None:
        root_manifest_before = (ROOT / "site-manifest.json").read_bytes()
        root_locales_before = (ROOT / "reader-navigation-locales.json").read_bytes()
        active_manifest = json.loads(root_manifest_before.decode("utf-8"))
        active_pages = list(_pages(active_manifest["navigation"]))
        self.assertTrue(
            any(
                page.get("publication") == "policy"
                and page.get("document") == "policy-concepts"
                for page in active_pages
            )
        )
        self.assertFalse(
            any(
                page.get("publication") == "policy"
                and page.get("document") == FUTURE_ID
                for page in active_pages
            )
        )

        with tempfile.TemporaryDirectory() as temporary_directory:
            site_root = Path(temporary_directory)
            _copy_inputs(site_root)
            _configure_future_mapping(site_root)
            materialize(site_root, FUTURE_ID)

            prepared_navigation = _prepared_navigation(site_root)
            overlays = load_overlays(
                site_root / "reader-navigation-locales.json",
                prepared_navigation,
            )
            policy_pages = [
                page
                for page in _pages(prepared_navigation)
                if page.get("publication") == "policy"
            ]
            identifiers = [page["document"] for page in policy_pages]
            getting_started = identifiers.index("getting-started")
            self.assertEqual(FUTURE_ID, identifiers[getting_started + 1])
            future_page = policy_pages[getting_started + 1]
            self.assertEqual(FUTURE_TITLE, future_page["title"])
            self.assertEqual(FUTURE_DESTINATION, future_page["destination"])
            self.assertEqual(FUTURE_LOCALIZED, overlays["ja"][FUTURE_TITLE])
            self.assertIn("Repository trees", overlays["ja"])
            self.assertIn("Composition tree", overlays["ja"])
            self.assertIn("Policy tree", overlays["ja"])

        self.assertEqual(root_manifest_before, (ROOT / "site-manifest.json").read_bytes())
        self.assertEqual(
            root_locales_before,
            (ROOT / "reader-navigation-locales.json").read_bytes(),
        )

    def test_unknown_staging_id_fails_without_mutating_site_files(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            site_root = Path(temporary_directory)
            _copy_inputs(site_root)
            before = {
                name: (site_root / name).read_bytes()
                for name in ("site-manifest.json", "reader-navigation-locales.json")
            }
            with self.assertRaises(PublicationStagingError):
                materialize(site_root, "missing")
            after = {
                name: (site_root / name).read_bytes()
                for name in ("site-manifest.json", "reader-navigation-locales.json")
            }
            self.assertEqual(before, after)

    def test_historical_active_staging_id_is_rejected_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            site_root = Path(temporary_directory)
            _copy_inputs(site_root)
            before = {
                name: (site_root / name).read_bytes()
                for name in ("site-manifest.json", "reader-navigation-locales.json")
            }
            with self.assertRaisesRegex(
                PublicationStagingError,
                "already active",
            ):
                materialize(site_root, "policy-concepts")
            after = {
                name: (site_root / name).read_bytes()
                for name in ("site-manifest.json", "reader-navigation-locales.json")
            }
            self.assertEqual(before, after)

    def test_existing_destination_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            site_root = Path(temporary_directory)
            _copy_inputs(site_root)
            _configure_future_mapping(site_root)
            staging_path = site_root / "publication-staging.json"
            staging = json.loads(staging_path.read_text(encoding="utf-8"))
            staging["mappings"][0]["destination"] = "policy/getting-started.md"
            staging_path.write_text(
                json.dumps(staging, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                PublicationStagingError,
                "staged destination is already active",
            ):
                materialize(site_root, FUTURE_ID)

    def test_missing_anchor_is_rejected_without_partial_write(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            site_root = Path(temporary_directory)
            _copy_inputs(site_root)
            _configure_future_mapping(site_root)
            staging_path = site_root / "publication-staging.json"
            staging = json.loads(staging_path.read_text(encoding="utf-8"))
            staging["mappings"][0]["insert_after"]["document"] = "not-present"
            staging_path.write_text(
                json.dumps(staging, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            before_manifest = (site_root / "site-manifest.json").read_bytes()
            before_locales = (site_root / "reader-navigation-locales.json").read_bytes()
            with self.assertRaisesRegex(PublicationStagingError, "anchor"):
                materialize(site_root, FUTURE_ID)
            self.assertEqual(
                before_manifest,
                (site_root / "site-manifest.json").read_bytes(),
            )
            self.assertEqual(
                before_locales,
                (site_root / "reader-navigation-locales.json").read_bytes(),
            )

    def test_new_title_requires_exact_locale_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            site_root = Path(temporary_directory)
            _copy_inputs(site_root)
            _configure_future_mapping(site_root)
            staging_path = site_root / "publication-staging.json"
            staging = json.loads(staging_path.read_text(encoding="utf-8"))
            staging["mappings"][0]["localizations"] = []
            staging_path.write_text(
                json.dumps(staging, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                PublicationStagingError,
                "exactly cover active reader locales",
            ):
                materialize(site_root, FUTURE_ID)

    def test_invalid_staging_language_is_rejected_at_the_contract_boundary(self) -> None:
        for invalid in ("JA", "Japanese", "j", "en"):
            with self.subTest(language=invalid):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    site_root = Path(temporary_directory)
                    _copy_inputs(site_root)
                    _configure_future_mapping(site_root)
                    staging_path = site_root / "publication-staging.json"
                    staging = json.loads(staging_path.read_text(encoding="utf-8"))
                    staging["mappings"][0]["localizations"][0]["language"] = invalid
                    staging_path.write_text(
                        json.dumps(staging, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    with self.assertRaisesRegex(
                        PublicationStagingError,
                        "non-English lowercase language tag",
                    ):
                        materialize(site_root, FUTURE_ID)

    def test_invalid_staging_label_id_is_rejected_at_the_contract_boundary(self) -> None:
        for invalid in ("Policy Concepts", "PolicyConcepts", "policy_concepts"):
            with self.subTest(label_id=invalid):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    site_root = Path(temporary_directory)
                    _copy_inputs(site_root)
                    _configure_future_mapping(site_root)
                    staging_path = site_root / "publication-staging.json"
                    staging = json.loads(staging_path.read_text(encoding="utf-8"))
                    staging["mappings"][0]["localizations"][0]["label_id"] = invalid
                    staging_path.write_text(
                        json.dumps(staging, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    with self.assertRaisesRegex(
                        PublicationStagingError,
                        "lowercase kebab-case",
                    ):
                        materialize(site_root, FUTURE_ID)

    def test_existing_canonical_title_reuses_locale_overlay(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            site_root = Path(temporary_directory)
            _copy_inputs(site_root)
            _configure_future_mapping(site_root)
            staging_path = site_root / "publication-staging.json"
            staging = json.loads(staging_path.read_text(encoding="utf-8"))
            mapping = staging["mappings"][0]
            mapping["title"] = "Getting started"
            mapping["localizations"] = []
            staging_path.write_text(
                json.dumps(staging, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            before_locales = json.loads(
                (site_root / "reader-navigation-locales.json").read_text(encoding="utf-8")
            )

            materialize(site_root, FUTURE_ID)

            prepared_navigation = _prepared_navigation(site_root)
            overlays = load_overlays(
                site_root / "reader-navigation-locales.json",
                prepared_navigation,
            )
            after_locales = json.loads(
                (site_root / "reader-navigation-locales.json").read_text(encoding="utf-8")
            )
            self.assertEqual(before_locales, after_locales)
            self.assertIn("Getting started", overlays["ja"])

    def test_existing_canonical_title_rejects_new_localizations(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            site_root = Path(temporary_directory)
            _copy_inputs(site_root)
            _configure_future_mapping(site_root)
            staging_path = site_root / "publication-staging.json"
            staging = json.loads(staging_path.read_text(encoding="utf-8"))
            staging["mappings"][0]["title"] = "Getting started"
            staging_path.write_text(
                json.dumps(staging, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                PublicationStagingError,
                "localizations must be empty when the canonical title already exists",
            ):
                materialize(site_root, FUTURE_ID)

    def test_schema_version_requires_exact_integer_one(self) -> None:
        for invalid in (True, 1.0, 2):
            with self.subTest(schema_version=invalid):
                with tempfile.TemporaryDirectory() as temporary_directory:
                    site_root = Path(temporary_directory)
                    _copy_inputs(site_root)
                    staging_path = site_root / "publication-staging.json"
                    staging = json.loads(staging_path.read_text(encoding="utf-8"))
                    staging["schema_version"] = invalid
                    staging_path.write_text(
                        json.dumps(staging, ensure_ascii=False, indent=2) + "\n",
                        encoding="utf-8",
                    )
                    with self.assertRaisesRegex(
                        PublicationStagingError,
                        "integer schema version 1",
                    ):
                        materialize(site_root, "policy-concepts")

    def test_nonstandard_json_numeric_constant_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            site_root = Path(temporary_directory)
            _copy_inputs(site_root)
            staging_path = site_root / "publication-staging.json"
            text = staging_path.read_text(encoding="utf-8")
            staging_path.write_text(
                text.replace('"schema_version": 1', '"schema_version": NaN', 1),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                PublicationStagingError,
                "non-standard numeric constant: NaN",
            ):
                materialize(site_root, "policy-concepts")

    def test_duplicate_staging_id_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            site_root = Path(temporary_directory)
            _copy_inputs(site_root)
            staging_path = site_root / "publication-staging.json"
            staging = json.loads(staging_path.read_text(encoding="utf-8"))
            staging["mappings"].append(copy.deepcopy(staging["mappings"][0]))
            staging_path.write_text(
                json.dumps(staging, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                PublicationStagingError,
                "duplicate publication staging id: policy-concepts",
            ):
                materialize(site_root, "policy-concepts")

    def test_non_markdown_destination_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            site_root = Path(temporary_directory)
            _copy_inputs(site_root)
            _configure_future_mapping(site_root)
            staging_path = site_root / "publication-staging.json"
            staging = json.loads(staging_path.read_text(encoding="utf-8"))
            staging["mappings"][0]["destination"] = "policy/future-policy-page.html"
            staging_path.write_text(
                json.dumps(staging, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                PublicationStagingError,
                "must be a Markdown destination",
            ):
                materialize(site_root, FUTURE_ID)

    def test_unsafe_destination_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            site_root = Path(temporary_directory)
            _copy_inputs(site_root)
            _configure_future_mapping(site_root)
            staging_path = site_root / "publication-staging.json"
            staging = json.loads(staging_path.read_text(encoding="utf-8"))
            staging["mappings"][0]["destination"] = "../future-policy-page.md"
            staging_path.write_text(
                json.dumps(staging, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            with self.assertRaises(PublicationStagingError):
                materialize(site_root, FUTURE_ID)


class PublicationStagingWorkflowTests(unittest.TestCase):
    def test_reusable_build_materializes_staging_only_when_explicitly_requested(self) -> None:
        workflow = (ROOT / ".github/workflows/build-pages.yml").read_text(encoding="utf-8")
        deploy = (ROOT / ".github/workflows/deploy-pages.yml").read_text(encoding="utf-8")

        self.assertIn("publication_staging_id:", workflow)
        self.assertIn("Materialize staged publication mapping", workflow)
        self.assertIn("inputs.publication_staging_id != ''", workflow)
        self.assertIn("scripts/materialize_publication_staging.py", workflow)
        self.assertIn(
            "PUBLICATION_STAGING_ID: ${{ inputs.publication_staging_id }}",
            workflow,
        )
        self.assertIn('--staging-id "$PUBLICATION_STAGING_ID"', workflow)
        self.assertNotIn('--staging-id "${{ inputs.publication_staging_id }}"', workflow)
        composition_checkout = workflow.index("- name: Check out composition publication")
        policy_checkout = workflow.index("- name: Check out policy publication")
        tests = workflow.index("- name: Run site assembly tests")
        materialize_step = workflow.index("- name: Materialize staged publication mapping")
        prepare = workflow.index("- name: Prepare repository-tree publication")
        self.assertLess(composition_checkout, tests)
        self.assertLess(policy_checkout, tests)
        self.assertLess(tests, materialize_step)
        self.assertLess(materialize_step, prepare)
        self.assertNotIn("publication_staging_id", deploy)


if __name__ == "__main__":
    unittest.main()
