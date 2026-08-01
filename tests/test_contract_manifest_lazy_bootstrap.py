from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


@unittest.skipUnless(hasattr(os, "mkfifo"), "requires POSIX FIFO support")
class LazyManifestBootstrapTests(unittest.TestCase):
    def test_manifest_symlink_is_rejected_before_implementation_import(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            shutil.copytree(ROOT / "scripts", root / "scripts")
            shutil.copytree(ROOT / "contracts", root / "contracts")
            shutil.copytree(ROOT / "schemas", root / "schemas")

            manifest = root / "contracts/manifest.json"
            fifo = root / "blocking-manifest"
            os.mkfifo(fifo)
            manifest.unlink()
            manifest.symlink_to(fifo)

            result = subprocess.run(
                [sys.executable, str(root / "scripts/validate_contracts.py")],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
                timeout=3,
            )

        self.assertEqual(1, result.returncode)
        self.assertIn(
            "contracts/manifest.json: manifest must not be a symbolic link",
            result.stderr,
        )


if __name__ == "__main__":
    unittest.main()
