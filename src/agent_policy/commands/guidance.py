from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from ..paths import resolve_inside


def run(
    repository_root: Path,
    *,
    script: str,
    bundle: str | None,
    operation: str | None,
    rule_id: str | None,
    all_rules: bool,
    output_format: str,
) -> int:
    try:
        script_path = resolve_inside(repository_root, script, allow_missing=False)
        if not script_path.is_file() or script_path.suffix != ".py":
            raise ValueError("guidance script must be a regular Python file")
        command = [
            sys.executable,
            "-I",
            str(script_path),
            "--root",
            str(repository_root),
        ]
        if bundle is not None:
            command.append(f"--bundle={bundle}")
        if operation is not None:
            command.extend(["--operation", operation])
        if rule_id is not None:
            command.extend(["--rule-id", rule_id])
        if all_rules:
            command.append("--all")
        command.extend(["--format", output_format])
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)
        return subprocess.run(
            command,
            cwd=repository_root,
            env=environment,
            check=False,
        ).returncode
    except (OSError, ValueError) as exc:
        print(f"agent-policy guidance error: {exc}", file=sys.stderr)
        return 2
