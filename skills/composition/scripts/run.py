from __future__ import annotations

import os
import sys
from pathlib import Path
from typing import Any

import run_checkout as _impl
import runtime

# Preserve provenance, argument parsing, command routing, and presentation helpers.
for _name, _value in vars(_impl).items():
    if not _name.startswith("__"):
        globals()[_name] = _value


def doctor_payload(
    repository: Path,
    explicit_revision: str | None = None,
) -> dict[str, Any]:
    """Inspect Python/snapshot/runtime readiness without network acquisition.

    Normal consumer execution no longer requires a local Git executable or a
    persistent Composition source checkout. Doctor therefore validates only
    prerequisites that can block the immutable archive path before network use.
    """

    manifest = runtime.load_manifest()
    stable = runtime.stable_revision(manifest)
    selected, selected_authority, recovery = _impl._selected_toolchain(
        repository,
        explicit_revision,
        manifest,
    )
    consumer = _impl.consumer_lock_source(repository)
    cache = runtime.cache_root()

    try:
        runtime.verify_host_python()
    except runtime.RunnerError as exc:
        host_python = {
            "status": "fail",
            "implementation": sys.implementation.name,
            "version": (
                f"{sys.version_info.major}.{sys.version_info.minor}."
                f"{sys.version_info.micro}"
            ),
            "executable": sys.executable,
            "supported": "CPython 3.11 through 3.14",
            "diagnostic": str(exc),
        }
    else:
        host_python = {
            "status": "pass",
            "implementation": sys.implementation.name,
            "version": (
                f"{sys.version_info.major}.{sys.version_info.minor}."
                f"{sys.version_info.micro}"
            ),
            "executable": sys.executable,
            "supported": "CPython 3.11 through 3.14",
            "diagnostic": None,
        }

    runtime_parent_probe = _impl._cache_probe(cache / "runtimes")
    cache_override = os.environ.get(runtime.CACHE_OVERRIDE)
    local_blockers: list[str] = []
    if host_python["status"] != "pass":
        diagnostic = host_python["diagnostic"]
        assert isinstance(diagnostic, str)
        local_blockers.append(diagnostic)
    if runtime_parent_probe["status"] != "pass":
        diagnostic = runtime_parent_probe["diagnostic"]
        assert isinstance(diagnostic, str)
        local_blockers.append(diagnostic)

    runtime_state = "unknown-until-source-acquisition"
    runtime_reason = (
        "doctor does not download the selected runtime lock or source snapshot; "
        "normal execution validates any matching runtime cache before reuse"
    )
    if selected == stable:
        runtime_lock = manifest["runtime_lock"]
        assert isinstance(runtime_lock, dict)
        identity = runtime.RuntimeIdentity(
            repository=runtime.CANONICAL_REPOSITORY,
            revision=selected,
            lock_sha256=runtime_lock["sha256"],
            python=runtime.python_token(),
            platform=runtime.platform_token(),
        )
        entry = runtime.runtime_cache_entry(cache, identity)
        runtime_state = "present-unverified" if entry.is_dir() else "absent"
        runtime_entry = str(entry)
    else:
        runtime_entry = None

    next_command = _impl._runner_command(repository, "inspect", explicit_revision)
    validation_command = _impl._runner_command(
        repository,
        "validate",
        explicit_revision,
    )
    return {
        "schema_version": 1,
        "status": "blocked" if local_blockers else "ready",
        "repository": str(repository),
        "selected_toolchain": {
            "repository": runtime.CANONICAL_REPOSITORY,
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
            "git": {
                "status": "not-required",
                "executable": None,
                "diagnostic": (
                    "normal consumers acquire immutable full-SHA source archives "
                    "over HTTPS; Git is required only for authority-maintainer "
                    "reviewed-checkout execution"
                ),
            },
            "runner_cache": {
                "root": str(cache),
                "override": {
                    "name": runtime.CACHE_OVERRIDE,
                    "set": cache_override is not None,
                    "value": cache_override,
                },
                "source_parent_probe": {
                    "status": "not-required",
                    "path": None,
                    "diagnostic": (
                        "Composition source snapshots are ephemeral and are not "
                        "stored in the persistent runner cache"
                    ),
                },
                "runtime_parent_probe": runtime_parent_probe,
                "probe_semantics": (
                    "runtime cache uses a transient write plus atomic rename; "
                    "probe artifacts are removed"
                ),
            },
            "source_cache": {
                "status": "ephemeral",
                "entry": None,
                "diagnostic": (
                    "the selected full-SHA archive is extracted into an OS "
                    "temporary directory for each invocation and removed on exit"
                ),
            },
            "runtime_cache": {
                "status": runtime_state,
                "entry": runtime_entry,
                "python": None,
                "diagnostic": runtime_reason,
            },
            "package_source": {
                "status": "not-probed",
                "network_requests": False,
                "diagnostic": (
                    "doctor performs no GitHub or package-index requests; a normal "
                    "runner command acquires the immutable source archive and any "
                    "missing runtime distributions"
                ),
            },
        },
        "acquisition": {
            "source_required": True,
            "source_mode": "ephemeral-full-sha-archive",
            "runtime_required": runtime_state != "present-unverified",
            "runtime_mode": "persistent-validated-cache",
            "network_guaranteed": False,
        },
        "blockers": local_blockers,
        "commands": {
            "next": {"name": "inspect", "argv": next_command},
            "validate": {"name": "validate", "argv": validation_command},
        },
    }


def render_doctor_human(payload: dict[str, Any]) -> str:
    checks = payload["checks"]
    toolchain = payload["selected_toolchain"]
    acquisition = payload["acquisition"]
    commands = payload["commands"]
    assert isinstance(checks, dict)
    assert isinstance(toolchain, dict)
    assert isinstance(acquisition, dict)
    assert isinstance(commands, dict)
    host_python = checks["host_python"]
    git = checks["git"]
    source = checks["source_cache"]
    runtime_cache = checks["runtime_cache"]
    runner_cache = checks["runner_cache"]
    assert isinstance(host_python, dict)
    assert isinstance(git, dict)
    assert isinstance(source, dict)
    assert isinstance(runtime_cache, dict)
    assert isinstance(runner_cache, dict)
    runtime_probe = runner_cache["runtime_parent_probe"]
    assert isinstance(runtime_probe, dict)

    lines = [
        f"Composition doctor: {str(payload['status']).upper()}",
        f"Repository: {payload['repository']}",
        (
            "Selected toolchain: "
            f"{toolchain['revision']} ({toolchain['authority']})"
        ),
        f"Host Python: {str(host_python['status']).upper()}",
        "Git: NOT REQUIRED for normal consumer execution",
        f"Source acquisition: {source['status']} — {source['diagnostic']}",
        (
            "Runtime cache: "
            f"{runtime_cache['status']} — {runtime_cache['diagnostic']}"
        ),
        f"Runtime cache root: {runner_cache['root']}",
        f"Runtime write/rename probe: {str(runtime_probe['status']).upper()}",
        "Network/package source: NOT PROBED",
        (
            "Acquisition mode: source="
            f"{acquisition['source_mode']}, runtime={acquisition['runtime_mode']}"
        ),
    ]
    blockers = payload["blockers"]
    assert isinstance(blockers, list)
    if blockers:
        lines.append("Blockers:")
        lines.extend(f"  - {item}" for item in blockers)
    next_command = commands["next"]
    validation_command = commands["validate"]
    assert isinstance(next_command, dict)
    assert isinstance(validation_command, dict)
    lines.append(f"Next command: {_impl._display_command(next_command['argv'])}")
    lines.append(
        "Validation command: "
        f"{_impl._display_command(validation_command['argv'])}"
    )
    return "\n".join(lines)


_impl.doctor_payload = doctor_payload
_impl.render_doctor_human = render_doctor_human

globals()["doctor_payload"] = doctor_payload
globals()["render_doctor_human"] = render_doctor_human

if __name__ == "__main__":
    raise SystemExit(_impl.main())
