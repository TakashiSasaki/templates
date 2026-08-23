from __future__ import annotations

import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "scripts" / "compose.py"


class ComposerGeneratedMaterialTests(unittest.TestCase):
    def test_webapp_apply_generates_and_locks_contract_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "composition.json"
            config_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "recipe": "webapp",
                        "components": {"include": [], "exclude": []},
                        "parameters": {},
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            target = root / "consumer"

            apply_result = subprocess.run(
                [
                    sys.executable,
                    str(COMPOSER),
                    "apply",
                    "--target",
                    str(target),
                    "--config",
                    str(config_path),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(
                apply_result.returncode,
                0,
                apply_result.stdout + apply_result.stderr,
            )

            manifest_path = target / "contracts" / "manifest.json"
            self.assertTrue(manifest_path.is_file())
            manifest_bytes = manifest_path.read_bytes()
            manifest = json.loads(manifest_bytes)
            self.assertEqual(manifest["schemaVersion"], 1)
            self.assertEqual(manifest["retiredContracts"], [])
            self.assertEqual(
                [entry["id"] for entry in manifest["contracts"]],
                [
                    "implementation_evidence",
                    "release_bundle",
                    "release_evidence",
                    "release_execution",
                    "routes",
                    "surfaces",
                    "ui_states",
                    "viewports",
                ],
            )

            lock = json.loads(
                (target / ".template-composition" / "lock.json").read_text(
                    encoding="utf-8"
                )
            )
            files = {entry["destination"]: entry for entry in lock["files"]}
            manifest_lock = files["contracts/manifest.json"]
            self.assertEqual(
                manifest_lock["component"], "lifecycle.contract-evolution"
            )
            self.assertEqual(manifest_lock["ownership"], "generated")
            self.assertEqual(
                manifest_lock["materialized_sha256"],
                hashlib.sha256(manifest_bytes).hexdigest(),
            )

            lifecycle_validation = subprocess.run(
                [
                    sys.executable,
                    str(
                        target
                        / ".template-composition"
                        / "validators"
                        / "validate_contract_evolution.py"
                    ),
                    str(target),
                ],
                cwd=target,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(
                lifecycle_validation.returncode,
                0,
                lifecycle_validation.stdout + lifecycle_validation.stderr,
            )

            source_validation = subprocess.run(
                [
                    sys.executable,
                    str(COMPOSER),
                    "validate",
                    "--target",
                    str(target),
                ],
                cwd=ROOT,
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(
                source_validation.returncode,
                0,
                source_validation.stdout + source_validation.stderr,
            )


if __name__ == "__main__":
    unittest.main()
