from __future__ import annotations

import importlib.util
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
RUN_PATH = ROOT / "skills" / "composition" / "scripts" / "run.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runner = load_module("composition_archive_doctor", RUN_PATH)


class CompositionArchiveDoctorTests(unittest.TestCase):
    def test_doctor_does_not_require_git_or_persistent_source_cache(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            repository = root / "consumer"
            cache = root / "cache"
            with (
                mock.patch.dict(
                    os.environ,
                    {"COMPOSITION_RUNTIME_CACHE": str(cache)},
                    clear=False,
                ),
                mock.patch("run_checkout.shutil.which", return_value=None),
            ):
                payload = runner.doctor_payload(repository)

            self.assertEqual(payload["status"], "ready")
            checks = payload["checks"]
            self.assertEqual(checks["git"]["status"], "not-required")
            self.assertEqual(checks["source_cache"]["status"], "ephemeral")
            self.assertEqual(
                payload["acquisition"]["source_mode"],
                "ephemeral-full-sha-archive",
            )
            self.assertEqual(
                payload["acquisition"]["runtime_mode"],
                "persistent-validated-cache",
            )
            self.assertFalse((cache / "sources").exists())
            self.assertTrue((cache / "runtimes").is_dir())

    def test_human_doctor_explains_git_is_not_required(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cache = root / "cache"
            with mock.patch.dict(
                os.environ,
                {"COMPOSITION_RUNTIME_CACHE": str(cache)},
                clear=False,
            ):
                payload = runner.doctor_payload(root / "consumer")
            rendered = runner.render_doctor_human(payload)
        self.assertIn("Git: NOT REQUIRED for normal consumer execution", rendered)
        self.assertIn("ephemeral-full-sha-archive", rendered)
        self.assertIn("persistent-validated-cache", rendered)


if __name__ == "__main__":
    unittest.main()
