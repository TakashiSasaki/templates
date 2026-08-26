from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "scripts" / "compose.py"


def config(
    recipe: str,
    *,
    include: list[str] | None = None,
    exclude: list[str] | None = None,
    parameters: dict | None = None,
) -> dict:
    return {
        "schema_version": 1,
        "recipe": recipe,
        "components": {
            "include": include or [],
            "exclude": exclude or [],
        },
        "parameters": parameters or {},
    }


class ComposerMVPTests(unittest.TestCase):
    def run_composer(
        self,
        command: str,
        *,
        target: Path,
        config_path: Path | None = None,
    ) -> tuple[subprocess.CompletedProcess, dict]:
        arguments = [sys.executable, str(COMPOSER), command, "--target", str(target)]
        if config_path is not None:
            arguments.extend(["--config", str(config_path)])
        result = subprocess.run(
            arguments,
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            self.fail(
                f"composer did not emit JSON: {exc}\nstdout={result.stdout}\nstderr={result.stderr}"
            )
        return result, payload

    def write_config(self, root: Path, value: dict) -> Path:
        path = root / "composition.json"
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        return path

    def test_minimal_skill_plan_resolves_only_artifact_and_composition_state(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self.write_config(root, config("skill"))
            target = root / "consumer"
            result, payload = self.run_composer(
                "plan", target=target, config_path=config_path
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                payload["resolved_components"],
                ["artifact.skill-core", "lifecycle.composition-state"],
            )
            self.assertEqual(payload["conflicts"], [])
            self.assertTrue(payload["actions"])

    def test_mcp_apps_include_resolves_mcp_runtime_and_evidence_dependencies(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self.write_config(
                root,
                config("skill", include=["capability.mcp-apps"]),
            )
            result, payload = self.run_composer(
                "plan", target=root / "consumer", config_path=config_path
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                payload["resolved_components"],
                [
                    "artifact.skill-core",
                    "capability.mcp",
                    "capability.mcp-apps",
                    "capability.runtime",
                    "lifecycle.composition-state",
                    "lifecycle.contract-evolution",
                    "lifecycle.implementation-evidence",
                ],
            )

    def test_minimal_webapp_resolves_evidence_baseline_without_release_or_runtime(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self.write_config(root, config("webapp"))
            result, payload = self.run_composer(
                "plan", target=root / "consumer", config_path=config_path
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                payload["resolved_components"],
                [
                    "artifact.webapp-core",
                    "lifecycle.composition-state",
                    "lifecycle.contract-evolution",
                    "lifecycle.implementation-evidence",
                ],
            )
            self.assertNotIn("capability.runtime", payload["resolved_components"])
            self.assertNotIn("lifecycle.release-bundle", payload["resolved_components"])

    def test_webapp_release_bundle_include_resolves_complete_release_lifecycle(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self.write_config(
                root,
                config("webapp", include=["lifecycle.release-bundle"]),
            )
            result, payload = self.run_composer(
                "plan", target=root / "consumer", config_path=config_path
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(
                payload["resolved_components"],
                [
                    "artifact.webapp-core",
                    "lifecycle.composition-state",
                    "lifecycle.contract-evolution",
                    "lifecycle.implementation-evidence",
                    "lifecycle.release-bundle",
                    "lifecycle.release-evidence",
                    "lifecycle.release-execution",
                ],
            )

    def test_excluding_transitive_dependency_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self.write_config(
                root,
                config(
                    "skill",
                    include=["capability.mcp"],
                    exclude=["capability.runtime"],
                ),
            )
            result, payload = self.run_composer(
                "plan", target=root / "consumer", config_path=config_path
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(payload["code"], "EXCLUDED_DEPENDENCY")

    def test_unexposed_component_selection_fails_closed(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self.write_config(
                root,
                config("webapp", include=["lifecycle.release-evidence"]),
            )
            result, payload = self.run_composer(
                "plan", target=root / "consumer", config_path=config_path
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(payload["code"], "COMPONENT_NOT_EXPOSED")

    def test_parameters_must_target_resolved_components(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self.write_config(
                root,
                config(
                    "skill",
                    parameters={"capability.cli": {"format": "json"}},
                ),
            )
            result, payload = self.run_composer(
                "plan", target=root / "consumer", config_path=config_path
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(payload["code"], "PARAMETER_COMPONENT_UNRESOLVED")

    def test_apply_writes_lock_last_and_materialized_consumer_validates(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self.write_config(root, config("skill"))
            target = root / "consumer"
            result, payload = self.run_composer(
                "apply", target=target, config_path=config_path
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual(payload["status"], "applied")
            lock_path = target / ".template-composition" / "lock.json"
            self.assertTrue(lock_path.is_file())

            consumer_validator = target / ".template-composition" / "validate_composition.py"
            validation = subprocess.run(
                [sys.executable, str(consumer_validator), str(target)],
                text=True,
                capture_output=True,
                check=False,
            )
            self.assertEqual(
                validation.returncode,
                0,
                validation.stdout + validation.stderr,
            )

            inspect_result, inspect_payload = self.run_composer(
                "inspect", target=target
            )
            self.assertEqual(inspect_result.returncode, 0, inspect_result.stderr)
            self.assertEqual(inspect_payload["state"], "managed-valid")

    def test_initial_apply_rejects_managed_target_with_current_lifecycle_guidance(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self.write_config(root, config("skill"))
            target = root / "consumer"
            first, _ = self.run_composer(
                "apply", target=target, config_path=config_path
            )
            self.assertEqual(first.returncode, 0, first.stderr)
            second, payload = self.run_composer(
                "apply", target=target, config_path=config_path
            )
            self.assertEqual(second.returncode, 2)
            self.assertEqual(payload["status"], "conflict")
            conflict = payload["conflicts"][0]
            self.assertIn("INITIAL_MODE_REQUIRES_UNMANAGED_TARGET", conflict)
            self.assertIn("--mode update", conflict)
            self.assertIn("--mode upgrade", conflict)
            self.assertNotIn("UPDATE_NOT_SUPPORTED", conflict)

    def test_identical_existing_file_is_adopted(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self.write_config(root, config("skill"))
            target = root / "consumer"
            target.mkdir()
            source = (
                ROOT
                / "components"
                / "artifact.skill-core"
                / "files"
                / ".editorconfig"
            )
            (target / ".editorconfig").write_bytes(source.read_bytes())
            result, payload = self.run_composer(
                "apply", target=target, config_path=config_path
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn(".editorconfig", payload["adopted"])

    def test_different_existing_file_is_never_overwritten_and_lock_is_not_written(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self.write_config(root, config("skill"))
            target = root / "consumer"
            target.mkdir()
            skill_path = target / "SKILL.md"
            original = b"consumer-owned existing bytes\n"
            skill_path.write_bytes(original)
            result, payload = self.run_composer(
                "apply", target=target, config_path=config_path
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(payload["status"], "conflict")
            self.assertEqual(skill_path.read_bytes(), original)
            self.assertFalse((target / ".template-composition" / "lock.json").exists())

    def test_case_variant_existing_path_is_a_conflict(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self.write_config(root, config("skill"))
            target = root / "consumer"
            target.mkdir()
            (target / "skill.md").write_text("case collision\n", encoding="utf-8")
            result, payload = self.run_composer(
                "plan", target=target, config_path=config_path
            )
            self.assertEqual(result.returncode, 2)
            self.assertTrue(
                any("portable case collision" in conflict for conflict in payload["conflicts"])
            )

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink support required")
    def test_symlink_destination_is_a_conflict(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self.write_config(root, config("skill"))
            target = root / "consumer"
            target.mkdir()
            backing = root / "backing"
            backing.write_text("do not follow\n", encoding="utf-8")
            try:
                os.symlink(backing, target / "SKILL.md")
            except OSError as exc:
                self.skipTest(f"cannot create symlink: {exc}")
            result, payload = self.run_composer(
                "plan", target=target, config_path=config_path
            )
            self.assertEqual(result.returncode, 2)
            self.assertTrue(
                any("symbolic link" in conflict for conflict in payload["conflicts"])
            )

    def test_seed_edits_are_allowed_but_managed_edits_are_detected(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self.write_config(root, config("skill"))
            target = root / "consumer"
            applied, _ = self.run_composer(
                "apply", target=target, config_path=config_path
            )
            self.assertEqual(applied.returncode, 0, applied.stderr)

            skill_path = target / "SKILL.md"
            skill_path.write_text(
                skill_path.read_text(encoding="utf-8") + "\nConsumer edit.\n",
                encoding="utf-8",
            )
            valid_seed, payload = self.run_composer("validate", target=target)
            self.assertEqual(valid_seed.returncode, 0, valid_seed.stderr)
            self.assertEqual(payload["status"], "valid")

            managed = target / "docs" / "architecture.md"
            managed.write_text(
                managed.read_text(encoding="utf-8") + "\nManaged tamper.\n",
                encoding="utf-8",
            )
            invalid, payload = self.run_composer("validate", target=target)
            self.assertEqual(invalid.returncode, 2)
            self.assertEqual(payload["status"], "invalid")
            self.assertTrue(
                any("managed material differs" in error for error in payload["errors"])
            )

    def test_lock_binds_exact_configuration_descriptor_and_material_bytes(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = self.write_config(root, config("skill"))
            target = root / "consumer"
            result, _ = self.run_composer(
                "apply", target=target, config_path=config_path
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            lock = json.loads(
                (target / ".template-composition" / "lock.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(
                lock["configuration_sha256"],
                hashlib.sha256(config_path.read_bytes()).hexdigest(),
            )
            descriptors = {
                entry["id"]: entry for entry in lock["resolved_components"]
            }
            skill_descriptor = (
                ROOT / "components" / "artifact.skill-core" / "component.json"
            )
            self.assertEqual(
                descriptors["artifact.skill-core"]["descriptor_sha256"],
                hashlib.sha256(skill_descriptor.read_bytes()).hexdigest(),
            )
            files = {entry["destination"]: entry for entry in lock["files"]}
            self.assertEqual(
                files["SKILL.md"]["materialized_sha256"],
                hashlib.sha256((target / "SKILL.md").read_bytes()).hexdigest(),
            )
            self.assertNotIn(".template-composition/lock.json", files)


if __name__ == "__main__":
    unittest.main()
