from __future__ import annotations

import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
REGISTRY = (
    ROOT
    / "components"
    / "lifecycle.composition-state"
    / "files"
    / ".template-composition"
    / "validation-registry.json"
)
RUNNER = REGISTRY.with_name("validate.py")
RUNTIME_LOCK = ROOT / "requirements-runtime.lock"


def runtime_lock_entries() -> list[str]:
    return [
        line.strip()
        for line in RUNTIME_LOCK.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]


def load_runner():
    spec = importlib.util.spec_from_file_location("materialized_validation_runner", RUNNER)
    if spec is None or spec.loader is None:
        raise AssertionError("cannot load materialized validation runner")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class ValidationRuntimeContractTests(unittest.TestCase):
    def test_registry_runtime_exactly_matches_provider_runtime_lock(self) -> None:
        registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
        self.assertEqual(registry["schema_version"], 2)
        self.assertEqual(
            set(registry),
            {"schema_version", "runtime", "validators"},
        )
        self.assertEqual(
            registry["runtime"],
            {"requirements": runtime_lock_entries()},
        )

    def test_runner_parses_exact_runtime_and_validator_dispatch_together(self) -> None:
        runner = load_runner()
        lines, expected, validators = runner._load_registry(REGISTRY)
        self.assertEqual(lines, runtime_lock_entries())
        self.assertEqual(
            expected,
            {
                line.split("===", 1)[0].replace("_", "-").lower(): line.split("===", 1)[1]
                for line in runtime_lock_entries()
            },
        )
        self.assertTrue(validators)
        self.assertEqual(
            len({entry["id"] for entry in validators}),
            len(validators),
        )

    def test_validation_cache_has_one_explicit_override(self) -> None:
        runner = load_runner()
        with tempfile.TemporaryDirectory() as temp_dir:
            override = str(Path(temp_dir) / "validation-cache")
            with mock.patch.dict(
                os.environ,
                {"COMPOSITION_VALIDATION_CACHE": override},
                clear=False,
            ):
                self.assertEqual(
                    runner._validation_cache_root(),
                    Path(override).resolve(),
                )

    def test_validation_runtime_ignores_user_python_and_pip_settings(self) -> None:
        runner = load_runner()
        with mock.patch.dict(
            os.environ,
            {
                "PIP_CACHE_DIR": "/untrusted/pip-cache",
                "PIP_INDEX_URL": "https://example.invalid/simple",
                "PYTHONPATH": "/untrusted/pythonpath",
                "PATH": os.environ.get("PATH", ""),
            },
            clear=False,
        ):
            environment = runner._runtime_environment()
        self.assertNotIn("PIP_CACHE_DIR", environment)
        self.assertNotIn("PIP_INDEX_URL", environment)
        self.assertNotIn("PYTHONPATH", environment)
        self.assertEqual(environment["PYTHONNOUSERSITE"], "1")
        self.assertEqual(environment["PIP_CONFIG_FILE"], os.devnull)
        self.assertEqual(environment["PIP_DISABLE_PIP_VERSION_CHECK"], "1")

    def test_cache_error_points_to_the_single_override(self) -> None:
        runner = load_runner()
        error = runner._cache_error(Path("blocked"), PermissionError("denied"))
        message = str(error)
        self.assertIn("Composition validation cache is unusable", message)
        self.assertIn("COMPOSITION_VALIDATION_CACHE", message)
        self.assertIn("writable directory", message)


if __name__ == "__main__":
    unittest.main()
