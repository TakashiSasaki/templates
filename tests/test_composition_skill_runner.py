from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PATH = ROOT / "skills" / "composition" / "scripts" / "runtime.py"
INSTALL_PATH = ROOT / "skills" / "composition" / "scripts" / "install.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


runtime = load_module("composition_skill_runtime", RUNTIME_PATH)
installer = load_module("composition_skill_installer", INSTALL_PATH)


class CompositionSkillRunnerTests(unittest.TestCase):
    def test_manifest_is_full_sha_and_matches_runtime_lock_digest(self) -> None:
        manifest = runtime.load_manifest()
        revision = manifest["toolchain"]["revision"]
        self.assertRegex(revision, r"^[0-9a-f]{40}$")
        lock = (ROOT / "requirements-runtime.lock").read_bytes()
        self.assertEqual(
            manifest["runtime_lock"]["sha256"],
            hashlib.sha256(lock).hexdigest(),
        )

    def test_select_revision_defaults_to_stable_manifest_pin(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary) / "consumer"
            self.assertEqual(
                runtime.select_revision(repository),
                runtime.stable_revision(),
            )

    def test_explicit_revision_requires_full_sha(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            with self.assertRaisesRegex(runtime.RunnerError, "full lowercase"):
                runtime.select_revision(repository, "composition")

    def test_transaction_revision_overrides_stable_pin(self) -> None:
        transaction_revision = "1" * 40
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            metadata = repository / ".template-composition"
            metadata.mkdir()
            (metadata / "transaction.json").write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "operation": "update",
                        "source": {
                            "repository": "TakashiSasaki/templates",
                            "revision": transaction_revision,
                        },
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                runtime.select_revision(repository),
                transaction_revision,
            )
            with self.assertRaisesRegex(runtime.RunnerError, "managed recovery requires"):
                runtime.select_revision(repository, "2" * 40)

    def test_malformed_transaction_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            metadata = repository / ".template-composition"
            metadata.mkdir()
            (metadata / "transaction.json").write_text(
                '{"schema_version":1,"operation":"update","source":{"repository":"TakashiSasaki/templates","revision":"composition"}}',
                encoding="utf-8",
            )
            with self.assertRaisesRegex(runtime.RunnerError, "full lowercase SHA"):
                runtime.select_revision(repository)

    def test_transaction_metadata_directory_symlink_is_rejected(self) -> None:
        if not hasattr(os, "symlink"):
            self.skipTest("symlink unavailable")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            actual = root / "actual"
            actual.mkdir()
            repository = root / "consumer"
            repository.mkdir()
            try:
                (repository / ".template-composition").symlink_to(
                    actual,
                    target_is_directory=True,
                )
            except OSError as exc:
                self.skipTest(f"symlink creation unavailable: {exc}")
            with self.assertRaisesRegex(runtime.RunnerError, "must not be a symbolic link"):
                runtime.select_revision(repository)

    def test_sanitized_environment_removes_python_and_pip_inputs(self) -> None:
        result = runtime.sanitized_environment(
            {
                "PATH": "safe",
                "PYTHONPATH": "unsafe",
                "PIP_INDEX_URL": "https://example.invalid",
                "OTHER": "value",
            }
        )
        self.assertEqual(result["PATH"], "safe")
        self.assertEqual(result["OTHER"], "value")
        self.assertNotIn("PYTHONPATH", result)
        self.assertNotIn("PIP_INDEX_URL", result)
        self.assertEqual(result["PYTHONNOUSERSITE"], "1")
        self.assertEqual(result["PIP_CONFIG_FILE"], os.devnull)

    def test_runtime_lock_rejects_duplicate_normalized_names(self) -> None:
        with self.assertRaisesRegex(runtime.RunnerError, "duplicate distribution"):
            runtime.parse_runtime_lock("rpds_py===1.0\nrpds-py===1.0\n")

    def test_installer_recognizes_only_composition_skill_marker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "composition"
            target.mkdir()
            (target / "SKILL.md").write_text(
                "---\nname: composition\ndescription: test\n---\n",
                encoding="utf-8",
            )
            self.assertTrue(installer.is_composition_skill_directory(target))
            (target / "SKILL.md").write_text(
                "---\nname: other\ndescription: test\n---\n",
                encoding="utf-8",
            )
            self.assertFalse(installer.is_composition_skill_directory(target))

    def test_installer_copies_runnable_skill_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "installed"
            installer.stage_and_install(
                ROOT / "skills" / "composition",
                target,
                replace=False,
            )
            self.assertTrue((target / "SKILL.md").is_file())
            self.assertTrue((target / "runtime-manifest.json").is_file())
            self.assertTrue((target / "scripts" / "run.py").is_file())
            self.assertTrue((target / "scripts" / "runtime.py").is_file())


if __name__ == "__main__":
    unittest.main()
