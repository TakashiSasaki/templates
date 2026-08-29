from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
COMPOSER = SCRIPTS / "compose.py"
WEBAPP_COMPONENT = ROOT / "components" / "artifact.webapp-core" / "component.json"
CURRENT_WEBAPP_VERSION = json.loads(WEBAPP_COMPONENT.read_text(encoding="utf-8"))["version"]
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import composer_core as core


class WebappV5SurfaceUpgradeTests(unittest.TestCase):
    def run_composer(
        self, *arguments: str
    ) -> tuple[subprocess.CompletedProcess[str], dict]:
        result = subprocess.run(
            [sys.executable, str(COMPOSER), *arguments],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            self.fail(
                f"composer did not emit JSON: {exc}\n"
                f"stdout={result.stdout}\nstderr={result.stderr}"
            )
        return result, payload

    def write_config(self, root: Path) -> Path:
        path = root / "webapp.json"
        path.write_text(
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
        return path

    def simulated_v4_consumer(self, root: Path) -> tuple[Path, Path, bytes]:
        target = root / "consumer"
        config = self.write_config(root)
        result, payload = self.run_composer(
            "apply",
            "--config",
            str(config),
            "--target",
            str(target),
        )
        self.assertEqual(result.returncode, 0, payload)

        lock_path = target / core.LOCK_RELATIVE
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        artifact = next(
            entry
            for entry in lock["resolved_components"]
            if entry["id"] == "artifact.webapp-core"
        )
        self.assertEqual(artifact["version"], CURRENT_WEBAPP_VERSION)
        artifact["version"] = 4
        artifact["descriptor_sha256"] = "4" * 64
        lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")

        surfaces_path = target / "contracts" / "surfaces.json"
        surfaces = json.loads(surfaces_path.read_text(encoding="utf-8"))
        surfaces["schemaVersion"] = 1
        for surface in surfaces["surfaces"]:
            surface["startupDependencies"] = surface.pop("surfaceDependencies")
        surfaces_path.write_text(
            json.dumps(surfaces, indent=2) + "\n", encoding="utf-8"
        )
        return target, config, surfaces_path.read_bytes()

    def test_update_requires_upgrade_and_upgrade_preserves_v1_seed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target, config, v1_seed = self.simulated_v4_consumer(root)

            result, plan = self.run_composer(
                "plan", "--mode", "update", "--target", str(target)
            )
            self.assertEqual(result.returncode, 2, plan)
            self.assertTrue(
                any(
                    conflict["code"] == "COMPONENT_VERSION_UPGRADE_REQUIRED"
                    and conflict.get("component") == "artifact.webapp-core"
                    for conflict in plan["conflicts"]
                ),
                plan,
            )

            result, plan = self.run_composer(
                "plan",
                "--mode",
                "upgrade",
                "--config",
                str(config),
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, plan)
            changed = {entry["id"]: entry for entry in plan["components"]["changed"]}
            self.assertEqual(changed["artifact.webapp-core"]["from_version"], 4)
            self.assertEqual(
                changed["artifact.webapp-core"]["to_version"], CURRENT_WEBAPP_VERSION
            )
            preserved = {
                entry["destination"] for entry in plan["files"]["preserve"]
            }
            self.assertIn("contracts/surfaces.json", preserved)

            result, applied = self.run_composer(
                "apply",
                "--mode",
                "upgrade",
                "--config",
                str(config),
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, applied)
            surfaces_path = target / "contracts" / "surfaces.json"
            self.assertEqual(surfaces_path.read_bytes(), v1_seed)
            lock = json.loads(
                (target / core.LOCK_RELATIVE).read_text(encoding="utf-8")
            )
            artifact = next(
                entry
                for entry in lock["resolved_components"]
                if entry["id"] == "artifact.webapp-core"
            )
            self.assertEqual(artifact["version"], CURRENT_WEBAPP_VERSION)

            result, validation = self.run_composer(
                "validate", "--target", str(target)
            )
            self.assertEqual(result.returncode, 2, validation)
            self.assertEqual(validation["status"], "invalid")
            self.assertTrue(
                any("surfaceDependencies" in error for error in validation["errors"]),
                validation,
            )

            surfaces = json.loads(surfaces_path.read_text(encoding="utf-8"))
            surfaces["schemaVersion"] = 2
            for surface in surfaces["surfaces"]:
                surface["surfaceDependencies"] = surface.pop("startupDependencies")
            surfaces_path.write_text(
                json.dumps(surfaces, indent=2) + "\n", encoding="utf-8"
            )

            result, validation = self.run_composer(
                "validate", "--target", str(target)
            )
            self.assertEqual(result.returncode, 0, validation)
            self.assertEqual(validation["status"], "valid")


if __name__ == "__main__":
    unittest.main()
