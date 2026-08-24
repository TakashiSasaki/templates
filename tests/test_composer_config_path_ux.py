from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "scripts" / "compose.py"
GUIDE = ROOT / "docs" / "consumer-guide.md"
JAPANESE_GUIDE = ROOT / "translations" / "ja" / "docs" / "consumer-guide.md"


class ComposerConfigPathUxTests(unittest.TestCase):
    def write_config(self, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
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

    def run_plan(
        self,
        cwd: Path,
        config_argument: str,
        target: Path,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(COMPOSER),
                "plan",
                "--config",
                config_argument,
                "--target",
                str(target),
            ],
            cwd=cwd,
            text=True,
            capture_output=True,
            check=False,
        )

    def test_relative_config_is_resolved_from_invocation_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            invocation_cwd = root / "invocation"
            invocation_cwd.mkdir()
            config = invocation_cwd / "configs" / "composition.json"
            self.write_config(config)
            target = root / "consumer"

            result = self.run_plan(
                invocation_cwd,
                "configs/composition.json",
                target,
            )
            self.assertEqual(
                result.returncode,
                0,
                f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}",
            )
            payload = json.loads(result.stdout)
            self.assertEqual(payload["operation"], "initial")
            self.assertFalse(target.exists(), "plan must remain read-only")

            other_cwd = root / "other"
            other_cwd.mkdir()
            missing = self.run_plan(
                other_cwd,
                "configs/composition.json",
                target,
            )
            self.assertEqual(missing.returncode, 2)
            missing_payload = json.loads(missing.stdout)
            self.assertEqual(missing_payload["code"], "READ_FAILED")
            self.assertIn(
                str(other_cwd / "configs" / "composition.json"),
                missing_payload["message"],
            )

    def test_consumer_guides_state_cwd_rule_and_absolute_example(self) -> None:
        guide = GUIDE.read_text(encoding="utf-8")
        self.assertIn(
            "A relative `--config` path is resolved from the process current working directory",
            guide,
        )
        self.assertIn("not from `--repository`", guide)
        self.assertIn(
            "plan --config /path/to/repository/composition.json",
            guide,
        )
        self.assertIn(
            "The same path rule applies to every initial or new-upgrade command",
            guide,
        )

        japanese = JAPANESE_GUIDE.read_text(encoding="utf-8")
        self.assertIn(
            "relative な `--config` path は `--repository` を基準にせず",
            japanese,
        )
        self.assertIn("current working directory", japanese)
        self.assertIn(
            "plan --config /path/to/repository/composition.json",
            japanese,
        )


if __name__ == "__main__":
    unittest.main()
