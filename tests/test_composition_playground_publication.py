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


class CompositionPlaygroundPublicationTests(unittest.TestCase):
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
        semantic_revision = publication.semantic_revision_from_manifest(GENERATED)
        semantic_objects = publication.semantic_objects_from_manifest(GENERATED)
        payloads = publication.publication_payloads(
            semantic_revision=semantic_revision,
            semantic_objects=semantic_objects,
        )
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
        self.assertEqual(2624, sum(recipe["case_count"] for recipe in base_projection["recipes"]))
        self.assertLess(len(base), 131_072)
        self.assertLess(len(intent), 131_072)
        with tempfile.TemporaryDirectory(prefix="composition-playground-publication-") as directory:
            target = Path(directory)
            (target / publication.MANIFEST_NAME).write_bytes((GENERATED / publication.MANIFEST_NAME).read_bytes())
            publication.write_directory(target)
            self.assertEqual(semantic_revision, publication.check_directory(target))

    def test_publication_generation_does_not_require_source_revision_history(self) -> None:
        semantic_revision = publication.semantic_revision_from_manifest(GENERATED)
        semantic_objects = publication.semantic_objects_from_manifest(GENERATED)
        with mock.patch.object(
            playground,
            "_git",
            side_effect=AssertionError("publication generation must not walk semantic revision history"),
        ):
            payloads = publication.publication_payloads(
                semantic_revision=semantic_revision,
                semantic_objects=semantic_objects,
            )
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
        provider_revision = subprocess.check_output(["git", "-C", str(ROOT), "rev-parse", "HEAD"], text=True).strip()
        self.assertRegex(provider_revision, re.compile(r"^[0-9a-f]{40}$"))
        self.assertNotEqual(semantic_revision, provider_revision)

    def test_publication_catalog_declares_materialized_projection_assets(self) -> None:
        catalog = json.loads(CATALOG.read_text(encoding="utf-8"))
        matches = [asset for asset in catalog["assets"] if asset["destination"].startswith("playground/composition-playground")]
        self.assertEqual([
            {"source": "generated/composition-playground-v1.json.gz", "destination": "playground/composition-playground-v1.json.gz", "optional": False},
            {"source": "generated/composition-playground-intent-v1.json.gz", "destination": "playground/composition-playground-intent-v1.json.gz", "optional": False},
        ], matches)

    def test_invalid_manifest_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory(prefix="composition-playground-publication-") as directory:
            target = Path(directory)
            (target / publication.MANIFEST_NAME).write_text("not-json", encoding="utf-8")
            with self.assertRaises(CompositionError) as context:
                publication.semantic_revision_from_manifest(target)
        self.assertEqual("INVALID_PLAYGROUND_PUBLICATION", context.exception.code)

    def test_intent_projection_consumes_matching_base_projection(self) -> None:
        semantic_revision = publication.semantic_revision_from_manifest(GENERATED)
        base = publication._bind_semantic_revision(playground.build_projection(), semantic_revision)
        intent = playground_intent.build_intent_projection(
            base_projection=base,
            source_revision=semantic_revision,
        )
        self.assertEqual("composition-playground-intent-v1", intent["projection_id"])
        self.assertEqual(semantic_revision, intent["source"]["revision"])
        self.assertEqual(base["projection_id"], intent["resolution_projection_id"])

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
        semantic_revision = publication.semantic_revision_from_manifest(GENERATED)
        semantic_objects = publication.semantic_objects_from_manifest(GENERATED)
        build_projection_count = 0
        real_build_projection = publication.build_projection

        def counted_build_projection(*args, **kwargs):
            nonlocal build_projection_count
            build_projection_count += 1
            return real_build_projection(*args, **kwargs)

        with mock.patch.object(publication, "build_projection", side_effect=counted_build_projection):
            payloads = publication.publication_payloads(
                semantic_revision=semantic_revision,
                semantic_objects=semantic_objects,
            )

        self.assertEqual(1, build_projection_count)
        self.assertIn(publication.BASE_NAME, payloads)
        self.assertIn(publication.INTENT_NAME, payloads)


if __name__ == "__main__":
    unittest.main()
