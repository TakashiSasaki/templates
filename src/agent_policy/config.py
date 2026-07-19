from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .diagnostics import Diagnostic
from .lockfile import LOCK_PATH, resolve_lock_path
from .paths import resolve_inside
from .yamlutil import load_yaml


@dataclass(frozen=True)
class Config:
    path: Path
    data: dict[str, Any]
    repository_root: Path | None = None

    @property
    def relative_path(self) -> str:
        if self.repository_root is None:
            return self.path.name
        return self.path.relative_to(self.repository_root).as_posix()

    @property
    def profiles(self) -> list[str]:
        return list(self.data.get("profiles", []))

    @property
    def project_policy_files(self) -> list[str]:
        return list(self.data.get("project_policy", {}).get("files", []))

    @property
    def configured_agents_path(self) -> str | None:
        item = self.data.get("outputs", {}).get("agents", {})
        path = item.get("path")
        return path if isinstance(path, str) else None

    @property
    def output_agents_path(self) -> str | None:
        item = self.data.get("outputs", {}).get("agents", {})
        return self.configured_agents_path if item.get("enabled", False) else None

    @property
    def enabled_skills(self) -> list[str]:
        return list(self.data.get("skills", {}).get("enabled", []))


def package_root() -> Path:
    source_root = Path(__file__).resolve().parents[2]
    if (source_root / "schemas").is_dir():
        return source_root
    installed_data = Path(__file__).resolve().parent / "_data"
    if installed_data.is_dir():
        return installed_data
    raise FileNotFoundError("agent-policy resource data is unavailable")


def schema_path() -> Path:
    return package_root() / "schemas" / "agent-policy.schema.json"


def load_config(repository_root: Path, config_path: str | Path) -> Config:
    root = repository_root.resolve()
    path = resolve_inside(root, config_path, allow_missing=False)
    value = load_yaml(path)
    if not isinstance(value, dict):
        raise ValueError("Configuration root must be a mapping")
    return Config(path=path, data=value, repository_root=root)


def _paths_overlap(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def validate_config(repository_root: Path, config: Config) -> list[Diagnostic]:
    import json

    schema = json.loads(schema_path().read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    diagnostics: list[Diagnostic] = []
    for error in sorted(validator.iter_errors(config.data), key=lambda item: list(item.path)):
        location = ".".join(str(part) for part in error.path) or None
        diagnostics.append(Diagnostic("error", "SCHEMA", error.message, location))

    profiles_dir = package_root() / "profiles"
    for profile in config.profiles:
        if not (profiles_dir / f"{profile}.yml").is_file():
            diagnostics.append(
                Diagnostic("error", "UNKNOWN_PROFILE", f"Unknown profile: {profile}", "profiles")
            )
    if len(set(config.profiles)) != len(config.profiles):
        diagnostics.append(Diagnostic("error", "DUPLICATE_PROFILE", "Profiles must be unique"))

    for policy_file in config.project_policy_files:
        try:
            path = resolve_inside(repository_root, policy_file, allow_missing=False)
        except (ValueError, FileNotFoundError) as exc:
            diagnostics.append(Diagnostic("error", "POLICY_PATH", str(exc), policy_file))
            continue
        if not path.is_file():
            diagnostics.append(
                Diagnostic(
                    "error",
                    "MISSING_POLICY",
                    "Project policy file does not exist",
                    policy_file,
                )
            )

    try:
        reserved_lock_path = resolve_lock_path(repository_root, allow_missing=True)
    except ValueError as exc:
        diagnostics.append(Diagnostic("error", "LOCK_PATH", str(exc), LOCK_PATH))
        reserved_lock_path = None

    output_paths = [path for path in [config.configured_agents_path] if path]
    if len(output_paths) != len(set(output_paths)):
        diagnostics.append(Diagnostic("error", "OUTPUT_COLLISION", "Output paths must be unique"))
    for output in output_paths:
        try:
            resolved_output = resolve_inside(repository_root, output, allow_missing=True)
        except ValueError as exc:
            diagnostics.append(Diagnostic("error", "OUTPUT_PATH", str(exc), output))
            continue
        if reserved_lock_path is not None and _paths_overlap(resolved_output, reserved_lock_path):
            diagnostics.append(
                Diagnostic(
                    "error",
                    "RESERVED_OUTPUT_PATH",
                    f"Output overlaps reserved generated path: {LOCK_PATH}",
                    output,
                )
            )
        if output in config.project_policy_files or output == config.relative_path:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "INPUT_OUTPUT_COLLISION",
                    "Output would overwrite an input",
                    output,
                )
            )
    return diagnostics
