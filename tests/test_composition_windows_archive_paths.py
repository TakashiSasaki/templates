from __future__ import annotations

import importlib.util
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_PATH = ROOT / "skills" / "composition" / "scripts" / "runtime.py"
INSTALLER_PATH = ROOT / "scripts" / "install_composition_skill.py"


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


runtime = load_module("composition_windows_archive_runtime", RUNTIME_PATH)
installer = load_module("composition_windows_archive_installer", INSTALLER_PATH)


class CompositionWindowsArchivePathTests(unittest.TestCase):
    def test_console_device_names_are_never_portable_archive_components(self) -> None:
        for value in ("CONIN$", "conin$.txt", "CONOUT$", "conout$.log"):
            with self.subTest(value=value):
                self.assertFalse(runtime._portable_archive_part(value))
                self.assertFalse(installer._portable_archive_part(value))

    def test_dollar_sign_is_not_rejected_outside_console_device_names(self) -> None:
        for value in ("report$.txt", "normal.txt", "composite.txt", "lpt-report.txt"):
            with self.subTest(value=value):
                self.assertTrue(runtime._portable_archive_part(value))
                self.assertTrue(installer._portable_archive_part(value))


if __name__ == "__main__":
    unittest.main()
