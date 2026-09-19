from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import validate_component_versions as guard


def descriptor(*, component_id: str = "capability.demo", version: int = 1, summary: str = "demo") -> bytes:
    return (
        json.dumps(
            {
                "schema_version": 1,
                "id": component_id,
                "kind": "capability",
                "version": version,
                "summary": summary,
                "requires": [],
                "conflicts": [],
                "materials": [
                    {
                        "source": "files/demo.txt",
                        "destination": "demo.txt",
                        "ownership": "managed",
                    }
                ],
            },
            indent=2,
        )
        + "\n"
    ).encode("utf-8")


class ComponentVersionGuardUnitTests(unittest.TestCase):
    def test_unchanged_descriptor_allows_same_version(self) -> None:
        value = descriptor()
        guard.validate_descriptor_transition(value, value, path="components/capability.demo/component.json")

    def test_changed_descriptor_requires_strict_version_increase(self) -> None:
        old = descriptor(version=2, summary="old")
        for new_version in (1, 2):
            with self.subTest(new_version=new_version):
                with self.assertRaises(guard.ComponentVersionGuardError):
                    guard.validate_descriptor_transition(
                        old,
                        descriptor(version=new_version, summary="changed"),
                        path="components/capability.demo/component.json",
                    )

    def test_changed_descriptor_accepts_higher_version(self) -> None:
        guard.validate_descriptor_transition(
            descriptor(version=2, summary="old"),
            descriptor(version=5, summary="changed"),
            path="components/capability.demo/component.json",
        )

    def test_format_only_change_also_requires_version_increase(self) -> None:
        old = descriptor(version=1)
        semantically_same = json.dumps(json.loads(old), separators=(",", ":")).encode("utf-8")
        with self.assertRaises(guard.ComponentVersionGuardError):
            guard.validate_descriptor_transition(
                old,
                semantically_same,
                path="components/capability.demo/component.json",
            )

    def test_component_id_cannot_change_in_place(self) -> None:
        with self.assertRaises(guard.ComponentVersionGuardError):
            guard.validate_descriptor_transition(
                descriptor(component_id="capability.old", version=1),
                descriptor(component_id="capability.new", version=2),
                path="components/capability.demo/component.json",
            )


@unittest.skipUnless(shutil.which("git"), "git is required for repository guard integration tests")
class ComponentVersionGuardRepositoryTests(unittest.TestCase):
    def run_git(self, root: Path, *arguments: str) -> str:
        result = subprocess.run(
            ["git", "-C", str(root), *arguments],
            text=True,
            capture_output=True,
            check=False,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return result.stdout.strip()

    def test_repository_guard_compares_existing_descriptors_to_base_revision(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            component_root = root / "components" / "capability.demo"
            (component_root / "files").mkdir(parents=True)
            descriptor_path = component_root / "component.json"
            descriptor_path.write_bytes(descriptor(version=1, summary="old"))
            (component_root / "files" / "demo.txt").write_text("demo\n", encoding="utf-8")

            self.run_git(root, "init", "-b", "composition")
            self.run_git(root, "config", "user.email", "test@example.invalid")
            self.run_git(root, "config", "user.name", "Composition Tests")
            self.run_git(root, "add", ".")
            self.run_git(root, "commit", "-m", "base")
            base = self.run_git(root, "rev-parse", "HEAD")

            descriptor_path.write_bytes(descriptor(version=1, summary="changed"))
            with self.assertRaises(guard.ComponentVersionGuardError):
                guard.validate_repository(base, root=root)

            descriptor_path.write_bytes(descriptor(version=2, summary="changed"))
            self.assertEqual(guard.validate_repository(base, root=root), 1)

            new_component = root / "components" / "capability.new"
            (new_component / "files").mkdir(parents=True)
            (new_component / "component.json").write_bytes(
                descriptor(component_id="capability.new", version=7, summary="new")
            )
            (new_component / "files" / "demo.txt").write_text("new\n", encoding="utf-8")
            self.assertEqual(guard.validate_repository(base, root=root), 1)

    def test_base_only_retarget_accepts_only_unchanged_landed_base_tree(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            self.run_git(root, "init", "-b", "composition")
            self.run_git(root, "config", "user.email", "test@example.invalid")
            self.run_git(root, "config", "user.name", "Composition Tests")
            path = root / "components/demo/component.json"
            path.parent.mkdir(parents=True)
            path.write_bytes(descriptor())
            self.run_git(root, "add", ".")
            self.run_git(root, "commit", "-m", "authority")
            self.run_git(root, "checkout", "-b", "lower")
            (root / "index.md").write_text("# Root\n")
            self.run_git(root, "add", "index.md")
            self.run_git(root, "commit", "-m", "lower")
            self.run_git(root, "checkout", "-b", "upper")
            (root / "guide.md").write_text("# Guide\n")
            self.run_git(root, "add", "guide.md")
            self.run_git(root, "commit", "-m", "upper")
            self.run_git(root, "checkout", "composition")
            self.run_git(root, "merge", "--no-ff", "lower", "-m", "land lower")
            landed = self.run_git(root, "rev-parse", "HEAD")
            (root / "drift.md").write_text("# Unreviewed target drift\n")
            self.run_git(root, "add", "drift.md")
            self.run_git(root, "commit", "-m", "target drift")
            drift = self.run_git(root, "rev-parse", "HEAD")
            self.run_git(root, "checkout", "upper")
            self.assertEqual(guard.validate_repository(landed, root=root), 1)
            with self.assertRaises(guard.ComponentVersionGuardError):
                guard.validate_repository(drift, root=root)
            path.write_bytes(descriptor(summary="changed without version bump"))
            with self.assertRaises(guard.ComponentVersionGuardError):
                guard.validate_repository(landed, root=root)


if __name__ == "__main__":
    unittest.main()
