from __future__ import annotations

import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
INVENTORY = ROOT / "examples/evaluations/remote-executable-integrity-inventory.txt"


class RemoteExecutableIntegrityInventoryTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.text = INVENTORY.read_text(encoding="utf-8")

    def test_inventory_covers_executable_resources_and_classifications(self) -> None:
        for resource in (
            "scripts/install_composition_skill.py",
            "skills/composition/scripts/runtime_checkout.py",
            "skills/composition/scripts/run_checkout.py",
            "examples/onboarding/task-ledger/browser_proof.py",
            "scripts/prepare_chromedriver.py",
        ):
            self.assertIn(resource, self.text)
        for classification in (
            "executed directly",
            "downloaded then executed",
            "imported/loaded as executable code",
            "data only",
            "documentation-only",
        ):
            self.assertIn(classification, self.text)

    def test_table_rows_bind_resources_to_classifications(self) -> None:
        expected = {
            "scripts/install_composition_skill.py": "downloaded then executed",
            "skills/composition/scripts/runtime_checkout.py": "imported/loaded as executable code",
            "examples/onboarding/task-ledger/browser_proof.py": "downloaded then executed",
            "scripts/prepare_chromedriver.py": "downloaded then executed",
        }
        rows = [line for line in self.text.splitlines() if line.startswith("|")]
        for resource, classification in expected.items():
            with self.subTest(resource=resource):
                matches = [row for row in rows if resource in row]
                self.assertEqual(len(matches), 1)
                self.assertIn(classification, matches[0])

    def test_inventory_requires_immutable_identity_and_received_bytes(self) -> None:
        self.assertIn("immutable identity", self.text)
        self.assertIn("exact bytes received for execution", self.text)
        self.assertIn("full Git SHA plus received-byte SHA-256", self.text)
        self.assertIn("no SHA-256 or signed manifest verification", self.text)
        self.assertIn("text reserialization", self.text)

    def test_inventory_limits_digest_requirement_to_executable_resources(self) -> None:
        self.assertIn("does not require digests for ordinary documentation links", self.text)
        self.assertIn("does not add a generic digest field to every remote file", self.text)
        self.assertIn("Residual supply-chain risk remains", self.text)


if __name__ == "__main__":
    unittest.main()
