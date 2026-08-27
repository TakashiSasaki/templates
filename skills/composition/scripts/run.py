from __future__ import annotations

import argparse
import json
import os
import shlex
import shutil
import sys
from pathlib import Path
from typing import Any

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from runtime import (
    CACHE_OVERRIDE,
    CANONICAL_REPOSITORY,
    FULL_SHA,
    RunnerError,
    cache_root,
    ensure_cache_parent,
    load_manifest,
    read_json_object,
    run_composer,
    runtime_cache_entry,
    runtime_identity,
    runtime_lock_data,
    runtime_valid,
    sanitized_environment,
    source_cache_entry,
    source_checkout,
    source_valid,
    stable_revision,
    transaction_revision,
    verify_host_python,
    venv_python,
)

COMPOSER_COMMANDS = ("inspect", "plan", "apply", "validate")
COMMANDS = ("provenance", "doctor", *COMPOSER_COMMANDS)
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
            "Inspect Composition provenance/runtime readiness or run the Composer "
            "from an immutable full-SHA source revision using an isolated transient runtime."
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


def _cache_probe(path: Path) -> dict[str, Any]:
    try:
        ensure_cache_parent(path)
    except RunnerError as exc:
        return {
            "status": "fail",
            "path": str(path),
            "diagnostic": str(exc),
        }
    return {
        "status": "pass",
        "path": str(path),
        "diagnostic": None,
    }


def _cache_entry_state(path: Path) -> str:
    if not path.exists() and not path.is_symlink():
        return "absent"
    return "present"


def _runner_command(
    repository: Path,
    command: str,
    explicit_revision: str | None,
) -> list[str]:
    argv = [
        sys.executable,
        "-I",
        str(Path(__file__).resolve()),
        "--repository",
        str(repository),
    ]
    if explicit_revision is not None:
        argv.extend(["--revision", explicit_revision])
    argv.append(command)
    return argv


def doctor_payload(
    repository: Path,
    explicit_revision: str | None = None,
) -> dict[str, Any]:
    """Inspect runner readiness without acquiring source/runtime caches or using network."""

    manifest = load_manifest()
    stable = stable_revision(manifest)
    selected, selected_authority, recovery = _selected_toolchain(
        repository,
        explicit_revision,
        manifest,
    )
    consumer = consumer_lock_source(repository)
    env = sanitized_environment()
    cache = cache_root()

    try:
        verify_host_python()
    except RunnerError as exc:
        host_python = {
            "status": "fail",
            "implementation": sys.implementation.name,
            "version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "executable": sys.executable,
            "supported": "CPython 3.11 through 3.14",
            "diagnostic": str(exc),
        }
    else:
        host_python = {
            "status": "pass",
            "implementation": sys.implementation.name,
            "version": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
            "executable": sys.executable,
            "supported": "CPython 3.11 through 3.14",
            "diagnostic": None,
        }

    git_executable = shutil.which("git")
    git = {
        "status": "pass" if git_executable is not None else "fail",
        "executable": git_executable,
        "diagnostic": (
            None
            if git_executable is not None
            else "Composition runner requires Git on PATH"
        ),
    }

    source_parent_probe = _cache_probe(cache / "sources")
    runtime_parent_probe = _cache_probe(cache / "runtimes")
    source_entry = source_cache_entry(cache, selected)
    source_state = _cache_entry_state(source_entry)
    source_reason: str | None = None
    source: Path | None = None
    if source_state == "present":
        if git_executable is None:
            source_state = "uncheckable"
            source_reason = "Git is unavailable, so cached source identity cannot be verified"
        elif source_valid(source_entry, selected, env):
            source_state = "valid"
            source = source_checkout(source_entry)
        else:
            source_state = "invalid"
            source_reason = "cached source does not satisfy immutable source-cache validation"

    runtime_state = "not-evaluable"
    runtime_reason: str | None = "runtime identity requires a valid selected source cache"
    runtime_entry: Path | None = None
    runtime_python: Path | None = None
    runtime_lock_blocker: str | None = None
    if source is not None:
        try:
            lock_data = runtime_lock_data(source, selected, manifest)
            identity = runtime_identity(selected, lock_data)
        except RunnerError as exc:
            runtime_state = "blocked"
            runtime_reason = str(exc)
            runtime_lock_blocker = f"selected source runtime lock is unusable: {exc}"
        else:
            runtime_entry = runtime_cache_entry(cache, identity)
            runtime_python = venv_python(runtime_entry)
            runtime_state = _cache_entry_state(runtime_entry)
            runtime_reason = None
            if runtime_state == "present":
                if runtime_valid(runtime_entry, identity, source, env):
                    runtime_state = "valid"
                else:
                    runtime_state = "invalid"
                    runtime_reason = (
                        "cached runtime does not satisfy the selected source/lock/Python/platform identity"
                    )

    source_acquisition_required = source_state != "valid"
    runtime_acquisition_required = runtime_state not in {"valid", "blocked"}
    local_blockers: list[str] = []
    if host_python["status"] != "pass":
        assert isinstance(host_python["diagnostic"], str)
        local_blockers.append(host_python["diagnostic"])
    if git["status"] != "pass":
        assert isinstance(git["diagnostic"], str)
        local_blockers.append(git["diagnostic"])
    if runtime_lock_blocker is not None:
        local_blockers.append(runtime_lock_blocker)
    if source_acquisition_required and source_parent_probe["status"] != "pass":
        assert isinstance(source_parent_probe["diagnostic"], str)
        local_blockers.append(source_parent_probe["diagnostic"])
    if runtime_acquisition_required and runtime_parent_probe["status"] != "pass":
        assert isinstance(runtime_parent_probe["diagnostic"], str)
        local_blockers.append(runtime_parent_probe["diagnostic"])

    cache_override = os.environ.get(CACHE_OVERRIDE)
    next_command = _runner_command(repository, "inspect", explicit_revision)
    validation_command = _runner_command(repository, "validate", explicit_revision)
    return {
        "schema_version": 1,
        "status": "blocked" if local_blockers else "ready",
        "repository": str(repository),
        "selected_toolchain": {
            "repository": CANONICAL_REPOSITORY,
            "revision": selected,
            "authority": selected_authority,
            "stable_revision": stable,
            "transaction_revision": recovery,
        },
        "consumer": {
            "managed": consumer is not None,
            "lock_source": consumer,
        },
        "checks": {
            "host_python": host_python,
            "git": git,
            "runner_cache": {
                "root": str(cache),
                "override": {
                    "name": CACHE_OVERRIDE,
                    "set": cache_override is not None,
                    "value": cache_override,
                },
                "source_parent_probe": source_parent_probe,
                "runtime_parent_probe": runtime_parent_probe,
                "probe_semantics": "transient write plus atomic rename; probe artifacts are removed",
            },
            "source_cache": {
                "status": source_state,
                "entry": str(source_entry),
                "diagnostic": source_reason,
            },
            "runtime_cache": {
                "status": runtime_state,
                "entry": str(runtime_entry) if runtime_entry is not None else None,
                "python": str(runtime_python) if runtime_python is not None else None,
                "diagnostic": runtime_reason,
            },
            "package_source": {
                "status": "not-probed",
                "network_requests": False,
                "diagnostic": (
                    "doctor does not contact the Git remote or package indexes; "
                    "a normal runner command acquires missing source/runtime state"
                ),
            },
        },
        "acquisition": {
            "source_required": source_acquisition_required,
            "runtime_required": runtime_acquisition_required,
            "network_guaranteed": False,
        },
        "blockers": local_blockers,
        "commands": {
            "next": {"name": "inspect", "argv": next_command},
            "validate": {"name": "validate", "argv": validation_command},
        },
    }


def _display_command(argv: list[str]) -> str:
    if os.name == "nt":
        import subprocess

        return subprocess.list2cmdline(argv)
    return shlex.join(argv)


def render_doctor_human(payload: dict[str, Any]) -> str:
    checks = payload["checks"]
    assert isinstance(checks, dict)
    toolchain = payload["selected_toolchain"]
    assert isinstance(toolchain, dict)
    acquisition = payload["acquisition"]
    assert isinstance(acquisition, dict)
    commands = payload["commands"]
    assert isinstance(commands, dict)
    lines = [
        f"Composition doctor: {str(payload['status']).upper()}",
        f"Repository: {payload['repository']}",
        (
            "Selected toolchain: "
            f"{toolchain['revision']} ({toolchain['authority']})"
        ),
    ]
    for label, key in (
        ("Host Python", "host_python"),
        ("Git", "git"),
        ("Source cache", "source_cache"),
        ("Runtime cache", "runtime_cache"),
    ):
        check = checks[key]
        assert isinstance(check, dict)
        detail = check.get("diagnostic")
        suffix = f" — {detail}" if detail else ""
        lines.append(f"{label}: {str(check['status']).upper()}{suffix}")
    runner_cache = checks["runner_cache"]
    assert isinstance(runner_cache, dict)
    source_probe = runner_cache["source_parent_probe"]
    runtime_probe = runner_cache["runtime_parent_probe"]
    assert isinstance(source_probe, dict) and isinstance(runtime_probe, dict)
    lines.append(f"Runner cache: {runner_cache['root']}")
    lines.append(
        "Cache write/rename probes: "
        f"sources={str(source_probe['status']).upper()}, "
        f"runtimes={str(runtime_probe['status']).upper()}"
    )
    lines.append(
        "Network/package source: NOT PROBED "
        "(doctor performs no remote or package-index requests)"
    )
    lines.append(
        "Acquisition required: "
        f"source={bool(acquisition['source_required'])}, "
        f"runtime={bool(acquisition['runtime_required'])}"
    )
    blockers = payload["blockers"]
    assert isinstance(blockers, list)
    if blockers:
        lines.append("Blockers:")
        lines.extend(f"  - {item}" for item in blockers)
    next_command = commands["next"]
    validation_command = commands["validate"]
    assert isinstance(next_command, dict) and isinstance(validation_command, dict)
    lines.append(f"Next command: {_display_command(next_command['argv'])}")
    lines.append(f"Validation command: {_display_command(validation_command['argv'])}")
    return "\n".join(lines)


def _doctor_format(arguments: list[str]) -> str:
    doctor_parser = argparse.ArgumentParser(prog="composition run.py doctor")
    doctor_parser.add_argument(
        "--format",
        choices=("human", "json"),
        default="human",
    )
    parsed = doctor_parser.parse_args(arguments)
    return parsed.format


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
        if args.command == "doctor":
            output_format = _doctor_format(list(args.arguments))
            payload = doctor_payload(repository, args.revision)
            if output_format == "json":
                print(json.dumps(payload, indent=2, sort_keys=True))
            else:
                print(render_doctor_human(payload))
            return 0 if payload["status"] == "ready" else 2
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
