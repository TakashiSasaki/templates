from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
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

    def test_forwarded_attributes_run_preflight_before_implementation_import(self) -> None:
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

            probe = root / "probe_forwarded_attributes.py"
            probe.write_text(
                textwrap.dedent(
                    """
                    from __future__ import annotations

                    import sys
                    from pathlib import Path

                    sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
                    import validate_contracts

                    for name in ("load_json", "load_contract_documents", "SCHEMA_DIALECT"):
                        try:
                            getattr(validate_contracts, name)
                        except RuntimeError as exc:
                            print(f"{name}: {exc}", file=sys.stderr)
                        else:
                            raise SystemExit(f"{name} unexpectedly bypassed preflight")
                        if "validate_contracts_impl" in sys.modules:
                            raise SystemExit(
                                f"implementation imported while resolving {name}"
                            )
                    """
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(probe)],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
                timeout=3,
            )

        self.assertEqual(0, result.returncode, result.stderr)
        for name in ("load_json", "load_contract_documents", "SCHEMA_DIALECT"):
            self.assertIn(f"{name}: cannot load validator attribute", result.stderr)
        self.assertIn(
            "contracts/manifest.json: manifest must not be a symbolic link",
            result.stderr,
        )


if __name__ == "__main__":
    unittest.main()
