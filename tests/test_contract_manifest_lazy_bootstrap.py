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


class WildcardExportTests(unittest.TestCase):
    def test_wildcard_import_preserves_public_validator_interface(self) -> None:
        probe = textwrap.dedent(
            """
            from __future__ import annotations

            import sys
            from pathlib import Path

            sys.path.insert(0, str(Path.cwd() / "scripts"))
            import validate_contracts

            expected = {
                "SCHEMA_DIALECT",
                "VISUALLY_BLANK_CHARACTERS",
                "CONTRACT_SCHEMAS",
                "DuplicateKeyError",
                "NonStandardJsonConstantError",
                "load_json",
                "load_contract_manifest",
                "validate_contract_manifest",
                "registry_from_manifest",
                "load_contract_registry",
                "load_contract_documents",
                "cross_validate",
                "validate_repository",
                "main",
            }
            if set(validate_contracts.__all__) != expected:
                raise SystemExit(
                    f"unexpected __all__: {sorted(validate_contracts.__all__)}"
                )

            namespace = {}
            exec("from validate_contracts import *", namespace)
            exported = set(namespace) - {"__builtins__"}
            if exported != expected:
                raise SystemExit(
                    f"wildcard export mismatch: expected={sorted(expected)}, "
                    f"actual={sorted(exported)}"
                )
            """
        )

        result = subprocess.run(
            [sys.executable, "-c", probe],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=3,
        )

        self.assertEqual(0, result.returncode, result.stderr)

    @unittest.skipUnless(hasattr(os, "symlink"), "requires symlink support")
    def test_manifest_validator_preflights_the_supplied_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            shutil.copytree(ROOT / "contracts", root / "contracts")
            shutil.copytree(ROOT / "schemas", root / "schemas")

            manifest = json.loads(
                (root / "contracts/manifest.json").read_text(encoding="utf-8")
            )
            document = root / "contracts/surfaces.json"
            document.unlink()
            document.symlink_to(document.name)

            probe = textwrap.dedent(
                """
                from __future__ import annotations

                import json
                import sys
                from pathlib import Path

                sys.path.insert(0, str(Path.cwd() / "scripts"))
                from validate_contracts import validate_contract_manifest

                root = Path(sys.argv[1])
                manifest = json.loads(
                    (root / "contracts/manifest.json").read_text(encoding="utf-8")
                )
                errors = validate_contract_manifest(root, manifest)
                expected = (
                    "contract manifest surfaces: document must not be a symbolic link: "
                    "contracts/surfaces.json"
                )
                if expected not in errors:
                    raise SystemExit(f"missing symlink diagnostic: {errors}")
                """
            )

            result = subprocess.run(
                [sys.executable, "-c", probe, str(root)],
                cwd=ROOT,
                capture_output=True,
                text=True,
                check=False,
                timeout=3,
            )

        self.assertEqual(0, result.returncode, result.stderr)


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

    def test_wildcard_import_runs_preflight_before_implementation_import(self) -> None:
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

            probe = root / "probe_wildcard_import.py"
            probe.write_text(
                textwrap.dedent(
                    """
                    from __future__ import annotations

                    import sys
                    from pathlib import Path

                    sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))
                    namespace = {}
                    try:
                        exec("from validate_contracts import *", namespace)
                    except RuntimeError as exc:
                        print(exc, file=sys.stderr)
                    else:
                        raise SystemExit("wildcard import unexpectedly bypassed preflight")
                    if "validate_contracts_impl" in sys.modules:
                        raise SystemExit("implementation imported during wildcard import")
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
        self.assertIn("cannot load validator attribute", result.stderr)
        self.assertIn(
            "contracts/manifest.json: manifest must not be a symbolic link",
            result.stderr,
        )


if __name__ == "__main__":
    unittest.main()
