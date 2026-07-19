from __future__ import annotations

import os
import shutil
import tempfile
from collections.abc import Callable
from pathlib import Path
from typing import Any

from ..adoption import (
    LOCK_PATH,
    AdoptionInspection,
    build_adoption_state,
    changed_adoption_sources,
    dump_adoption_state,
    finalized_adoption_state,
    inspect_repository,
    load_adoption_state,
)
from ..config import Config, load_config, package_root
from ..diagnostics import Diagnostic
from ..lockfile import load_lock_output_paths
from ..manifest import build_manifest
from ..paths import resolve_inside
from ..renderer import GENERATED_MARKER, render_skill
from ..yamlutil import dump_yaml
from .check import run as check_run
from .render import run as render_run

DEFAULT_STATE_PATH = ".agent-policy/adoption.json"
DEFAULT_PRIMARY_INSTRUCTIONS = "AGENTS.md"
DEFAULT_PREVIEW_OUTPUT_PATH = ".agent-policy/preview/AGENTS.md"
DEFAULT_PROJECT_POLICY_FILES = ["policy/project.md"]
DEFAULT_ENABLED_SKILLS = ["validate-agent-policy"]
DEFAULT_BACKUP_PATH = ".agent-policy/adoption/original/AGENTS.md"


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
    handle = path.open("xb")
    try:
        with handle:
            handle.write(content)
    except Exception:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        raise


def _write_atomic_bytes(path: Path, content: bytes) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile("wb", dir=path.parent, delete=False) as handle:
        handle.write(content)
        temporary = Path(handle.name)
    try:
        os.replace(temporary, path)
    except Exception:
        try:
            temporary.unlink()
        except FileNotFoundError:
            pass
        raise


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


def _verification_command(config: Config) -> str | None:
    verification = config.data.get("verification")
    if not isinstance(verification, dict):
        return None
    command = verification.get("command")
    return command if isinstance(command, str) else None


def _load_prepared_context(
    repository_root: Path,
    state_path: str,
) -> tuple[dict[str, Any], Config, str]:
    repository_root = repository_root.resolve()
    state_target = resolve_inside(repository_root, state_path, allow_missing=False)
    state_name = _relative_name(repository_root, state_target)
    state = load_adoption_state(repository_root, state_name)
    if state["state_path"] != state_name:
        raise ValueError("Adoption state path does not match its recorded path")
    if state["status"] != "prepared":
        raise ValueError(f"Adoption state is not prepared: {state['status']}")

    config = load_config(repository_root, state["config_path"])
    toolchain = config.data.get("toolchain")
    if toolchain != state["toolchain"]:
        raise ValueError("Configuration toolchain does not match adoption state")
    if config.profiles != state["selected_profiles"]:
        raise ValueError("Configuration profiles do not match adoption state")
    if config.project_policy_files != state["project_policy_files"]:
        raise ValueError("Configuration project policies do not match adoption state")
    if config.output_agents_path != state["preview_output"]:
        raise ValueError("Configuration output does not match adoption preview path")
    if config.enabled_skills != state["generated_skills"]:
        raise ValueError("Configuration skills do not match adoption state")
    if _verification_command(config) != state["verification_command"]:
        raise ValueError("Configuration verification does not match adoption state")
    return state, config, state_name


def _source_change_diagnostics(
    repository_root: Path,
    state: dict[str, Any],
) -> list[Diagnostic]:
    return [
        Diagnostic(
            "error",
            "ADOPTION_SOURCE_CHANGED",
            "Recorded adoption source changed after preparation",
            relative,
        )
        for relative in changed_adoption_sources(repository_root, state)
    ]


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
            allow_missing=True,
        )
        primary_name = _relative_name(repository_root, primary_target)
        if not primary_target.is_file() or primary_name not in source_paths:
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


def preview_run(
    repository_root: Path,
    *,
    state_path: str = DEFAULT_STATE_PATH,
) -> list[Diagnostic]:
    try:
        repository_root = repository_root.resolve()
        state, _, _ = _load_prepared_context(repository_root, state_path)
        source_diagnostics = _source_change_diagnostics(repository_root, state)
        if source_diagnostics:
            return source_diagnostics
        diagnostics = render_run(repository_root, state["config_path"])
        if diagnostics:
            return diagnostics
        return check_run(repository_root, state["config_path"])
    except Exception as exc:
        return [Diagnostic("error", "ADOPT_PREVIEW", str(exc))]


def _validate_backup_path(
    repository_root: Path,
    state: dict[str, Any],
    backup_path: str,
) -> str:
    backup_target = resolve_inside(repository_root, backup_path, allow_missing=True)
    backup_name = _relative_name(repository_root, backup_target)
    protected = {
        state["config_path"],
        state["state_path"],
        state["primary_instructions"],
        state["preview_output"],
        LOCK_PATH,
        *state["project_policy_files"],
        *(item["path"] for item in state["sources"]),
        *(_generated_skill_files(state["generated_skills"])),
    }
    if backup_name in protected:
        raise ValueError("Backup path overlaps an adoption input or generated output")
    if backup_target.exists():
        raise FileExistsError(f"Backup path already exists: {backup_name}")
    return backup_name


def _stage_finalization(
    repository_root: Path,
    state: dict[str, Any],
    backup_name: str,
) -> tuple[dict[str, bytes], list[str]]:
    with tempfile.TemporaryDirectory(prefix="agent-policy-finalize-") as temporary:
        staged = Path(temporary) / "repo"
        shutil.copytree(
            repository_root,
            staged,
            ignore=shutil.ignore_patterns(".git"),
            symlinks=True,
        )

        primary_name = state["primary_instructions"]
        preview_name = state["preview_output"]
        config_name = state["config_path"]
        state_name = state["state_path"]
        staged_primary = resolve_inside(staged, primary_name, allow_missing=False)
        staged_backup = resolve_inside(staged, backup_name, allow_missing=True)
        _write_new_file(staged_backup, staged_primary.read_bytes())

        final_manifest = build_manifest(
            toolchain_revision=state["toolchain"]["revision"],
            profiles=state["selected_profiles"],
            project_policy_files=state["project_policy_files"],
            verification_command=state["verification_command"],
            agents_output_enabled=True,
            agents_output_path=primary_name,
            enabled_skills=state["generated_skills"],
        )
        staged_config = resolve_inside(staged, config_name, allow_missing=False)
        staged_config.write_text(dump_yaml(final_manifest), encoding="utf-8")
        staged_primary.unlink()

        diagnostics = render_run(staged, config_name)
        if diagnostics:
            raise RuntimeError(
                "; ".join(f"{item.code}: {item.message}" for item in diagnostics)
            )
        generated_primary = resolve_inside(staged, primary_name, allow_missing=False)
        if GENERATED_MARKER.encode("utf-8") not in generated_primary.read_bytes():
            raise ValueError("Final primary instructions do not contain the generated marker")

        staged_preview = resolve_inside(staged, preview_name, allow_missing=True)
        if staged_preview.exists():
            if not staged_preview.is_file():
                raise ValueError("Preview output is not a file")
            if GENERATED_MARKER.encode("utf-8") not in staged_preview.read_bytes():
                raise ValueError("Refusing to delete a non-generated preview file")
            staged_preview.unlink()

        final_state = finalized_adoption_state(
            state,
            backup_path=backup_name,
            final_output=primary_name,
        )
        staged_state = resolve_inside(staged, state_name, allow_missing=False)
        staged_state.write_text(dump_adoption_state(final_state), encoding="utf-8")

        diagnostics = check_run(staged, config_name)
        if diagnostics:
            raise RuntimeError(
                "; ".join(f"{item.code}: {item.message}" for item in diagnostics)
            )

        write_names = [config_name, state_name, LOCK_PATH, primary_name, backup_name]
        writes = {
            relative: resolve_inside(staged, relative, allow_missing=False).read_bytes()
            for relative in write_names
        }
        return writes, [preview_name]


def _apply_transaction(
    repository_root: Path,
    writes: dict[str, bytes],
    deletes: list[str],
    *,
    must_be_absent: set[str],
    verify: Callable[[], list[Diagnostic]] | None = None,
) -> None:
    names = sorted({*writes, *deletes})
    snapshots: dict[str, bytes | None] = {}
    for relative in names:
        path = resolve_inside(repository_root, relative, allow_missing=True)
        if path.exists() and not path.is_file():
            raise ValueError(f"Transaction path is not a file: {relative}")
        snapshots[relative] = path.read_bytes() if path.is_file() else None
    conflicts = sorted(relative for relative in must_be_absent if snapshots[relative] is not None)
    if conflicts:
        raise FileExistsError(f"Paths must not exist: {', '.join(conflicts)}")

    created_by_transaction: set[str] = set()
    try:
        for relative in sorted(writes):
            path = resolve_inside(repository_root, relative, allow_missing=True)
            if relative in must_be_absent:
                _write_new_file(path, writes[relative])
            else:
                _write_atomic_bytes(path, writes[relative])
            if snapshots[relative] is None:
                created_by_transaction.add(relative)
        for relative in sorted(deletes):
            path = resolve_inside(repository_root, relative, allow_missing=False)
            path.unlink()
        if verify is not None:
            diagnostics = verify()
            if diagnostics:
                raise RuntimeError(
                    "; ".join(f"{item.code}: {item.message}" for item in diagnostics)
                )
    except Exception as exc:
        rollback_errors: list[str] = []
        for relative in reversed(names):
            path = resolve_inside(repository_root, relative, allow_missing=True)
            original = snapshots[relative]
            try:
                if original is None:
                    if relative in created_by_transaction and path.exists():
                        path.unlink()
                else:
                    _write_atomic_bytes(path, original)
            except Exception as rollback_exc:
                rollback_errors.append(f"{relative}: {rollback_exc}")
        if rollback_errors:
            raise RuntimeError(
                f"Transaction failed ({exc}); rollback failed: {', '.join(rollback_errors)}"
            ) from exc
        raise


def finalize_run(
    repository_root: Path,
    *,
    state_path: str = DEFAULT_STATE_PATH,
    backup_path: str = DEFAULT_BACKUP_PATH,
    apply: bool,
) -> list[Diagnostic]:
    try:
        repository_root = repository_root.resolve()
        state, _, _ = _load_prepared_context(repository_root, state_path)
        source_diagnostics = _source_change_diagnostics(repository_root, state)
        if source_diagnostics:
            return source_diagnostics

        diagnostics = check_run(repository_root, state["config_path"])
        if diagnostics:
            return diagnostics
        backup_name = _validate_backup_path(repository_root, state, backup_path)
        writes, deletes = _stage_finalization(repository_root, state, backup_name)
        plan = [
            Diagnostic("info", "CREATE", "Backup original instructions", backup_name),
            Diagnostic(
                "info",
                "REPLACE",
                "Replace primary instructions with generated output",
                state["primary_instructions"],
            ),
            Diagnostic("info", "UPDATE", "Activate final instruction output", state["config_path"]),
            Diagnostic("info", "UPDATE", "Record finalized adoption state", state["state_path"]),
            Diagnostic("info", "DELETE", "Remove generated preview", state["preview_output"]),
        ]
        if not apply:
            return plan

        source_diagnostics = _source_change_diagnostics(repository_root, state)
        if source_diagnostics:
            return source_diagnostics
        _apply_transaction(
            repository_root,
            writes,
            deletes,
            must_be_absent={backup_name},
            verify=lambda: check_run(repository_root, state["config_path"]),
        )
        return []
    except Exception as exc:
        return [Diagnostic("error", "ADOPT_FINALIZE", str(exc))]
