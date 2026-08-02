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
class RepositoryFacadePreflightTests(unittest.TestCase):
    def test_repository_validator_preflights_facade_root_before_import(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            facade = root / "facade"
            alternate = root / "alternate"
            shutil.copytree(ROOT / "scripts", facade / "scripts")
            shutil.copytree(ROOT / "contracts", facade / "contracts")
            shutil.copytree(ROOT / "schemas", facade / "schemas")
            shutil.copytree(ROOT / "contracts", alternate / "contracts")
            shutil.copytree(ROOT / "schemas", alternate / "schemas")

            manifest = facade / "contracts/manifest.json"
            fifo = facade / "blocking-manifest"
            os.mkfifo(fifo)
            manifest.unlink()
            manifest.symlink_to(fifo)

            probe = root / "probe_repository_validator.py"
            probe.write_text(
                textwrap.dedent(
                    """
                    from __future__ import annotations

                    import sys
                    from pathlib import Path

                    facade = Path(sys.argv[1])
                    alternate = Path(sys.argv[2])
                    sys.path.insert(0, str(facade / "scripts"))
                    import validate_contracts

                    errors = validate_contracts.validate_repository(alternate)
                    expected = (
                        "contracts/manifest.json: manifest must not be a symbolic link"
                    )
                    if expected not in errors:
                        raise SystemExit(f"missing facade diagnostic: {errors}")
                    if "validate_contracts_impl" in sys.modules:
                        raise SystemExit("implementation imported before facade preflight")
                    """
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(probe), str(facade), str(alternate)],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
                timeout=3,
            )

        self.assertEqual(0, result.returncode, result.stderr)


if __name__ == "__main__":
    unittest.main()
