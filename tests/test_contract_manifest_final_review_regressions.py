from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import textwrap
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class FinalReviewRegressionTests(unittest.TestCase):
    @unittest.skipUnless(hasattr(os, "mkfifo"), "requires POSIX FIFO support")
    def test_external_bootstrap_reference_is_rejected_before_retrieval(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            repository = root / "repository"
            shutil.copytree(ROOT / "contracts", repository / "contracts")
            shutil.copytree(ROOT / "schemas", repository / "schemas")

            fifo = root / "blocking-reference"
            os.mkfifo(fifo)
            schema_path = repository / "schemas/contract-manifest.schema.json"
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            schema.setdefault("allOf", []).append({"$ref": fifo.as_uri()})
            schema_path.write_text(
                json.dumps(schema, indent=2) + "\n",
                encoding="utf-8",
            )

            probe = root / "probe_external_reference.py"
            probe.write_text(
                textwrap.dedent(
                    """
                    from __future__ import annotations

                    import sys
                    from pathlib import Path

                    repository = Path(sys.argv[1])
                    scripts = Path(sys.argv[2])
                    sys.path.insert(0, str(scripts))
                    import validate_contracts

                    errors = validate_contracts.validate_repository(repository)
                    expected = (
                        "schemas/contract-manifest.schema.json: external JSON "
                        "Schema reference is not allowed:"
                    )
                    if not any(error.startswith(expected) for error in errors):
                        raise SystemExit(f"missing external-reference diagnostic: {errors}")
                    """
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(probe), str(repository), str(ROOT / "scripts")],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
                timeout=3,
            )

        self.assertEqual(0, result.returncode, result.stderr)

    def test_top_level_import_uses_verified_sibling_implementation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            marker = root / "hijacked"
            (root / "validate_contracts_impl.py").write_text(
                "from pathlib import Path\n"
                f"Path({str(marker)!r}).write_text('executed', encoding='utf-8')\n"
                "raise RuntimeError('search-path implementation executed')\n",
                encoding="utf-8",
            )

            environment = os.environ.copy()
            existing_pythonpath = environment.get("PYTHONPATH")
            environment["PYTHONPATH"] = (
                str(ROOT / "scripts")
                if not existing_pythonpath
                else os.pathsep.join((str(ROOT / "scripts"), existing_pythonpath))
            )
            result = subprocess.run(
                [
                    sys.executable,
                    "-c",
                    (
                        "import validate_contracts; "
                        "print(validate_contracts.SCHEMA_DIALECT)"
                    ),
                ],
                cwd=root,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
                timeout=5,
            )
            marker_exists = marker.exists()

        self.assertEqual(0, result.returncode, result.stderr)
        self.assertIn(
            "https://json-schema.org/draft/2020-12/schema",
            result.stdout,
        )
        self.assertFalse(marker_exists)

    @unittest.skipUnless(hasattr(os, "symlink"), "requires symbolic-link support")
    def test_cyclic_ancestor_root_is_rejected_before_delegation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            loop = root / "loop"
            loop.symlink_to(loop)
            repository = loop / "repository"

            probe = root / "probe_cyclic_ancestor.py"
            probe.write_text(
                textwrap.dedent(
                    """
                    from __future__ import annotations

                    import sys
                    from pathlib import Path

                    repository = Path(sys.argv[1])
                    scripts = Path(sys.argv[2])
                    sys.path.insert(0, str(scripts))
                    import validate_contracts

                    errors = validate_contracts.validate_repository(repository)
                    expected = "repository root path cannot be resolved safely:"
                    if not any(error.startswith(expected) for error in errors):
                        raise SystemExit(f"missing root-resolution diagnostic: {errors}")
                    if "validate_contracts_impl" in sys.modules:
                        raise SystemExit("implementation imported before root preflight")
                    """
                ),
                encoding="utf-8",
            )

            result = subprocess.run(
                [sys.executable, str(probe), str(repository), str(ROOT / "scripts")],
                cwd=root,
                capture_output=True,
                text=True,
                check=False,
                timeout=3,
            )

        self.assertEqual(0, result.returncode, result.stderr)


if __name__ == "__main__":
    unittest.main()
