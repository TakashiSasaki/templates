from __future__ import annotations

import shutil
import tempfile
from pathlib import Path

from ..adoption import (
    LOCK_PATH,
    AdoptionInspection,
    build_adoption_state,
    dump_adoption_state,
    inspect_repository,
)
from ..config import package_root
from ..diagnostics import Diagnostic
from ..lockfile import load_lock_output_paths
from ..manifest import build_manifest
from ..paths import resolve_inside
from ..renderer import render_skill
from ..yamlutil import dump_yaml
from .render import run as render_run

DEFAULT_STATE_PATH = ".agent-policy/adoption.json"
DEFAULT_PRIMARY_INSTRUCTIONS = "AGENTS.md"
DEFAULT_PREVIEW_OUTPUT_PATH = ".agent-policy/preview/AGENTS.md"
DEFAULT_PROJECT_POLICY_FILES = ["policy/project.md"]
DEFAULT_ENABLED_SKILLS = ["validate-agent-policy"]


def _inspection_diagnostics(inspection: AdoptionInspection) -> list[Diagnostic]:
    diagnostics = [Diagnostic("info", "ADOPTION_STATE", inspection.state)]
    diagnostics.extend(
        Diagnostic(
            "info",
            "ADOPTION_SOURCE",
            f"sha256={item.sha256}; generated={str(item.generated).lower()}",
            item.path,
        )
        for item in inspection.sources
    )
    return diagnostics


def inspect_run(
    repository_root: Path,
    config_path: str,
    *,
    state_path: str = DEFAULT_STATE_PATH,
) -> list[Diagnostic]:
    try:
        inspection = inspect_repository(
            repository_root,
            config_path=config_path,
            state_path=state_path,
        )
        return _inspection_diagnostics(inspection)
    except Exception as exc:
        return [Diagnostic("error", "ADOPT_INSPECT", str(exc))]


def _relative_name(repository_root: Path, path: Path) -> str:
    return path.relative_to(repository_root.resolve()).as_posix()


def _resolve_names(repository_root: Path, values: list[str]) -> list[tuple[str, Path]]:
    result: list[tuple[str, Path]] = []
    for value in values:
        path = resolve_inside(repository_root, value, allow_missing=True)
        result.append((_relative_name(repository_root, path), path))
    return result


def _generated_skill_files(skills: list[str]) -> list[str]:
    result: list[str] = []
    for skill in skills:
        for relative in render_skill(skill):
            result.append(f".agents/skills/{skill}/{relative}")
    return sorted(result)


def _write_new_file(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("xb") as handle:
        handle.write(content)


def _remove_created(paths: list[Path]) -> None:
    for path in reversed(paths):
        try:
            path.unlink()
        except FileNotFoundError:
            pass


def _state_error(state: str) -> Diagnostic | None:
    if state == "managed":
        return Diagnostic(
            "error",
            "ALREADY_MANAGED",
            "Repository already contains an agent-policy configuration",
        )
    if state == "unmanaged-empty":
        return Diagnostic(
            "error",
            "ADOPT_REQUIRES_EXISTING",
            "No existing instruction or policy sources were found; use init instead",
        )
    if state == "inconsistent":
        return Diagnostic(
            "error",
            "ADOPTION_INCONSISTENT",
            "Repository contains partial or generated agent-policy artifacts",
        )
    return None


def prepare_run(
    repository_root: Path,
    config_path: str,
    *,
    apply: bool,
    toolchain_revision: str,
    profiles: list[str],
    primary_instructions: str = DEFAULT_PRIMARY_INSTRUCTIONS,
    state_path: str = DEFAULT_STATE_PATH,
    project_policy_files: list[str] | None = None,
    verification_command: str | None = None,
    preview_output_path: str = DEFAULT_PREVIEW_OUTPUT_PATH,
    enabled_skills: list[str] | None = None,
) -> list[Diagnostic]:
    created: list[Path] = []
    try:
        repository_root = repository_root.resolve()
        policies = (
            list(DEFAULT_PROJECT_POLICY_FILES)
            if project_policy_files is None
            else list(project_policy_files)
        )
        skills = (
            list(DEFAULT_ENABLED_SKILLS) if enabled_skills is None else list(enabled_skills)
        )
        if not policies:
            raise ValueError("At least one project policy file is required")
        if len(set(policies)) != len(policies):
            raise ValueError("Project policy files must be unique")

        inspection = inspect_repository(
            repository_root,
            config_path=config_path,
            state_path=state_path,
        )
        error = _state_error(inspection.state)
        if error is not None:
            return [error]

        source_paths = {item.path for item in inspection.sources}
        primary_target = resolve_inside(
            repository_root,
            primary_instructions,
            allow_missing=False,
        )
        primary_name = _relative_name(repository_root, primary_target)
        if primary_name not in source_paths:
            return [
                Diagnostic(
                    "error",
                    "PRIMARY_INSTRUCTIONS",
                    "Primary instructions must be one of the discovered sources",
                    primary_name,
                )
            ]

        config_target = resolve_inside(repository_root, config_path, allow_missing=True)
        state_target = resolve_inside(repository_root, state_path, allow_missing=True)
        preview_target = resolve_inside(
            repository_root,
            preview_output_path,
            allow_missing=True,
        )
        config_name = _relative_name(repository_root, config_target)
        state_name = _relative_name(repository_root, state_target)
        preview_name = _relative_name(repository_root, preview_target)

        policy_targets = _resolve_names(repository_root, policies)
        missing_policies: list[str] = []
        for relative, target in policy_targets:
            if target.exists() and not target.is_file():
                raise ValueError(f"Project policy path is not a file: {relative}")
            if not target.exists():
                missing_policies.append(relative)
        if len(missing_policies) > 1:
            raise ValueError("adopt prepare can scaffold at most one missing project policy")

        generated_skill_files = _generated_skill_files(skills)
        reserved = {
            config_name,
            state_name,
            LOCK_PATH,
            preview_name,
            *generated_skill_files,
        }
        policy_names = {relative for relative, _ in policy_targets}
        if len(reserved) != 4 + len(generated_skill_files):
            raise ValueError("Generated and management paths must be unique")
        collisions = sorted(reserved & source_paths)
        if collisions:
            raise ValueError(f"Adoption outputs overlap existing sources: {', '.join(collisions)}")
        if reserved & policy_names:
            raise ValueError("Generated or management paths overlap project policy files")

        conflict_names = [config_name, state_name, LOCK_PATH, preview_name, *generated_skill_files]
        conflicts = [
            relative
            for relative in conflict_names
            if resolve_inside(repository_root, relative, allow_missing=True).exists()
        ]
        if conflicts:
            return [
                Diagnostic(
                    "error",
                    "FILE_CONFLICT",
                    f"Existing files would conflict: {', '.join(sorted(conflicts))}",
                )
            ]

        manifest = build_manifest(
            toolchain_revision=toolchain_revision,
            profiles=profiles,
            project_policy_files=[relative for relative, _ in policy_targets],
            verification_command=verification_command,
            agents_output_enabled=True,
            agents_output_path=preview_name,
            enabled_skills=skills,
        )
        plan = [
            Diagnostic("info", "PRESERVE", "Existing primary instructions", primary_name),
            Diagnostic("info", "CREATE", config_name),
            Diagnostic("info", "CREATE", state_name),
        ]
        plan.extend(Diagnostic("info", "CREATE", relative) for relative in missing_policies)
        plan.append(Diagnostic("info", "GENERATE", preview_name))
        plan.extend(
            Diagnostic("info", "GENERATE", relative) for relative in generated_skill_files
        )
        plan.append(Diagnostic("info", "GENERATE", LOCK_PATH))

        with tempfile.TemporaryDirectory(prefix="agent-policy-adopt-") as temporary:
            staged = Path(temporary) / "repo"
            shutil.copytree(
                repository_root,
                staged,
                ignore=shutil.ignore_patterns(".git"),
                symlinks=True,
            )
            staged_config = resolve_inside(staged, config_name, allow_missing=True)
            staged_config.parent.mkdir(parents=True, exist_ok=True)
            staged_config.write_text(dump_yaml(manifest), encoding="utf-8")

            project_template = (
                package_root() / "templates" / "project-policy.md.j2"
            ).read_text(encoding="utf-8")
            for relative in missing_policies:
                target = resolve_inside(staged, relative, allow_missing=True)
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text(project_template, encoding="utf-8")

            diagnostics = render_run(staged, config_name)
            if diagnostics:
                return diagnostics

            state = build_adoption_state(
                toolchain_revision=toolchain_revision,
                config_path=config_name,
                state_path=state_name,
                primary_instructions=primary_name,
                sources=inspection.sources,
                preview_output=preview_name,
                selected_profiles=profiles,
                project_policy_files=[relative for relative, _ in policy_targets],
                verification_command=verification_command,
                generated_skills=skills,
            )
            staged_state = resolve_inside(staged, state_name, allow_missing=True)
            staged_state.parent.mkdir(parents=True, exist_ok=True)
            staged_state.write_text(dump_adoption_state(state), encoding="utf-8")

            staged_lock = resolve_inside(staged, LOCK_PATH, allow_missing=False)
            generated_outputs = list(load_lock_output_paths(staged_lock))
            if not apply:
                return plan

            apply_names = sorted(
                {
                    config_name,
                    state_name,
                    LOCK_PATH,
                    *missing_policies,
                    *generated_outputs,
                }
            )
            for relative in apply_names:
                source = resolve_inside(staged, relative, allow_missing=False)
                target = resolve_inside(repository_root, relative, allow_missing=True)
                if target.exists():
                    raise FileExistsError(f"Refusing to overwrite existing file: {relative}")
                _write_new_file(target, source.read_bytes())
                created.append(target)
        return []
    except Exception as exc:
        _remove_created(created)
        return [Diagnostic("error", "ADOPT_PREPARE", str(exc))]
