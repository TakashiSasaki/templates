from __future__ import annotations

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
RUNNER_PATH = ROOT / "skills" / "composition" / "scripts" / "run.py"


def load_runner():
    spec = importlib.util.spec_from_file_location(
        "composition_runtime_doctor_runner", RUNNER_PATH
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


runner = load_runner()


def offline_environment(cache: Path) -> dict[str, str]:
    environment = dict(os.environ)
    environment["COMPOSITION_RUNTIME_CACHE"] = str(cache)
    blocked = "http://127.0.0.1:9"
    for name in (
        "HTTP_PROXY",
        "HTTPS_PROXY",
        "ALL_PROXY",
        "http_proxy",
        "https_proxy",
        "all_proxy",
    ):
        environment[name] = blocked
    environment["NO_PROXY"] = ""
    environment["no_proxy"] = ""
    return environment


class CompositionRuntimeDoctorTests(unittest.TestCase):
    def test_json_doctor_is_offline_and_does_not_acquire_cache_entries(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = root / "consumer"
            cache = root / "cache"
            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    str(RUNNER_PATH),
                    "--repository",
                    str(repository),
                    "doctor",
                    "--format",
                    "json",
                ],
                env=offline_environment(cache),
                check=False,
                text=True,
                capture_output=True,
            )
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            payload = json.loads(result.stdout)

            self.assertEqual(payload["schema_version"], 1)
            self.assertEqual(payload["status"], "ready")
            self.assertEqual(payload["checks"]["host_python"]["status"], "pass")
            self.assertEqual(payload["checks"]["git"]["status"], "pass")
            self.assertEqual(payload["checks"]["source_cache"]["status"], "absent")
            self.assertEqual(
                payload["checks"]["runtime_cache"]["status"], "not-evaluable"
            )
            self.assertEqual(
                payload["checks"]["package_source"],
                {
                    "diagnostic": (
                        "doctor does not contact the Git remote or package indexes; "
                        "a normal runner command acquires missing source/runtime state"
                    ),
                    "network_requests": False,
                    "status": "not-probed",
                },
            )
            self.assertTrue(payload["acquisition"]["source_required"])
            self.assertTrue(payload["acquisition"]["runtime_required"])
            self.assertFalse(payload["acquisition"]["network_guaranteed"])
            self.assertEqual(payload["commands"]["next"]["name"], "inspect")
            self.assertEqual(payload["commands"]["validate"]["name"], "validate")
            self.assertIn("-I", payload["commands"]["next"]["argv"])
            self.assertEqual(payload["commands"]["next"]["argv"][-1], "inspect")
            self.assertEqual(payload["commands"]["validate"]["argv"][-1], "validate")

            self.assertTrue((cache / "sources").is_dir())
            self.assertTrue((cache / "runtimes").is_dir())
            self.assertEqual(list((cache / "sources").iterdir()), [])
            self.assertEqual(list((cache / "runtimes").iterdir()), [])

    def test_human_doctor_surfaces_next_and_validation_commands(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    str(RUNNER_PATH),
                    "--repository",
                    str(root / "consumer"),
                    "doctor",
                ],
                env=offline_environment(root / "cache"),
                check=False,
                text=True,
                capture_output=True,
            )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Composition doctor: READY", result.stdout)
        self.assertIn("Network/package source: NOT PROBED", result.stdout)
        self.assertIn("Next command:", result.stdout)
        self.assertIn(" inspect", result.stdout)
        self.assertIn("Validation command:", result.stdout)
        self.assertIn(" validate", result.stdout)

    def test_missing_cache_is_blocked_when_required_cache_parents_are_unusable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / "cache"
            diagnostic = "cache probe failed"
            with (
                mock.patch.object(runner, "cache_root", return_value=cache),
                mock.patch.object(runner.shutil, "which", return_value="/usr/bin/git"),
                mock.patch.object(
                    runner,
                    "ensure_cache_parent",
                    side_effect=runner.RunnerError(diagnostic),
                ),
            ):
                payload = runner.doctor_payload(Path(temporary) / "consumer")

        self.assertEqual(payload["status"], "blocked")
        self.assertTrue(payload["acquisition"]["source_required"])
        self.assertTrue(payload["acquisition"]["runtime_required"])
        self.assertEqual(payload["blockers"], [diagnostic, diagnostic])
        self.assertEqual(
            payload["checks"]["runner_cache"]["source_parent_probe"]["status"],
            "fail",
        )
        self.assertEqual(
            payload["checks"]["runner_cache"]["runtime_parent_probe"]["status"],
            "fail",
        )

    def test_warm_valid_cache_remains_ready_when_write_probe_fails(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            repository = root / "consumer"
            manifest = runner.load_manifest()
            selected = runner.stable_revision(manifest)
            source_entry = runner.source_cache_entry(cache, selected)
            source_entry.mkdir(parents=True)
            source = runner.source_checkout(source_entry)
            source.mkdir()
            lock_data = b"jsonschema===4.26.0\n"
            identity = runner.runtime_identity(selected, lock_data)
            runtime_entry = runner.runtime_cache_entry(cache, identity)
            runtime_entry.mkdir(parents=True)

            with (
                mock.patch.object(runner, "cache_root", return_value=cache),
                mock.patch.object(runner.shutil, "which", return_value="/usr/bin/git"),
                mock.patch.object(
                    runner,
                    "ensure_cache_parent",
                    side_effect=runner.RunnerError("cache read-only"),
                ),
                mock.patch.object(runner, "source_valid", return_value=True),
                mock.patch.object(runner, "runtime_lock_data", return_value=lock_data),
                mock.patch.object(runner, "runtime_valid", return_value=True),
            ):
                payload = runner.doctor_payload(repository)

        self.assertEqual(payload["status"], "ready")
        self.assertEqual(payload["checks"]["source_cache"]["status"], "valid")
        self.assertEqual(payload["checks"]["runtime_cache"]["status"], "valid")
        self.assertFalse(payload["acquisition"]["source_required"])
        self.assertFalse(payload["acquisition"]["runtime_required"])
        self.assertEqual(payload["blockers"], [])

    def test_invalid_selected_source_runtime_lock_is_a_blocker_not_acquisition(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            repository = root / "consumer"
            manifest = runner.load_manifest()
            selected = runner.stable_revision(manifest)
            source_entry = runner.source_cache_entry(cache, selected)
            source_entry.mkdir(parents=True)
            runner.source_checkout(source_entry).mkdir()
            diagnostic = "stable runtime lock digest mismatch"

            with (
                mock.patch.object(runner, "cache_root", return_value=cache),
                mock.patch.object(runner.shutil, "which", return_value="/usr/bin/git"),
                mock.patch.object(runner, "source_valid", return_value=True),
                mock.patch.object(
                    runner,
                    "runtime_lock_data",
                    side_effect=runner.RunnerError(diagnostic),
                ),
            ):
                payload = runner.doctor_payload(repository)

        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["checks"]["source_cache"]["status"], "valid")
        self.assertEqual(payload["checks"]["runtime_cache"]["status"], "blocked")
        self.assertEqual(payload["checks"]["runtime_cache"]["diagnostic"], diagnostic)
        self.assertFalse(payload["acquisition"]["source_required"])
        self.assertFalse(payload["acquisition"]["runtime_required"])
        self.assertEqual(
            payload["blockers"],
            [f"selected source runtime lock is unusable: {diagnostic}"],
        )

    def test_host_python_failure_is_reported_as_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / "cache"
            with (
                mock.patch.object(runner, "cache_root", return_value=cache),
                mock.patch.object(runner.shutil, "which", return_value="/usr/bin/git"),
                mock.patch.object(
                    runner,
                    "verify_host_python",
                    side_effect=runner.RunnerError("unsupported test Python"),
                ),
            ):
                payload = runner.doctor_payload(Path(temporary) / "consumer")

        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(payload["checks"]["host_python"]["status"], "fail")
        self.assertIn("unsupported test Python", payload["blockers"])

    def test_explicit_revision_is_preserved_in_recommended_commands(self) -> None:
        revision = "a" * 40
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / "cache"
            with (
                mock.patch.object(runner, "cache_root", return_value=cache),
                mock.patch.object(runner.shutil, "which", return_value="/usr/bin/git"),
            ):
                payload = runner.doctor_payload(
                    Path(temporary) / "consumer",
                    revision,
                )

        self.assertEqual(payload["selected_toolchain"]["revision"], revision)
        self.assertEqual(
            payload["selected_toolchain"]["authority"],
            "explicit_revision_argument",
        )
        for name in ("next", "validate"):
            argv = payload["commands"][name]["argv"]
            self.assertIn("--revision", argv)
            index = argv.index("--revision")
            self.assertEqual(argv[index + 1], revision)


if __name__ == "__main__":
    unittest.main()
