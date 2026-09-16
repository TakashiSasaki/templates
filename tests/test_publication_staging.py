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
    materialize_many,
)
from scripts.prepare_repository_tree_publication import augment_manifest
from scripts.reader_navigation_locales import load_overlays


ROOT = Path(__file__).resolve().parents[1]
FUTURE_ID = "future-policy-page"
FUTURE_TITLE = "Future policy page"
FUTURE_DESTINATION = "policy/future-policy-page.md"
FUTURE_LOCALIZED = "将来の Policy ページ"
COMPOSITION_STAGING_IDS = (
    "composition-provider-maintenance",
    "composition-installer-release",
)
POLICY_MAINTAINER_STAGING_IDS = (
    "contributing",
    "maintainer-workflow",
    "adr-review-authority-and-github-runtime-boundary",
    "adr-review-result-representation-boundary",
)


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


def _configure_composition_mappings(site_root: Path) -> None:
    # Reconstruct the historical pre-promotion Site state so staging behavior
    # remains regression-tested after these mappings become active authority.
    manifest_path = site_root / "site-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    def remove_promoted(nodes):
        if isinstance(nodes, dict):
            for child in nodes.values():
                if isinstance(child, list):
                    remove_promoted(child)
            return
        retained = []
        for node in nodes:
            children = node.get("children")
            if isinstance(children, list):
                remove_promoted(children)
                retained.append(node)
            elif not (
                node.get("publication") == "composition"
                and node.get("document") in {"provider-maintenance", "installer-release"}
            ):
                retained.append(node)
        nodes[:] = retained

    remove_promoted(manifest["navigation"])
    if "documents" in manifest:
        manifest["documents"] = [
            doc
            for doc in manifest["documents"]
            if not (
                doc.get("publication") == "composition"
                and doc.get("document") in {"provider-maintenance", "installer-release"}
            )
        ]
    write = json.dumps(manifest, ensure_ascii=False, indent=2) + "\n"
    manifest_path.write_text(write, encoding="utf-8")

    locales_path = site_root / "reader-navigation-locales.json"
    locales = json.loads(locales_path.read_text(encoding="utf-8"))
    for locale in locales["locales"]:
        locale["labels"] = [
            label for label in locale["labels"]
            if label.get("id") not in COMPOSITION_STAGING_IDS
        ]
    write = json.dumps(locales, ensure_ascii=False, indent=2) + "\n"
    locales_path.write_text(write, encoding="utf-8")

    staging_path = site_root / "publication-staging.json"
    staging = json.loads(staging_path.read_text(encoding="utf-8"))
    staging["mappings"] = [
        mapping
        for mapping in staging["mappings"]
        if mapping["id"] not in COMPOSITION_STAGING_IDS
    ]
    staging["mappings"].extend(
        [
            {
                "id": COMPOSITION_STAGING_IDS[0],
                "publication": "composition",
                "document": "provider-maintenance",
                "title": "Composition maintainer overview",
                "destination": "composition/authorities/provider-maintenance.md",
                "insert_after": {
                    "publication": "composition",
                    "document": "publication-boundary",
                },
                "localizations": [
                    {
                        "language": "ja",
                        "label_id": COMPOSITION_STAGING_IDS[0],
                        "localized": "Composition メンテナー概要",
                    }
                ],
            },
            {
                "id": COMPOSITION_STAGING_IDS[1],
                "publication": "composition",
                "document": "installer-release",
                "title": "Installer release",
                "destination": "composition/authorities/installer-release.md",
                "insert_after": {
                    "publication": "composition",
                    "document": "publication-boundary",
                },
                "localizations": [
                    {
                        "language": "ja",
                        "label_id": COMPOSITION_STAGING_IDS[1],
                        "localized": "インストーラーリリース",
                    }
                ],
            },
        ]
    )
    staging_path.write_text(
        json.dumps(staging, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _configure_policy_maintainer_mappings(site_root: Path) -> None:
    manifest_path = site_root / "site-manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    def remove_promoted(nodes):
        if isinstance(nodes, dict):
            for child in nodes.values():
                if isinstance(child, list):
                    remove_promoted(child)
            return
        retained = []
        for node in nodes:
            children = node.get("children")
            if isinstance(children, list):
                remove_promoted(children)
                retained.append(node)
            elif not (
                node.get("publication") == "policy"
                and node.get("document") in set(POLICY_MAINTAINER_STAGING_IDS)
            ):
                retained.append(node)
        nodes[:] = retained

    remove_promoted(manifest["navigation"])
    if "documents" in manifest:
        manifest["documents"] = [
            doc
            for doc in manifest["documents"]
            if not (
                doc.get("publication") == "policy"
                and doc.get("document") in set(POLICY_MAINTAINER_STAGING_IDS)
            )
        ]
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    locales_path = site_root / "reader-navigation-locales.json"
    locales = json.loads(locales_path.read_text(encoding="utf-8"))
    label_ids_to_remove = {
        "contributing",
        "maintainer-workflow",
        "adr-review-authority",
        "adr-review-result",
    }
    for locale in locales["locales"]:
        locale["labels"] = [
            label
            for label in locale["labels"]
            if label.get("id") not in label_ids_to_remove
        ]
    locales_path.write_text(
        json.dumps(locales, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    staging_path = site_root / "publication-staging.json"
    staging = json.loads(staging_path.read_text(encoding="utf-8"))
    staging["mappings"] = [
        mapping
        for mapping in staging["mappings"]
        if mapping["id"] not in set(POLICY_MAINTAINER_STAGING_IDS)
    ]
    staging["mappings"].extend([
        {
            "id": "contributing",
            "publication": "policy",
            "document": "contributing",
            "title": "Contributing",
            "destination": "policy/contributing.md",
            "insert_after": {"publication": "policy", "document": "publication-catalog"},
            "localizations": [
                {"language": "ja", "label_id": "contributing", "localized": "コントリビューション"}
            ],
        },
        {
            "id": "maintainer-workflow",
            "publication": "policy",
            "document": "maintainer-workflow",
            "title": "Policy maintainer workflow",
            "destination": "policy/policy-maintainer-workflow.md",
            "insert_after": {"publication": "policy", "document": "publication-catalog"},
            "localizations": [
                {"language": "ja", "label_id": "maintainer-workflow", "localized": "Policy メンテナワークフロー"}
            ],
        },
        {
            "id": "adr-review-authority-and-github-runtime-boundary",
            "publication": "policy",
            "document": "adr-review-authority-and-github-runtime-boundary",
            "title": "ADR-0008 Review authority and GitHub runtime boundary",
            "destination": "policy/adr/0008-review-authority-and-github-runtime-boundary.md",
            "insert_after": {"publication": "policy", "document": "adr-single-agent-policy-skill-runtime-cache"},
            "localizations": [
                {"language": "ja", "label_id": "adr-review-authority", "localized": "ADR-0008 レビュー権限と GitHub ランタイム境界"}
            ],
        },
        {
            "id": "adr-review-result-representation-boundary",
            "publication": "policy",
            "document": "adr-review-result-representation-boundary",
            "title": "ADR-0009 Review result representation boundary",
            "destination": "policy/adr/0009-review-result-representation-boundary.md",
            "insert_after": {"publication": "policy", "document": "adr-single-agent-policy-skill-runtime-cache"},
            "localizations": [
                {"language": "ja", "label_id": "adr-review-result", "localized": "ADR-0009 レビュー結果の表現境界"}
            ],
        },
    ])
    staging_path.write_text(
        json.dumps(staging, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def _pages(nodes):
    if isinstance(nodes, dict):
        for child in nodes.values():
            if isinstance(child, list):
                yield from _pages(child)
        return
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
    def test_two_explicit_mappings_materialize_atomically_with_locales(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            site_root = Path(temporary_directory) / "site-source"
            site_root.mkdir()
            _copy_inputs(site_root)
            _configure_composition_mappings(site_root)
            source_before = {
                name: (site_root / name).read_bytes()
                for name in ("site-manifest.json", "reader-navigation-locales.json")
            }
            active_manifest = json.loads(source_before["site-manifest.json"].decode("utf-8"))
            active_pages = list(_pages(active_manifest["navigation"]))
            self.assertFalse(
                any(
                    page.get("document") in {"provider-maintenance", "installer-release"}
                    for page in active_pages
                )
            )

            staged_root = materialize_many(site_root, list(COMPOSITION_STAGING_IDS))

            self.assertNotEqual(site_root, staged_root)
            self.assertEqual(
                source_before,
                {
                    name: (site_root / name).read_bytes()
                    for name in source_before
                },
            )
            prepared_navigation = _prepared_navigation(staged_root)
            composition_pages = [
                page
                for page in _pages(prepared_navigation)
                if page.get("publication") == "composition"
            ]
            publication_boundary = [
                index
                for index, page in enumerate(composition_pages)
                if page.get("document") == "publication-boundary"
            ][0]
            self.assertEqual(
                [
                    page["document"]
                    for page in composition_pages[publication_boundary + 1 : publication_boundary + 3]
                ],
                ["provider-maintenance", "installer-release"],
            )
            overlays = load_overlays(
                staged_root / "reader-navigation-locales.json", prepared_navigation
            )
            self.assertEqual(
                overlays["ja"]["Composition maintainer overview"],
                "Composition メンテナー概要",
            )
            self.assertEqual(
                overlays["ja"]["Installer release"],
                "インストーラーリリース",
            )

    def test_duplicate_selected_id_fails_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            site_root = Path(temporary_directory)
            _copy_inputs(site_root)
            _configure_composition_mappings(site_root)
            before = {
                name: (site_root / name).read_bytes()
                for name in ("site-manifest.json", "reader-navigation-locales.json")
            }
            with self.assertRaisesRegex(
                PublicationStagingError, "duplicate selected publication staging id"
            ):
                materialize_many(site_root, [COMPOSITION_STAGING_IDS[0]] * 2)
            self.assertEqual(
                before,
                {
                    name: (site_root / name).read_bytes()
                    for name in ("site-manifest.json", "reader-navigation-locales.json")
                },
            )

    def test_second_invalid_mapping_fails_before_any_file_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            site_root = Path(temporary_directory)
            _copy_inputs(site_root)
            _configure_composition_mappings(site_root)
            before = {
                name: (site_root / name).read_bytes()
                for name in ("site-manifest.json", "reader-navigation-locales.json")
            }
            with self.assertRaisesRegex(PublicationStagingError, "unknown publication staging id"):
                materialize_many(site_root, [COMPOSITION_STAGING_IDS[0], "missing"])
            self.assertEqual(
                before,
                {
                    name: (site_root / name).read_bytes()
                    for name in ("site-manifest.json", "reader-navigation-locales.json")
                },
            )

    def test_selected_destination_conflict_fails_before_any_file_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            site_root = Path(temporary_directory)
            _copy_inputs(site_root)
            _configure_composition_mappings(site_root)
            staging_path = site_root / "publication-staging.json"
            staging = json.loads(staging_path.read_text(encoding="utf-8"))
            staging["mappings"][-1]["destination"] = staging["mappings"][-2]["destination"]
            staging_path.write_text(
                json.dumps(staging, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            before = {
                name: (site_root / name).read_bytes()
                for name in ("site-manifest.json", "reader-navigation-locales.json")
            }
            with self.assertRaisesRegex(PublicationStagingError, "duplicate selected staged destination"):
                materialize_many(site_root, list(COMPOSITION_STAGING_IDS))
            self.assertEqual(
                before,
                {
                    name: (site_root / name).read_bytes()
                    for name in ("site-manifest.json", "reader-navigation-locales.json")
                },
            )

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
            site_root = Path(temporary_directory) / "site-source"
            site_root.mkdir()
            _copy_inputs(site_root)
            _configure_future_mapping(site_root)
            source_before = {
                name: (site_root / name).read_bytes()
                for name in ("site-manifest.json", "reader-navigation-locales.json")
            }
            staged_root = materialize(site_root, FUTURE_ID)

            self.assertEqual(
                source_before,
                {name: (site_root / name).read_bytes() for name in source_before},
            )
            prepared_navigation = _prepared_navigation(staged_root)
            overlays = load_overlays(
                staged_root / "reader-navigation-locales.json",
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
            site_root = Path(temporary_directory) / "site-source"
            site_root.mkdir()
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

            staged_root = materialize(site_root, FUTURE_ID)

            prepared_navigation = _prepared_navigation(staged_root)
            overlays = load_overlays(
                staged_root / "reader-navigation-locales.json",
                prepared_navigation,
            )
            staged_locales = json.loads(
                (staged_root / "reader-navigation-locales.json").read_text(encoding="utf-8")
            )
            source_locales = json.loads(
                (site_root / "reader-navigation-locales.json").read_text(encoding="utf-8")
            )
            self.assertEqual(before_locales, staged_locales)
            self.assertEqual(before_locales, source_locales)
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



    def test_policy_maintainer_staging(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            site_root = Path(temporary_directory)
            _copy_inputs(site_root)
            _configure_policy_maintainer_mappings(site_root)

            from scripts.materialize_publication_staging import materialize_many
            snapshot_root = materialize_many(site_root, list(POLICY_MAINTAINER_STAGING_IDS))

            manifest_path = snapshot_root / "site-manifest.json"
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

            documents = json.dumps(manifest)
            for doc in POLICY_MAINTAINER_STAGING_IDS:
                self.assertIn(doc, documents)

class PublicationStagingWorkflowTests(unittest.TestCase):
    def test_reusable_build_materializes_staging_only_when_explicitly_requested(self) -> None:
        workflow = (ROOT / '.github/workflows/site-producer.yml').read_text()
        self.assertIn('publication_staging_id:',workflow)
        self.assertIn('publication_staging_ids:',workflow)
        self.assertIn('if [ -n "$STAGING_IDS" ] && [ -n "$STAGING_ID" ]; then',workflow)
        self.assertIn('--staging-ids "${STAGING_IDS:-$STAGING_ID}"',workflow)
        producer = (Path(__file__).resolve().parents[1] / 'integration/producer.py').read_text()
        self.assertIn('if staging_ids:',producer)
        self.assertIn('stage_models(',producer)
        self.assertNotIn('publication_staging_id',(ROOT / '.github/workflows/deploy-pages.yml').read_text())


if __name__ == "__main__":
    unittest.main()
