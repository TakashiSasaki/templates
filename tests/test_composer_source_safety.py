from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSER_PATH = ROOT / "scripts" / "compose.py"


def load_composer_module():
    spec = importlib.util.spec_from_file_location("composition_compose_test_module", COMPOSER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load composer module")
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


class ComposerSourceSafetyTests(unittest.TestCase):
    def run_plan(self, config_path: Path, target: Path) -> tuple[subprocess.CompletedProcess, dict]:
        result = subprocess.run(
            [
                sys.executable,
                str(COMPOSER_PATH),
                "plan",
                "--config",
                str(config_path),
                "--target",
                str(target),
            ],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        return result, json.loads(result.stdout)

    @unittest.skipUnless(hasattr(os, "symlink"), "symlink support required")
    def test_plan_rejects_symlinked_parent_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path = root / "composition.json"
            config_path.write_text(
                json.dumps(
                    {
                        "schema_version": 1,
                        "recipe": "skill",
                        "components": {"include": [], "exclude": []},
                        "parameters": {},
                    },
                    indent=2,
                )
                + "\n",
                encoding="utf-8",
            )
            target = root / "consumer"
            target.mkdir()
            backing = root / "backing-docs"
            backing.mkdir()
            try:
                os.symlink(backing, target / "docs", target_is_directory=True)
            except OSError as exc:
                self.skipTest(f"cannot create directory symlink: {exc}")

            result, payload = self.run_plan(config_path, target)
            self.assertEqual(result.returncode, 2, result.stderr)
            self.assertTrue(
                any(
                    "planned parent path is existing symlink: docs" in conflict
                    for conflict in payload["conflicts"]
                ),
                payload,
            )

    def test_untracked_source_file_cannot_become_authority(self) -> None:
        module = load_composer_module()
        candidate = ROOT / ".composer-untracked-authority-test"
        try:
            candidate.write_text("untracked authority\n", encoding="utf-8")
            with self.assertRaises(module.CompositionError) as captured:
                module._assert_tracked_authority(candidate)
            self.assertEqual(captured.exception.code, "UNTRACKED_SOURCE_AUTHORITY")
        finally:
            try:
                candidate.unlink()
            except FileNotFoundError:
                pass


if __name__ == "__main__":
    unittest.main()
