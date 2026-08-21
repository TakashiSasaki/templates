from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PATH = ROOT / "skills" / "composition" / "scripts" / "runtime.py"
INSTALL_PATH = ROOT / "skills" / "composition" / "scripts" / "install.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
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

    def test_boolean_transaction_schema_version_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            repository = Path(temporary)
            metadata = repository / ".template-composition"
            metadata.mkdir()
            (metadata / "transaction.json").write_text(
                json.dumps(
                    {
                        "schema_version": True,
                        "operation": "update",
                        "source": {
                            "repository": "TakashiSasaki/templates",
                            "revision": "1" * 40,
                        },
                    }
                ),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(runtime.RunnerError, "unsupported Composition transaction schema"):
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

    def test_sanitized_environment_removes_python_pip_and_git_inputs(self) -> None:
        result = runtime.sanitized_environment(
            {
                "PATH": "safe",
                "PYTHONPATH": "unsafe",
                "PIP_INDEX_URL": "https://example.invalid",
                "GIT_DIR": "/tmp/redirected-git-dir",
                "GIT_WORK_TREE": "/tmp/redirected-work-tree",
                "COMPOSITION_RUNTIME_CACHE": "/tmp/composition-cache",
                "OTHER": "value",
            }
        )
        self.assertEqual(result["PATH"], "safe")
        self.assertEqual(result["OTHER"], "value")
        self.assertEqual(result["COMPOSITION_RUNTIME_CACHE"], "/tmp/composition-cache")
        self.assertNotIn("PYTHONPATH", result)
        self.assertNotIn("PIP_INDEX_URL", result)
        self.assertNotIn("GIT_DIR", result)
        self.assertNotIn("GIT_WORK_TREE", result)
        self.assertEqual(result["PYTHONNOUSERSITE"], "1")
        self.assertEqual(result["PIP_CONFIG_FILE"], os.devnull)
        self.assertEqual(result["GIT_TERMINAL_PROMPT"], "0")
        self.assertEqual(result["GIT_CONFIG_NOSYSTEM"], "1")
        self.assertEqual(result["GIT_CONFIG_GLOBAL"], os.devnull)
        self.assertEqual(result["GIT_NO_REPLACE_OBJECTS"], "1")

    def test_cache_root_honors_explicit_override(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            expected = Path(temporary) / "cache"
            with mock.patch.dict(
                os.environ,
                {"COMPOSITION_RUNTIME_CACHE": str(expected)},
                clear=False,
            ):
                self.assertEqual(runtime.cache_root(), expected.resolve())

    def test_runtime_identity_binds_revision_lock_python_and_platform(self) -> None:
        revision = "1" * 40
        first = runtime.runtime_identity(revision, b"attrs===1\n")
        same = runtime.runtime_identity(revision, b"attrs===1\n")
        changed_lock = runtime.runtime_identity(revision, b"attrs===2\n")
        changed_revision = runtime.runtime_identity("2" * 40, b"attrs===1\n")
        self.assertEqual(first.digest(), same.digest())
        self.assertNotEqual(first.digest(), changed_lock.digest())
        self.assertNotEqual(first.digest(), changed_revision.digest())
        self.assertRegex(first.lock_sha256, r"^[0-9a-f]{64}$")
        self.assertEqual(first.python, runtime.python_token())
        self.assertEqual(first.platform, runtime.platform_token())

    def test_source_cache_rejects_shallow_grafts_and_replace_refs_before_git(self) -> None:
        revision = "1" * 40
        with tempfile.TemporaryDirectory() as temporary:
            for relative in (
                Path("shallow"),
                Path("info") / "grafts",
                Path("refs") / "replace",
            ):
                with self.subTest(relative=relative.as_posix()):
                    root = Path(temporary) / relative.as_posix().replace("/", "-")
                    entry = root / "entry"
                    checkout = entry / "checkout"
                    git_directory = checkout / ".git"
                    (checkout / "scripts").mkdir(parents=True)
                    git_directory.mkdir()
                    runtime.source_marker(entry).write_text(
                        json.dumps(runtime.source_marker_payload(revision)),
                        encoding="utf-8",
                    )
                    (checkout / "requirements-runtime.lock").write_text(
                        "attrs===1\n",
                        encoding="utf-8",
                    )
                    (checkout / "scripts" / "compose.py").write_text(
                        "",
                        encoding="utf-8",
                    )
                    (checkout / "scripts" / "verify_runtime_environment.py").write_text(
                        "",
                        encoding="utf-8",
                    )
                    forbidden = git_directory / relative
                    if relative.name == "replace":
                        forbidden.mkdir(parents=True)
                    else:
                        forbidden.parent.mkdir(parents=True, exist_ok=True)
                        forbidden.write_text("forbidden\n", encoding="utf-8")
                    self.assertFalse(runtime.source_valid(entry, revision, {}))

    def test_source_valid_rejects_dirty_worktree(self) -> None:
        revision = "1" * 40
        with tempfile.TemporaryDirectory() as temporary:
            entry = Path(temporary) / "entry"
            checkout = entry / "checkout"
            (checkout / ".git").mkdir(parents=True)
            (checkout / "scripts").mkdir()
            runtime.source_marker(entry).write_text(
                json.dumps(runtime.source_marker_payload(revision)),
                encoding="utf-8",
            )
            (checkout / "requirements-runtime.lock").write_text(
                "attrs===1\n",
                encoding="utf-8",
            )
            (checkout / "scripts" / "compose.py").write_text("", encoding="utf-8")
            (checkout / "scripts" / "verify_runtime_environment.py").write_text(
                "",
                encoding="utf-8",
            )
            outputs = iter(
                (
                    revision,
                    runtime.CANONICAL_REMOTE,
                    "false",
                    "lf",
                    "true",
                    "?? untracked.txt\n",
                    "1",
                )
            )

            def fake_run(*_args: object, **_kwargs: object):
                return subprocess.CompletedProcess([], 0, stdout=next(outputs), stderr="")

            with mock.patch.object(runtime, "run", side_effect=fake_run):
                self.assertFalse(runtime.source_valid(entry, revision, {}))

    def test_cache_install_reuses_valid_winner(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target"
            stage = root / "stage"
            target.mkdir()
            stage.mkdir()
            (target / "valid").write_text("winner", encoding="utf-8")
            (stage / "valid").write_text("stage", encoding="utf-8")
            result = runtime.install_cache_directory(
                stage,
                target,
                lambda candidate: (candidate / "valid").read_text(
                    encoding="utf-8"
                )
                == "winner",
            )
            self.assertEqual(result, target)
            self.assertFalse(stage.exists())
            self.assertEqual(
                (target / "valid").read_text(encoding="utf-8"),
                "winner",
            )

    def test_cache_install_replaces_invalid_entry(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target"
            stage = root / "stage"
            target.mkdir()
            stage.mkdir()
            (target / "state").write_text("invalid", encoding="utf-8")
            (stage / "state").write_text("valid", encoding="utf-8")
            result = runtime.install_cache_directory(
                stage,
                target,
                lambda candidate: candidate.is_dir()
                and (candidate / "state").is_file()
                and (candidate / "state").read_text(encoding="utf-8") == "valid",
            )
            self.assertEqual(result, target)
            self.assertFalse(stage.exists())
            self.assertEqual(
                (target / "state").read_text(encoding="utf-8"),
                "valid",
            )

    def test_runtime_lock_rejects_duplicate_normalized_names(self) -> None:
        with self.assertRaisesRegex(runtime.RunnerError, "duplicate distribution"):
            runtime.parse_runtime_lock("rpds_py===1.0\nrpds-py===1.0\n")

    def test_runtime_lock_rejects_invalid_syntax_with_line_number(self) -> None:
        for invalid in ("attrs>=24.0.0", "package-1.0", "===1.0"):
            with self.subTest(invalid=invalid):
                with self.assertRaisesRegex(
                    runtime.RunnerError,
                    r"requirements-runtime\.lock:2: entry must be exact name===version",
                ):
                    runtime.parse_runtime_lock(f"# header\n{invalid}\n")

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

    def test_install_replace_refuses_unclosed_frontmatter(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            target = Path(temporary) / "composition"
            target.mkdir()
            marker = target / "SKILL.md"
            malformed = "---\nname: composition\n"
            marker.write_text(malformed, encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    str(INSTALL_PATH),
                    str(target),
                    "--replace",
                ],
                check=False,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn(
                "refusing to replace a directory that is not this skill",
                result.stderr,
            )
            self.assertEqual(marker.read_text(encoding="utf-8"), malformed)

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
