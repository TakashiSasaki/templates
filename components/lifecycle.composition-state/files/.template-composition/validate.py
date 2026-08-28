#!/usr/bin/env python3
"""Run validators selected by the resolved Composition component set."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any

LOCK_RELATIVE = ".template-composition/lock.json"
STATE_VALIDATOR_RELATIVE = ".template-composition/validate_composition.py"
REGISTRY_RELATIVE = ".template-composition/validation-registry.json"
CHECKPOINT_ACTION_REGISTRY_RELATIVE = ".template-composition/lifecycle-checkpoint-actions.json"
RUNNER_RELATIVE = ".template-composition/validate.py"
COMPONENT_RE = re.compile(
    r"^(artifact|capability|lifecycle)\.[a-z][a-z0-9]*(?:-[a-z0-9]+)*$"
)
EXACT_REQUIREMENT = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9_.-]*===([A-Za-z0-9][A-Za-z0-9_.+!-]*)$"
)
SUPPORTED_MIN = (3, 11)
SUPPORTED_MAX_EXCLUSIVE = (3, 15)
CACHE_SCHEMA = 1
CACHE_OVERRIDE = "COMPOSITION_VALIDATION_CACHE"
BOOTSTRAP_DISTRIBUTIONS = frozenset({"pip", "setuptools", "wheel"})


class ValidationRegistryError(ValueError):
    pass


class ValidationRuntimeError(RuntimeError):
    pass


class StrictJsonError(ValueError):
    pass


def _object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise StrictJsonError(f"duplicate JSON object key {key!r}")
        result[key] = value
    return result


def _constant(value: str) -> Any:
    raise StrictJsonError(f"non-standard JSON numeric constant {value!r}")


def _load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(
            handle,
            object_pairs_hook=_object_pairs,
            parse_constant=_constant,
        )


def _portable_path(value: Any) -> str:
    if not isinstance(value, str) or not value or "\\" in value or value.startswith("/"):
        raise ValidationRegistryError(f"invalid portable repository path: {value!r}")
    if re.match(r"^[A-Za-z]:", value):
        raise ValidationRegistryError(f"invalid portable repository path: {value!r}")
    parts = value.split("/")
    if any(not part or part in {".", ".."} for part in parts):
        raise ValidationRegistryError(f"invalid portable repository path: {value!r}")
    return value


def _normalize_distribution_name(name: str) -> str:
    return re.sub(r"[-_.]+", "-", name).lower()


def _parse_runtime_requirements(value: Any) -> tuple[list[str], dict[str, str]]:
    if not isinstance(value, dict) or set(value) != {"requirements"}:
        raise ValidationRegistryError(
            "validation registry runtime must contain exactly requirements"
        )
    raw_requirements = value.get("requirements")
    if not isinstance(raw_requirements, list) or not raw_requirements:
        raise ValidationRegistryError(
            "validation registry runtime requirements must be a non-empty array"
        )
    rendered: list[str] = []
    parsed: dict[str, str] = {}
    for index, requirement in enumerate(raw_requirements):
        if not isinstance(requirement, str) or EXACT_REQUIREMENT.fullmatch(requirement) is None:
            raise ValidationRegistryError(
                f"validation runtime requirements[{index}] must be exact name===version"
            )
        name, version = requirement.split("===", 1)
        normalized = _normalize_distribution_name(name)
        if normalized in parsed:
            raise ValidationRegistryError(
                f"validation runtime contains duplicate distribution {name!r}"
            )
        parsed[normalized] = version
        rendered.append(requirement)
    return rendered, parsed


def _validate_when(value: Any, *, validator_id: str) -> dict[str, str] | None:
    if value is None:
        return None
    if not isinstance(value, dict) or set(value) != {
        "document",
        "field",
        "equals",
        "otherwise",
        "message",
    }:
        raise ValidationRegistryError(
            f"validator {validator_id}: when must contain exactly document, field, equals, otherwise, and message"
        )
    document = _portable_path(value.get("document"))
    field = value.get("field")
    expected = value.get("equals")
    otherwise = value.get("otherwise")
    message = value.get("message")
    if not isinstance(field, str) or not re.fullmatch(r"[A-Za-z][A-Za-z0-9_-]*", field):
        raise ValidationRegistryError(f"validator {validator_id}: invalid condition field")
    if not isinstance(expected, str) or not expected:
        raise ValidationRegistryError(
            f"validator {validator_id}: condition equals must be a non-empty string"
        )
    if otherwise != "defer":
        raise ValidationRegistryError(
            f"validator {validator_id}: unsupported condition outcome {otherwise!r}"
        )
    if not isinstance(message, str) or not message:
        raise ValidationRegistryError(
            f"validator {validator_id}: deferred validation message is required"
        )
    return {
        "document": document,
        "field": field,
        "equals": expected,
        "otherwise": otherwise,
        "message": message,
    }


def _load_registry(path: Path) -> tuple[list[str], dict[str, str], list[dict[str, Any]]]:
    value = _load_json(path)
    if not isinstance(value, dict) or set(value) != {
        "schema_version",
        "runtime",
        "validators",
    }:
        raise ValidationRegistryError(
            "validation registry must contain exactly schema_version, runtime, and validators"
        )
    if value.get("schema_version") != 2:
        raise ValidationRegistryError("validation registry schema_version must be 2")
    runtime_lines, runtime_requirements = _parse_runtime_requirements(value.get("runtime"))
    validators = value.get("validators")
    if not isinstance(validators, list):
        raise ValidationRegistryError("validation registry validators must be an array")

    normalized: list[dict[str, Any]] = []
    ids: set[str] = set()
    for index, entry in enumerate(validators):
        if not isinstance(entry, dict):
            raise ValidationRegistryError(f"validators[{index}] must be an object")
        allowed = {"id", "component", "entrypoint", "arguments", "purpose", "when"}
        required = {"id", "component", "entrypoint", "arguments", "purpose"}
        if not required <= set(entry) or not set(entry) <= allowed:
            raise ValidationRegistryError(
                f"validators[{index}] has invalid fields: {sorted(entry)}"
            )
        validator_id = entry.get("id")
        if not isinstance(validator_id, str) or not re.fullmatch(
            r"[a-z][a-z0-9]*(?:-[a-z0-9]+)*", validator_id
        ):
            raise ValidationRegistryError(f"validators[{index}].id is invalid")
        if validator_id in ids:
            raise ValidationRegistryError(f"duplicate validator id: {validator_id}")
        ids.add(validator_id)

        component = entry.get("component")
        if not isinstance(component, str) or not COMPONENT_RE.fullmatch(component):
            raise ValidationRegistryError(f"validator {validator_id}: invalid component id")
        entrypoint = _portable_path(entry.get("entrypoint"))
        arguments = entry.get("arguments")
        if not isinstance(arguments, list) or any(
            not isinstance(argument, str) or "\x00" in argument for argument in arguments
        ):
            raise ValidationRegistryError(
                f"validator {validator_id}: arguments must be strings"
            )
        purpose = entry.get("purpose")
        if not isinstance(purpose, str) or not purpose:
            raise ValidationRegistryError(
                f"validator {validator_id}: purpose is required"
            )
        condition = _validate_when(entry.get("when"), validator_id=validator_id)
        normalized.append(
            {
                "id": validator_id,
                "component": component,
                "entrypoint": entrypoint,
                "arguments": list(arguments),
                "purpose": purpose,
                "when": condition,
            }
        )
    return (
        runtime_lines,
        runtime_requirements,
        sorted(normalized, key=lambda entry: (entry["component"], entry["id"])),
    )


def _lock_files(lock: dict[str, Any]) -> dict[str, dict[str, Any]]:
    files = lock.get("files")
    if not isinstance(files, list):
        raise ValidationRegistryError("composition lock files must be an array")
    result: dict[str, dict[str, Any]] = {}
    for entry in files:
        if not isinstance(entry, dict):
            raise ValidationRegistryError(
                "composition lock contains a non-object file entry"
            )
        destination = entry.get("destination")
        if not isinstance(destination, str):
            raise ValidationRegistryError(
                "composition lock file entry has an invalid destination"
            )
        if destination in result:
            raise ValidationRegistryError(
                f"duplicate lock destination: {destination}"
            )
        result[destination] = entry
    return result


def _require_locked_material(
    files: dict[str, dict[str, Any]],
    destination: str,
    *,
    component: str,
    ownership: str | None = None,
) -> dict[str, Any]:
    entry = files.get(destination)
    if entry is None:
        raise ValidationRegistryError(
            f"selected validator material is not declared by the composition lock: {destination}"
        )
    if entry.get("component") != component:
        raise ValidationRegistryError(
            f"validation material owner mismatch for {destination}: expected {component}, got {entry.get('component')!r}"
        )
    if ownership is not None and entry.get("ownership") != ownership:
        raise ValidationRegistryError(
            f"validation material ownership mismatch for {destination}: expected {ownership}, got {entry.get('ownership')!r}"
        )
    return entry


def _verify_host_python() -> None:
    if sys.implementation.name != "cpython":
        raise ValidationRuntimeError("Composition validation requires CPython")
    version = sys.version_info[:2]
    if not (SUPPORTED_MIN <= version < SUPPORTED_MAX_EXCLUSIVE):
        raise ValidationRuntimeError(
            f"unsupported CPython {version[0]}.{version[1]}; "
            "supported versions are 3.11 through 3.14"
        )


def _python_token() -> str:
    return f"{sys.version_info.major}.{sys.version_info.minor}"


def _platform_token() -> str:
    machine = platform.machine().lower() or "unknown"
    return f"{sys.platform}-{machine}"


def _validation_cache_root() -> Path:
    try:
        override = os.environ.get(CACHE_OVERRIDE)
        if override:
            return Path(override).expanduser().resolve()
        if os.name == "nt":
            local = os.environ.get("LOCALAPPDATA")
            base = Path(local) if local else Path.home() / ".cache"
        else:
            xdg = os.environ.get("XDG_CACHE_HOME")
            base = Path(xdg) if xdg else Path.home() / ".cache"
        return base / "composition" / "validation-v1"
    except (OSError, RuntimeError) as exc:
        raise ValidationRuntimeError(
            f"cannot determine Composition validation cache directory: {exc}. "
            f"Set {CACHE_OVERRIDE} to a writable directory."
        ) from exc


def _runtime_environment() -> dict[str, str]:
    environment = {
        key: value
        for key, value in os.environ.items()
        if not key.upper().startswith("PIP_")
        and not key.upper().startswith("PYTHON")
    }
    environment["PYTHONNOUSERSITE"] = "1"
    environment["PIP_CONFIG_FILE"] = os.devnull
    environment["PIP_DISABLE_PIP_VERSION_CHECK"] = "1"
    return environment


def _cache_error(path: Path, exc: BaseException) -> ValidationRuntimeError:
    return ValidationRuntimeError(
        f"Composition validation cache is unusable at {path}: {exc}. "
        f"Set {CACHE_OVERRIDE} to a writable directory."
    )


def _remove_path(path: Path) -> None:
    if path.is_symlink() or path.is_file():
        path.unlink(missing_ok=True)
    elif path.is_dir():
        shutil.rmtree(path, ignore_errors=True)


def _ensure_cache_parent(parent: Path) -> None:
    probe: Path | None = None
    renamed: Path | None = None
    try:
        parent.mkdir(parents=True, exist_ok=True)
        probe = Path(
            tempfile.mkdtemp(prefix=".composition-validation-probe-", dir=parent)
        )
        (probe / "probe").write_text("ok\n", encoding="utf-8")
        renamed = probe.with_name(f"{probe.name}.renamed")
        probe.rename(renamed)
        probe = None
        _remove_path(renamed)
        renamed = None
    except OSError as exc:
        if probe is not None:
            _remove_path(probe)
        if renamed is not None:
            _remove_path(renamed)
        raise _cache_error(parent, exc) from exc


def _runtime_identity(lock_data: bytes) -> dict[str, str]:
    return {
        "requirements_sha256": hashlib.sha256(lock_data).hexdigest(),
        "python": _python_token(),
        "platform": _platform_token(),
    }


def _runtime_digest(identity: dict[str, str]) -> str:
    encoded = json.dumps(
        identity, sort_keys=True, separators=(",", ":")
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _runtime_entry(cache: Path, identity: dict[str, str]) -> Path:
    return cache / "runtimes" / _runtime_digest(identity)


def _runtime_marker(entry: Path) -> Path:
    return entry / "runtime.json"


def _runtime_marker_payload(identity: dict[str, str]) -> dict[str, Any]:
    return {"schema_version": CACHE_SCHEMA, "identity": identity}


def _venv_python(entry: Path) -> Path:
    if os.name == "nt":
        return entry / "venv" / "Scripts" / "python.exe"
    return entry / "venv" / "bin" / "python"


def _run_checked(
    command: list[str],
    *,
    environment: dict[str, str],
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            command,
            cwd=cwd,
            env=environment,
            text=True,
            capture_output=True,
            check=True,
        )
    except OSError as exc:
        raise ValidationRuntimeError(
            f"cannot execute validation runtime command {command[0]}: {exc}"
        ) from exc
    except subprocess.CalledProcessError as exc:
        detail = (exc.stderr or exc.stdout or "").strip()
        suffix = f": {detail}" if detail else ""
        raise ValidationRuntimeError(
            f"validation runtime command failed with exit {exc.returncode}: "
            f"{' '.join(command)}{suffix}"
        ) from exc


_RUNTIME_PROBE = (
    "import importlib.metadata,json,platform,sys;"
    "normalize=lambda name:__import__('re').sub(r'[-_.]+','-',name).lower();"
    "d={};"
    "\nfor item in importlib.metadata.distributions():"
    "\n name=item.metadata.get('Name');"
    "\n assert name;"
    "\n key=normalize(name);"
    "\n assert key not in d;"
    "\n d[key]=item.version;"
    "\nmachine=platform.machine().lower() or 'unknown';"
    "\nprint(json.dumps({'implementation':sys.implementation.name,"
    "'python':str(sys.version_info.major)+'.'+str(sys.version_info.minor),"
    "'platform':sys.platform+'-'+machine,'distributions':d},sort_keys=True))"
)


def _runtime_valid(
    entry: Path,
    identity: dict[str, str],
    expected: dict[str, str],
    environment: dict[str, str],
) -> bool:
    if entry.is_symlink() or not entry.is_dir():
        return False
    marker = _runtime_marker(entry)
    try:
        if marker.is_symlink() or not marker.is_file():
            return False
        if _load_json(marker) != _runtime_marker_payload(identity):
            return False
    except (OSError, UnicodeError, json.JSONDecodeError, StrictJsonError):
        return False

    lock = entry / "requirements-runtime.lock"
    python = _venv_python(entry)
    if lock.is_symlink() or not lock.is_file() or not python.is_file():
        return False
    try:
        if hashlib.sha256(lock.read_bytes()).hexdigest() != identity["requirements_sha256"]:
            return False
        probe = _run_checked(
            [str(python), "-I", "-c", _RUNTIME_PROBE],
            environment=environment,
        )
        value = json.loads(probe.stdout)
        if not isinstance(value, dict):
            return False
        if value.get("implementation") != "cpython":
            return False
        if value.get("python") != identity["python"]:
            return False
        if value.get("platform") != identity["platform"]:
            return False
        installed = value.get("distributions")
        if not isinstance(installed, dict):
            return False
        checked = {
            name: version
            for name, version in installed.items()
            if name not in BOOTSTRAP_DISTRIBUTIONS
        }
        if checked != expected:
            return False
        _run_checked(
            [str(python), "-I", "-m", "pip", "check"],
            environment=environment,
        )
    except (
        OSError,
        UnicodeError,
        ValueError,
        json.JSONDecodeError,
        ValidationRuntimeError,
    ):
        return False
    return True


def _install_cache_directory(
    stage: Path,
    target: Path,
    identity: dict[str, str],
    expected: dict[str, str],
    environment: dict[str, str],
) -> Path:
    if _runtime_valid(target, identity, expected, environment):
        _remove_path(stage)
        return target

    backup: Path | None = None
    if target.exists() or target.is_symlink():
        placeholder = Path(
            tempfile.mkdtemp(prefix=f".{target.name}.backup-", dir=target.parent)
        )
        placeholder.rmdir()
        backup = placeholder
        try:
            target.rename(backup)
        except FileNotFoundError:
            backup = None

    try:
        stage.rename(target)
    except OSError as rename_error:
        if _runtime_valid(target, identity, expected, environment):
            _remove_path(stage)
            if backup is not None:
                _remove_path(backup)
            return target
        if (
            backup is not None
            and (backup.exists() or backup.is_symlink())
            and not (target.exists() or target.is_symlink())
        ):
            try:
                backup.rename(target)
            except OSError as restore_error:
                raise ValidationRuntimeError(
                    f"validation cache installation failed for {target}: "
                    f"{rename_error}; previous cache entry could not be restored: "
                    f"{restore_error}"
                ) from restore_error
        raise

    if backup is not None:
        _remove_path(backup)
    return target


def _build_validation_runtime(
    target: Path,
    identity: dict[str, str],
    requirement_lines: list[str],
    expected: dict[str, str],
    environment: dict[str, str],
) -> Path:
    _ensure_cache_parent(target.parent)
    stage: Path | None = None
    try:
        stage = Path(
            tempfile.mkdtemp(prefix=f".{target.name}.build-", dir=target.parent)
        )
        lock = stage / "requirements-runtime.lock"
        lock_data = ("\n".join(requirement_lines) + "\n").encode("utf-8")
        lock.write_bytes(lock_data)
        _run_checked(
            [sys.executable, "-I", "-m", "venv", str(stage / "venv")],
            environment=environment,
        )
        python = _venv_python(stage)
        _run_checked(
            [
                str(python),
                "-I",
                "-m",
                "pip",
                "install",
                "--isolated",
                "--disable-pip-version-check",
                "--no-cache-dir",
                "--no-deps",
                "--requirement",
                str(lock),
            ],
            environment=environment,
        )
        _run_checked(
            [str(python), "-I", "-m", "pip", "check"],
            environment=environment,
        )
        _runtime_marker(stage).write_text(
            json.dumps(
                _runtime_marker_payload(identity),
                indent=2,
                sort_keys=True,
            )
            + "\n",
            encoding="utf-8",
        )
        if not _runtime_valid(stage, identity, expected, environment):
            raise ValidationRuntimeError(
                "new Composition validation runtime cache failed validation"
            )
        return _install_cache_directory(
            stage,
            target,
            identity,
            expected,
            environment,
        )
    except OSError as exc:
        if stage is not None:
            _remove_path(stage)
        raise _cache_error(target.parent, exc) from exc
    except Exception:
        if stage is not None:
            _remove_path(stage)
        raise


def _ensure_validation_python(
    requirement_lines: list[str],
    expected: dict[str, str],
) -> tuple[Path, dict[str, str]]:
    _verify_host_python()
    lock_data = ("\n".join(requirement_lines) + "\n").encode("utf-8")
    identity = _runtime_identity(lock_data)
    environment = _runtime_environment()
    target = _runtime_entry(_validation_cache_root(), identity)
    if _runtime_valid(target, identity, expected, environment):
        return _venv_python(target), environment
    entry = _build_validation_runtime(
        target,
        identity,
        requirement_lines,
        expected,
        environment,
    )
    return _venv_python(entry), environment


def _run_process(
    root: Path,
    entrypoint: str,
    arguments: list[str],
    *,
    python: Path | str | None = None,
    environment: dict[str, str] | None = None,
) -> subprocess.CompletedProcess[str]:
    executable = str(python) if python is not None else sys.executable
    try:
        return subprocess.run(
            [executable, str(root / entrypoint), *arguments],
            cwd=root,
            env=environment,
            text=True,
            capture_output=True,
            check=False,
        )
    except OSError as exc:
        return subprocess.CompletedProcess(
            [executable, str(root / entrypoint), *arguments],
            126,
            "",
            f"cannot execute validator with {executable}: {exc}",
        )


def _process_check(
    *,
    check_id: str,
    component: str,
    entrypoint: str,
    process: subprocess.CompletedProcess[str],
    purpose: str,
) -> dict[str, Any]:
    return {
        "id": check_id,
        "component": component,
        "status": "passed" if process.returncode == 0 else "failed",
        "entrypoint": entrypoint,
        "purpose": purpose,
        "returncode": process.returncode,
        "stdout": process.stdout,
        "stderr": process.stderr,
    }


def _failed_check(
    *,
    check_id: str,
    component: str,
    entrypoint: str,
    purpose: str,
    message: str,
) -> dict[str, Any]:
    return {
        "id": check_id,
        "component": component,
        "status": "failed",
        "entrypoint": entrypoint,
        "purpose": purpose,
        "returncode": None,
        "stdout": "",
        "stderr": message,
    }


def _condition_decision(
    root: Path,
    condition: dict[str, str],
    files: dict[str, dict[str, Any]],
    *,
    component: str,
) -> tuple[str, str | None]:
    document = condition["document"]
    _require_locked_material(files, document, component=component)
    try:
        value = _load_json(root / document)
    except (OSError, UnicodeError, json.JSONDecodeError, StrictJsonError) as exc:
        return "failed", f"cannot read validation condition document {document}: {exc}"
    if not isinstance(value, dict):
        return (
            "failed",
            f"validation condition document must contain a JSON object: {document}",
        )
    actual = value.get(condition["field"])
    if actual == condition["equals"]:
        return "run", None
    return "deferred", condition["message"]



def _evidence_mode(root: Path) -> str:
    """Read the consumer evidence mode for the lifecycle projection only."""
    try:
        evidence = _load_json(root / "contracts/implementation-evidence.json")
    except FileNotFoundError:
        return "missing"
    except (OSError, UnicodeError, json.JSONDecodeError, StrictJsonError):
        return "invalid"
    if not isinstance(evidence, dict):
        return "invalid"
    mode = evidence.get("mode")
    return mode if mode in {"template", "planning", "product"} else "invalid"


def _checkpoint_phase(root: Path, checks: list[dict[str, Any]]) -> str:
    """Return the latest validated checkpoint phase for lifecycle presentation.

    Checkpoint semantics remain owned by lifecycle.lifecycle-checkpoints. This
    projection reads the ledger only when that selected component has already
    contributed a validation check. Unexpected ledger shapes fail closed here;
    normal selected-component validation remains the authoritative validator.
    """
    if not any(
        check.get("component") == "lifecycle.lifecycle-checkpoints"
        for check in checks
    ):
        return "not-selected"
    try:
        ledger = _load_json(root / "contracts/lifecycle-checkpoints.json")
    except (OSError, UnicodeError, json.JSONDecodeError, StrictJsonError):
        return "invalid"
    if not isinstance(ledger, dict):
        return "invalid"
    checkpoints = ledger.get("checkpoints")
    if not isinstance(checkpoints, list):
        return "invalid"
    if not checkpoints:
        return "missing"
    latest = checkpoints[-1]
    if not isinstance(latest, dict):
        return "invalid"
    phase = latest.get("phase")
    return phase if phase in {"planning", "product"} else "invalid"



def _checkpoint_latest_id(root: Path) -> str | None:
    try:
        ledger = _load_json(root / "contracts/lifecycle-checkpoints.json")
    except (OSError, UnicodeError, json.JSONDecodeError, StrictJsonError):
        return None
    if not isinstance(ledger, dict):
        return None
    checkpoints = ledger.get("checkpoints")
    if not isinstance(checkpoints, list) or not checkpoints:
        return None
    latest = checkpoints[-1]
    if not isinstance(latest, dict):
        return None
    checkpoint_id = latest.get("id")
    if not isinstance(checkpoint_id, str) or re.fullmatch(r"[a-z][a-z0-9-]*", checkpoint_id) is None:
        return None
    return checkpoint_id


def _checkpoint_action_command(root: Path, action: str) -> dict[str, Any] | None:
    try:
        registry = _load_json(root / CHECKPOINT_ACTION_REGISTRY_RELATIVE)
    except (OSError, UnicodeError, json.JSONDecodeError, StrictJsonError):
        return None
    if (
        not isinstance(registry, dict)
        or set(registry) != {"$schema", "schemaVersion", "actions"}
        or registry.get("schemaVersion") != 1
    ):
        return None
    actions = registry.get("actions")
    if (
        registry.get("$schema") != "./lifecycle-checkpoint-actions.schema.json"
        or not isinstance(actions, dict)
        or set(actions) != {
            "create-planning-checkpoint",
            "create-product-checkpoint",
        }
    ):
        return None
    entry = actions.get(action)
    if not isinstance(entry, dict) or set(entry) != {"argv", "caller_inputs", "bindings"}:
        return None
    argv = entry.get("argv")
    caller_inputs = entry.get("caller_inputs")
    bindings = entry.get("bindings")
    if (
        not isinstance(argv, list)
        or not argv
        or any(not isinstance(token, str) or not token for token in argv)
        or not isinstance(caller_inputs, list)
        or len(caller_inputs) != len(set(caller_inputs))
        or any(
            not isinstance(token, str)
            or re.fullmatch(r"\{[a-z_]+\}", token) is None
            for token in caller_inputs
        )
        or not isinstance(bindings, dict)
        or any(
            not isinstance(token, str)
            or re.fullmatch(r"\{[a-z_]+\}", token) is None
            or binding != "latest-checkpoint-id"
            for token, binding in bindings.items()
        )
        or set(caller_inputs) & set(bindings)
    ):
        return None

    resolved: list[str] = []
    placeholder = re.compile(r"^\{[a-z_]+\}$")
    for token in argv:
        if token in bindings:
            latest_id = _checkpoint_latest_id(root)
            if latest_id is None:
                return None
            resolved.append(latest_id)
        elif placeholder.fullmatch(token) is not None:
            if token not in caller_inputs:
                return None
            resolved.append(token)
        else:
            resolved.append(token)
    if (
        any(token not in argv for token in caller_inputs)
        or any(token not in argv for token in bindings)
    ):
        return None
    return {
        "action": action,
        "argv": resolved,
        "caller_inputs": list(caller_inputs),
    }


def _checkpoint_command_failure(mode: str) -> dict[str, Any]:
    return {
        "schema_version": 2,
        "lifecycle_stage": "composition-invalid",
        "implementation_evidence_mode": mode,
        "release_readiness": "not-evaluated",
        "blocking_conditions": ["checkpoint-command-registry-invalid"],
        "deferred_checks": [],
        "next_actions": ["inspect", "plan", "apply", "validate"],
    }

def _lifecycle_projection(
    root: Path, status: str, checks: list[dict[str, Any]]
) -> dict[str, Any]:
    """Project existing validation/evidence state into deterministic next actions.

    This is a presentation projection, not a second lifecycle authority. It
    deliberately reports ordinary validation and revision-bound release
    readiness as separate dimensions. When lifecycle checkpoints are selected,
    the projection never skips the checkpoint boundary already required by the
    selected checkpoint authority.
    """
    mode = _evidence_mode(root)
    failed = status != "valid" or any(
        check.get("status") == "failed" for check in checks
    )
    if failed:
        return {
            "schema_version": 2,
            "lifecycle_stage": "composition-invalid",
            "implementation_evidence_mode": mode,
            "release_readiness": "not-evaluated",
            "blocking_conditions": ["composition-validation-failed"],
            "deferred_checks": [],
            "next_actions": ["inspect", "plan", "apply", "validate"],
        }

    if mode == "invalid":
        return {
            "schema_version": 2,
            "lifecycle_stage": "composition-invalid",
            "implementation_evidence_mode": mode,
            "release_readiness": "not-evaluated",
            "blocking_conditions": ["implementation-evidence-invalid"],
            "deferred_checks": [],
            "next_actions": ["inspect", "plan", "apply", "validate"],
        }

    checkpoint_phase = _checkpoint_phase(root, checks)
    if checkpoint_phase == "invalid":
        return {
            "schema_version": 2,
            "lifecycle_stage": "composition-invalid",
            "implementation_evidence_mode": mode,
            "release_readiness": "not-evaluated",
            "blocking_conditions": ["checkpoint-state-invalid"],
            "deferred_checks": [],
            "next_actions": ["inspect", "plan", "apply", "validate"],
        }

    checkpoints_selected = checkpoint_phase != "not-selected"

    if mode == "template":
        return {
            "schema_version": 2,
            "lifecycle_stage": "scaffold-valid",
            "implementation_evidence_mode": mode,
            "release_readiness": "not-evaluated",
            "blocking_conditions": ["implementation-evidence-template"],
            "deferred_checks": [],
            "next_actions": (
                ["define-product-requirements"]
                if checkpoints_selected
                else [
                    "define-product-requirements",
                    "implement-product",
                    "populate-product-evidence",
                    "run-product-verifier",
                    "validate-product-state",
                    "check-release-readiness",
                ]
            ),
        }

    if mode == "planning":
        if checkpoints_selected and checkpoint_phase != "planning":
            command = _checkpoint_action_command(root, "create-planning-checkpoint")
            if command is None:
                return _checkpoint_command_failure(mode)
            return {
                "schema_version": 2,
                "lifecycle_stage": "scaffold-valid",
                "implementation_evidence_mode": mode,
                "release_readiness": "not-evaluated",
                "blocking_conditions": [
                    "implementation-evidence-planning",
                    "planning-checkpoint-required",
                ],
                "deferred_checks": [],
                "next_actions": ["create-planning-checkpoint"],
                "next_action_command": command,
            }
        return {
            "schema_version": 2,
            "lifecycle_stage": "scaffold-valid",
            "implementation_evidence_mode": mode,
            "release_readiness": "not-evaluated",
            "blocking_conditions": ["implementation-evidence-planning"],
            "deferred_checks": [],
            "next_actions": (
                [
                    "implement-product",
                    "populate-product-evidence",
                    "run-product-verifier",
                    "validate-product-state",
                ]
                if checkpoints_selected
                else [
                    "implement-product",
                    "populate-product-evidence",
                    "run-product-verifier",
                    "validate-product-state",
                    "check-release-readiness",
                ]
            ),
        }

    if mode == "product":
        deferred = sorted(
            str(check.get("id"))
            for check in checks
            if check.get("status") == "deferred"
        )
        if checkpoints_selected and checkpoint_phase != "product":
            command = _checkpoint_action_command(root, "create-product-checkpoint")
            if command is None:
                return _checkpoint_command_failure(mode)
            blockers = ["product-checkpoint-required"]
            readiness = "not-evaluated"
            if deferred:
                blockers.append("deferred-proof")
                readiness = "not-ready"
            return {
                "schema_version": 2,
                "lifecycle_stage": "implemented-product",
                "implementation_evidence_mode": mode,
                "release_readiness": readiness,
                "blocking_conditions": blockers,
                "deferred_checks": deferred,
                "next_actions": ["create-product-checkpoint"],
                "next_action_command": command,
            }

        if deferred:
            return {
                "schema_version": 2,
                "lifecycle_stage": "implemented-product",
                "implementation_evidence_mode": mode,
                "release_readiness": "not-ready",
                "blocking_conditions": ["deferred-proof"],
                "deferred_checks": deferred,
                "next_actions": [
                    "resolve-deferred-proof",
                    "run-product-verifier",
                    "validate-product-state",
                    "check-release-readiness",
                ],
            }

        explicitly_ready = any(
            check.get("id") == "release-readiness"
            and check.get("status") == "passed"
            for check in checks
        )
        if explicitly_ready:
            return {
                "schema_version": 2,
                "lifecycle_stage": "release-ready",
                "implementation_evidence_mode": mode,
                "release_readiness": "ready",
                "blocking_conditions": [],
                "deferred_checks": [],
                "next_actions": [],
            }

        return {
            "schema_version": 2,
            "lifecycle_stage": "implemented-product",
            "implementation_evidence_mode": mode,
            "release_readiness": "not-evaluated",
            "blocking_conditions": ["release-readiness-not-evaluated"],
            "deferred_checks": [],
            "next_actions": ["check-release-readiness"],
        }

    return {
        "schema_version": 2,
        "lifecycle_stage": "scaffold-valid",
        "implementation_evidence_mode": mode,
        "release_readiness": "not-evaluated",
        "blocking_conditions": ["implementation-evidence-missing"],
        "deferred_checks": [],
        "next_actions": (
            ["define-product-requirements"]
            if checkpoints_selected
            else [
                "define-product-requirements",
                "implement-product",
                "populate-product-evidence",
                "run-product-verifier",
                "validate-product-state",
                "check-release-readiness",
            ]
        ),
    }

def _validate_base(root: Path) -> dict[str, Any]:
    state_validator = root / STATE_VALIDATOR_RELATIVE
    if state_validator.is_symlink() or not state_validator.is_file():
        return {
            "schema_version": 1,
            "status": "invalid",
            "target": str(root),
            "resolved_components": [],
            "checks": [
                _failed_check(
                    check_id="composition-state",
                    component="lifecycle.composition-state",
                    entrypoint=STATE_VALIDATOR_RELATIVE,
                    purpose="Validate the resolved Composition lock and material ownership state.",
                    message=(
                        "composition state validator is missing or unsafe: "
                        f"{STATE_VALIDATOR_RELATIVE}"
                    ),
                )
            ],
        }

    state = _run_process(root, STATE_VALIDATOR_RELATIVE, [str(root)])
    state_check = _process_check(
        check_id="composition-state",
        component="lifecycle.composition-state",
        entrypoint=STATE_VALIDATOR_RELATIVE,
        process=state,
        purpose="Validate the resolved Composition lock and material ownership state.",
    )
    if state.returncode != 0:
        return {
            "schema_version": 1,
            "status": "invalid",
            "target": str(root),
            "resolved_components": [],
            "checks": [state_check],
        }

    try:
        lock = _load_json(root / LOCK_RELATIVE)
        if not isinstance(lock, dict):
            raise ValidationRegistryError(
                "composition lock must contain a JSON object"
            )
        resolved_entries = lock.get("resolved_components")
        if not isinstance(resolved_entries, list):
            raise ValidationRegistryError(
                "composition lock resolved_components must be an array"
            )
        selected = [
            entry.get("id")
            for entry in resolved_entries
            if isinstance(entry, dict) and isinstance(entry.get("id"), str)
        ]
        if len(selected) != len(resolved_entries):
            raise ValidationRegistryError(
                "composition lock has invalid resolved component entries"
            )
        selected_set = set(selected)
        files = _lock_files(lock)
        _require_locked_material(
            files,
            REGISTRY_RELATIVE,
            component="lifecycle.composition-state",
            ownership="managed",
        )
        _require_locked_material(
            files,
            RUNNER_RELATIVE,
            component="lifecycle.composition-state",
            ownership="managed",
        )
        runtime_lines, runtime_requirements, registry = _load_registry(
            root / REGISTRY_RELATIVE
        )
    except (
        OSError,
        UnicodeError,
        json.JSONDecodeError,
        StrictJsonError,
        ValidationRegistryError,
    ) as exc:
        return {
            "schema_version": 1,
            "status": "invalid",
            "target": str(root),
            "resolved_components": [],
            "checks": [
                state_check,
                _failed_check(
                    check_id="validation-registry",
                    component="lifecycle.composition-state",
                    entrypoint=REGISTRY_RELATIVE,
                    purpose=(
                        "Resolve validator dispatch and validation runtime from "
                        "the trusted managed registry and composition lock."
                    ),
                    message=str(exc),
                ),
            ],
        }

    try:
        validation_python, validation_environment = _ensure_validation_python(
            runtime_lines,
            runtime_requirements,
        )
    except ValidationRuntimeError as exc:
        return {
            "schema_version": 1,
            "status": "invalid",
            "target": str(root),
            "resolved_components": selected,
            "checks": [
                state_check,
                _failed_check(
                    check_id="validation-runtime",
                    component="lifecycle.composition-state",
                    entrypoint=REGISTRY_RELATIVE,
                    purpose=(
                        "Provide the exact isolated Python dependency set used "
                        "by selected component validators."
                    ),
                    message=str(exc),
                ),
            ],
        }

    checks: list[dict[str, Any]] = [state_check]
    for entry in registry:
        component = entry["component"]
        if component not in selected_set:
            continue
        try:
            _require_locked_material(
                files,
                entry["entrypoint"],
                component=component,
                ownership="managed",
            )
        except ValidationRegistryError as exc:
            checks.append(
                _failed_check(
                    check_id=entry["id"],
                    component=component,
                    entrypoint=entry["entrypoint"],
                    purpose=entry["purpose"],
                    message=str(exc),
                )
            )
            continue

        condition = entry["when"]
        if condition is not None:
            try:
                decision, message = _condition_decision(
                    root,
                    condition,
                    files,
                    component=component,
                )
            except ValidationRegistryError as exc:
                decision, message = "failed", str(exc)
            if decision == "failed":
                checks.append(
                    _failed_check(
                        check_id=entry["id"],
                        component=component,
                        entrypoint=entry["entrypoint"],
                        purpose=entry["purpose"],
                        message=message or "validation condition failed",
                    )
                )
                continue
            if decision == "deferred":
                checks.append(
                    {
                        "id": entry["id"],
                        "component": component,
                        "status": "deferred",
                        "entrypoint": entry["entrypoint"],
                        "purpose": entry["purpose"],
                        "returncode": None,
                        "stdout": "",
                        "stderr": message or "",
                    }
                )
                continue

        process = _run_process(
            root,
            entry["entrypoint"],
            entry["arguments"],
            python=validation_python,
            environment=validation_environment,
        )
        checks.append(
            _process_check(
                check_id=entry["id"],
                component=component,
                entrypoint=entry["entrypoint"],
                process=process,
                purpose=entry["purpose"],
            )
        )

    return {
        "schema_version": 1,
        "status": (
            "invalid"
            if any(check["status"] == "failed" for check in checks)
            else "valid"
        ),
        "target": str(root),
        "resolved_components": selected,
        "checks": checks,
    }



def validate(root: Path) -> dict[str, Any]:
    result = _validate_base(root)
    result["lifecycle"] = _lifecycle_projection(
        root, result["status"], result.get("checks", [])
    )
    return result


def _render_human(result: dict[str, Any]) -> None:
    for check in result["checks"]:
        label = check["status"].upper()
        print(f"{label}: {check['id']} ({check['component']})")
        detail = check.get("stderr") or check.get("stdout")
        if check["status"] in {"failed", "deferred"} and detail:
            indented = "\n".join(
                f"  {line}" for line in detail.strip().splitlines()
            )
            print(indented)
    print(f"Composition validation: {result['status'].upper()}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".")
    parser.add_argument("--format", choices=("human", "json"), default="human")
    args = parser.parse_args()
    root = Path(args.root).absolute()
    result = validate(root)
    if args.format == "json":
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        _render_human(result)
    return 0 if result["status"] == "valid" else 1


if __name__ == "__main__":
    raise SystemExit(main())
