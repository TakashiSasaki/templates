from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PATH = ROOT / "skills" / "composition" / "scripts" / "runtime.py"


def load_runtime():
    spec = importlib.util.spec_from_file_location("composition_runtime_cache_ux", RUNTIME_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runtime = load_runtime()


class CompositionRuntimeCacheUxTests(unittest.TestCase):
    def test_non_directory_cache_parent_reports_override(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            blocker = root / "not-a-directory"
            blocker.write_text("blocked\n", encoding="utf-8")

            with self.assertRaises(runtime.RunnerError) as raised:
                runtime.ensure_cache_parent(blocker / "sources")

            message = str(raised.exception)
            self.assertIn("not a directory", message.lower())
            self.assertIn("COMPOSITION_RUNTIME_CACHE", message)
            self.assertIn(str(blocker / "sources"), message)

    def test_cache_parent_preflight_executes_atomic_rename_and_cleans_probe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary) / "cache" / "sources"
            original_rename = Path.rename
            renames: list[tuple[Path, Path]] = []

            def rename_spy(source: Path, target: Path) -> Path:
                renames.append((source, target))
                return original_rename(source, target)

            with mock.patch.object(Path, "rename", rename_spy):
                runtime.ensure_cache_parent(parent)

            self.assertTrue(parent.is_dir())
            self.assertEqual(list(parent.iterdir()), [])
            self.assertEqual(len(renames), 1)
            source, target = renames[0]
            self.assertTrue(source.name.startswith(".composition-write-probe-"))
            self.assertEqual(target.name, f"{source.name}.renamed")
            self.assertEqual(source.parent, parent)
            self.assertEqual(target.parent, parent)

    def test_cache_parent_preflight_cleans_probe_on_rename_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary) / "cache" / "sources"
            with mock.patch.object(Path, "rename", side_effect=OSError("rename failed")):
                with self.assertRaises(runtime.RunnerError) as raised:
                    runtime.ensure_cache_parent(parent)

            self.assertIn("COMPOSITION_RUNTIME_CACHE", str(raised.exception))
            self.assertTrue(parent.is_dir())
            self.assertEqual(list(parent.iterdir()), [])

    def test_stage_creation_failure_is_normalized_for_source_and_runtime_builds(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_target = root / "sources" / ("1" * 40)
            runtime_target = root / "runtimes" / ("2" * 64)
            identity = runtime.RuntimeIdentity(
                repository=runtime.CANONICAL_REPOSITORY,
                revision="1" * 40,
                lock_sha256="2" * 64,
                python=runtime.python_token(),
                platform=runtime.platform_token(),
            )

            for operation in (
                lambda: runtime.build_source_cache(source_target, "1" * 40, {}),
                lambda: runtime.build_runtime_cache(
                    runtime_target,
                    identity,
                    root / "source",
                    b"jsonschema===4.26.0\n",
                    {},
                ),
            ):
                with self.subTest(operation=operation):
                    with (
                        mock.patch.object(runtime, "ensure_cache_parent"),
                        mock.patch.object(
                            runtime.tempfile,
                            "mkdtemp",
                            side_effect=OSError("disk full"),
                        ),
                    ):
                        with self.assertRaises(runtime.RunnerError) as raised:
                            operation()
                    self.assertIn("COMPOSITION_RUNTIME_CACHE", str(raised.exception))
                    self.assertIn("disk full", str(raised.exception))

    def test_warm_cache_hits_bypass_cache_parent_preflight(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            revision = "1" * 40
            source_target = runtime.source_cache_entry(root, revision)

            with (
                mock.patch.object(runtime.shutil, "which", return_value="git"),
                mock.patch.object(runtime, "source_valid", return_value=True),
                mock.patch.object(
                    runtime,
                    "ensure_cache_parent",
                    side_effect=AssertionError("warm source hit must not preflight"),
                ),
            ):
                self.assertEqual(
                    runtime.ensure_source_cache(revision, root, {}),
                    runtime.source_checkout(source_target),
                )

            source = root / "cached-source"
            source.mkdir()
            (source / "requirements-runtime.lock").write_text(
                "jsonschema===4.26.0\n",
                encoding="utf-8",
            )
            manifest = {
                "toolchain": {
                    "repository": runtime.CANONICAL_REPOSITORY,
                    "revision": "2" * 40,
                }
            }
            identity = runtime.runtime_identity(
                revision,
                b"jsonschema===4.26.0\n",
            )
            runtime_target = runtime.runtime_cache_entry(root, identity)
            with (
                mock.patch.object(runtime, "runtime_valid", return_value=True),
                mock.patch.object(
                    runtime,
                    "ensure_cache_parent",
                    side_effect=AssertionError("warm runtime hit must not preflight"),
                ),
            ):
                self.assertEqual(
                    runtime.ensure_runtime_cache(source, revision, manifest, root, {}),
                    runtime.venv_python(runtime_target),
                )

    def test_runtime_install_disables_pip_download_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            (source / "scripts").mkdir(parents=True)
            target = root / "cache" / "runtimes" / "runtime"
            identity = runtime.RuntimeIdentity(
                repository=runtime.CANONICAL_REPOSITORY,
                revision="1" * 40,
                lock_sha256="2" * 64,
                python=runtime.python_token(),
                platform=runtime.platform_token(),
            )
            commands: list[list[str]] = []

            def fake_run(command, **_kwargs):
                value = list(command)
                commands.append(value)
                return subprocess.CompletedProcess(value, 0, stdout="", stderr="")

            with (
                mock.patch.object(runtime, "run", side_effect=fake_run),
                mock.patch.object(runtime, "runtime_valid", return_value=True),
            ):
                runtime.build_runtime_cache(
                    target,
                    identity,
                    source,
                    b"jsonschema===4.26.0\n",
                    {},
                )

            installs = [
                command
                for command in commands
                if len(command) >= 5
                and command[2:5] == ["-m", "pip", "install"]
            ]
            self.assertEqual(len(installs), 1, commands)
            self.assertIn("--no-cache-dir", installs[0])
            self.assertIn("--isolated", installs[0])
            self.assertIn("--no-deps", installs[0])


if __name__ == "__main__":
    unittest.main()
