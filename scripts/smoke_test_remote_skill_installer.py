#!/usr/bin/env python3
"""Smoke-test remote Composition skill download, archive safety, and installation."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
INSTALLER = ROOT / "scripts" / "install_composition_skill.py"
REQUIRED = (
    Path("SKILL.md"),
    Path("runtime-manifest.json"),
    Path("scripts/install.py"),
    Path("scripts/run.py"),
    Path("scripts/runtime.py"),
)


def run(command: list[str], *, capture_output: bool = False) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        check=True,
        text=True,
        capture_output=capture_output,
    )


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="composition-remote-installer-smoke-") as temporary:
        target = Path(temporary) / "composition"
        run([sys.executable, "-I", str(INSTALLER), str(target)])

        for relative in REQUIRED:
            path = target / relative
            if not path.is_file() or path.is_symlink():
                raise RuntimeError(f"remote installer did not materialize regular file: {relative}")

        manifest = json.loads((target / "runtime-manifest.json").read_text(encoding="utf-8"))
        revision = manifest.get("toolchain", {}).get("revision")
        if not isinstance(revision, str) or len(revision) != 40:
            raise RuntimeError("installed Composition skill has invalid runtime manifest revision")

        help_result = run(
            [sys.executable, "-I", str(target / "scripts" / "run.py"), "--help"],
            capture_output=True,
        )
        if "--repository" not in help_result.stdout:
            raise RuntimeError("installed Composition runner help is incomplete")

        run([sys.executable, "-I", str(INSTALLER), str(target), "--replace"])
        for relative in REQUIRED:
            if not (target / relative).is_file():
                raise RuntimeError(f"replacement lost required skill file: {relative}")

    print("Composition immutable remote installer smoke test passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
