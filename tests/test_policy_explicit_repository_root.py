from __future__ import annotations

import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.dont_write_bytecode = True

ROOT = Path(__file__).resolve().parents[1]
POLICY_SCRIPTS = ROOT / "skills" / "agent-policy" / "scripts"
if str(POLICY_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(POLICY_SCRIPTS))
SPEC = importlib.util.spec_from_file_location(
    "policy_bootstrap_explicit_root", POLICY_SCRIPTS / "bootstrap.py"
)
if SPEC is None or SPEC.loader is None:
    raise RuntimeError("cannot load Policy bootstrap")
bootstrap = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = bootstrap
SPEC.loader.exec_module(bootstrap)

PATHS_SPEC = importlib.util.spec_from_file_location(
    "policy_paths_explicit_root", ROOT / "src" / "agent_policy" / "paths.py"
)
if PATHS_SPEC is None or PATHS_SPEC.loader is None:
    raise RuntimeError("cannot load Policy paths")
paths = importlib.util.module_from_spec(PATHS_SPEC)
sys.modules[PATHS_SPEC.name] = paths
PATHS_SPEC.loader.exec_module(paths)


class PolicyExplicitRepositoryRootTests(unittest.TestCase):
    def run_git_init(self, root: Path) -> None:
        result = subprocess.run(
            ["git", "-c", "init.defaultBranch=main", "init", str(root)],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_bootstrap_rejects_nested_path_in_parent_repository(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repository"
            nested = root / "nested"
            nested.mkdir(parents=True)
            self.run_git_init(root)

            self.assertEqual(bootstrap.repository_root(root), root.resolve())
            with self.assertRaisesRegex(ValueError, "parent repositories are not searched"):
                bootstrap.repository_root(nested)

    def test_managed_policy_path_resolution_rejects_explicit_nested_path(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repository"
            nested = root / "nested"
            (root / ".git").mkdir(parents=True)
            nested.mkdir()

            self.assertEqual(paths.find_repository_root(root), root.resolve())
            with self.assertRaisesRegex(FileNotFoundError, "parent repositories are not searched"):
                paths.find_repository_root(nested)

    def test_implicit_current_directory_lookup_still_walks_to_a_parent_root(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir) / "repository"
            nested = root / "nested"
            (root / ".git").mkdir(parents=True)
            nested.mkdir()

            self.assertEqual(paths.find_repository_root.__name__, "find_repository_root")
            original = Path.cwd()
            try:
                import os
                os.chdir(nested)
                self.assertEqual(paths.find_repository_root(), root.resolve())
            finally:
                os.chdir(original)


if __name__ == "__main__":
    unittest.main()
