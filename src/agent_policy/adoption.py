from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .config import package_root
from .paths import UnsafePathError, resolve_inside
from .renderer import GENERATED_MARKER

KNOWN_INSTRUCTION_FILES = (
    "AGENTS.md",
    "CLAUDE.md",
    "GEMINI.md",
    ".github/copilot-instructions.md",
)
KNOWN_INSTRUCTION_DIRECTORIES = (
    ".agents/policies",
    ".agents/skills",
)
LOCK_PATH = ".agent-policy.lock"


@dataclass(frozen=True)
class AdoptionSource:
    path: str
    sha256: str
    generated: bool


@dataclass(frozen=True)
class AdoptionInspection:
    state: str
    sources: tuple[AdoptionSource, ...]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(path.read_bytes())
    return digest.hexdigest()


def lexical_relative_name(repository_root: Path, relative: str | Path) -> str:
    repository_root = repository_root.resolve()
    raw = Path(relative)
    if raw.is_absolute():
        raise UnsafePathError(f"Absolute paths are not allowed: {relative}")

    literal = Path(os.path.abspath(repository_root / raw))
    try:
        normalized = literal.relative_to(repository_root)
    except ValueError as exc:
        raise UnsafePathError(f"Path escapes repository root: {relative}") from exc

    git_path = repository_root / ".git"
    if literal == git_path or git_path in literal.parents:
        raise UnsafePathError(f"Writing under .git is forbidden: {relative}")
    return normalized.as_posix()


def _is_absolute_symlink(path: Path) -> bool:
    return path.is_symlink() and path.readlink().is_absolute()


def _has_absolute_symlink_component(
    repository_root: Path,
    target: Path,
) -> bool:
    repository_root = repository_root.resolve()
    for component in (target, *target.parents):
        if component == repository_root:
            break
        if _is_absolute_symlink(component):
            return True
    return False


def _source(repository_root: Path, relative: str) -> AdoptionSource:
    lexical_name = lexical_relative_name(repository_root, relative)
    resolved_path = resolve_inside(repository_root, lexical_name, allow_missing=False)
    content = resolved_path.read_bytes()
    return AdoptionSource(
        path=lexical_name,
        sha256=hashlib.sha256(content).hexdigest(),
        generated=GENERATED_MARKER.encode("utf-8") in content,
    )


def _has_inconsistent_known_source_artifact(repository_root: Path) -> bool:
    repository_root = repository_root.resolve()
    for relative in KNOWN_INSTRUCTION_FILES:
        lexical_name = lexical_relative_name(repository_root, relative)
        literal = repository_root / lexical_name
        if _has_absolute_symlink_component(repository_root, literal):
            return True
        resolved = resolve_inside(repository_root, lexical_name, allow_missing=True)
        if (literal.exists() or literal.is_symlink()) and not resolved.is_file():
            return True

    for relative in KNOWN_INSTRUCTION_DIRECTORIES:
        lexical_name = lexical_relative_name(repository_root, relative)
        literal = repository_root / lexical_name
        if _has_absolute_symlink_component(repository_root, literal):
            return True
        resolved = resolve_inside(repository_root, lexical_name, allow_missing=True)
        if (literal.exists() or literal.is_symlink()) and not resolved.is_dir():
            return True
        if not resolved.is_dir():
            continue
        for path in sorted(literal.rglob("*")):
            if not path.is_symlink():
                continue
            if _has_absolute_symlink_component(repository_root, path):
                return True
            child_name = lexical_relative_name(
                repository_root,
                path.relative_to(repository_root),
            )
            child_target = resolve_inside(
                repository_root,
                child_name,
                allow_missing=True,
            )
            if not child_target.is_file():
                return True

    return False


def discover_sources(repository_root: Path) -> tuple[AdoptionSource, ...]:
    repository_root = repository_root.resolve()
    candidates: set[str] = set()
    for relative in KNOWN_INSTRUCTION_FILES:
        lexical_name = lexical_relative_name(repository_root, relative)
        path = resolve_inside(repository_root, lexical_name, allow_missing=True)
        if path.is_file():
            candidates.add(lexical_name)

    for relative in KNOWN_INSTRUCTION_DIRECTORIES:
        lexical_directory = lexical_relative_name(repository_root, relative)
        resolved_directory = resolve_inside(
            repository_root,
            lexical_directory,
            allow_missing=True,
        )
        if not resolved_directory.is_dir():
            continue
        literal_directory = repository_root / lexical_directory
        for path in sorted(literal_directory.rglob("*")):
            if not path.is_file():
                continue
            lexical_name = lexical_relative_name(
                repository_root,
                path.relative_to(repository_root),
            )
            resolve_inside(repository_root, lexical_name, allow_missing=False)
            candidates.add(lexical_name)

    return tuple(_source(repository_root, relative) for relative in sorted(candidates))


def inspect_repository(
    repository_root: Path,
    *,
    config_path: str = ".agent-policy.yml",
    state_path: str = ".agent-policy/adoption.json",
) -> AdoptionInspection:
    repository_root = repository_root.resolve()
    config_name = lexical_relative_name(repository_root, config_path)
    state_name = lexical_relative_name(repository_root, state_path)
    lock_name = lexical_relative_name(repository_root, LOCK_PATH)
    config_literal = repository_root / config_name
    state_literal = repository_root / state_name
    lock_literal = repository_root / lock_name
    config_target = resolve_inside(repository_root, config_name, allow_missing=True)
    state_target = resolve_inside(repository_root, state_name, allow_missing=True)
    lock_target = resolve_inside(repository_root, lock_name, allow_missing=True)
    inconsistent_source_artifact = _has_inconsistent_known_source_artifact(
        repository_root
    )
    sources = discover_sources(repository_root)

    config_artifact = config_literal.exists() or config_literal.is_symlink()
    state_artifact = state_literal.exists() or state_literal.is_symlink()
    lock_artifact = lock_literal.exists() or lock_literal.is_symlink()

    if config_target.exists() and config_target.is_file():
        state = "managed"
    elif config_artifact:
        state = "inconsistent"
    elif (
        inconsistent_source_artifact
        or state_artifact
        or lock_artifact
        or state_target.exists()
        or lock_target.exists()
        or any(item.generated for item in sources)
    ):
        state = "inconsistent"
    elif sources:
        state = "unmanaged-existing"
    else:
        state = "unmanaged-empty"
    return AdoptionInspection(state=state, sources=sources)


def adoption_state_schema_path() -> Path:
    return package_root() / "schemas" / "adoption-state.schema.json"


def build_adoption_state(
    *,
    toolchain_revision: str,
    config_path: str,
    state_path: str,
    primary_instructions: str,
    sources: tuple[AdoptionSource, ...],
    preview_output: str,
    selected_profiles: list[str],
    project_policy_files: list[str],
    verification_command: str | None,
    generated_skills: list[str],
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "status": "prepared",
        "toolchain": {
            "repository": "TakashiSasaki/agent-policy",
            "revision": toolchain_revision,
        },
        "config_path": config_path,
        "state_path": state_path,
        "primary_instructions": primary_instructions,
        "sources": [
            {
                "path": item.path,
                "sha256": item.sha256,
                "generated": item.generated,
            }
            for item in sources
        ],
        "preview_output": preview_output,
        "selected_profiles": list(selected_profiles),
        "project_policy_files": list(project_policy_files),
        "verification_command": verification_command,
        "generated_skills": list(generated_skills),
        "backup_path": None,
        "final_output": None,
    }


def validate_adoption_state(value: object) -> None:
    schema = json.loads(adoption_state_schema_path().read_text(encoding="utf-8"))
    errors = sorted(
        Draft202012Validator(schema).iter_errors(value),
        key=lambda item: list(item.path),
    )
    if errors:
        location = ".".join(str(part) for part in errors[0].path) or "root"
        raise ValueError(f"Invalid adoption state at {location}: {errors[0].message}")


def load_adoption_state(repository_root: Path, state_path: str) -> dict[str, Any]:
    state_name = lexical_relative_name(repository_root, state_path)
    path = resolve_inside(repository_root, state_name, allow_missing=False)
    value = json.loads(path.read_text(encoding="utf-8"))
    validate_adoption_state(value)
    if not isinstance(value, dict):
        raise ValueError("Adoption state root must be an object")
    return value


def dump_adoption_state(value: object) -> str:
    validate_adoption_state(value)
    return json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"


def immutable_adoption_sources(
    state: dict[str, Any],
) -> tuple[dict[str, Any], ...]:
    editable_policy_paths = set(state["project_policy_files"])
    editable_policy_paths.discard(state["primary_instructions"])
    return tuple(
        sorted(
            (
                item
                for item in state["sources"]
                if item["path"] not in editable_policy_paths
            ),
            key=lambda item: item["path"],
        )
    )


def changed_adoption_sources(
    repository_root: Path,
    state: dict[str, Any],
) -> tuple[str, ...]:
    changed: list[str] = []
    for item in immutable_adoption_sources(state):
        relative = item["path"]
        lexical_name = lexical_relative_name(repository_root, relative)
        path = resolve_inside(repository_root, lexical_name, allow_missing=True)
        if not path.is_file() or sha256_file(path) != item["sha256"]:
            changed.append(relative)
    return tuple(sorted(changed))


def finalized_adoption_state(
    state: dict[str, Any],
    *,
    backup_path: str,
    final_output: str,
) -> dict[str, Any]:
    result = dict(state)
    result["status"] = "finalized"
    result["backup_path"] = backup_path
    result["final_output"] = final_output
    validate_adoption_state(result)
    return result
