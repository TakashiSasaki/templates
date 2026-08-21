from __future__ import annotations

import argparse
import sys
from pathlib import Path

from runtime import RunnerError, run_composer

COMMANDS = ("inspect", "plan", "apply", "validate")


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description=(
            "Run the Composition Composer from an immutable full-SHA source revision "
            "using an isolated transient runtime."
        )
    )
    value.add_argument(
        "--repository",
        required=True,
        type=Path,
        help="Consumer repository path; injected as the Composer --target.",
    )
    value.add_argument(
        "--revision",
        help=(
            "Advanced full-SHA source override. Managed recovery still requires the "
            "transaction-pinned revision."
        ),
    )
    value.add_argument("command", choices=COMMANDS)
    value.add_argument("arguments", nargs=argparse.REMAINDER)
    return value


def composer_arguments(command: str, arguments: list[str]) -> list[str]:
    for argument in arguments:
        if argument == "--target" or argument.startswith("--target="):
            raise RunnerError(
                "do not pass Composer --target through the runner; use --repository"
            )
    return [command, *arguments]


def main() -> int:
    args = parser().parse_args()
    repository = args.repository.expanduser().absolute()
    if repository.is_symlink():
        parser().error("consumer repository root must not be a symbolic link")
    try:
        arguments = composer_arguments(args.command, list(args.arguments))
        return run_composer(
            repository,
            arguments,
            explicit_revision=args.revision,
        )
    except RunnerError as exc:
        print(f"composition runner error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
