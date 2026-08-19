from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import composer_core as core
import composer_managed as managed
import composer_transaction as transaction


class UpdateApplyTests(unittest.TestCase):
    def make_target(self, root: Path) -> Path:
        config_path = root / "composition.json"
        config = {
            "schema_version": 1,
            "recipe": "skill",
            "components": {"include": [], "exclude": []},
            "parameters": {},
        }
        config_path.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        target = root / "consumer"
        status, payload = core.command_apply(config_path, target)
        self.assertEqual(status, 0, payload)
        return target

    def force_clean_replacement(self, target: Path, destination: str = "docs/architecture.md") -> bytes:
        path = target / destination
        desired = path.read_bytes()
        old = b"synthetic previous managed bytes\n"
        self.assertNotEqual(old, desired)
        path.write_bytes(old)
        lock_path = target / core.LOCK_RELATIVE
        lock = json.loads(lock_path.read_text(encoding="utf-8"))
        entry = next(item for item in lock["files"] if item["destination"] == destination)
        self.assertEqual(entry["ownership"], "managed")
        entry["materialized_sha256"] = core.sha256_bytes(old)
        lock_path.write_bytes(transaction._lock_bytes(lock))
        return desired

    def build_marker(self, target: Path) -> tuple[dict, bytes, dict]:
        lock_path = target / core.LOCK_RELATIVE
        old_lock_bytes = lock_path.read_bytes()
        status, plan = managed.plan_update(target)
        self.assertEqual(status, 0, plan)
        old_lock = json.loads(old_lock_bytes)
        marker = transaction._build_transaction(target, plan, old_lock_bytes, old_lock)
        marker_bytes = transaction._transaction_bytes(marker)
        transaction._write_no_overwrite_durable(
            target,
            target / core.TRANSACTION_RELATIVE,
            marker_bytes,
        )
        return marker, marker_bytes, plan

    def test_transaction_schema_is_valid(self) -> None:
        schema = json.loads(
            (ROOT / "schemas" / "composition-transaction.schema.json").read_text(encoding="utf-8")
        )
        Draft202012Validator.check_schema(schema)

    def test_no_op_update_does_not_create_transaction_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.make_target(Path(temp_dir))
            status, payload = transaction.apply_update(target)
            self.assertEqual(status, 0, payload)
            self.assertTrue(payload["no_op"])
            self.assertFalse((target / core.TRANSACTION_RELATIVE).exists())
            self.assertEqual(payload["applied"], [])

    def test_clean_managed_replacement_updates_bytes_and_lock(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.make_target(Path(temp_dir))
            desired = self.force_clean_replacement(target)
            status, payload = transaction.apply_update(target)
            self.assertEqual(status, 0, payload)
            self.assertFalse(payload["no_op"])
            self.assertFalse(payload["recovered"])
            self.assertEqual((target / "docs" / "architecture.md").read_bytes(), desired)
            self.assertFalse((target / core.TRANSACTION_RELATIVE).exists())
            valid, errors = core.validate_consumer_with_source_validator(target)
            self.assertTrue(valid, errors)

    def test_interrupted_replacement_recovers_when_file_is_already_new(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.make_target(Path(temp_dir))
            desired = self.force_clean_replacement(target)
            marker, marker_bytes, _ = self.build_marker(target)
            destination = "docs/architecture.md"
            (target / destination).write_bytes(desired)

            status, payload = transaction.apply_update(target)
            self.assertEqual(status, 0, payload)
            self.assertTrue(payload["recovered"])
            self.assertIn(destination, payload["resumed"])
            self.assertFalse((target / core.TRANSACTION_RELATIVE).exists())
            self.assertEqual(
                core.sha256_bytes((target / core.LOCK_RELATIVE).read_bytes()),
                marker["new_lock_file_sha256"],
            )
            self.assertNotEqual(marker_bytes, b"")

    def test_interrupted_after_lock_switch_only_removes_marker_after_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.make_target(Path(temp_dir))
            desired = self.force_clean_replacement(target)
            marker, _, _ = self.build_marker(target)
            (target / "docs" / "architecture.md").write_bytes(desired)
            (target / core.LOCK_RELATIVE).write_bytes(transaction._lock_bytes(marker["new_lock"]))

            status, payload = transaction.apply_update(target)
            self.assertEqual(status, 0, payload)
            self.assertTrue(payload["recovered"])
            self.assertIn(core.LOCK_RELATIVE, payload["resumed"])
            self.assertFalse((target / core.TRANSACTION_RELATIVE).exists())

    def test_consumer_change_after_marker_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.make_target(Path(temp_dir))
            self.force_clean_replacement(target)
            self.build_marker(target)
            path = target / "docs" / "architecture.md"
            consumer_bytes = b"consumer changed managed file after transaction start\n"
            path.write_bytes(consumer_bytes)

            with self.assertRaises(transaction.TransactionError) as captured:
                transaction.apply_update(target)
            self.assertEqual(captured.exception.code, "PRECONDITION_CHANGED")
            self.assertEqual(path.read_bytes(), consumer_bytes)
            self.assertTrue((target / core.TRANSACTION_RELATIVE).is_file())

    def test_successful_update_can_be_updated_again_as_no_op(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = self.make_target(Path(temp_dir))
            self.force_clean_replacement(target)
            first_status, first = transaction.apply_update(target)
            self.assertEqual(first_status, 0, first)
            second_status, second = transaction.apply_update(target)
            self.assertEqual(second_status, 0, second)
            self.assertTrue(second["no_op"])
            self.assertFalse(second["recovered"])

    def test_create_replace_remove_helpers_are_idempotent_and_digest_guarded(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            target = Path(temp_dir)
            create_path = target / "create.txt"
            new = b"new\n"
            digest = core.sha256_bytes(new)
            self.assertEqual(
                transaction._create_expected(target, create_path, new, expected_sha256=digest),
                "applied",
            )
            self.assertEqual(
                transaction._create_expected(target, create_path, new, expected_sha256=digest),
                "already-applied",
            )

            replace_path = target / "replace.txt"
            old = b"old\n"
            replace_path.write_bytes(old)
            self.assertEqual(
                transaction._atomic_replace_expected(
                    target,
                    replace_path,
                    new,
                    expected_sha256=core.sha256_bytes(old),
                    already_sha256=digest,
                ),
                "applied",
            )
            self.assertEqual(
                transaction._atomic_replace_expected(
                    target,
                    replace_path,
                    new,
                    expected_sha256=core.sha256_bytes(old),
                    already_sha256=digest,
                ),
                "already-applied",
            )

            remove_path = target / "remove.txt"
            remove_path.write_bytes(old)
            self.assertEqual(
                transaction._remove_expected(
                    target,
                    remove_path,
                    expected_sha256=core.sha256_bytes(old),
                ),
                "applied",
            )
            self.assertEqual(
                transaction._remove_expected(
                    target,
                    remove_path,
                    expected_sha256=core.sha256_bytes(old),
                ),
                "already-applied",
            )

    def test_symlink_is_never_replaced_by_transaction_helpers(self) -> None:
        if not hasattr(__import__("os"), "symlink"):
            self.skipTest("symlink support required")
        import os

        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            backing = root / "backing"
            backing.write_bytes(b"backing\n")
            link = root / "link"
            try:
                os.symlink(backing, link)
            except OSError as exc:
                self.skipTest(f"cannot create symlink: {exc}")
            with self.assertRaises(transaction.TransactionError):
                transaction._atomic_replace_expected(
                    root,
                    link,
                    b"new\n",
                    expected_sha256=core.sha256_bytes(backing.read_bytes()),
                    already_sha256=core.sha256_bytes(b"new\n"),
                )
            self.assertEqual(backing.read_bytes(), b"backing\n")


if __name__ == "__main__":
    unittest.main()
