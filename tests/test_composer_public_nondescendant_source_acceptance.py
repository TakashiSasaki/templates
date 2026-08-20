from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
COMPOSER = ROOT / "scripts" / "compose.py"


class ComposerPublicNonDescendantSourceAcceptanceTests(unittest.TestCase):
    def run_git(
        self,
        *arguments: str,
        env: dict[str, str] | None = None,
        input_text: str | None = None,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            ["git", "-C", str(ROOT), *arguments],
            cwd=ROOT,
            text=True,
            input=input_text,
            capture_output=True,
            env=env,
            check=False,
        )

    def run_composer(
        self,
        *arguments: str,
        env: dict[str, str] | None = None,
    ) -> tuple[subprocess.CompletedProcess[str], dict]:
        result = subprocess.run(
            [sys.executable, str(COMPOSER), *arguments],
            cwd=ROOT,
            text=True,
            capture_output=True,
            env=env,
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

    def isolated_git_environment(self, root: Path) -> dict[str, str]:
        objects_result = self.run_git("rev-parse", "--git-path", "objects")
        self.assertEqual(objects_result.returncode, 0, objects_result.stderr)
        objects_path = Path(objects_result.stdout.strip())
        if not objects_path.is_absolute():
            objects_path = (ROOT / objects_path).resolve()

        isolated_objects = root / "git-objects"
        isolated_objects.mkdir()
        env = os.environ.copy()
        env["GIT_OBJECT_DIRECTORY"] = str(isolated_objects)
        alternates = [str(objects_path)]
        inherited_alternates = env.get("GIT_ALTERNATE_OBJECT_DIRECTORIES")
        if inherited_alternates:
            alternates.append(inherited_alternates)
        env["GIT_ALTERNATE_OBJECT_DIRECTORIES"] = os.pathsep.join(alternates)
        env.update(
            {
                "GIT_AUTHOR_NAME": "Composition Acceptance",
                "GIT_AUTHOR_EMAIL": "composition-acceptance@example.invalid",
                "GIT_AUTHOR_DATE": "2000-01-01T00:00:00+0000",
                "GIT_COMMITTER_NAME": "Composition Acceptance",
                "GIT_COMMITTER_EMAIL": "composition-acceptance@example.invalid",
                "GIT_COMMITTER_DATE": "2000-01-01T00:00:00+0000",
            }
        )
        return env

    def create_unrelated_commit(self, env: dict[str, str]) -> str:
        tree_result = self.run_git("rev-parse", "HEAD^{tree}", env=env)
        self.assertEqual(tree_result.returncode, 0, tree_result.stderr)
        synthetic = self.run_git(
            "commit-tree",
            tree_result.stdout.strip(),
            env=env,
            input_text="synthetic non-descendant Composition source\n",
        )
        self.assertEqual(synthetic.returncode, 0, synthetic.stderr)
        revision = synthetic.stdout.strip()
        self.assertEqual(len(revision), 40)
        self.assertTrue(all(character in "0123456789abcdef" for character in revision))

        current = self.run_git("rev-parse", "HEAD", env=env)
        self.assertEqual(current.returncode, 0, current.stderr)
        exists = self.run_git("cat-file", "-e", f"{revision}^{{commit}}", env=env)
        self.assertEqual(exists.returncode, 0, exists.stderr)
        ancestry = self.run_git(
            "merge-base",
            "--is-ancestor",
            revision,
            current.stdout.strip(),
            env=env,
        )
        self.assertEqual(ancestry.returncode, 1)
        return revision

    def snapshot_files(self, target: Path) -> dict[str, bytes]:
        return {
            path.relative_to(target).as_posix(): path.read_bytes()
            for path in target.rglob("*")
            if path.is_file()
        }

    def assert_non_descendant(self, result: subprocess.CompletedProcess[str], payload: dict) -> None:
        self.assertEqual(result.returncode, 2, payload)
        self.assertEqual(payload["code"], "SOURCE_REVISION_NOT_DESCENDANT")
        self.assertIn("descendant of it", payload["message"])
        self.assertIn("unrelated source history", payload["message"])

    def test_public_managed_plan_and_apply_reject_non_descendant_locked_source_without_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            config_path, target = self.materialize_initial(root)
            git_env = self.isolated_git_environment(root)
            unrelated_revision = self.create_unrelated_commit(git_env)

            lock_path = target / ".template-composition" / "lock.json"
            lock = json.loads(lock_path.read_text(encoding="utf-8"))
            lock["source"]["revision"] = unrelated_revision
            lock_path.write_text(json.dumps(lock, indent=2) + "\n", encoding="utf-8")
            before = self.snapshot_files(target)
            marker_path = target / ".template-composition" / "transaction.json"
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
                        env=git_env,
                    )
                    self.assert_non_descendant(result, payload)
                    self.assertEqual(self.snapshot_files(target), before)
                    self.assertFalse(marker_path.exists())


if __name__ == "__main__":
    unittest.main()
