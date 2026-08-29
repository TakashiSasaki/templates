from __future__ import annotations

import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HELPER_SOURCE = (
    ROOT
    / "components"
    / "capability.pwa"
    / "files"
    / "scripts"
    / "pwa_evidence_targets.py"
)
VALIDATOR_SOURCE = (
    ROOT
    / "components"
    / "capability.pwa"
    / "files"
    / ".template-composition"
    / "validators"
    / "validate_pwa_evidence.py"
)


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


helper_source = load_module("pwa_evidence_targets_source", HELPER_SOURCE)
validator = load_module("validate_pwa_evidence_under_test", VALIDATOR_SOURCE)


class PwaImplementationEvidenceTests(unittest.TestCase):
    def write_json(self, path: Path, value: object) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def fixture(self, root: Path, mode: str) -> None:
        scripts = root / "scripts"
        scripts.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(HELPER_SOURCE, scripts / "pwa_evidence_targets.py")
        for filename in ("pwa-manifest.json", "pwa-offline.json", "pwa-update.json"):
            self.write_json(root / "contracts" / filename, {"mode": mode})

    def targets(self) -> list[dict[str, str]]:
        return [dict(target) for target in helper_source.family_targets()]

    def planning_evidence(self) -> dict:
        requirements = []
        for index, target in enumerate(self.targets(), 1):
            requirements.append(
                {
                    "id": f"requirement-{index:02d}",
                    "targets": [target],
                    "requiredPositiveProofKinds": ["end-to-end-test"],
                }
            )
        return {
            "mode": "planning",
            "commands": [],
            "records": [],
            "requirements": requirements,
        }

    def product_evidence(self) -> dict:
        records = []
        requirements = []
        for index, target in enumerate(self.targets(), 1):
            record_id = f"pwa-record-{index:02d}"
            records.append(
                {
                    "id": record_id,
                    "target": target,
                    "positiveEvidence": [
                        {
                            "id": f"positive-{index:02d}",
                            "kind": "end-to-end-test",
                            "commandId": "browser-proof",
                        }
                    ],
                    "negativeEvidence": [
                        {
                            "id": f"negative-{index:02d}",
                            "kind": "end-to-end-test",
                            "commandId": "browser-proof",
                        }
                    ],
                }
            )
            requirements.append(
                {
                    "id": f"requirement-{index:02d}",
                    "targets": [target],
                    "recordIds": [record_id],
                    "requiredPositiveProofKinds": ["end-to-end-test"],
                }
            )
        return {
            "mode": "product",
            "commands": [
                {
                    "id": "browser-proof",
                    "execution": {"capabilities": ["browser"]},
                }
            ],
            "records": records,
            "requirements": requirements,
        }

    def test_product_requires_all_pwa_proof_families_with_browser_backing(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.fixture(root, "product")
            self.write_json(root / "contracts" / "implementation-evidence.json", self.product_evidence())
            self.assertEqual(validator.validate(root), [])

    def test_contract_declarations_alone_do_not_count_as_product_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.fixture(root, "product")
            evidence = self.product_evidence()
            evidence["records"] = []
            evidence["requirements"] = []
            self.write_json(root / "contracts" / "implementation-evidence.json", evidence)
            errors = validator.validate(root)
            self.assertEqual(sum("missing PWA implementation-evidence target" in error for error in errors), 8)

    def test_product_rejects_unknown_pwa_proof_family(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.fixture(root, "product")
            evidence = self.product_evidence()
            evidence["records"][0]["target"] = {
                "kind": "contract-item",
                "contractId": "pwa_offline",
                "itemKind": "proof-family",
                "itemId": "cache-first",
            }
            self.write_json(root / "contracts" / "implementation-evidence.json", evidence)
            errors = validator.validate(root)
            self.assertTrue(any("unknown PWA implementation-evidence target" in error for error in errors), errors)
            self.assertTrue(any("missing PWA implementation-evidence target" in error for error in errors), errors)

    def test_product_requires_browser_capability_for_browser_level_proof(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.fixture(root, "product")
            evidence = self.product_evidence()
            evidence["commands"][0]["execution"]["capabilities"] = []
            self.write_json(root / "contracts" / "implementation-evidence.json", evidence)
            errors = validator.validate(root)
            self.assertTrue(any("lacks browser execution capability" in error for error in errors), errors)
            self.assertTrue(any("positive browser-level proof" in error for error in errors), errors)
            self.assertTrue(any("negative browser-level proof" in error for error in errors), errors)

    def test_planning_requires_every_family_and_browser_level_intent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.fixture(root, "planning")
            evidence = self.planning_evidence()
            self.write_json(root / "contracts" / "implementation-evidence.json", evidence)
            self.assertEqual(validator.validate(root), [])

            evidence["requirements"][0]["requiredPositiveProofKinds"] = ["inspection"]
            self.write_json(root / "contracts" / "implementation-evidence.json", evidence)
            errors = validator.validate(root)
            self.assertTrue(any("browser-level kind" in error for error in errors), errors)

    def test_template_mode_activates_no_pwa_product_proof_claim(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            self.fixture(root, "template")
            self.write_json(
                root / "contracts" / "implementation-evidence.json",
                {"mode": "template", "commands": [], "records": [], "requirements": []},
            )
            self.assertEqual(validator.validate(root), [])


if __name__ == "__main__":
    unittest.main()
