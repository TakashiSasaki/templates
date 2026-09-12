from __future__ import annotations

import gzip
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import generate_composition_playground as playground  # noqa: E402
import generate_composition_playground_intent as playground_intent  # noqa: E402
import generate_composition_playground_publication as publication  # noqa: E402
from composer_core_impl import CompositionError  # noqa: E402

GENERATED = ROOT / "generated"
CATALOG = ROOT / "docs" / "publication-catalog.json"
CLASSIFICATION = ROOT / "docs" / "publication-classification.json"
DOCS_INDEX = ROOT / "docs" / "index.md"
SCHEMA_VALIDATION = ROOT / ".github" / "workflows" / "schema-validation.yml"
REFERENCE_CONSUMER_PUBLICATION = ROOT / ".github" / "workflows" / "reference-consumer-publication.yml"
EXPECTED_SITE_COMPATIBILITY_REVISION = "cbdb90be9e22b8e3212aaccc095bc9e539afcd23"


class CompositionPlaygroundPublicationTests(unittest.TestCase):
    _generated_fixture: tuple[str, dict[str, str], dict[str, bytes]] | None = None
    _build_projection_count = 0

    @classmethod
    def generated_fixture(cls) -> tuple[str, dict[str, str], dict[str, bytes]]:
        """Generate the expensive canonical publication projection once per test process."""
        if cls._generated_fixture is None:
            semantic_revision = publication.semantic_revision_from_manifest(GENERATED)
            semantic_objects = publication.semantic_objects_from_manifest(GENERATED)
            build_projection_count = 0
            real_build_projection = publication.build_projection

            def counted_build_projection(*args, **kwargs):
                nonlocal build_projection_count
                build_projection_count += 1
                return real_build_projection(*args, **kwargs)

            with (
                mock.patch.object(
                    playground,
                    "_git",
                    side_effect=AssertionError(
                        "publication generation must not walk semantic revision history"
                    ),
                ),
                mock.patch.object(
                    publication,
                    "build_projection",
                    side_effect=counted_build_projection,
                ),
            ):
                payloads = publication.publication_payloads(
                    semantic_revision=semantic_revision,
                    semantic_objects=semantic_objects,
                )

            cls._generated_fixture = (semantic_revision, semantic_objects, payloads)
            cls._build_projection_count = build_projection_count
        return cls._generated_fixture

    def test_manifest_pins_exact_semantic_source_and_asset_inventory(self) -> None:
        manifest = publication.read_publication_manifest(GENERATED)
        self.assertEqual(2, manifest["schema_version"])
        self.assertRegex(str(manifest["semantic_revision"]), re.compile(r"^[0-9a-f]{40}$"))
        self.assertEqual(
            set(playground.SEMANTIC_PATHS),
            set(manifest["semantic_objects"]),
        )
        self.assertEqual(
            [publication.BASE_NAME, publication.INTENT_NAME],
            manifest["assets"],
        )
        publication.verify_semantic_snapshot(
            publication.semantic_objects_from_manifest(GENERATED)
        )

    def test_generated_assets_are_deterministic_and_bounded(self) -> None:
        semantic_revision, _, payloads = self.generated_fixture()
        base = payloads[publication.BASE_NAME]
        intent = payloads[publication.INTENT_NAME]
        self.assertEqual(b"\x1f\x8b", base[:2])
        self.assertEqual(b"\x1f\x8b", intent[:2])
        base_projection = json.loads(gzip.decompress(base))
        intent_projection = json.loads(gzip.decompress(intent))
        self.assertEqual("composition-playground-v1", base_projection["projection_id"])
        self.assertEqual("composition-playground-intent-v1", intent_projection["projection_id"])
        self.assertEqual(semantic_revision, base_projection["source"]["revision"])
        self.assertEqual(semantic_revision, intent_projection["source"]["revision"])
        self.assertEqual(5248, sum(recipe["case_count"] for recipe in base_projection["recipes"]))
        self.assertLess(len(base), 131_072)
        self.assertLess(len(intent), 131_072)

        with tempfile.TemporaryDirectory(prefix="composition-playground-publication-") as directory:
            target = Path(directory)
            (target / publication.MANIFEST_NAME).write_bytes(
                (GENERATED / publication.MANIFEST_NAME).read_bytes()
            )
            for name, payload in payloads.items():
                (target / name).write_bytes(payload)
            publication.validate_written_payloads(target, payloads, semantic_revision)
            self.assertEqual(
                semantic_revision,
                publication.semantic_revision_from_gzip(target / publication.BASE_NAME),
            )
            self.assertEqual(
                semantic_revision,
                publication.semantic_revision_from_gzip(target / publication.INTENT_NAME),
            )

    def test_publication_generation_does_not_require_source_revision_history(self) -> None:
        semantic_revision, _, payloads = self.generated_fixture()
        base_projection = json.loads(gzip.decompress(payloads[publication.BASE_NAME]))
        self.assertEqual(semantic_revision, base_projection["source"]["revision"])

    def test_semantic_snapshot_rejects_a_different_current_object(self) -> None:
        semantic_objects = publication.semantic_objects_from_manifest(GENERATED)
        semantic_objects[playground.SEMANTIC_PATHS[0]] = "1" * 40
        with self.assertRaises(CompositionError) as context:
            publication.verify_semantic_snapshot(semantic_objects)
        self.assertEqual("STALE_PLAYGROUND_SOURCE", context.exception.code)

    def test_publication_provider_may_be_semantically_equivalent_descendant(self) -> None:
        semantic_revision = publication.semantic_revision_from_manifest(GENERATED)
        provider_revision = subprocess.check_output(
            ["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True
        ).strip()
        self.assertRegex(provider_revision, re.compile(r"^[0-9a-f]{40}$"))
        self.assertNotEqual(semantic_revision, provider_revision)

    def test_publication_catalog_declares_materialized_projection_assets(self) -> None:
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        matches = [
            asset
            for asset in catalog["assets"]
            if asset["destination"].startswith("playground/composition-playground")
        ]
        self.assertEqual(
            [
                {
                    "source": "generated/composition-playground-v1.json.gz",
                    "destination": "playground/composition-playground-v1.json.gz",
                    "optional": False,
                },
                {
                    "source": "generated/composition-playground-intent-v1.json.gz",
                    "destination": "playground/composition-playground-intent-v1.json.gz",
                    "optional": False,
                },
            ],
            matches,
        )

    def test_invalid_manifest_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="composition-playground-publication-") as directory:
            target = Path(directory)
            (target / publication.MANIFEST_NAME).write_text("not-json", encoding="utf-8")
            with self.assertRaises(CompositionError) as context:
                publication.semantic_revision_from_manifest(target)
        self.assertEqual("INVALID_PLAYGROUND_PUBLICATION", context.exception.code)

    def test_intent_projection_consumes_matching_base_projection(self) -> None:
        semantic_revision = publication.semantic_revision_from_manifest(GENERATED)
        base = {
            "projection_id": "composition-playground-v1",
            "source": {
                "repository": "TakashiSasaki/templates",
                "authority": "composition",
                "revision": semantic_revision,
            },
            "recipes": [
                {
                    "id": "minimal-publication-regression",
                    "optional_components": [],
                    "case_count": 1,
                }
            ],
            "outcomes": [],
        }
        intent = playground_intent.build_intent_projection(
            base_projection=base,
            source_revision=semantic_revision,
        )
        self.assertEqual("composition-playground-intent-v1", intent["projection_id"])
        self.assertEqual(semantic_revision, intent["source"]["revision"])
        self.assertEqual(base["projection_id"], intent["resolution_projection_id"])
        self.assertEqual([[]], intent["recipes"][0]["cases"])

    def test_intent_projection_rejects_mismatched_or_malformed_base_projection(self) -> None:
        with self.assertRaises(CompositionError) as ctx:
            playground_intent.build_intent_projection(base_projection="not-a-dict")  # type: ignore[arg-type]
        self.assertEqual("INVALID_PLAYGROUND_PROJECTION", ctx.exception.code)

        with self.assertRaises(CompositionError) as ctx:
            playground_intent.build_intent_projection(base_projection={"projection_id": "wrong-id"})
        self.assertEqual("INVALID_PLAYGROUND_PROJECTION", ctx.exception.code)

        with self.assertRaises(CompositionError) as ctx:
            playground_intent.build_intent_projection(
                base_projection={"projection_id": "composition-playground-v1", "source": {}}
            )
        self.assertEqual("INVALID_PLAYGROUND_PROJECTION", ctx.exception.code)

        with self.assertRaises(CompositionError) as ctx:
            playground_intent.build_intent_projection(
                source_revision="a" * 40,
                base_projection={
                    "projection_id": "composition-playground-v1",
                    "source": {"revision": "b" * 40},
                    "recipes": [],
                    "outcomes": [],
                },
            )
        self.assertEqual("INVALID_PLAYGROUND_PROJECTION", ctx.exception.code)

    def test_one_publication_build_performs_one_base_projection_computation(self) -> None:
        _, _, payloads = self.generated_fixture()
        self.assertEqual(1, self._build_projection_count)
        self.assertIn(publication.BASE_NAME, payloads)
        self.assertIn(publication.INTENT_NAME, payloads)


class PublicationLifecycleRegressionTests(unittest.TestCase):
    def test_schema_validation_executes_materializer_before_both_validators(self) -> None:
        workflow = SCHEMA_VALIDATION.read_text(encoding="utf-8")
        primary = workflow.split("\n  primary:\n", 1)[1].split("\n  parallel:\n", 1)[0]
        materialize = "scripts/materialize_publication.py --source-root ."
        site_contract = (
            '"$SITE_PUBLICATION_PROTOCOL_ROOT/scripts/publication_contract.py" --source-root .'
        )
        composition_semantics = "scripts/validate_publication.py"

        self.assertEqual(1, primary.count(materialize))
        self.assertEqual(1, primary.count(site_contract))
        self.assertEqual(1, primary.count(composition_semantics))
        self.assertLess(primary.index(materialize), primary.index(site_contract))
        self.assertLess(primary.index(site_contract), primary.index(composition_semantics))

    def test_supplemental_webmcp_guide_is_classified_and_canonical_route_is_indexed(self) -> None:
        classification = json.loads(CLASSIFICATION.read_text(encoding="utf-8"))
        matches = [
            entry
            for entry in classification["excluded_markdown"]
            if entry["source"] == "docs/guides/webmcp-capability.md"
        ]
        self.assertEqual(1, len(matches))
        self.assertIn("components/capability.webmcp", matches[0]["reason"])

        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        published_sources = {document["source"] for document in catalog["documents"]}
        self.assertNotIn("docs/guides/webmcp-capability.md", published_sources)
        self.assertIn("components/capability.webmcp/files/WEBMCP.md", published_sources)

        index = DOCS_INDEX.read_text(encoding="utf-8")
        canonical_link = "../components/capability.webmcp/files/WEBMCP.md"
        self.assertEqual(1, index.count(canonical_link))

    def test_reference_consumer_compatibility_pin_is_immutable_and_intentional(self) -> None:
        workflow = REFERENCE_CONSUMER_PUBLICATION.read_text(encoding="utf-8")
        uses_match = re.search(
            r"uses: TakashiSasaki/templates/\.github/workflows/build-pages\.yml@([0-9a-f]{40})",
            workflow,
        )
        site_ref_match = re.search(r"^\s+site_ref: ([0-9a-f]{40})$", workflow, re.MULTILINE)
        self.assertIsNotNone(uses_match)
        self.assertIsNotNone(site_ref_match)
        assert uses_match is not None
        assert site_ref_match is not None
        self.assertEqual(EXPECTED_SITE_COMPATIBILITY_REVISION, uses_match.group(1))
        self.assertEqual(uses_match.group(1), site_ref_match.group(1))
        self.assertIn(
            "composition_ref: ${{ github.event.pull_request.head.sha }}",
            workflow,
        )
        self.assertNotIn("publication_staging_id:", workflow)


if __name__ == "__main__":
    unittest.main()
