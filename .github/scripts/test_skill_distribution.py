#!/usr/bin/env python3
"""Regression tests for the canonical Skill distribution manifest."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Callable

SOURCE_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = SOURCE_ROOT / ".github/scripts/validate_skill_distribution.py"


def run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        encoding="utf-8",
        capture_output=True,
        check=False,
    )


def run_validator(root: Path) -> subprocess.CompletedProcess[str]:
    return run([sys.executable, str(VALIDATOR), str(root)], cwd=root)


def copy_source(target: Path) -> None:
    target.mkdir(parents=True, exist_ok=True)
    for source in sorted(SOURCE_ROOT.iterdir(), key=lambda path: path.name):
        if source.name == ".git":
            continue
        destination = target / source.name
        if source.is_dir() and not source.is_symlink():
            shutil.copytree(source, destination, symlinks=True)
        else:
            shutil.copy2(source, destination, follow_symlinks=False)
    for command in (["git", "init", "--quiet"], ["git", "add", "."]):
        completed = run(command, cwd=target)
        if completed.returncode != 0:
            raise RuntimeError(f"{' '.join(command)} failed: {completed.stderr}")


def main() -> int:
    failures: list[str] = []
    manifest = json.loads(
        (SOURCE_ROOT / "distribution-manifest.json").read_text(encoding="utf-8")
    )
    required_policy_exclusions = [
        ".agent-policy",
        ".agent-policy.lock",
        ".agent-policy.yml",
        ".github/workflows/check-agent-policy.yml",
        "policy",
    ]
    missing_policy_exclusions = [
        path
        for path in required_policy_exclusions
        if path not in manifest["forbidden_distribution_paths"]
    ]
    if missing_policy_exclusions:
        failures.append(
            "source-maintainer policy paths must remain forbidden from template/: "
            f"{missing_policy_exclusions!r}"
        )
    if "AGENTS.md" not in manifest["distribution_files"]:
        failures.append("template/AGENTS.md must remain a canonical distribution file")
    if "mirrors" in manifest or "distribution_owned_files" in manifest:
        failures.append(
            "distribution manifest must not retain legacy mirror ownership fields"
        )
    if manifest.get("schema_version") != 2:
        failures.append("distribution manifest schema_version must be 2")

    completed = run_validator(SOURCE_ROOT)
    if not (
        completed.returncode == 0
        and not completed.stderr
        and "Skill template distribution is valid." in completed.stdout
    ):
        failures.append(
            "canonical distribution: "
            f"status={completed.returncode!r}, stdout={completed.stdout!r}, "
            f"stderr={completed.stderr!r}"
        )

    def expect_failure(
        label: str, expected: str, mutation: Callable[[Path], None]
    ) -> None:
        with tempfile.TemporaryDirectory(prefix="skill-distribution-negative") as temp:
            root = Path(temp)
            copy_source(root)
            mutation(root)
            run(["git", "add", "-A"], cwd=root)
            result = run_validator(root)
            if result.returncode == 0:
                failures.append(
                    f"{label}: validation unexpectedly succeeded: {result.stdout!r}"
                )
            if expected not in result.stderr:
                failures.append(
                    f"{label}: missing diagnostic {expected!r}: {result.stderr!r}"
                )

    expect_failure(
        "missing declared file",
        "declared files are missing",
        lambda root: (root / "template/SKILL.md").unlink(),
    )

    def omit_inventory(root: Path) -> None:
        path = root / "distribution-manifest.json"
        local_manifest = json.loads(path.read_text(encoding="utf-8"))
        local_manifest["distribution_files"].remove(
            ".github/scripts/validate_skill_repository.py"
        )
        path.write_text(
            json.dumps(local_manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    expect_failure(
        "canonical inventory omission", "undeclared files are present", omit_inventory
    )

    def reverse_inventory(root: Path) -> None:
        path = root / "distribution-manifest.json"
        local_manifest = json.loads(path.read_text(encoding="utf-8"))
        local_manifest["distribution_files"] = list(
            reversed(local_manifest["distribution_files"])
        )
        path.write_text(
            json.dumps(local_manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    expect_failure(
        "unsorted canonical inventory",
        "distribution manifest distribution_files: paths must be sorted",
        reverse_inventory,
    )

    expect_failure(
        "undeclared distribution file",
        "undeclared files are present",
        lambda root: (root / "template/UNDECLARED.txt").write_text(
            "unexpected\n", encoding="utf-8"
        ),
    )

    def add_symlink(root: Path) -> None:
        (root / "template/LINK.md").symlink_to("SKILL.md")

    expect_failure("symbolic link", "symbolic links are prohibited", add_symlink)

    def enable_transformation(root: Path) -> None:
        path = root / "distribution-manifest.json"
        local_manifest = json.loads(path.read_text(encoding="utf-8"))
        local_manifest["content_transformation_allowed"] = True
        path.write_text(
            json.dumps(local_manifest, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    expect_failure(
        "transformation enabled",
        "content transformation must remain disabled",
        enable_transformation,
    )

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1
    print("Skill template distribution tests passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
