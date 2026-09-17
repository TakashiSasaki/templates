from __future__ import annotations

import copy
import json
from pathlib import Path
import tempfile
import unittest

from publication_bundle.contract import canonical, digest, inventory, requirements_digest
from scripts.classify_site_compatibility import classify
from tests.bundle_consumer_fixture import fixture, finish


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REQUIREMENTS = [
    {"provider": "modeling", "feature": "publication.generic-document.v1", "required": True, "fallback": "generic-document"},
    {"provider": "modeling", "feature": "publication.opaque-json.v1", "required": True, "fallback": "generic-document"},
    {"provider": "modeling", "feature": "publication.static-asset.v1", "required": True, "fallback": "none"},
]


class SiteCompatibilityClassifierTests(unittest.TestCase):
    def _support(self, root: Path, **changes) -> Path:
        support = json.loads((ROOT / "contracts/site-publication-support.json").read_text(encoding="utf-8"))
        support.update(changes)
        path = root / "support.json"
        path.write_bytes(canonical(support))
        return path

    def _v4(self, root: Path, requirements=None) -> Path:
        bundle = fixture(root / "bundle")
        finish(bundle)
        providers = {
            "modeling": "d" * 40,
            "composition": "b" * 40,
            "policy": "c" * 40,
        }
        graph = json.loads((bundle / "guided-navigation.json").read_text(encoding="utf-8"))
        graph["providers"].insert(0, copy.deepcopy(graph["providers"][0]))
        graph["providers"][0]["name"] = "modeling"
        graph["providers"][0]["revision"] = providers["modeling"]
        (bundle / "guided-navigation.json").write_bytes(canonical(graph))
        provenance = {
            "schema_version": 1,
            "producer": {"authority": "integration", "revision": "a" * 40},
            "providers": providers,
        }
        (bundle / "provenance.json").write_bytes(canonical(provenance))
        requirements = copy.deepcopy(requirements or DEFAULT_REQUIREMENTS)
        data = {
            "schema_version": 4,
            "producer": provenance["producer"],
            "providers": providers,
            "configuration_digest": "d" * 64,
            "requirements": requirements,
            "requirements_digest": requirements_digest(requirements),
            "files": inventory(bundle),
        }
        data["content_digest"] = digest(canonical(data["files"]))
        data["identity"] = digest(canonical(data))
        (bundle / "bundle.json").write_bytes(canonical(data))
        return bundle

    def test_v3_historical_reader_uses_legacy_generic_requirement(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = fixture(root / "bundle")
            finish(bundle)
            result = classify(bundle, support_path=self._support(root))
            self.assertEqual(result["classification"], "COMPATIBLE_PENDING_QUALIFICATION")
            self.assertEqual(len(result["requirements"]["closure"]), 2)

    def test_v4_compares_the_exact_integration_closure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            result = classify(self._v4(root), support_path=self._support(root))
            self.assertEqual(result["classification"], "COMPATIBLE_PENDING_QUALIFICATION")
            self.assertEqual(result["requirements"]["closure"], DEFAULT_REQUIREMENTS)
            self.assertEqual(result["inputs"]["requirements_digest"], requirements_digest(DEFAULT_REQUIREMENTS))

    def test_unknown_required_feature_stops_before_qualification(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            requirements = [{**DEFAULT_REQUIREMENTS[0], "feature": "publication.future-required.v1", "fallback": "none"}]
            result = classify(self._v4(root, requirements), support_path=self._support(root))
            self.assertEqual(result["classification"], "ADAPTATION_REQUIRED")
            self.assertEqual(result["reason_codes"], ["REQUIRED_FEATURE_UNSUPPORTED"])
            self.assertNotIn("generic-markdown-renderer", result["checks"]["results"])
            self.assertIn("generic-markdown-renderer", result["checks"]["not_run"])

    def test_known_feature_without_an_allowed_fallback_is_adaptation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            requirements = [{**DEFAULT_REQUIREMENTS[1], "fallback": "none"}]
            support = self._support(
                root,
                supported_features=["publication.generic-document.v1", "publication.static-asset.v1"],
                fallbacks={
                    "publication.generic-document.v1": "generic-document",
                    "publication.static-asset.v1": "none",
                    "publication.opaque-json.v1": "none",
                },
            )
            result = classify(self._v4(root, requirements), support_path=support)
            self.assertEqual(result["classification"], "ADAPTATION_REQUIRED")
            self.assertIn("publication.opaque-json.v1", result["requirements"]["unsupported"])

    def test_optional_unknown_feature_with_explicit_generic_fallback_is_processable(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            feature = "publication.optional-future.v1"
            requirements = [{**DEFAULT_REQUIREMENTS[0], "feature": feature, "required": False, "fallback": "generic-document"}]
            support = self._support(
                root,
                fallbacks={
                    "publication.generic-document.v1": "generic-document",
                    "publication.opaque-json.v1": "generic-document",
                    "publication.static-asset.v1": "none",
                    feature: "generic-document",
                },
            )
            result = classify(self._v4(root, requirements), support_path=support)
            self.assertEqual(result["classification"], "COMPATIBLE_PENDING_QUALIFICATION")
            self.assertEqual(result["requirements"]["fallbacks"], {f"modeling:{feature}": "generic-document"})

    def test_optional_unknown_feature_without_explicit_fallback_is_adaptation(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            feature = "publication.optional-future.v1"
            requirements = [{**DEFAULT_REQUIREMENTS[0], "feature": feature, "required": False, "fallback": "ignore"}]
            result = classify(self._v4(root, requirements), support_path=self._support(root))
            self.assertEqual(result["classification"], "ADAPTATION_REQUIRED")
            self.assertEqual(result["reason_codes"], ["OPTIONAL_FEATURE_UNSUPPORTED"])

    def test_malformed_requirements_and_digest_mismatch_are_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bundle = self._v4(root)
            manifest = json.loads((bundle / "bundle.json").read_text(encoding="utf-8"))
            manifest["requirements_digest"] = "e" * 64
            manifest["identity"] = digest(canonical({key: value for key, value in manifest.items() if key != "identity"}))
            (bundle / "bundle.json").write_bytes(canonical(manifest))
            result = classify(bundle, support_path=self._support(root))
            self.assertEqual(result["classification"], "INVALID_INPUT")

    def test_requirement_for_a_provider_outside_the_bundle_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            requirements = [{**DEFAULT_REQUIREMENTS[0], "provider": "foreign"}]
            result = classify(self._v4(root, requirements), support_path=self._support(root))
            self.assertEqual(result["classification"], "INVALID_INPUT")

    def test_new_site_support_major_version_is_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            support = json.loads((ROOT / "contracts/site-publication-support.json").read_text(encoding="utf-8"))
            support["schema_version"] = 2
            path = root / "support.json"
            path.write_bytes(canonical(support))
            result = classify(self._v4(root), support_path=path)
            self.assertEqual(result["classification"], "UNKNOWN")
            self.assertEqual(result["reason_codes"], ["UNKNOWN_CONTRACT_VERSION_OR_PROTOCOL"])


if __name__ == "__main__":
    unittest.main()
