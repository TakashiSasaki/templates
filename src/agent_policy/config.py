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
class OverrideDeclaration:
    id: str
    reason: str


@dataclass(frozen=True)
class PolicyContext:
    name: str
    profiles: tuple[str, ...]
    project_policy_files: tuple[str, ...]
    overrides: tuple[OverrideDeclaration, ...]

    @property
    def override_reasons(self) -> dict[str, str]:
        return {item.id: item.reason for item in self.overrides}


@dataclass(frozen=True)
class OutputSpec:
    name: str
    enabled: bool
    path: str
    context: str
    renderer: str


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
    def schema_version(self) -> int:
        value = self.data.get("schema_version")
        return value if isinstance(value, int) and not isinstance(value, bool) else 0

    @property
    def contexts(self) -> dict[str, PolicyContext]:
        if self.schema_version == 1:
            profiles = self.data.get("profiles")
            project_policy = self.data.get("project_policy")
            if not isinstance(profiles, list) or not isinstance(project_policy, dict):
                return {}
            files = project_policy.get("files")
            if not isinstance(files, list):
                return {}
            return {
                "default": PolicyContext(
                    name="default",
                    profiles=tuple(item for item in profiles if isinstance(item, str)),
                    project_policy_files=tuple(
                        item for item in files if isinstance(item, str)
                    ),
                    overrides=(),
                )
            }

        raw_contexts = self.data.get("contexts")
        if not isinstance(raw_contexts, dict):
            return {}

        result: dict[str, PolicyContext] = {}
        for name, raw in raw_contexts.items():
            if not isinstance(name, str) or not isinstance(raw, dict):
                continue
            profiles = raw.get("profiles")
            project_policy = raw.get("project_policy")
            files = (
                project_policy.get("files")
                if isinstance(project_policy, dict)
                else None
            )
            raw_overrides = raw.get("overrides", [])
            if (
                not isinstance(profiles, list)
                or not isinstance(files, list)
                or not isinstance(raw_overrides, list)
            ):
                continue
            overrides: list[OverrideDeclaration] = []
            for item in raw_overrides:
                if not isinstance(item, dict):
                    continue
                rule_id = item.get("id")
                reason = item.get("reason")
                if isinstance(rule_id, str) and isinstance(reason, str):
                    overrides.append(OverrideDeclaration(rule_id, reason))
            result[name] = PolicyContext(
                name=name,
                profiles=tuple(item for item in profiles if isinstance(item, str)),
                project_policy_files=tuple(
                    item for item in files if isinstance(item, str)
                ),
                overrides=tuple(overrides),
            )
        return result

    @property
    def profiles(self) -> list[str]:
        default = self.contexts.get("default")
        return list(default.profiles) if default is not None else []

    @property
    def project_policy_files(self) -> list[str]:
        result: list[str] = []
        seen: set[str] = set()
        for context in self.contexts.values():
            for relative in context.project_policy_files:
                if relative in seen:
                    continue
                seen.add(relative)
                result.append(relative)
        return result

    @property
    def output_specs(self) -> tuple[OutputSpec, ...]:
        raw_outputs = self.data.get("outputs")
        if not isinstance(raw_outputs, dict):
            return ()

        if self.schema_version == 1:
            item = raw_outputs.get("agents")
            if not isinstance(item, dict):
                return ()
            path = item.get("path")
            enabled = item.get("enabled")
            if not isinstance(path, str) or not isinstance(enabled, bool):
                return ()
            return (
                OutputSpec(
                    name="agents",
                    enabled=enabled,
                    path=path,
                    context="default",
                    renderer="agents-md",
                ),
            )

        result: list[OutputSpec] = []
        for name, item in raw_outputs.items():
            if not isinstance(name, str) or not isinstance(item, dict):
                continue
            path = item.get("path")
            enabled = item.get("enabled")
            context = item.get("context")
            renderer = item.get("renderer")
            if (
                not isinstance(path, str)
                or not isinstance(enabled, bool)
                or not isinstance(context, str)
                or not isinstance(renderer, str)
            ):
                continue
            result.append(
                OutputSpec(
                    name=name,
                    enabled=enabled,
                    path=path,
                    context=context,
                    renderer=renderer,
                )
            )
        return tuple(result)

    @property
    def configured_output_paths(self) -> list[str]:
        return [item.path for item in self.output_specs]

    @property
    def configured_agents_path(self) -> str | None:
        for item in self.output_specs:
            if item.name == "agents" and item.renderer == "agents-md":
                return item.path
        return None

    @property
    def output_agents_path(self) -> str | None:
        for item in self.output_specs:
            if (
                item.name == "agents"
                and item.renderer == "agents-md"
                and item.enabled
            ):
                return item.path
        return None

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
    invalid_policy_inputs = False
    for context in config.contexts.values():
        profile_path = (
            "profiles"
            if config.schema_version == 1
            else f"contexts.{context.name}.profiles"
        )
        for profile in context.profiles:
            if not (profiles_dir / f"{profile}.yml").is_file():
                invalid_policy_inputs = True
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "UNKNOWN_PROFILE",
                        f"Unknown profile: {profile}",
                        profile_path,
                    )
                )
        if len(set(context.profiles)) != len(context.profiles):
            diagnostics.append(
                Diagnostic(
                    "error",
                    "DUPLICATE_PROFILE",
                    "Profiles must be unique",
                    profile_path,
                )
            )

        override_ids = [item.id for item in context.overrides]
        if len(override_ids) != len(set(override_ids)):
            diagnostics.append(
                Diagnostic(
                    "error",
                    "DUPLICATE_OVERRIDE",
                    "Override rule IDs must be unique within a context",
                    f"contexts.{context.name}.overrides",
                )
            )

    for output in config.output_specs:
        if output.context not in config.contexts:
            diagnostics.append(
                Diagnostic(
                    "error",
                    "UNKNOWN_CONTEXT",
                    f"Unknown policy context: {output.context}",
                    f"outputs.{output.name}.context",
                )
            )

    for policy_file in config.project_policy_files:
        try:
            path = resolve_inside(repository_root, policy_file, allow_missing=False)
        except (ValueError, FileNotFoundError) as exc:
            invalid_policy_inputs = True
            diagnostics.append(Diagnostic("error", "POLICY_PATH", str(exc), policy_file))
            continue
        if not path.is_file():
            invalid_policy_inputs = True
            diagnostics.append(
                Diagnostic(
                    "error",
                    "MISSING_POLICY",
                    "Project policy file does not exist",
                    policy_file,
                )
            )

    if not invalid_policy_inputs:
        from .policy_loader import load_rules

        for context in config.contexts.values():
            try:
                load_rules(
                    repository_root,
                    list(context.profiles),
                    list(context.project_policy_files),
                    declared_overrides=context.override_reasons,
                    require_explicit_overrides=config.schema_version >= 2,
                )
            except Exception as exc:
                diagnostics.append(
                    Diagnostic(
                        "error",
                        "POLICY_COMPOSITION",
                        str(exc),
                        f"contexts.{context.name}",
                    )
                )

    try:
        reserved_lock_path = resolve_lock_path(repository_root, allow_missing=True)
    except ValueError as exc:
        diagnostics.append(Diagnostic("error", "LOCK_PATH", str(exc), LOCK_PATH))
        reserved_lock_path = None

    output_paths = config.configured_output_paths
    if len(output_paths) != len(set(output_paths)):
        diagnostics.append(
            Diagnostic("error", "OUTPUT_COLLISION", "Output paths must be unique")
        )
    for output in output_paths:
        try:
            resolved_output = resolve_inside(repository_root, output, allow_missing=True)
        except ValueError as exc:
            diagnostics.append(Diagnostic("error", "OUTPUT_PATH", str(exc), output))
            continue
        if reserved_lock_path is not None and _paths_overlap(
            resolved_output,
            reserved_lock_path,
        ):
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
