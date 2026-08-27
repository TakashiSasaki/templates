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
    def test_json_doctor_is_offline_and_reports_ephemeral_source(self) -> None:
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
            self.assertEqual(payload["checks"]["git"]["status"], "not-required")
            self.assertEqual(payload["checks"]["source_cache"]["status"], "ephemeral")
            self.assertEqual(
                payload["checks"]["package_source"]["status"], "not-probed"
            )
            self.assertFalse(payload["checks"]["package_source"]["network_requests"])
            self.assertTrue(payload["acquisition"]["source_required"])
            self.assertEqual(
                payload["acquisition"]["source_mode"],
                "ephemeral-full-sha-archive",
            )
            self.assertEqual(
                payload["acquisition"]["runtime_mode"],
                "persistent-validated-cache",
            )
            self.assertFalse(payload["acquisition"]["network_guaranteed"])
            self.assertEqual(payload["commands"]["next"]["name"], "inspect")
            self.assertEqual(payload["commands"]["validate"]["name"], "validate")

            self.assertFalse((cache / "sources").exists())
            self.assertTrue((cache / "runtimes").is_dir())
            self.assertEqual(list((cache / "runtimes").iterdir()), [])

    def test_human_doctor_surfaces_zero_clone_contract_and_commands(self) -> None:
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
        self.assertIn("Git: NOT REQUIRED for normal consumer execution", result.stdout)
        self.assertIn("ephemeral-full-sha-archive", result.stdout)
        self.assertIn("persistent-validated-cache", result.stdout)
        self.assertIn("Network/package source: NOT PROBED", result.stdout)
        self.assertIn("Next command:", result.stdout)
        self.assertIn("Validation command:", result.stdout)

    def test_unusable_runtime_cache_parent_blocks_doctor_but_source_needs_no_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache_file = root / "cache-file"
            cache_file.write_text("not a directory\n", encoding="utf-8")
            result = subprocess.run(
                [
                    sys.executable,
                    "-I",
                    str(RUNNER_PATH),
                    "--repository",
                    str(root / "consumer"),
                    "doctor",
                    "--format",
                    "json",
                ],
                env=offline_environment(cache_file),
                check=False,
                text=True,
                capture_output=True,
            )

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "blocked")
        self.assertEqual(
            payload["checks"]["runner_cache"]["source_parent_probe"]["status"],
            "not-required",
        )
        self.assertEqual(
            payload["checks"]["runner_cache"]["runtime_parent_probe"]["status"],
            "fail",
        )
        self.assertEqual(len(payload["blockers"]), 1)

    def test_host_python_failure_is_reported_as_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            cache = Path(temporary) / "cache"
            with (
                mock.patch.object(runner.runtime, "cache_root", return_value=cache),
                mock.patch.object(
                    runner.runtime,
                    "verify_host_python",
                    side_effect=runner.runtime.RunnerError("unsupported test Python"),
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
            with mock.patch.object(runner.runtime, "cache_root", return_value=cache):
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
