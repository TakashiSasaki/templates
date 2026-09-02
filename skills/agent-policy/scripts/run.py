from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

# The installed Skill tree can be deployment-attested trust material. Prevent
# importing sibling modules from creating __pycache__ entries inside that tree.
sys.dont_write_bytecode = True

# These imports intentionally follow the bytecode-write guard because the modules
# are inside the deployment-attested Skill tree.
from runtime import (  # noqa: E402
    cli_command,
    find_repository_root,
    runtime_command,
    sanitized_environment,
)
from runtime_image import verify_image  # noqa: E402


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
    if repository.is_symlink() or not repository.is_dir():
        raise ValueError("trusted review repository must be a regular frozen snapshot")
    if (repository / ".git").exists() or (repository / ".git").is_symlink():
        raise ValueError("trusted review snapshot must not contain .git metadata")
    return repository


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
            verify_image(
                repository,
                args.runtime_attestation,
                image,
                execute_probe=True,
            )
            command = [
                *cli_command(image),
                "--repository",
                str(repository),
                "--trusted-review-snapshot",
                *args.arguments,
            ]
        else:
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
