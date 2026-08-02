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


class FragmentReferencePreflightTests(unittest.TestCase):
    @unittest.skipUnless(hasattr(os, "mkfifo"), "requires POSIX FIFO support")
    def test_local_pointer_target_is_scanned_before_external_retrieval(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            repository = root / "repository"
            shutil.copytree(ROOT / "contracts", repository / "contracts")
            shutil.copytree(ROOT / "schemas", repository / "schemas")

            fifo = root / "blocking-reference"
            os.mkfifo(fifo)
            schema_path = repository / "schemas/contract-manifest.schema.json"
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            schema["examples"] = [{"$ref": fifo.as_uri()}]
            schema.setdefault("allOf", []).append({"$ref": "#/examples/0"})
            schema_path.write_text(
                json.dumps(schema, indent=2) + "\n",
                encoding="utf-8",
            )

            probe = root / "probe_fragment_reference.py"
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
                        raise SystemExit(
                            f"missing fragment-target reference diagnostic: {errors}"
                        )
                    if "validate_contracts_impl" in sys.modules:
                        raise SystemExit(
                            "implementation imported before fragment-target preflight"
                        )
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

    @unittest.skipUnless(hasattr(os, "mkfifo"), "requires POSIX FIFO support")
    def test_pointer_target_preserves_nested_resource_root(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            repository = root / "repository"
            shutil.copytree(ROOT / "contracts", repository / "contracts")
            shutil.copytree(ROOT / "schemas", repository / "schemas")

            fifo = root / "nested-resource-blocking-reference"
            os.mkfifo(fifo)
            schema_path = repository / "schemas/contract-manifest.schema.json"
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            schema.setdefault("$defs", {})["embeddedResource"] = {
                "$id": "embedded-resource",
                "examples": [{"$ref": fifo.as_uri()}],
                "properties": {
                    "x": {"$ref": "#/examples/0"},
                },
            }
            schema.setdefault("allOf", []).append(
                {"$ref": "#/$defs/embeddedResource/properties/x"}
            )
            schema_path.write_text(
                json.dumps(schema, indent=2) + "\n",
                encoding="utf-8",
            )

            probe = root / "probe_nested_resource_reference.py"
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
                        raise SystemExit(
                            f"missing nested-resource reference diagnostic: {errors}"
                        )
                    if "validate_contracts_impl" in sys.modules:
                        raise SystemExit(
                            "implementation imported before nested-resource preflight"
                        )
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

    @unittest.skipUnless(hasattr(os, "mkfifo"), "requires POSIX FIFO support")
    def test_pointer_ignores_id_on_instance_valued_ancestor(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            repository = root / "repository"
            shutil.copytree(ROOT / "contracts", repository / "contracts")
            shutil.copytree(ROOT / "schemas", repository / "schemas")

            fifo = root / "instance-ancestor-blocking-reference"
            os.mkfifo(fifo)
            schema_path = repository / "schemas/contract-manifest.schema.json"
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            schema["danger"] = {"$ref": fifo.as_uri()}
            schema["examples"] = {
                "$id": "not-a-schema-resource",
                "target": {"$ref": "#/danger"},
            }
            schema.setdefault("allOf", []).append(
                {"$ref": "#/examples/target"}
            )
            schema_path.write_text(
                json.dumps(schema, indent=2) + "\n",
                encoding="utf-8",
            )

            probe = root / "probe_instance_ancestor_reference.py"
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
                        raise SystemExit(
                            f"instance ancestor changed the resource root: {errors}"
                        )
                    if "validate_contracts_impl" in sys.modules:
                        raise SystemExit(
                            "implementation imported before instance-ancestor preflight"
                        )
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

    def test_additional_items_is_not_a_draft_2020_12_applicator(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            repository = root / "repository"
            shutil.copytree(ROOT / "contracts", repository / "contracts")
            shutil.copytree(ROOT / "schemas", repository / "schemas")

            schema_path = repository / "schemas/contract-manifest.schema.json"
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            schema["additionalItems"] = {"$ref": "ignored-extension.json"}
            schema_path.write_text(
                json.dumps(schema, indent=2) + "\n",
                encoding="utf-8",
            )

            probe = root / "probe_removed_keyword.py"
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
                    if errors:
                        raise SystemExit(
                            f"additionalItems was treated as an active applicator: {errors}"
                        )
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

    def test_removed_legacy_keywords_are_not_traversed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            repository = root / "repository"
            shutil.copytree(ROOT / "contracts", repository / "contracts")
            shutil.copytree(ROOT / "schemas", repository / "schemas")

            schema_path = repository / "schemas/contract-manifest.schema.json"
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            schema["definitions"] = {
                "ignored": {"$ref": "ignored-definition-extension.json"}
            }
            schema["dependencies"] = {
                "ignored": {"$ref": "ignored-dependency-extension.json"}
            }
            schema_path.write_text(
                json.dumps(schema, indent=2) + "\n",
                encoding="utf-8",
            )

            probe = root / "probe_removed_legacy_keywords.py"
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
                    if errors:
                        raise SystemExit(
                            f"removed legacy keywords were traversed: {errors}"
                        )
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

    @unittest.skipUnless(hasattr(os, "mkfifo"), "requires POSIX FIFO support")
    def test_explicit_pointer_into_legacy_keyword_is_scanned(self) -> None:
        with tempfile.TemporaryDirectory() as temporary_directory:
            root = Path(temporary_directory)
            repository = root / "repository"
            shutil.copytree(ROOT / "contracts", repository / "contracts")
            shutil.copytree(ROOT / "schemas", repository / "schemas")

            fifo = root / "legacy-pointer-blocking-reference"
            os.mkfifo(fifo)
            schema_path = repository / "schemas/contract-manifest.schema.json"
            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            schema["definitions"] = {
                "target": {"$ref": fifo.as_uri()}
            }
            schema.setdefault("allOf", []).append(
                {"$ref": "#/definitions/target"}
            )
            schema_path.write_text(
                json.dumps(schema, indent=2) + "\n",
                encoding="utf-8",
            )

            probe = root / "probe_legacy_pointer_reference.py"
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
                        raise SystemExit(
                            f"explicit legacy pointer was not scanned: {errors}"
                        )
                    if "validate_contracts_impl" in sys.modules:
                        raise SystemExit(
                            "implementation imported before legacy-pointer preflight"
                        )
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
