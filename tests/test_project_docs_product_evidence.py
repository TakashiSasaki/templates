from __future__ import annotations

import copy
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

import test_website_artifact as website_artifact


ROOT = Path(__file__).resolve().parents[1]
PROJECT_DOCS = ROOT / "examples" / "onboarding" / "project-docs"
PLANNING_EXAMPLE = PROJECT_DOCS / "implementation-evidence.planning.json"
PRODUCT_EXAMPLE = PROJECT_DOCS / "implementation-evidence.product.json"
PUBLICATION_CATALOG = ROOT / "docs" / "publication-catalog.json"
EVIDENCE_SCHEMA = (
    ROOT
    / "components"
    / "lifecycle.implementation-evidence"
    / "files"
    / "schemas"
    / "implementation-evidence.schema.json"
)
GENERIC_VALIDATOR = (
    ROOT
    / "components"
    / "lifecycle.implementation-evidence"
    / "files"
    / ".template-composition"
    / "validators"
    / "validate_implementation_evidence.py"
)
CONTRACT_VALIDATOR_DIR = (
    ROOT
    / "components"
    / "lifecycle.contract-evolution"
    / "files"
    / ".template-composition"
    / "validators"
)
WEBSITE_VALIDATOR = (
    ROOT
    / "components"
    / "artifact.website-core"
    / "files"
    / "scripts"
    / "validate_website_evidence.py"
)
WALKTHROUGH = ROOT / "docs" / "guides" / "website-product-walkthrough.md"
PRODUCT_EXAMPLE_SOURCE = "examples/onboarding/project-docs/implementation-evidence.product.json"
PRODUCT_EXAMPLE_DESTINATION = (
    "lifecycle/implementation-evidence/project-docs/implementation-evidence.product.json"
)
PRODUCT_EXAMPLE_LINK = f"../../{PRODUCT_EXAMPLE_SOURCE}"


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


class ProjectDocsProductEvidenceTests(unittest.TestCase):
    def materialize(self, evidence: dict) -> Path:
        helper = website_artifact.WebsiteArtifactTests(
            methodName="test_component_and_recipe_establish_sibling_website_artifact"
        )
        self.addCleanup(helper.doCleanups)
        helper.setUp()
        root = helper.project_docs_fixture(evidence)

        manifest = {
            "contracts": [
                {"id": contract_id}
                for contract_id in (
                    "browser_identity",
                    "document_metadata",
                    "site_discovery",
                    "site_structure",
                    "viewports",
                )
            ]
        }
        (root / "contracts" / "manifest.json").write_text(
            json.dumps(manifest, indent=2) + "\n",
            encoding="utf-8",
        )

        harnesses = {
            "tests/verify_project_docs_browser.py": "raise SystemExit(0)\n",
            "tests/verify_project_docs_discovery.py": "raise SystemExit(0)\n",
        }
        for relative, content in harnesses.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")
        return root

    def run_generic(self, root: Path, *args: str) -> subprocess.CompletedProcess[str]:
        env = os.environ.copy()
        existing = env.get("PYTHONPATH")
        env["PYTHONPATH"] = (
            str(CONTRACT_VALIDATOR_DIR)
            if not existing
            else os.pathsep.join((str(CONTRACT_VALIDATOR_DIR), existing))
        )
        return subprocess.run(
            [sys.executable, str(GENERIC_VALIDATOR), str(root), *args],
            cwd=ROOT,
            env=env,
            text=True,
            capture_output=True,
            check=False,
        )

    def run_website(self, root: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(WEBSITE_VALIDATOR), str(root)],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_product_example_preserves_planning_targets_and_validates(self) -> None:
        schema = load(EVIDENCE_SCHEMA)
        planning = load(PLANNING_EXAMPLE)
        product = load(PRODUCT_EXAMPLE)
        Draft202012Validator.check_schema(schema)
        self.assertEqual(list(Draft202012Validator(schema).iter_errors(product)), [])

        planning_requirements = {
            item["id"]: (item["targets"], item["requiredPositiveProofKinds"])
            for item in planning["requirements"]
        }
        product_requirements = {
            item["id"]: (item["targets"], item["requiredPositiveProofKinds"])
            for item in product["requirements"]
        }
        self.assertEqual(product_requirements, planning_requirements)
        self.assertTrue(all(item["recordIds"] for item in product["requirements"]))
        self.assertTrue(all(item["releaseGateIds"] for item in product["records"]))

        root = self.materialize(product)
        generic = self.run_generic(root)
        self.assertEqual(generic.returncode, 0, generic.stdout + generic.stderr)
        self.assertNotIn("WARNING: broad implementation-evidence proof reuse", generic.stdout)
        website = self.run_website(root)
        self.assertEqual(website.returncode, 0, website.stdout + website.stderr)

    def test_deferred_example_is_valid_product_evidence_but_not_release_ready(self) -> None:
        root = self.materialize(load(PRODUCT_EXAMPLE))
        result = self.run_generic(root, "--release-readiness", "--format", "json")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["release_readiness"], "not-ready")
        self.assertTrue(payload["deferred_proofs"])
        self.assertEqual(payload.get("warnings", []), [])
        self.assertTrue(
            all(
                proof["status"] == "deferred"
                for record in load(PRODUCT_EXAMPLE)["records"]
                for field in ("positiveEvidence", "negativeEvidence")
                for proof in record[field]
            )
        )

    def test_product_record_without_release_gate_fails_closed(self) -> None:
        evidence = copy.deepcopy(load(PRODUCT_EXAMPLE))
        evidence["records"][0]["releaseGateIds"] = []
        root = self.materialize(evidence)
        result = self.run_generic(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("has no release gate", result.stderr)

    def test_selected_release_gate_must_execute_every_record_proof_command(self) -> None:
        evidence = copy.deepcopy(load(PRODUCT_EXAMPLE))
        evidence["records"][0]["releaseGateIds"] = ["project-docs-discovery-gate"]
        root = self.materialize(evidence)
        result = self.run_generic(root)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn(
            "proof command project-docs-browser-proof is not executed by a selected release gate",
            result.stderr,
        )

    def test_product_example_is_published_for_normal_consumers(self) -> None:
        catalog = load(PUBLICATION_CATALOG)
        self.assertIn(
            {
                "source": PRODUCT_EXAMPLE_SOURCE,
                "destination": PRODUCT_EXAMPLE_DESTINATION,
                "optional": False,
            },
            catalog["assets"],
        )
        text = WALKTHROUGH.read_text(encoding="utf-8")
        self.assertIn(f"]({PRODUCT_EXAMPLE_LINK})", text)
        linked_source = (WALKTHROUGH.parent / PRODUCT_EXAMPLE_LINK).resolve()
        self.assertEqual(linked_source, PRODUCT_EXAMPLE.resolve())
        self.assertTrue(linked_source.is_file())

    def test_walkthrough_explains_the_product_evidence_release_gate_graph(self) -> None:
        text = WALKTHROUGH.read_text(encoding="utf-8")
        for required in (
            "implementation-evidence.product.json",
            "releaseGates",
            "commandIds",
            "commandId",
            "releaseGateIds",
            "project-docs-browser-gate",
            "project-docs-discovery-gate",
            "unused command or release gate",
            "deferred",
            "verified",
        ):
            self.assertIn(required, text)


if __name__ == "__main__":
    unittest.main()
