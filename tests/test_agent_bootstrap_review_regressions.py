from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from scripts import generate_agent_bootstrap as bootstrap

ROOT = Path(__file__).resolve().parents[1]


class AgentBootstrapReviewRegressionTests(unittest.TestCase):
    def test_policy_bootstrap_rejects_empty_installer_download(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            empty_installer = root / "empty-policy-installer.py"
            empty_installer.write_bytes(b"")
            skill_target = root / "policy-skill"

            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    "-c",
                    bootstrap.IMMUTABLE_INSTALLER_BOOTSTRAP,
                    empty_installer.as_uri(),
                    str(skill_target),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("Policy installer download was empty", result.stderr)
            self.assertFalse(skill_target.exists())

    def test_schema_requires_integration_contracts_and_requirements(self) -> None:
        schema = json.loads(
            (ROOT / "schemas/agent-bootstrap.schema.json").read_text(encoding="utf-8")
        )
        required = schema["required"]
        for field in ("integration_contracts", "requirements"):
            with self.subTest(field=field):
                self.assertIn(field, required)


if __name__ == "__main__":
    unittest.main()
