from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "template"
sys.path.insert(0, str(ROOT / "scripts"))

import validate_contracts  # noqa: E402

OPTIONAL_POLICY_ARTIFACTS = {
    ".agent-policy.yml": "profiles:\n  - core\n",
    ".agent-policy.lock": '{"version": 1}\n',
}


class ResponsibilityBoundaryTests(unittest.TestCase):
    def test_product_owned_prose_and_policy_artifacts_do_not_affect_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            temporary_root = Path(temporary_directory)
            shutil.copytree(ROOT / "contracts", temporary_root / "contracts")
            shutil.copytree(ROOT / "schemas", temporary_root / "schemas")

            (temporary_root / "README.md").write_text(
                "# Product repository\n\nProduct-owned documentation.\n",
                encoding="utf-8",
            )
            (temporary_root / "TEMPLATE.md").write_text(
                "# Product-specific operating notes\n",
                encoding="utf-8",
            )
            for relative_path, content in OPTIONAL_POLICY_ARTIFACTS.items():
                (temporary_root / relative_path).write_text(content, encoding="utf-8")

            errors = validate_contracts.validate_repository(temporary_root)

        self.assertEqual([], errors)


if __name__ == "__main__":
    unittest.main()
