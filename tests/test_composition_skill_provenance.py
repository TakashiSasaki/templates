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
RUNNER = ROOT / "skills" / "composition" / "scripts" / "run.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runner = load_module("composition_skill_provenance_runner", RUNNER)


def write_lock(repository: Path, revision: str) -> None:
    metadata = repository / ".template-composition"
    metadata.mkdir(parents=True, exist_ok=True)
    (metadata / "lock.json").write_text(
        json.dumps(
            {
                "schema_version": 2,
                "source": {
                    "repository": "TakashiSasaki/templates",
                    "revision": revision,
                },
                "intent": {
                    "recipe": "webapp",
                    "components": {"include": [], "exclude": []},
                    "parameters": {},
                },
                "recipe_sha256": "1" * 64,
                "configuration_sha256": "2" * 64,
                "resolved_components": [],
                "files": [],
            }
        )
        + "\n",
        encoding="utf-8",
    )


def write_transaction(repository: Path, revision: str) -> None:
    metadata = repository / ".template-composition"
    metadata.mkdir(parents=True, exist_ok=True)
    (metadata / "transaction.json").write_text(
        json.dumps(
            {
                "schema_version": 1,
                "operation": "update",
                "source": {
                    "repository": "TakashiSasaki/templates",
                    "revision": revision,
                },
            }
        )
        + "\n",
        encoding="utf-8",
    )


class CompositionSkillProvenanceTests(unittest.TestCase):
    def test_unmanaged_local_skill_reports_unrecorded_source_without_network(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "consumer"
            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    str(RUNNER),
                    "--repository",
                    str(repository),
                    "provenance",
                ],
                check=False,
                text=True,
                capture_output=True,
                env={**os.environ, "COMPOSITION_RUNTIME_CACHE": str(Path(temporary) / "cache")},
            )
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            roles = payload["roles"]
            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["canonical_repository"], "TakashiSasaki/templates")
            self.assertEqual(roles["skill_source"]["status"], "unrecorded")
            self.assertIsNone(roles["skill_source"]["source"])
            self.assertEqual(roles["stable_toolchain"]["authority"], "runtime_manifest")
            self.assertEqual(roles["selected_toolchain"]["authority"], "runtime_manifest")
            self.assertEqual(
                roles["selected_toolchain"]["source"],
                roles["stable_toolchain"]["source"],
            )
            self.assertEqual(roles["consumer_lock"]["status"], "absent")
            self.assertEqual(roles["transaction"]["status"], "absent")
            self.assertTrue(payload["relationships"]["selected_matches_stable"])
            self.assertIsNone(
                payload["relationships"]["consumer_lock_matches_selected"]
            )
            self.assertFalse((Path(temporary) / "cache").exists())

    def test_explicit_revision_changes_only_selected_toolchain_role(self) -> None:
        explicit = "a" * 40
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "consumer"
            payload = runner.provenance_payload(repository, explicit)
        self.assertEqual(
            payload["roles"]["selected_toolchain"],
            {
                "authority": "explicit_revision_argument",
                "source": {
                    "repository": "TakashiSasaki/templates",
                    "revision": explicit,
                },
            },
        )
        self.assertFalse(payload["relationships"]["selected_matches_stable"])
        self.assertEqual(payload["roles"]["consumer_lock"]["status"], "absent")

    def test_consumer_lock_reports_materialized_source_and_relationship(self) -> None:
        stable = runner.stable_revision(runner.load_manifest())
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "consumer"
            write_lock(repository, stable)
            payload = runner.provenance_payload(repository)
        self.assertEqual(payload["roles"]["consumer_lock"]["status"], "present")
        self.assertEqual(
            payload["roles"]["consumer_lock"]["source"]["revision"], stable
        )
        self.assertTrue(payload["relationships"]["consumer_lock_matches_selected"])

    def test_transaction_is_selected_authority_and_conflicting_override_fails(self) -> None:
        recovery = "b" * 40
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "consumer"
            write_transaction(repository, recovery)
            payload = runner.provenance_payload(repository)
            self.assertEqual(
                payload["roles"]["selected_toolchain"]["authority"],
                "composition_transaction",
            )
            self.assertEqual(
                payload["roles"]["selected_toolchain"]["source"]["revision"],
                recovery,
            )
            self.assertEqual(payload["roles"]["transaction"]["status"], "present")
            self.assertEqual(
                payload["roles"]["transaction"]["source"]["revision"], recovery
            )
            with self.assertRaisesRegex(
                runner.RunnerError, "managed recovery requires the exact transaction"
            ):
                runner.provenance_payload(repository, "c" * 40)

    def test_installation_receipt_is_strict_and_never_guessed(self) -> None:
        source_revision = "d" * 40
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            absent = root / "absent.json"
            self.assertIsNone(runner.load_installation_source(absent))

            receipt = root / "receipt.json"
            receipt.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "source": {
                            "repository": "TakashiSasaki/templates",
                            "revision": source_revision,
                        },
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                runner.load_installation_source(receipt),
                {
                    "repository": "TakashiSasaki/templates",
                    "revision": source_revision,
                },
            )

            receipt.write_text(
                '{"schema_version":1,"source":{"repository":"TakashiSasaki/templates","revision":"composition"}}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(runner.RunnerError, "full lowercase SHA"):
                runner.load_installation_source(receipt)

    def test_installation_receipt_symlink_is_rejected(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlink unavailable")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target.json"
            target.write_text("{}", encoding="utf-8")
            receipt = root / "receipt.json"
            try:
                receipt.symlink_to(target)
            except OSError as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")
            with self.assertRaisesRegex(runner.RunnerError, "must be a regular file"):
                runner.load_installation_source(receipt)

    def test_lock_source_fails_closed_on_wrong_schema_or_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "consumer"
            write_lock(repository, "e" * 40)
            lock = repository / ".template-composition" / "lock.json"
            value = json.loads(lock.read_text(encoding="utf-8"))
            value["schema_version"] = 1
            lock.write_text(json.dumps(value), encoding="utf-8")
            with self.assertRaisesRegex(runner.RunnerError, "unsupported Composition lock schema"):
                runner.consumer_lock_source(repository)

            if hasattr(os, "symlink"):
                lock.unlink()
                target = Path(temporary) / "outside.json"
                target.write_text(json.dumps(value), encoding="utf-8")
                try:
                    lock.symlink_to(target)
                except OSError:
                    return
                with self.assertRaisesRegex(runner.RunnerError, "must be a regular file"):
                    runner.consumer_lock_source(repository)


if __name__ == "__main__":
    unittest.main()
