#!/usr/bin/env python3
"""Validate materialized composition state without a source checkout."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

LOCK_RELATIVE = ".template-composition/lock.json"
TRANSACTION_RELATIVE = ".template-composition/transaction.json"
STAGING_PREFIX = ".template-composition/staging"
POLICY_CONFIG_RELATIVE = ".agent-policy.yml"
POLICY_LOCK_RELATIVE = ".agent-policy.lock"
POLICY_STATE_PREFIX = ".agent-policy"
CANONICAL_REPOSITORY = "TakashiSasaki/templates"
COMPONENT_RE = re.compile(r"^(foundation|artifact|capability|lifecycle)\.[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
SELECTABLE_COMPONENT_RE = re.compile(r"^(capability|lifecycle)\.[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
PARAMETER_COMPONENT_RE = re.compile(r"^(artifact|capability|lifecycle)\.[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
RECIPE_RE = re.compile(r"^[a-z][a-z0-9]*(?:-[a-z0-9]+)*$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REVISION_RE = re.compile(r"^(?!0{40}$)[0-9a-f]{40}$")
OWNERSHIPS = {"managed", "seed", "generated"}


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


def load_json(path: Path) -> Any:
    with path.open("r", encoding="utf-8") as handle:
        return json.load(
            handle,
            object_pairs_hook=_object_pairs,
            parse_constant=_constant,
        )


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _portable_parts(value: str) -> tuple[str, ...] | None:
    if not value or "\\" in value or value.startswith("/") or re.match(r"^[A-Za-z]:", value):
        return None
    parts = tuple(value.split("/"))
    if any(
        not part
        or part in {".", ".."}
        or part.startswith("-")
        or part.casefold() == ".git"
        for part in parts
    ):
        return None
    return parts


def _normalized_parts(value: str) -> tuple[str, ...]:
    return tuple(part.casefold() for part in value.split("/"))


def _at_or_below(parts: tuple[str, ...], prefix: tuple[str, ...]) -> bool:
    return parts == prefix or prefix == parts[: len(prefix)]


def _reserved_destination(value: str) -> bool:
    parts = _normalized_parts(value)
    lock_parts = _normalized_parts(LOCK_RELATIVE)
    transaction_parts = _normalized_parts(TRANSACTION_RELATIVE)
    staging_parts = _normalized_parts(STAGING_PREFIX)
    policy_config_parts = _normalized_parts(POLICY_CONFIG_RELATIVE)
    policy_lock_parts = _normalized_parts(POLICY_LOCK_RELATIVE)
    policy_state_parts = _normalized_parts(POLICY_STATE_PREFIX)
    return (
        parts == lock_parts[: len(parts)]
        or lock_parts == parts[: len(lock_parts)]
        or parts == transaction_parts[: len(parts)]
        or transaction_parts == parts[: len(transaction_parts)]
        or parts == staging_parts
        or staging_parts == parts[: len(staging_parts)]
        or _at_or_below(parts, policy_config_parts)
        or _at_or_below(parts, policy_lock_parts)
        or _at_or_below(parts, policy_state_parts)
    )


def _path_has_symlink(root: Path, parts: tuple[str, ...]) -> bool:
    candidate = root
    for part in parts:
        candidate /= part
        try:
            if candidate.is_symlink():
                return True
        except OSError:
            return True
    return False


def _validate_intent(intent: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(intent, dict) or set(intent) != {"recipe", "components", "parameters"}:
        return ["composition lock intent must contain exactly recipe, components, and parameters"]
    recipe = intent.get("recipe")
    if not isinstance(recipe, str) or not RECIPE_RE.fullmatch(recipe):
        errors.append("composition lock intent recipe is invalid")
    components = intent.get("components")
    if not isinstance(components, dict) or set(components) != {"include", "exclude"}:
        errors.append("composition lock intent components must contain exactly include and exclude")
    else:
        selections: dict[str, list[str]] = {}
        for name in ("include", "exclude"):
            value = components.get(name)
            if not isinstance(value, list) or any(
                not isinstance(item, str) or not SELECTABLE_COMPONENT_RE.fullmatch(item)
                for item in value
            ):
                errors.append(f"composition lock intent components.{name} is invalid")
                continue
            if value != sorted(value):
                errors.append(f"composition lock intent components.{name} must be lexically ordered")
            if len(value) != len(set(value)):
                errors.append(f"composition lock intent components.{name} must be unique")
            selections[name] = value
        if set(selections.get("include", [])) & set(selections.get("exclude", [])):
            errors.append("composition lock intent include/exclude sets must be disjoint")
    parameters = intent.get("parameters")
    if not isinstance(parameters, dict):
        errors.append("composition lock intent parameters must be an object")
    else:
        for key, value in parameters.items():
            if not PARAMETER_COMPONENT_RE.fullmatch(key) or not isinstance(value, dict):
                errors.append(f"composition lock intent parameter namespace is invalid: {key!r}")
    return errors


def validate_lock_shape(lock: Any) -> list[str]:
    errors: list[str] = []
    if not isinstance(lock, dict):
        return ["composition lock must be a JSON object"]
    expected_keys = {
        "schema_version",
        "source",
        "intent",
        "recipe_sha256",
        "configuration_sha256",
        "resolved_components",
        "files",
    }
    if set(lock) != expected_keys:
        errors.append(
            f"composition lock keys must be exactly {sorted(expected_keys)}; got {sorted(lock)}"
        )
    if lock.get("schema_version") != 2:
        errors.append("composition lock schema_version must be 2")

    source = lock.get("source")
    if not isinstance(source, dict) or set(source) != {"repository", "revision"}:
        errors.append("composition lock source must contain exactly repository and revision")
    else:
        if source.get("repository") != CANONICAL_REPOSITORY:
            errors.append(f"composition lock source repository must be {CANONICAL_REPOSITORY}")
        revision = source.get("revision")
        if not isinstance(revision, str) or not REVISION_RE.fullmatch(revision):
            errors.append("composition lock source revision must be a nonzero lowercase 40-hex commit")

    errors.extend(_validate_intent(lock.get("intent")))
    for field in ("recipe_sha256", "configuration_sha256"):
        digest = lock.get(field)
        if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
            errors.append(f"composition lock {field} must be lowercase 64-hex")

    resolved = lock.get("resolved_components")
    resolved_ids: list[str] = []
    if not isinstance(resolved, list) or not resolved:
        errors.append("composition lock resolved_components must be a non-empty array")
    else:
        for index, entry in enumerate(resolved):
            if not isinstance(entry, dict) or set(entry) != {"id", "version", "descriptor_sha256"}:
                errors.append(f"resolved_components[{index}] has invalid fields")
                continue
            component_id = entry.get("id")
            if not isinstance(component_id, str) or not COMPONENT_RE.fullmatch(component_id):
                errors.append(f"resolved_components[{index}].id is invalid")
            else:
                resolved_ids.append(component_id)
            if not isinstance(entry.get("version"), int) or isinstance(entry.get("version"), bool) or entry["version"] < 1:
                errors.append(f"resolved_components[{index}].version must be a positive integer")
            digest = entry.get("descriptor_sha256")
            if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
                errors.append(f"resolved_components[{index}].descriptor_sha256 is invalid")
        if resolved_ids != sorted(resolved_ids):
            errors.append("resolved component IDs must be lexically ordered")
        if len(resolved_ids) != len(set(resolved_ids)):
            errors.append("resolved component IDs must be unique")
        if sum(component_id.startswith("artifact.") for component_id in resolved_ids) != 1:
            errors.append("composition lock must resolve exactly one artifact component")

    files = lock.get("files")
    destinations: list[str] = []
    owners: set[str] = set()
    resolved_set = set(resolved_ids)
    if not isinstance(files, list) or not files:
        errors.append("composition lock files must be a non-empty array")
    else:
        for index, entry in enumerate(files):
            expected = {"destination", "component", "ownership", "materialized_sha256"}
            if not isinstance(entry, dict) or set(entry) != expected:
                errors.append(f"files[{index}] has invalid fields")
                continue
            destination = entry.get("destination")
            parts = _portable_parts(destination) if isinstance(destination, str) else None
            if parts is None:
                errors.append(f"files[{index}].destination is not a safe portable path")
            else:
                destinations.append(destination)
                if _reserved_destination(destination):
                    errors.append(f"files[{index}].destination conflicts with reserved provider metadata")
            component = entry.get("component")
            if component not in resolved_set:
                errors.append(f"files[{index}].component is not a resolved component")
            elif isinstance(component, str):
                owners.add(component)
            if entry.get("ownership") not in OWNERSHIPS:
                errors.append(f"files[{index}].ownership is invalid")
            digest = entry.get("materialized_sha256")
            if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
                errors.append(f"files[{index}].materialized_sha256 is invalid")

        if destinations != sorted(destinations):
            errors.append("materialized file destinations must be lexically ordered")
        normalized_destinations = [_normalized_parts(destination) for destination in destinations]
        for index, left in enumerate(normalized_destinations):
            for right in normalized_destinations[index + 1 :]:
                if left == right:
                    errors.append("materialized destinations collide case-insensitively")
                elif left == right[: len(left)] or right == left[: len(right)]:
                    errors.append("materialized file/directory destinations conflict")
        missing_owners = resolved_set - owners
        if missing_owners:
            errors.append(f"resolved components own no materialized files: {sorted(missing_owners)}")

    return errors


def validate_materialized_files(root: Path, lock: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    if root.is_symlink():
        return ["consumer repository root must not be a symbolic link"]
    for entry in lock.get("files", []):
        if not isinstance(entry, dict):
            continue
        destination = entry.get("destination")
        if not isinstance(destination, str):
            continue
        parts = _portable_parts(destination)
        if parts is None:
            continue
        if _path_has_symlink(root, parts):
            errors.append(f"materialized path must not contain symbolic links: {destination}")
            continue
        candidate = root.joinpath(*parts)
        if not candidate.is_file():
            errors.append(f"materialized file is missing or not a regular file: {destination}")
            continue
        ownership = entry.get("ownership")
        if ownership in {"managed", "generated"}:
            actual = sha256_file(candidate)
            if actual != entry.get("materialized_sha256"):
                errors.append(f"{ownership} material differs from composition lock: {destination}")
    return errors


def validate_repository(root: Path) -> list[str]:
    transaction_path = root / TRANSACTION_RELATIVE
    if transaction_path.exists() or transaction_path.is_symlink():
        return [f"composition transaction is present; recovery required: {TRANSACTION_RELATIVE}"]
    errors: list[str] = []
    lock_path = root / LOCK_RELATIVE
    if lock_path.is_symlink():
        return ["composition lock must not be a symbolic link"]
    if not lock_path.is_file():
        return [f"composition lock is missing: {LOCK_RELATIVE}"]
    try:
        lock = load_json(lock_path)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError, StrictJsonError) as exc:
        return [f"cannot read composition lock: {exc}"]
    errors.extend(validate_lock_shape(lock))
    if errors or not isinstance(lock, dict):
        return errors
    errors.extend(validate_materialized_files(root, lock))
    return errors


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", nargs="?", default=".")
    args = parser.parse_args()
    errors = validate_repository(Path(args.root).absolute())
    if errors:
        for error in errors:
            print(f"ERROR: {error}", file=sys.stderr)
        return 1
    print("Composition state validation: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
