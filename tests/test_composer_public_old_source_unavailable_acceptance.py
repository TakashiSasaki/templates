from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
COMPOSER = SCRIPTS / "compose.py"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import composer_core as core  # noqa: E402


class ComposerPublicOldSourceUnavailableAcceptanceTests(unittest.TestCase):
    def run_composer(self, *arguments: str) -> tuple[subprocess.CompletedProcess[str], dict]:
        result = subprocess.run(
            [sys.executable, str(COMPOSER), *arguments],
            cwd=ROOT,
            text=True,
            capture_output=True,
            check=False,
        )
        try:
            payload = json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            self.fail(f"composer did not emit JSON: {exc}\n{result.stdout}\n{result.stderr}")
        return result, payload

    def write_config(self, path: Path) -> None:
        path.write_text(
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

    def materialize_initial(self, root: Path) -> tuple[Path, Path]:
        config_path = root / "composition.json"
        self.write_config(config_path)
        target = root / "consumer"
        result, payload = self.run_composer(
            "apply",
            "--config",
            str(config_path),
            "--target",
            str(target),
        )
        self.assertEqual(result.returncode, 0, payload)
        return config_path, target

    def snapshot_files(self, target: Path) -> dict[str, bytes]:
        return {
            path.relative_to(target).as_posix(): path.read_bytes()
            for path in target.rglob("*")
            if path.is_file()
        }

    def assert_unavailable_source(self, result: subprocess.CompletedProcess[str], payload: dict) -> None:
        self.assertEqual(result.returncode, 2, payload)
        self.assertEqual(payload["code"], "OLD_SOURCE_REVISION_UNAVAILABLE")
        self.assertIn("Make that locked revision available", payload["message"])
        self.assertIn("do not bypass the ancestry check", payload["message"])

    def test_public_managed_plan_and_apply_fail_closed_when_locked_source_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path, target = self.materialize_initial(root)
            unavailable_revision = "f" * 40
            probe = core._run_git(
                "cat-file",
                "-e",
                f"{unavailable_revision}^{{commit}}",
                allow_failure=True,
            )
            self.assertNotEqual(probe.returncode, 0)

            lock_path = target / core.LOCK_RELATIVE
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            lock["source"]["revision"] = unavailable_revision
            lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
            before = self.snapshot_files(target)
            marker_path = target / core.TRANSACTION_RELATIVE
            self.assertFalse(marker_path.exists())

            cases = (
                ("plan", "update", []),
                ("apply", "update", []),
                ("plan", "upgrade", ["--config", str(config_path)]),
                ("apply", "upgrade", ["--config", str(config_path)]),
            )
            for command, mode, extra in cases:
                with self.subTest(command=command, mode=mode):
                    result, payload = self.run_composer(
                        command,
                        "--mode",
                        mode,
                        *extra,
                        "--target",
                        str(target),
                    )
                    self.assert_unavailable_source(result, payload)
                    self.assertEqual(self.snapshot_files(target), before)
                    self.assertFalse(marker_path.exists())


if __name__ == "__main__":
    unittest.main()
