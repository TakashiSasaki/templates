from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# The installed Skill tree can be deployment-attested trust material. Prevent
# importing sibling modules from creating __pycache__ entries inside that tree.
sys.dont_write_bytecode = True

from runtime import (  # noqa: E402
    CLI_MODULE,
    find_repository_root,
    runtime_command,
    sanitized_environment,
    venv_python,
)
from runtime_image import trusted_environment, verify_image  # noqa: E402


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description=(
            "Run the repository-pinned agent-policy toolchain from the persistent "
            "runtime cache or a deployment-frozen trusted-review runtime image."
        )
    )
    value.add_argument("--repository", type=Path)
    value.add_argument(
        "--trusted-review-runtime-image",
        type=Path,
        default=None,
        help=argparse.SUPPRESS,
    )
    value.add_argument(
        "--runtime-attestation",
        type=Path,
        default=None,
        help=argparse.SUPPRESS,
    )
    value.add_argument("arguments", nargs=argparse.REMAINDER)
    return value


def _trusted_snapshot(raw: Path | None) -> Path:
    if raw is None:
        raise ValueError("trusted review execution requires --repository")
    repository = raw.expanduser().absolute()
    current = Path(repository.anchor)
    for part in repository.parts[1:]:
        current = current / part
        if current.is_symlink():
            raise ValueError(
                f"trusted review snapshot path contains a symbolic-link component: {current}"
            )
    if repository.is_symlink() or not repository.is_dir():
        raise ValueError("trusted review repository must be a regular frozen snapshot")
    if (repository / ".git").exists() or (repository / ".git").is_symlink():
        raise ValueError("trusted review snapshot must not contain .git metadata")
    return repository


def _trusted_command(image: Path) -> list[str]:
    # -B is required even though the outer Skill also disables bytecode: the
    # managed interpreter is a distinct process executing from the frozen image.
    return [str(venv_python(image)), "-B", "-I", "-m", CLI_MODULE]


def _trusted_arguments(arguments: list[str]) -> list[str]:
    values = list(arguments)
    if values and values[0] == "--":
        values = values[1:]
    if not values or values[0] not in {"validate", "check"}:
        raise ValueError("trusted review execution permits only validate or check")
    forbidden = ("--repository", "--trusted-review-snapshot", "--format")
    for value in values[1:]:
        if any(value == option or value.startswith(f"{option}=") for option in forbidden):
            raise ValueError(
                f"trusted review command arguments must not override wrapper option: {value}"
            )
    return values


def main() -> int:
    args = parser().parse_args()
    try:
        trusted_mode = (
            args.trusted_review_runtime_image is not None
            or args.runtime_attestation is not None
        )
        if trusted_mode:
            if (
                args.trusted_review_runtime_image is None
                or args.runtime_attestation is None
            ):
                raise ValueError(
                    "trusted review runtime image and attestation must be supplied together"
                )
            repository = _trusted_snapshot(args.repository)
            image = args.trusted_review_runtime_image.expanduser().absolute()
            trusted_arguments = _trusted_arguments(args.arguments)
            verify_image(
                repository,
                args.runtime_attestation,
                image,
                execute_probe=True,
            )
            command = [
                *_trusted_command(image),
                "--repository",
                str(repository),
                "--trusted-review-snapshot",
                *trusted_arguments,
            ]
            environment = trusted_environment()
        else:
            repository = find_repository_root(args.repository)
            command = [
                *runtime_command(repository),
                "--repository",
                str(repository),
                *args.arguments,
            ]
            environment = sanitized_environment()
        result = subprocess.run(
            command,
            cwd=repository,
            env=environment,
            check=False,
        )
        if trusted_mode:
            # Execution must not mutate the frozen runtime image. Revalidate the
            # closed inventory after the managed process exits, regardless of its
            # semantic command result.
            verify_image(
                repository,
                args.runtime_attestation,
                image,
                execute_probe=False,
            )
        return result.returncode
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"agent-policy skill error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
