from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from runtime import (
    CANONICAL_REPOSITORY,
    FULL_SHA,
    RunnerError,
    load_manifest,
    read_json_object,
    run_composer,
    stable_revision,
    transaction_revision,
)

COMPOSER_COMMANDS = ("inspect", "plan", "apply", "validate")
COMMANDS = ("provenance", *COMPOSER_COMMANDS)
INSTALLATION_RECEIPT_PATH = SCRIPT_DIR.parent / "installation-receipt.json"
LOCK_MEMBERS = {
    "schema_version",
    "source",
    "intent",
    "recipe_sha256",
    "configuration_sha256",
    "resolved_components",
    "files",
}


def parser() -> argparse.ArgumentParser:
    value = argparse.ArgumentParser(
        description=(
            "Inspect Composition provenance or run the Composer from an immutable "
            "full-SHA source revision using an isolated transient runtime."
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


def _source_identity(value: Any, label: str) -> dict[str, str]:
    if not isinstance(value, dict) or set(value) != {"repository", "revision"}:
        raise RunnerError(f"{label} source must contain repository and revision")
    repository = value["repository"]
    revision = value["revision"]
    if repository != CANONICAL_REPOSITORY:
        raise RunnerError(f"{label} source repository is unsupported")
    if not isinstance(revision, str) or FULL_SHA.fullmatch(revision) is None:
        raise RunnerError(f"{label} source revision must be a full lowercase SHA")
    return {"repository": repository, "revision": revision}


def load_installation_source(
    path: Path = INSTALLATION_RECEIPT_PATH,
) -> dict[str, str] | None:
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file():
        raise RunnerError("Composition installation receipt must be a regular file")
    value = read_json_object(path, "Composition installation receipt")
    if set(value) != {"schema_version", "source"}:
        raise RunnerError("Composition installation receipt has unsupported members")
    if type(value["schema_version"]) is not int or value["schema_version"] != 1:
        raise RunnerError("unsupported Composition installation receipt schema")
    return _source_identity(value["source"], "installation receipt")


def consumer_lock_source(repository: Path) -> dict[str, str] | None:
    metadata = repository / ".template-composition"
    if metadata.is_symlink():
        raise RunnerError("Composition metadata directory must not be a symbolic link")
    path = metadata / "lock.json"
    if not path.exists() and not path.is_symlink():
        return None
    if path.is_symlink() or not path.is_file():
        raise RunnerError("Composition lock metadata must be a regular file")
    value = read_json_object(path, "Composition lock")
    if set(value) != LOCK_MEMBERS:
        raise RunnerError("Composition lock has unsupported members")
    if type(value["schema_version"]) is not int or value["schema_version"] != 2:
        raise RunnerError("unsupported Composition lock schema")
    return _source_identity(value["source"], "Composition lock")


def _selected_toolchain(
    repository: Path,
    explicit_revision: str | None,
    manifest: dict[str, Any],
) -> tuple[str, str, str | None]:
    if explicit_revision is not None and FULL_SHA.fullmatch(explicit_revision) is None:
        raise RunnerError("--revision must be a full lowercase 40-character commit SHA")
    recovery = transaction_revision(repository)
    if recovery is not None:
        if explicit_revision is not None and explicit_revision != recovery:
            raise RunnerError(
                "managed recovery requires the exact transaction source revision "
                f"{recovery}; refusing explicit revision {explicit_revision}"
            )
        return recovery, "composition_transaction", recovery
    if explicit_revision is not None:
        return explicit_revision, "explicit_revision_argument", None
    return stable_revision(manifest), "runtime_manifest", None


def provenance_payload(
    repository: Path,
    explicit_revision: str | None = None,
) -> dict[str, Any]:
    manifest = load_manifest()
    stable = stable_revision(manifest)
    selected, selected_authority, recovery = _selected_toolchain(
        repository,
        explicit_revision,
        manifest,
    )
    installed = load_installation_source()
    consumer = consumer_lock_source(repository)
    runtime_lock = manifest["runtime_lock"]
    assert isinstance(runtime_lock, dict)

    skill_role: dict[str, Any] = {
        "authority": "installation_receipt",
        "status": "recorded" if installed is not None else "unrecorded",
        "source": installed,
    }
    transaction_role: dict[str, Any] = {
        "authority": "composition_transaction",
        "status": "present" if recovery is not None else "absent",
        "source": (
            {"repository": CANONICAL_REPOSITORY, "revision": recovery}
            if recovery is not None
            else None
        ),
    }
    consumer_role: dict[str, Any] = {
        "authority": "composition_lock",
        "status": "present" if consumer is not None else "absent",
        "source": consumer,
    }

    return {
        "schema_version": 1,
        "canonical_repository": CANONICAL_REPOSITORY,
        "roles": {
            "skill_source": skill_role,
            "stable_toolchain": {
                "authority": "runtime_manifest",
                "source": {
                    "repository": CANONICAL_REPOSITORY,
                    "revision": stable,
                },
                "runtime_lock": {
                    "path": runtime_lock["path"],
                    "sha256": runtime_lock["sha256"],
                },
            },
            "selected_toolchain": {
                "authority": selected_authority,
                "source": {
                    "repository": CANONICAL_REPOSITORY,
                    "revision": selected,
                },
            },
            "consumer_lock": consumer_role,
            "transaction": transaction_role,
        },
        "relationships": {
            "skill_source_may_differ_from_toolchain": True,
            "selected_matches_stable": selected == stable,
            "consumer_lock_matches_selected": (
                consumer["revision"] == selected if consumer is not None else None
            ),
        },
    }


def main() -> int:
    cli_parser = parser()
    args = cli_parser.parse_args()
    repository = args.repository.expanduser().absolute()
    if repository.is_symlink():
        cli_parser.error("consumer repository root must not be a symbolic link")
    try:
        if args.command == "provenance":
            if args.arguments:
                cli_parser.error("provenance does not accept Composer arguments")
            print(
                json.dumps(
                    provenance_payload(repository, args.revision),
                    indent=2,
                    sort_keys=True,
                )
            )
            return 0
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
