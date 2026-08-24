from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from runtime import find_repository_root, runtime_command, sanitized_environment


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description=(
            "Run the repository-pinned agent-policy toolchain from the persistent "
            "runtime cache."
        )
    )
    value.add_argument("--repository", type=Path)
    value.add_argument("arguments", nargs=argparse.REMAINDER)
    return value


def main() -> int:
    args = parser().parse_args()
    try:
        repository = find_repository_root(args.repository)
        command = [
            *runtime_command(repository),
            "--repository",
            str(repository),
            *args.arguments,
        ]
        return subprocess.run(
            command,
            cwd=repository,
            env=sanitized_environment(),
            check=False,
        ).returncode
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"agent-policy skill error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
