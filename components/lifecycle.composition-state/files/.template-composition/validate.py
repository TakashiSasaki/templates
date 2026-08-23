#!/usr/bin/env python3
"""Run validators selected by the resolved Composition component set."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

LOCK_RELATIVE = ".template-composition/lock.json"
STATE_VALIDATOR_RELATIVE = ".template-composition/validate_composition.py"
REGISTRY_RELATIVE = ".template-composition/validation-registry.json"
RUNNER_RELATIVE = ".template-composition/validate.py"
COMPONENT_RE = re.compile(
    r"^(artifact|capability|lifecycle)\.[a-z][a-z0-9]*(?:-[a-z0-9]+)*$"
)


class ValidationRegistryError(ValueError):
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
        raise ValidationRegistryError(f"validator {validator_id}: condition equals must be a non-empty string")
    if otherwise != "defer":
        raise ValidationRegistryError(f"validator {validator_id}: unsupported condition outcome {otherwise!r}")
    if not isinstance(message, str) or not message:
        raise ValidationRegistryError(f"validator {validator_id}: deferred validation message is required")
    return {
        "document": document,
        "field": field,
        "equals": expected,
        "otherwise": otherwise,
        "message": message,
    }


def _load_registry(path: Path) -> list[dict[str, Any]]:
    value = _load_json(path)
    if not isinstance(value, dict) or set(value) != {"schema_version", "validators"}:
        raise ValidationRegistryError(
            "validation registry must contain exactly schema_version and validators"
        )
    if value.get("schema_version") != 1:
        raise ValidationRegistryError("validation registry schema_version must be 1")
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
            raise ValidationRegistryError(f"validator {validator_id}: arguments must be strings")
        purpose = entry.get("purpose")
        if not isinstance(purpose, str) or not purpose:
            raise ValidationRegistryError(f"validator {validator_id}: purpose is required")
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
    return sorted(normalized, key=lambda entry: (entry["component"], entry["id"]))


def _lock_files(lock: dict[str, Any]) -> dict[str, dict[str, Any]]:
    files = lock.get("files")
    if not isinstance(files, list):
        raise ValidationRegistryError("composition lock files must be an array")
    result: dict[str, dict[str, Any]] = {}
    for entry in files:
        if not isinstance(entry, dict):
            raise ValidationRegistryError("composition lock contains a non-object file entry")
        destination = entry.get("destination")
        if not isinstance(destination, str):
            raise ValidationRegistryError("composition lock file entry has an invalid destination")
        if destination in result:
            raise ValidationRegistryError(f"duplicate lock destination: {destination}")
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


def _run_process(root: Path, entrypoint: str, arguments: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(root / entrypoint), *arguments],
        cwd=root,
        text=True,
        capture_output=True,
        check=False,
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
        return "failed", f"validation condition document must contain a JSON object: {document}"
    actual = value.get(condition["field"])
    if actual == condition["equals"]:
        return "run", None
    return "deferred", condition["message"]


def validate(root: Path) -> dict[str, Any]:
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
                    message=f"composition state validator is missing or unsafe: {STATE_VALIDATOR_RELATIVE}",
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
            raise ValidationRegistryError("composition lock must contain a JSON object")
        resolved_entries = lock.get("resolved_components")
        if not isinstance(resolved_entries, list):
            raise ValidationRegistryError("composition lock resolved_components must be an array")
        selected = [
            entry.get("id")
            for entry in resolved_entries
            if isinstance(entry, dict) and isinstance(entry.get("id"), str)
        ]
        if len(selected) != len(resolved_entries):
            raise ValidationRegistryError("composition lock has invalid resolved component entries")
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
        registry = _load_registry(root / REGISTRY_RELATIVE)
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
                    purpose="Resolve validator dispatch from the trusted managed registry and composition lock.",
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

        process = _run_process(root, entry["entrypoint"], entry["arguments"])
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
        "status": "invalid" if any(check["status"] == "failed" for check in checks) else "valid",
        "target": str(root),
        "resolved_components": selected,
        "checks": checks,
    }


def _render_human(result: dict[str, Any]) -> None:
    for check in result["checks"]:
        label = check["status"].upper()
        print(f"{label}: {check['id']} ({check['component']})")
        detail = check.get("stderr") or check.get("stdout")
        if check["status"] in {"failed", "deferred"} and detail:
            indented = "\n".join(f"  {line}" for line in detail.strip().splitlines())
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
