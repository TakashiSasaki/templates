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
class NonRegularArtifactPreflightTests(unittest.TestCase):
    def copied_repository(self, target: Path) -> None:
        shutil.copytree(ROOT / "contracts", target / "contracts")
        shutil.copytree(ROOT / "schemas", target / "schemas")

    def run_probe(self, root: Path, source: str) -> subprocess.CompletedProcess[str]:
        probe = root.parent / "probe.py"
        probe.write_text(textwrap.dedent(source), encoding="utf-8")
        return subprocess.run(
            [sys.executable, str(probe), str(root), str(ROOT / "scripts")],
            cwd=root.parent,
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )

    def test_non_regular_bootstrap_schema_is_rejected_before_loading(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repository"
            self.copied_repository(root)
            schema_path = root / "schemas/contract-manifest.schema.json"
            schema_path.unlink()
            os.mkfifo(schema_path)

            result = self.run_probe(
                root,
                """
                from __future__ import annotations

                import sys
                from pathlib import Path

                repository = Path(sys.argv[1])
                scripts = Path(sys.argv[2])
                sys.path.insert(0, str(scripts))
                import validate_contracts

                expected = (
                    "schemas/contract-manifest.schema.json: bootstrap schema "
                    "must be a regular file"
                )
                errors = validate_contracts.validate_repository(repository)
                if expected not in errors:
                    raise SystemExit(f"missing bootstrap diagnostic: {errors}")
                if "validate_contracts_impl" in sys.modules:
                    raise SystemExit("implementation imported before bootstrap file check")
                """,
            )

        self.assertEqual(0, result.returncode, result.stderr)

    def test_non_regular_registered_document_is_rejected_before_loader_delegation(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory) / "repository"
            self.copied_repository(root)
            document_path = root / "contracts/surfaces.json"
            document_path.unlink()
            os.mkfifo(document_path)

            result = self.run_probe(
                root,
                """
                from __future__ import annotations

                import sys
                from pathlib import Path

                repository = Path(sys.argv[1])
                scripts = Path(sys.argv[2])
                sys.path.insert(0, str(scripts))
                import validate_contracts

                expected = (
                    "contract manifest surfaces: document must be a regular file: "
                    "contracts/surfaces.json"
                )
                errors = validate_contracts.validate_repository(repository)
                if expected not in errors:
                    raise SystemExit(f"missing document diagnostic: {errors}")
                try:
                    validate_contracts.load_contract_documents(repository)
                except RuntimeError as exc:
                    if expected not in str(exc):
                        raise SystemExit(f"wrong loader diagnostic: {exc}")
                else:
                    raise SystemExit("document loader opened a non-regular artifact")
                if "validate_contracts_impl" in sys.modules:
                    raise SystemExit("implementation imported before artifact file check")
                """,
            )

        self.assertEqual(0, result.returncode, result.stderr)


if __name__ == "__main__":
    unittest.main()
