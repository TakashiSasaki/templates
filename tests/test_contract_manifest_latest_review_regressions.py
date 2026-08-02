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
sys.path.insert(0, str(ROOT / "scripts"))

import validate_contracts  # noqa: E402


@unittest.skipUnless(hasattr(os, "mkfifo"), "requires POSIX FIFO support")
class PublicLoaderPreflightTests(unittest.TestCase):
    def test_root_taking_loaders_preflight_the_caller_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            facade = root / "facade"
            alternate = root / "alternate"
            shutil.copytree(ROOT / "scripts", facade / "scripts")
            shutil.copytree(ROOT / "contracts", facade / "contracts")
            shutil.copytree(ROOT / "schemas", facade / "schemas")
            shutil.copytree(ROOT / "contracts", alternate / "contracts")
            shutil.copytree(ROOT / "schemas", alternate / "schemas")

            manifest = alternate / "contracts/manifest.json"
            fifo = alternate / "blocking-manifest"
            os.mkfifo(fifo)
            manifest.unlink()
            manifest.symlink_to(fifo)

            probe = root / "probe_loaders.py"
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

                    expected = (
                        "contracts/manifest.json: manifest must not be a symbolic link"
                    )
                    for name in (
                        "load_contract_manifest",
                        "load_contract_registry",
                        "load_contract_documents",
                    ):
                        loader = getattr(validate_contracts, name)
                        try:
                            loader(alternate)
                        except RuntimeError as exc:
                            if expected not in str(exc):
                                raise SystemExit(
                                    f"{name} returned the wrong diagnostic: {exc}"
                                )
                        else:
                            raise SystemExit(f"{name} bypassed caller-root preflight")
                        if "validate_contracts_impl" in sys.modules:
                            raise SystemExit(
                                f"implementation imported while calling {name}"
                            )
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

    def test_direct_import_ignores_import_protocol_dunders(self) -> None:
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

            probe = root / "probe_direct_import.py"
            probe.write_text(
                textwrap.dedent(
                    """
                    from __future__ import annotations

                    import json
                    import sys
                    from pathlib import Path

                    facade = Path(sys.argv[1])
                    alternate = Path(sys.argv[2])
                    sys.path.insert(0, str(facade / "scripts"))
                    from validate_contracts import (
                        validate_contract_manifest,
                        validate_repository,
                    )

                    expected = (
                        "contracts/manifest.json: manifest must not be a symbolic link"
                    )
                    repository_errors = validate_repository(alternate)
                    if expected not in repository_errors:
                        raise SystemExit(
                            f"missing repository diagnostic: {repository_errors}"
                        )
                    alternate_manifest = json.loads(
                        (alternate / "contracts/manifest.json").read_text(
                            encoding="utf-8"
                        )
                    )
                    manifest_errors = validate_contract_manifest(
                        alternate, alternate_manifest
                    )
                    if expected not in manifest_errors:
                        raise SystemExit(
                            f"missing manifest diagnostic: {manifest_errors}"
                        )
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


class CrossValidationMetadataTests(unittest.TestCase):
    def test_non_object_core_document_is_rejected_before_cross_validation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            shutil.copytree(ROOT / "contracts", root / "contracts")
            shutil.copytree(ROOT / "schemas", root / "schemas")

            (root / "contracts/surfaces.json").write_text("[]\n", encoding="utf-8")
            (root / "schemas/surfaces.schema.json").write_text(
                json.dumps(
                    {
                        "$schema": "https://json-schema.org/draft/2020-12/schema",
                        "type": "array",
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )

            errors = validate_contracts.validate_repository(root)

        self.assertIn(
            "contracts/surfaces.json: registered contract document must be a JSON "
            "object with $schema and schemaVersion metadata",
            errors,
        )


if __name__ == "__main__":
    unittest.main()
