from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "scripts" / "compose.py"
COMPONENT_SCRIPTS = ROOT / "components" / "artifact.webapp-core" / "files" / "scripts"
SCAFFOLD = COMPONENT_SCRIPTS / "scaffold_webapp_evidence.py"

if str(COMPONENT_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(COMPONENT_SCRIPTS))
SPEC = importlib.util.spec_from_file_location("webapp_evidence_scaffold", SCAFFOLD)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load Webapp evidence scaffold")
scaffold_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(scaffold_module)


class WebappEvidenceScaffoldOutputTests(unittest.TestCase):
    def run_python(
        self, cwd: Path, *arguments: str
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, *arguments],
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
        )

    def write_json(self, path: Path, value: object) -> None:
        path.write_text(json.dumps(value, indent=2) + "\n", encoding="utf-8")

    def materialize_webapp(self, root: Path) -> Path:
        target = root / "consumer"
        config = root / "composition.json"
        self.write_json(
            config,
            {
                "schema_version": 1,
                "recipe": "webapp",
                "components": {"include": [], "exclude": []},
                "parameters": {},
            },
        )
        result = self.run_python(
            ROOT,
            str(COMPOSER),
            "apply",
            "--config",
            str(config),
            "--target",
            str(target),
        )
        self.assertEqual(
            result.returncode,
            0,
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
        )
        return target

    def run_scaffold(
        self, target: Path, *arguments: str, cwd: Path | None = None
    ) -> subprocess.CompletedProcess[str]:
        return self.run_python(
            cwd or target,
            str(target / "scripts/scaffold_webapp_evidence.py"),
            str(target),
            *arguments,
        )

    def test_output_is_repository_relative_exclusive_and_non_destructive(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = self.materialize_webapp(root)
            canonical = target / "contracts/implementation-evidence.json"
            original = canonical.read_bytes()
            output_dir = target / "work"
            output_dir.mkdir()
            output = output_dir / "implementation-evidence-worklist.json"

            stdout_result = self.run_scaffold(target)
            file_result = self.run_scaffold(
                target,
                "--output",
                "work/implementation-evidence-worklist.json",
                cwd=ROOT,
            )

            self.assertEqual(stdout_result.returncode, 0, stdout_result.stderr)
            self.assertEqual(file_result.returncode, 0, file_result.stderr)
            self.assertEqual(file_result.stdout, "")
            self.assertEqual(output.read_text(encoding="utf-8"), stdout_result.stdout)
            self.assertEqual(canonical.read_bytes(), original)

            worksheet = (target / "TEMPLATE.md").read_text(encoding="utf-8")
            self.assertIn(
                "--output implementation-evidence-worklist.json",
                worksheet,
            )

            before = output.read_bytes()
            repeated = self.run_scaffold(
                target,
                "--output",
                "work/implementation-evidence-worklist.json",
                cwd=ROOT,
            )
            self.assertNotEqual(repeated.returncode, 0)
            self.assertIn("--output path already exists", repeated.stderr)
            self.assertEqual(output.read_bytes(), before)
            self.assertEqual(canonical.read_bytes(), original)

    def test_output_rejects_canonical_escape_and_missing_parent(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            target = self.materialize_webapp(root)
            canonical = target / "contracts/implementation-evidence.json"
            original = canonical.read_bytes()

            canonical_result = self.run_scaffold(
                target,
                "--output",
                "contracts/../contracts/implementation-evidence.json",
                cwd=ROOT,
            )
            self.assertNotEqual(canonical_result.returncode, 0)
            self.assertIn(
                "refuses the canonical implementation-evidence document",
                canonical_result.stderr,
            )
            self.assertEqual(canonical.read_bytes(), original)

            outside = root / "outside.json"
            escape_result = self.run_scaffold(
                target,
                "--output",
                "../outside.json",
                cwd=ROOT,
            )
            self.assertNotEqual(escape_result.returncode, 0)
            self.assertIn("must stay within the Webapp repository root", escape_result.stderr)
            self.assertFalse(outside.exists())

            missing_parent = self.run_scaffold(
                target,
                "--output",
                "missing/worklist.json",
                cwd=ROOT,
            )
            self.assertNotEqual(missing_parent.returncode, 0)
            self.assertIn("--output parent does not exist", missing_parent.stderr)
            self.assertFalse((target / "missing").exists())
            self.assertEqual(canonical.read_bytes(), original)

    def test_output_write_failure_removes_partial_file(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir).resolve()
            destination = root / "worklist.json"
            with mock.patch.object(
                scaffold_module.os,
                "fsync",
                side_effect=OSError("synthetic fsync failure"),
            ):
                with self.assertRaisesRegex(OSError, "synthetic fsync failure"):
                    scaffold_module.write_worklist(
                        root,
                        "worklist.json",
                        {"format": "test"},
                    )
            self.assertFalse(os.path.lexists(destination))


if __name__ == "__main__":
    unittest.main()
