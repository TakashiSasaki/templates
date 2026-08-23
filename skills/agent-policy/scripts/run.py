from __future__ import annotations

import argparse
import subprocess
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


if __name__ == "__main__":
    raise SystemExit(main())
