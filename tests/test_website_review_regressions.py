from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WEBSITE_FILES = ROOT / "components" / "artifact.website-core" / "files"
FOUNDATION_FILES = ROOT / "components" / "foundation.web" / "files"
CONTRACT_VALIDATOR = WEBSITE_FILES / "scripts" / "validate_website_contracts.py"
EVIDENCE_VALIDATOR = WEBSITE_FILES / "scripts" / "validate_website_evidence.py"
TARGET_HELPER = WEBSITE_FILES / "scripts" / "website_evidence_targets.py"


def load(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


helper = load_module("website_evidence_targets_review", TARGET_HELPER)


class WebsiteReviewRegressionTests(unittest.TestCase):
    def write_json(self, root: Path, relative: str, value: object) -> None:
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def fixture(self, root: Path, *, mode: str = "template") -> None:
        for relative, source in {
            "contracts/site-structure.json": WEBSITE_FILES / "contracts/site-structure.json",
            "contracts/document-metadata.json": WEBSITE_FILES / "contracts/document-metadata.json",
            "contracts/site-discovery.json": WEBSITE_FILES / "contracts/site-discovery.json",
            "contracts/routes.json": FOUNDATION_FILES / "contracts/routes.json",
            "contracts/viewports.json": FOUNDATION_FILES / "contracts/viewports.json",
            "contracts/browser-identity.json": FOUNDATION_FILES / "contracts/browser-identity.json",
        }.items():
            self.write_json(root, relative, load(source))
        self.write_json(root, "contracts/implementation-evidence.json", {"mode": mode, "commands": [], "records": [], "requirements": []})

    def run_validator(self, source: Path, root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run([sys.executable, str(source), str(root)], cwd=ROOT, text=True, capture_output=True, check=False)

    def complete_product_evidence(self, root: Path) -> dict:
        targets = [dict(target) for target in helper.expected_targets(root)]
        records = []
        requirements = []
        for index, target in enumerate(targets, 1):
            record_id = f"website-record-{index:02d}"
            proof = {"id": f"proof-{index:02d}", "kind": "end-to-end-test", "commandId": "browser-proof"}
            records.append({"id": record_id, "target": target, "positiveEvidence": [proof], "negativeEvidence": [dict(proof, id=f"negative-{index:02d}")]})
            requirements.append({"id": f"requirement-{index:02d}", "targets": [target], "recordIds": [record_id], "requiredPositiveProofKinds": ["end-to-end-test"]})
        return {"mode": "product", "commands": [{"id": "browser-proof", "execution": {"capabilities": ["browser"]}}], "records": records, "requirements": requirements}

    def test_route_path_namespace_and_viewport_ordering_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.fixture(root)
            routes = load(root / "contracts/routes.json")
            routes["routes"].append({"id": "duplicate", "path": "/", "canonical": True, "aliases": [], "deepLink": True, "accessibility": {"documentTitleRequired": True, "focusTarget": "main-heading"}})
            self.write_json(root, "contracts/routes.json", routes)
            result = self.run_validator(CONTRACT_VALIDATOR, root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("duplicate shared Website canonical route path", result.stderr)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.fixture(root)
            routes = load(root / "contracts/routes.json")
            routes["routes"][0]["aliases"] = ["/"]
            self.write_json(root, "contracts/routes.json", routes)
            result = self.run_validator(CONTRACT_VALIDATOR, root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("alias collides with canonical route path", result.stderr)

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.fixture(root)
            viewports = load(root / "contracts/viewports.json")
            viewports["viewports"][0]["minWidthPx"] = 320
            self.write_json(root, "contracts/viewports.json", viewports)
            result = self.run_validator(CONTRACT_VALIDATOR, root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must start at minWidthPx 0", result.stderr)

    def test_discovery_metadata_and_canonical_origin_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.fixture(root)
            discovery = load(root / "contracts/site-discovery.json")
            discovery["sitemap"]["path"] = discovery["robots"]["path"]
            self.write_json(root, "contracts/site-discovery.json", discovery)
            result = self.run_validator(CONTRACT_VALIDATOR, root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("robots and sitemap discovery paths must be distinct", result.stderr)

        for field, value in (("siteName", " \u2800 "), ("title", "\u2800"), ("description", "\n\t")):
            with self.subTest(field=field), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                self.fixture(root)
                metadata = load(root / "contracts/document-metadata.json")
                if field == "siteName":
                    metadata[field] = value
                else:
                    metadata["pages"][0][field] = value
                self.write_json(root, "contracts/document-metadata.json", metadata)
                result = self.run_validator(CONTRACT_VALIDATOR, root)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("visible character", result.stderr)

        for origin in ("https://-", "https://example..com", "https://example.com:99999"):
            with self.subTest(origin=origin), tempfile.TemporaryDirectory() as temp_dir:
                root = Path(temp_dir)
                self.fixture(root, mode="product")
                discovery = load(root / "contracts/site-discovery.json")
                discovery["canonicalOrigin"] = origin
                self.write_json(root, "contracts/site-discovery.json", discovery)
                result = self.run_validator(CONTRACT_VALIDATOR, root)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("valid HTTPS canonicalOrigin", result.stderr)

    def test_website_evidence_ignores_other_components_but_requires_browser_linkage(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.fixture(root, mode="product")
            evidence = self.complete_product_evidence(root)
            evidence["records"].append({"id": "pwa-extra", "target": {"kind": "contract-item", "contractId": "pwa_manifest", "itemKind": "proof-family", "itemId": "installability"}, "positiveEvidence": [], "negativeEvidence": []})
            self.write_json(root, "contracts/implementation-evidence.json", evidence)
            result = self.run_validator(EVIDENCE_VALIDATOR, root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

            browser_record = next(record for record in evidence["records"] if record["target"].get("contractId") == "browser_identity")
            for requirement in evidence["requirements"]:
                requirement["recordIds"] = [record_id for record_id in requirement.get("recordIds", []) if record_id != browser_record["id"]]
            self.write_json(root, "contracts/implementation-evidence.json", evidence)
            result = self.run_validator(EVIDENCE_VALIDATOR, root)
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("must be linked from at least one product requirement", result.stderr)

    def test_planning_website_evidence_ignores_other_component_targets(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.fixture(root, mode="planning")
            requirements = [{"id": f"requirement-{index:02d}", "targets": [dict(target)], "requiredPositiveProofKinds": ["end-to-end-test"]} for index, target in enumerate(helper.expected_targets(root), 1)]
            requirements.append({"id": "pwa-plan", "targets": [{"kind": "contract-item", "contractId": "pwa_manifest", "itemKind": "proof-family", "itemId": "installability"}], "requiredPositiveProofKinds": ["end-to-end-test"]})
            self.write_json(root, "contracts/implementation-evidence.json", {"mode": "planning", "commands": [], "records": [], "requirements": requirements})
            result = self.run_validator(EVIDENCE_VALIDATOR, root)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)


if __name__ == "__main__":
    unittest.main()
