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
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import composer_core as core

RELEASE_COMPONENTS = {
    "lifecycle.release-execution",
    "lifecycle.release-evidence",
    "lifecycle.release-bundle",
}
RELEASE_SEEDS = {
    "contracts/release-execution.json",
    "contracts/release-evidence.json",
    "contracts/release-bundle.json",
}


class WebappLegacyUpgradeTests(unittest.TestCase):
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

    def write_config(
        self,
        root: Path,
        name: str,
        *,
        include: list[str],
    ) -> Path:
        path = root / name
        path.write_text(
            json.dumps(
                {
                    "schema_version": 1,
                    "recipe": "webapp",
                    "components": {"include": include, "exclude": []},
                    "parameters": {},
                },
                indent=2,
            )
            + "\n",
            encoding="utf-8",
        )
        return path

    def materialize_simulated_v3_webapp(self, root: Path) -> Path:
        """Build the legacy release closure, then rewrite lock intent/version.

        The v3 Webapp artifact selected the complete release chain transitively from an
        empty include list. The current artifact can materialize the same file/component
        closure by explicitly selecting lifecycle.release-bundle. Rewriting only lock
        intent and the artifact version gives the managed planners the relevant v3 state
        shape without maintaining a second historical source tree inside the test suite.
        """

        target = root / "consumer"
        release_config = self.write_config(
            root,
            "release-ready.json",
            include=["lifecycle.release-bundle"],
        )
        result, payload = self.run_composer(
            "apply",
            "--mode",
            "initial",
            "--config",
            str(release_config),
            "--target",
            str(target),
        )
        self.assertEqual(result.returncode, 0, payload)

        lock_path = target / core.LOCK_RELATIVE
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        lock["intent"]["components"]["include"] = []
        artifact = next(
            entry
            for entry in lock["resolved_components"]
            if entry["id"] == "artifact.webapp-core"
        )
        self.assertEqual(artifact["version"], 9)
        artifact["version"] = 3
        artifact["descriptor_sha256"] = "3" * 64
        lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
        return target

    def test_ordinary_update_rejects_webapp_v3_to_current_component_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.materialize_simulated_v3_webapp(Path(temp_dir))
            result, plan = self.run_composer(
                "plan",
                "--mode",
                "update",
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 2, plan)
            self.assertTrue(
                any(
                    conflict["code"] == "COMPONENT_VERSION_UPGRADE_REQUIRED"
                    and conflict.get("component") == "artifact.webapp-core"
                    for conflict in plan["conflicts"]
                )
            )

    def test_upgrade_can_explicitly_retain_full_release_lifecycle(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = self.materialize_simulated_v3_webapp(root)
            upgrade_config = self.write_config(
                root,
                "upgrade-retain-release.json",
                include=["lifecycle.release-bundle"],
            )

            result, plan = self.run_composer(
                "plan",
                "--mode",
                "upgrade",
                "--config",
                str(upgrade_config),
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, plan)
            self.assertEqual(plan["conflicts"], [])
            self.assertEqual(plan["components"]["removed"], [])
            changed = {entry["id"]: entry for entry in plan["components"]["changed"]}
            self.assertEqual(changed["artifact.webapp-core"]["from_version"], 3)
            self.assertEqual(changed["artifact.webapp-core"]["to_version"], 9)
            self.assertEqual(
                changed["artifact.webapp-core"]["compatibility_boundary"],
                "component-version",
            )

            result, applied = self.run_composer(
                "apply",
                "--mode",
                "upgrade",
                "--config",
                str(upgrade_config),
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, applied)
            lock = json.loads(
                (target / core.LOCK_RELATIVE).read_text(encoding="utf-8")
            )
            resolved = {entry["id"] for entry in lock["resolved_components"]}
            self.assertTrue(RELEASE_COMPONENTS <= resolved)
            self.assertEqual(
                lock["intent"]["components"]["include"],
                ["lifecycle.release-bundle"],
            )

    def test_upgrade_can_drop_release_lifecycle_after_consumer_cleans_preserved_seeds(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = self.materialize_simulated_v3_webapp(root)
            original_seed_bytes = {
                relative: (target / relative).read_bytes() for relative in RELEASE_SEEDS
            }
            upgrade_config = self.write_config(
                root,
                "upgrade-minimal.json",
                include=[],
            )

            result, plan = self.run_composer(
                "plan",
                "--mode",
                "upgrade",
                "--config",
                str(upgrade_config),
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, plan)
            self.assertEqual(plan["conflicts"], [])
            self.assertEqual(set(plan["components"]["removed"]), RELEASE_COMPONENTS)
            preserved = {entry["destination"] for entry in plan["files"]["preserve"]}
            removed = {entry["destination"] for entry in plan["files"]["remove"]}
            self.assertTrue(RELEASE_SEEDS <= preserved)
            self.assertIn(
                ".template-composition/validators/validate_release_bundle.py",
                removed,
            )
            self.assertIn("schemas/release-bundle.schema.json", removed)

            result, applied = self.run_composer(
                "apply",
                "--mode",
                "upgrade",
                "--config",
                str(upgrade_config),
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, applied)

            lock = json.loads(
                (target / core.LOCK_RELATIVE).read_text(encoding="utf-8")
            )
            resolved = {entry["id"] for entry in lock["resolved_components"]}
            destinations = {entry["destination"] for entry in lock["files"]}
            self.assertFalse(resolved & RELEASE_COMPONENTS)
            self.assertFalse(destinations & RELEASE_SEEDS)
            for relative, expected_bytes in original_seed_bytes.items():
                self.assertEqual((target / relative).read_bytes(), expected_bytes, relative)
            self.assertFalse(
                (
                    target
                    / ".template-composition/validators/validate_release_bundle.py"
                ).exists()
            )

            # Preserved release seeds remain ordinary consumer files, but contracts/
            # is a closed active registry. Until the consumer archives or removes the
            # retired release documents, semantic validation must reject them rather
            # than silently treating file existence as lifecycle selection authority.
            result, validation = self.run_composer(
                "validate",
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 2, validation)
            self.assertEqual(validation["status"], "invalid")
            self.assertTrue(
                any("unregistered contract document" in error for error in validation["errors"])
            )

            archive = target / "release-history"
            archive.mkdir()
            for relative, expected_bytes in original_seed_bytes.items():
                source = target / relative
                destination = archive / Path(relative).name
                source.replace(destination)
                self.assertEqual(destination.read_bytes(), expected_bytes)

            result, validation = self.run_composer(
                "validate",
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, validation)
            self.assertEqual(validation["status"], "valid")
            self.assertFalse(
                any(
                    check["id"].startswith("release-")
                    for check in validation["checks"]
                )
            )


if __name__ == "__main__":
    unittest.main()
