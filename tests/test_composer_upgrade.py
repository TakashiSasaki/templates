from __future__ import annotations

import hashlib
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
import composer_transaction as transaction
import composer_upgrade as upgrade


def config(
    *,
    recipe: str = "skill",
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


class UpgradeCLITests(unittest.TestCase):
    def run_composer(self, *arguments: str) -> tuple[subprocess.CompletedProcess[str], dict]:
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
            self.fail(f"composer did not emit JSON: {exc}\n{result.stdout}\n{result.stderr}")
        return result, payload

    def write_config(self, root: Path, name: str, value: dict) -> Path:
        path = root / name
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")
        return path

    def materialize(self, root: Path, value: dict | None = None) -> tuple[Path, Path]:
        config_path = self.write_config(root, "initial.json", value or config())
        target = root / "consumer"
        result, payload = self.run_composer(
            "apply",
            "--mode",
            "initial",
            "--config",
            str(config_path),
            "--target",
            str(target),
        )
        self.assertEqual(result.returncode, 0, payload)
        return config_path, target

    def test_upgrade_requires_explicit_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            _, target = self.materialize(Path(temp_dir))
            for command in ("plan", "apply"):
                result, payload = self.run_composer(
                    command,
                    "--mode",
                    "upgrade",
                    "--target",
                    str(target),
                )
                self.assertEqual(result.returncode, 2)
                self.assertEqual(payload["code"], "UPGRADE_CONFIG_REQUIRED")

    def test_include_change_adds_components_and_applies_safely(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _, target = self.materialize(root)
            new_config = self.write_config(
                root,
                "upgrade.json",
                config(include=["capability.cli"]),
            )
            first, first_payload = self.run_composer(
                "plan",
                "--mode",
                "upgrade",
                "--config",
                str(new_config),
                "--target",
                str(target),
            )
            second, second_payload = self.run_composer(
                "plan",
                "--mode=upgrade",
                "--config",
                str(new_config),
                "--target",
                str(target),
            )
            self.assertEqual(first.returncode, 0, first_payload)
            self.assertEqual(second.returncode, 0, second_payload)
            self.assertEqual(first_payload, second_payload)
            self.assertEqual(
                first_payload["components"]["added"],
                [
                    "capability.cli",
                    "capability.runtime",
                    "lifecycle.contract-evolution",
                    "lifecycle.implementation-evidence",
                    "lifecycle.lifecycle-checkpoints",
                ],
            )
            creates = {entry["destination"] for entry in first_payload["files"]["create"]}
            self.assertTrue({"CLI_INTERFACE.md", "RUNTIME.md", "docs/runtime-selection.md"} <= creates)

            result, payload = self.run_composer(
                "apply",
                "--mode",
                "upgrade",
                "--config",
                str(new_config),
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, payload)
            self.assertEqual(payload["status"], "upgraded")
            self.assertFalse(payload["no_op"])
            lock = json.loads((target / core.LOCK_RELATIVE).read_text(encoding="utf-8"))
            self.assertEqual(lock["intent"]["components"]["include"], ["capability.cli"])
            self.assertTrue((target / "CLI_INTERFACE.md").is_file())
            self.assertTrue((target / "RUNTIME.md").is_file())
            self.assertTrue((target / "docs" / "runtime-selection.md").is_file())
            valid, errors = core.validate_consumer_with_source_validator(target)
            self.assertTrue(valid, errors)

    def test_exclude_change_removes_clean_managed_but_preserves_removed_seeds(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _, target = self.materialize(root, config(include=["capability.cli"]))
            cli_seed = target / "CLI_INTERFACE.md"
            runtime_seed = target / "RUNTIME.md"
            cli_seed.write_bytes(cli_seed.read_bytes() + b"consumer cli edit\n")
            runtime_seed.write_bytes(runtime_seed.read_bytes() + b"consumer runtime edit\n")
            managed_runtime = target / "docs" / "runtime-selection.md"
            self.assertTrue(managed_runtime.is_file())

            new_config = self.write_config(
                root,
                "upgrade.json",
                config(exclude=["capability.cli"]),
            )
            result, plan = self.run_composer(
                "plan",
                "--mode",
                "upgrade",
                "--config",
                str(new_config),
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, plan)
            self.assertEqual(
                plan["components"]["removed"],
                [
                    "capability.cli",
                    "capability.runtime",
                    "lifecycle.contract-evolution",
                    "lifecycle.implementation-evidence",
                    "lifecycle.lifecycle-checkpoints",
                ],
            )
            preserved = {entry["destination"] for entry in plan["files"]["preserve"]}
            removed = {entry["destination"] for entry in plan["files"]["remove"]}
            self.assertTrue({"CLI_INTERFACE.md", "RUNTIME.md"} <= preserved)
            self.assertIn("docs/runtime-selection.md", removed)

            result, payload = self.run_composer(
                "apply",
                "--mode",
                "upgrade",
                "--config",
                str(new_config),
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, payload)
            self.assertIn(b"consumer cli edit", cli_seed.read_bytes())
            self.assertIn(b"consumer runtime edit", runtime_seed.read_bytes())
            self.assertFalse(managed_runtime.exists())
            lock = json.loads((target / core.LOCK_RELATIVE).read_text(encoding="utf-8"))
            self.assertEqual(lock["intent"]["components"]["exclude"], ["capability.cli"])
            destinations = {entry["destination"] for entry in lock["files"]}
            self.assertNotIn("CLI_INTERFACE.md", destinations)
            self.assertNotIn("RUNTIME.md", destinations)

    def test_parameter_change_updates_intent_and_exact_config_provenance(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _, target = self.materialize(root)
            new_config = self.write_config(
                root,
                "upgrade.json",
                config(parameters={"artifact.skill-core": {"answer": 42, "nested": {"z": 1, "a": 2}}}),
            )
            result, plan = self.run_composer(
                "plan",
                "--mode",
                "upgrade",
                "--config",
                str(new_config),
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, plan)
            self.assertEqual(plan["files"]["create"], [])
            self.assertEqual(plan["files"]["replace"], [])
            self.assertEqual(plan["files"]["remove"], [])
            expected_config_sha = hashlib.sha256(new_config.read_bytes()).hexdigest()
            self.assertEqual(plan["configuration_sha256"]["to"], expected_config_sha)

            result, payload = self.run_composer(
                "apply",
                "--mode",
                "upgrade",
                "--config",
                str(new_config),
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, payload)
            lock = json.loads((target / core.LOCK_RELATIVE).read_text(encoding="utf-8"))
            self.assertEqual(lock["configuration_sha256"], expected_config_sha)
            self.assertEqual(
                list(lock["intent"]["parameters"]["artifact.skill-core"]["nested"]),
                ["a", "z"],
            )

    def test_recipe_change_is_explicit_but_owner_transitions_are_not_inferred(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _, target = self.materialize(root)
            new_config = self.write_config(root, "webapp.json", config(recipe="webapp"))
            result, plan = self.run_composer(
                "plan",
                "--mode",
                "upgrade",
                "--config",
                str(new_config),
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(plan["operation"], "upgrade")
            self.assertEqual(plan["recipe"]["from_id"], "skill")
            self.assertEqual(plan["recipe"]["to_id"], "webapp")
            self.assertTrue(plan["recipe"]["changed"])
            self.assertTrue(
                any(
                    entry["code"] == "FILE_OWNER_TRANSITION_NOT_SUPPORTED"
                    for entry in plan["conflicts"]
                )
            )

    def test_update_still_refuses_new_intent_while_upgrade_accepts_it(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _, target = self.materialize(root)
            new_config = self.write_config(
                root,
                "upgrade.json",
                config(include=["capability.cli"]),
            )
            result, payload = self.run_composer(
                "plan",
                "--mode",
                "update",
                "--config",
                str(new_config),
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(payload["code"], "UPDATE_CONFIG_NOT_ALLOWED")
            result, payload = self.run_composer(
                "plan",
                "--mode",
                "upgrade",
                "--config",
                str(new_config),
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, payload)

    def test_interrupted_upgrade_recovers_from_marker_without_config(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _, target = self.materialize(root)
            new_config = self.write_config(
                root,
                "upgrade.json",
                config(include=["capability.cli"]),
            )
            old_lock_path = target / core.LOCK_RELATIVE
            old_lock_bytes = old_lock_path.read_bytes()
            status, plan = upgrade.plan_upgrade(target, new_config)
            self.assertEqual(status, 0, plan)
            old_lock = json.loads(old_lock_bytes)
            marker = upgrade._build_upgrade_transaction(plan, old_lock_bytes, old_lock)
            marker_bytes = transaction._transaction_bytes(marker)
            transaction._write_no_overwrite_durable(
                target,
                target / core.TRANSACTION_RELATIVE,
                marker_bytes,
            )
            material_map = upgrade._desired_materials_for_upgrade_transaction(marker)
            create_action = next(entry for entry in marker["actions"] if entry["action"] == "create")
            destination = create_action["destination"]
            material = material_map[destination]
            transaction._create_expected(
                target,
                target / destination,
                material.data,
                expected_sha256=create_action["to_sha256"],
            )

            result, payload = self.run_composer(
                "apply",
                "--mode",
                "upgrade",
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 0, payload)
            self.assertTrue(payload["recovered"])
            self.assertIn(destination, payload["resumed"])
            self.assertFalse((target / core.TRANSACTION_RELATIVE).exists())
            valid, errors = core.validate_consumer_with_source_validator(target)
            self.assertTrue(valid, errors)


class UpgradeCompatibilityTests(unittest.TestCase):
    def test_component_version_change_is_allowed_only_by_upgrade_planner(self) -> None:
        state = core.load_source_state()
        selected = ["artifact.skill-core", "lifecycle.composition-state"]
        old_entries = []
        for component_id in selected:
            descriptor_digest = core.sha256_bytes(core._component_path(component_id).read_bytes())
            old_entries.append(
                {
                    "id": component_id,
                    "version": state.components[component_id]["version"] + 1,
                    "descriptor_sha256": descriptor_digest,
                }
            )
        old_lock = {"resolved_components": old_entries}
        components, conflicts = upgrade._upgrade_component_plan(old_lock, state, selected)
        self.assertEqual(conflicts, [])
        self.assertEqual(
            [entry["id"] for entry in components["changed"]],
            ["artifact.skill-core", "lifecycle.composition-state"],
        )
        self.assertTrue(
            all(entry["compatibility_boundary"] == "component-version" for entry in components["changed"])
        )

    def test_same_version_descriptor_drift_is_rejected_even_by_upgrade(self) -> None:
        state = core.load_source_state()
        selected = ["artifact.skill-core", "lifecycle.composition-state"]
        old_entries = []
        for component_id in selected:
            descriptor_digest = core.sha256_bytes(core._component_path(component_id).read_bytes())
            old_entries.append(
                {
                    "id": component_id,
                    "version": state.components[component_id]["version"],
                    "descriptor_sha256": descriptor_digest,
                }
            )
        old_entries[0]["descriptor_sha256"] = "f" * 64
        old_lock = {"resolved_components": old_entries}
        _, conflicts = upgrade._upgrade_component_plan(old_lock, state, selected)
        self.assertEqual(conflicts[0]["code"], "COMPONENT_DESCRIPTOR_CHANGED_WITHOUT_VERSION")

    def test_owner_and_ownership_transitions_remain_unsupported(self) -> None:
        old_lock = {
            "files": [
                {
                    "destination": "file.txt",
                    "component": "artifact.skill-core",
                    "ownership": "managed",
                    "materialized_sha256": "a" * 64,
                }
            ]
        }
        new_lock = {
            "files": [
                {
                    "destination": "file.txt",
                    "component": "artifact.webapp-core",
                    "ownership": "managed",
                    "materialized_sha256": "b" * 64,
                }
            ]
        }
        with self.assertRaises(upgrade.UpgradeError) as captured:
            upgrade._assert_supported_lock_transition(old_lock, new_lock)
        self.assertEqual(captured.exception.code, "FILE_OWNER_TRANSITION_NOT_SUPPORTED")

        new_lock["files"][0]["component"] = "artifact.skill-core"
        new_lock["files"][0]["ownership"] = "seed"
        with self.assertRaises(upgrade.UpgradeError) as captured:
            upgrade._assert_supported_lock_transition(old_lock, new_lock)
        self.assertEqual(captured.exception.code, "OWNERSHIP_TRANSITION_NOT_SUPPORTED")


if __name__ == "__main__":
    unittest.main()
