from __future__ import annotations

import importlib.util
import json
import os
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
import composer_managed as managed


def config(recipe: str = "skill") -> dict:
    return {
        "schema_version": 1,
        "recipe": recipe,
        "components": {"include": [], "exclude": []},
        "parameters": {},
    }


def file_entry(destination: str, ownership: str, data: bytes, component: str = "artifact.skill-core") -> dict:
    return {
        "destination": destination,
        "component": component,
        "ownership": ownership,
        "materialized_sha256": core.sha256_bytes(data),
    }


def material(destination: str, ownership: str, data: bytes, component: str = "artifact.skill-core") -> core.Material:
    return core.Material(component, destination, ownership, data)


class UpdatePlannerUnitTests(unittest.TestCase):
    def plan_files(self, target: Path, old_files: list[dict], new_materials: list[core.Material]):
        old_lock = {"files": sorted(old_files, key=lambda entry: entry["destination"])}
        return managed._file_plan(
            target,
            old_lock,
            sorted(new_materials, key=lambda entry: entry.destination),
        )

    def test_managed_replacement_requires_old_digest_match(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            old = b"old\n"
            new = b"new\n"
            (target / "managed.txt").write_bytes(old)
            files, conflicts, _ = self.plan_files(
                target,
                [file_entry("managed.txt", "managed", old)],
                [material("managed.txt", "managed", new)],
            )
            self.assertEqual(conflicts, [])
            self.assertEqual([entry["destination"] for entry in files["replace"]], ["managed.txt"])

            (target / "managed.txt").write_bytes(b"consumer edit\n")
            files, conflicts, _ = self.plan_files(
                target,
                [file_entry("managed.txt", "managed", old)],
                [material("managed.txt", "managed", new)],
            )
            self.assertEqual(files["replace"], [])
            self.assertEqual(conflicts[0]["code"], "LOCAL_MODIFICATION")

    def test_generated_regeneration_requires_old_digest_match(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            old = b'{"value":1}\n'
            new = b'{"value":2}\n'
            (target / "generated.json").write_bytes(old)
            files, conflicts, _ = self.plan_files(
                target,
                [file_entry("generated.json", "generated", old)],
                [material("generated.json", "generated", new)],
            )
            self.assertEqual(conflicts, [])
            self.assertEqual(len(files["replace"]), 1)

            (target / "generated.json").write_bytes(b"local generated edit\n")
            _, conflicts, _ = self.plan_files(
                target,
                [file_entry("generated.json", "generated", old)],
                [material("generated.json", "generated", new)],
            )
            self.assertEqual(conflicts[0]["code"], "LOCAL_MODIFICATION")

    def test_seed_is_preserved_and_old_seed_digest_is_carried(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            original_seed = b"source seed v1\n"
            consumer = b"consumer-owned edit\n"
            (target / "seed.txt").write_bytes(consumer)
            files, conflicts, carried = self.plan_files(
                target,
                [file_entry("seed.txt", "seed", original_seed)],
                [material("seed.txt", "seed", b"source seed v2\n")],
            )
            self.assertEqual(conflicts, [])
            self.assertEqual([entry["destination"] for entry in files["preserve"]], ["seed.txt"])
            self.assertEqual(carried["seed.txt"], core.sha256_bytes(original_seed))

    def test_new_files_require_an_empty_safe_destination(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            files, conflicts, _ = self.plan_files(
                target,
                [],
                [material("new.txt", "managed", b"new\n")],
            )
            self.assertEqual(conflicts, [])
            self.assertEqual([entry["destination"] for entry in files["create"]], ["new.txt"])

            (target / "new.txt").write_bytes(b"preexisting\n")
            files, conflicts, _ = self.plan_files(
                target,
                [],
                [material("new.txt", "managed", b"new\n")],
            )
            self.assertEqual(files["create"], [])
            self.assertTrue(all(entry["code"] == "DESTINATION_CONFLICT" for entry in conflicts))

    def test_removed_clean_managed_and_generated_are_remove_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            managed_bytes = b"managed\n"
            generated_bytes = b"generated\n"
            (target / "managed.txt").write_bytes(managed_bytes)
            (target / "generated.txt").write_bytes(generated_bytes)
            files, conflicts, _ = self.plan_files(
                target,
                [
                    file_entry("managed.txt", "managed", managed_bytes),
                    file_entry("generated.txt", "generated", generated_bytes),
                ],
                [],
            )
            self.assertEqual(conflicts, [])
            self.assertEqual(
                [entry["destination"] for entry in files["remove"]],
                ["generated.txt", "managed.txt"],
            )

    def test_removed_modified_managed_conflicts_and_removed_seed_is_preserved(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            old_managed = b"managed\n"
            old_seed = b"seed\n"
            (target / "managed.txt").write_bytes(b"consumer modified managed\n")
            (target / "seed.txt").write_bytes(b"consumer seed edit\n")
            files, conflicts, _ = self.plan_files(
                target,
                [
                    file_entry("managed.txt", "managed", old_managed),
                    file_entry("seed.txt", "seed", old_seed),
                ],
                [],
            )
            self.assertEqual(conflicts[0]["code"], "LOCAL_MODIFICATION")
            self.assertEqual([entry["destination"] for entry in files["preserve"]], ["seed.txt"])

    def test_ownership_and_owner_transitions_require_upgrade(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            old = b"old\n"
            (target / "file.txt").write_bytes(old)
            _, conflicts, _ = self.plan_files(
                target,
                [file_entry("file.txt", "managed", old)],
                [material("file.txt", "seed", b"new\n")],
            )
            self.assertEqual(conflicts[0]["code"], "OWNERSHIP_TRANSITION_UPGRADE_REQUIRED")

            _, conflicts, _ = self.plan_files(
                target,
                [file_entry("file.txt", "managed", old, "artifact.skill-core")],
                [material("file.txt", "managed", b"new\n", "lifecycle.composition-state")],
            )
            self.assertEqual(conflicts[0]["code"], "FILE_OWNER_TRANSITION_UPGRADE_REQUIRED")

    def test_portable_case_and_file_directory_collisions_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            (target / "README.md").write_bytes(b"existing\n")
            _, conflicts, _ = self.plan_files(
                target,
                [],
                [material("readme.md", "managed", b"new\n")],
            )
            self.assertTrue(any("portable case collision" in entry["message"] for entry in conflicts))

            (target / "node").write_bytes(b"file parent\n")
            _, conflicts, _ = self.plan_files(
                target,
                [],
                [material("node/child.txt", "managed", b"new\n")],
            )
            self.assertTrue(any("parent path" in entry["message"] for entry in conflicts))

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink support required")
    def test_symlink_attack_is_a_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = root / "consumer"
            target.mkdir()
            backing = root / "backing"
            backing.write_bytes(b"backing\n")
            try:
                os.symlink(backing, target / "managed.txt")
            except OSError as exc:
                self.skipTest(f"cannot create symlink: {exc}")
            _, conflicts, _ = self.plan_files(
                target,
                [file_entry("managed.txt", "managed", b"old\n")],
                [material("managed.txt", "managed", b"new\n")],
            )
            self.assertEqual(conflicts[0]["code"], "OLD_STATE_INVALID")

    def test_component_version_change_requires_upgrade_and_same_version_descriptor_drift_is_invalid(self) -> None:
        state = core.load_source_state()
        selected = ["artifact.skill-core", "lifecycle.composition-state"]
        current_entries = []
        for component_id in selected:
            descriptor = core._component_path(component_id).read_bytes()
            current_entries.append(
                {
                    "id": component_id,
                    "version": state.components[component_id]["version"],
                    "descriptor_sha256": core.sha256_bytes(descriptor),
                }
            )

        old_lock = {"resolved_components": json.loads(json.dumps(current_entries))}
        old_lock["resolved_components"][0]["version"] += 1
        components, conflicts = managed._component_plan(old_lock, state, selected)
        self.assertEqual(components["changed"][0]["id"], "artifact.skill-core")
        self.assertTrue(any(entry["code"] == "COMPONENT_VERSION_UPGRADE_REQUIRED" for entry in conflicts))

        old_lock = {"resolved_components": json.loads(json.dumps(current_entries))}
        old_lock["resolved_components"][0]["descriptor_sha256"] = "f" * 64
        _, conflicts = managed._component_plan(old_lock, state, selected)
        self.assertTrue(
            any(entry["code"] == "COMPONENT_DESCRIPTOR_CHANGED_WITHOUT_VERSION" for entry in conflicts)
        )


class UpdatePlannerCLITests(unittest.TestCase):
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

    def materialize(self, root: Path) -> tuple[Path, Path]:
        config_path = root / "composition.json"
        config_path.write_text(json.dumps(config(), indent=2) + "\n", encoding="utf-8")
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

    def test_no_op_update_plan_is_read_only_and_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _, target = self.materialize(root)
            before = {
                path.relative_to(target).as_posix(): path.read_bytes()
                for path in target.rglob("*")
                if path.is_file()
            }
            first, first_payload = self.run_composer(
                "plan", "--mode", "update", "--target", str(target)
            )
            second, second_payload = self.run_composer(
                "plan", "--mode=update", "--target", str(target)
            )
            self.assertEqual(first.returncode, 0, first_payload)
            self.assertEqual(second.returncode, 0, second_payload)
            self.assertEqual(first_payload, second_payload)
            self.assertEqual(first_payload["operation"], "update")
            self.assertEqual(first_payload["from_revision"], first_payload["to_revision"])
            self.assertEqual(first_payload["conflicts"], [])
            self.assertEqual(first_payload["files"]["create"], [])
            self.assertEqual(first_payload["files"]["replace"], [])
            self.assertEqual(first_payload["files"]["remove"], [])
            after = {
                path.relative_to(target).as_posix(): path.read_bytes()
                for path in target.rglob("*")
                if path.is_file()
            }
            self.assertEqual(before, after)

    def test_locally_modified_managed_is_reported_as_conflict(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _, target = self.materialize(root)
            managed_path = target / "docs" / "architecture.md"
            managed_path.write_bytes(managed_path.read_bytes() + b"local edit\n")
            result, payload = self.run_composer(
                "plan", "--mode", "update", "--target", str(target)
            )
            self.assertEqual(result.returncode, 2)
            self.assertTrue(any(entry["code"] == "LOCAL_MODIFICATION" for entry in payload["conflicts"]))

    def test_modified_seed_is_preserved_by_update_plan(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _, target = self.materialize(root)
            seed_path = target / "SKILL.md"
            seed_path.write_bytes(seed_path.read_bytes() + b"consumer edit\n")
            result, payload = self.run_composer(
                "plan", "--mode", "update", "--target", str(target)
            )
            self.assertEqual(result.returncode, 0, payload)
            preserved = {entry["destination"] for entry in payload["files"]["preserve"]}
            self.assertIn("SKILL.md", preserved)
            self.assertEqual(seed_path.read_bytes()[-14:], b"consumer edit\n")

    def test_update_rejects_explicit_config_and_apply_remains_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path, target = self.materialize(root)
            result, payload = self.run_composer(
                "plan",
                "--mode",
                "update",
                "--config",
                str(config_path),
                "--target",
                str(target),
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(payload["code"], "UPDATE_CONFIG_NOT_ALLOWED")

            lock_before = (target / ".template-composition" / "lock.json").read_bytes()
            result, payload = self.run_composer(
                "apply", "--mode", "update", "--target", str(target)
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(payload["code"], "UPDATE_APPLY_NOT_IMPLEMENTED")
            self.assertEqual((target / ".template-composition" / "lock.json").read_bytes(), lock_before)

    def test_malformed_old_lock_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _, target = self.materialize(root)
            lock_path = target / ".template-composition" / "lock.json"
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            lock["schema_version"] = 1
            lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
            result, payload = self.run_composer(
                "plan", "--mode", "update", "--target", str(target)
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(payload["code"], "INVALID_OLD_LOCK")

    def test_unsupported_source_identity_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _, target = self.materialize(root)
            lock_path = target / ".template-composition" / "lock.json"
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            lock["source"]["repository"] = "example/other"
            lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
            result, payload = self.run_composer(
                "plan", "--mode", "update", "--target", str(target)
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(payload["code"], "INVALID_OLD_LOCK")

    def test_unavailable_old_source_revision_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            _, target = self.materialize(root)
            lock_path = target / ".template-composition" / "lock.json"
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            lock["source"]["revision"] = "1" * 40
            lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
            result, payload = self.run_composer(
                "plan", "--mode", "update", "--target", str(target)
            )
            self.assertEqual(result.returncode, 2)
            self.assertEqual(payload["code"], "OLD_SOURCE_REVISION_UNAVAILABLE")


if __name__ == "__main__":
    unittest.main()
