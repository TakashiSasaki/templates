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
    def test_unwritable_cache_parent_reports_override(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            blocker = root / "not-a-directory"
            blocker.write_text("blocked\n", encoding="utf-8")

            with self.assertRaises(runtime.RunnerError) as raised:
                runtime.ensure_cache_parent(blocker / "sources")

            message = str(raised.exception)
            self.assertIn("Composition runtime cache is not writable", message)
            self.assertIn("COMPOSITION_RUNTIME_CACHE", message)
            self.assertIn(str(blocker / "sources"), message)

    def test_cache_parent_preflight_cleans_probe(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            parent = Path(temporary) / "cache" / "sources"
            runtime.ensure_cache_parent(parent)
            self.assertTrue(parent.is_dir())
            self.assertEqual(list(parent.iterdir()), [])

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
