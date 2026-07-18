from __future__ import annotations

import re
from pathlib import Path

from ..config import package_root
from ..diagnostics import Diagnostic
from ..manifest import build_manifest
from ..paths import resolve_inside
from ..renderer import render_skill
from ..yamlutil import dump_yaml
from .render import run as render_run

DEFAULT_PROJECT_POLICY_FILES = ["policy/project.md"]
DEFAULT_VERIFICATION_COMMAND = "./scripts/verify.sh"
DEFAULT_AGENTS_OUTPUT_PATH = "AGENTS.md"
DEFAULT_ENABLED_SKILLS = ["validate-agent-policy"]
LOCK_PATH = ".agent-policy.lock"
SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")


def proposed_manifest(
    toolchain_revision: str,
    profiles: list[str],
    *,
    project_policy_files: list[str] | None = None,
    verification_command: str | None = DEFAULT_VERIFICATION_COMMAND,
    agents_output_enabled: bool = True,
    agents_output_path: str = DEFAULT_AGENTS_OUTPUT_PATH,
    enabled_skills: list[str] | None = None,
) -> dict[str, object]:
    policies = (
        DEFAULT_PROJECT_POLICY_FILES if project_policy_files is None else project_policy_files
    )
    skills = DEFAULT_ENABLED_SKILLS if enabled_skills is None else enabled_skills
    return build_manifest(
        toolchain_revision=toolchain_revision,
        profiles=profiles,
        project_policy_files=policies,
        verification_command=verification_command,
        agents_output_enabled=agents_output_enabled,
        agents_output_path=agents_output_path,
        enabled_skills=skills,
    )


def _generated_skill_outputs(skills: list[str]) -> list[tuple[str, str]]:
    outputs: list[tuple[str, str]] = []
    for skill in skills:
        if SKILL_NAME_PATTERN.fullmatch(skill) is None:
            raise ValueError(f"Invalid generated skill name: {skill}")
        for relative in render_skill(skill):
            outputs.append((f"generated skill {skill}", f".agents/skills/{skill}/{relative}"))
    return outputs


def _paths_overlap(left: Path, right: Path) -> bool:
    return left == right or left in right.parents or right in left.parents


def _planned_path_collision(
    repository_root: Path,
    planned: list[tuple[str, str, Path]],
) -> Diagnostic | None:
    collisions: list[str] = []
    for index, (left_role, _left_relative, left_target) in enumerate(planned):
        for right_role, _right_relative, right_target in planned[index + 1 :]:
            if not _paths_overlap(left_target, right_target):
                continue
            left_name = left_target.relative_to(repository_root).as_posix()
            right_name = right_target.relative_to(repository_root).as_posix()
            collisions.append(
                f"{left_name} ({left_role}) overlaps {right_name} ({right_role})"
            )
    if not collisions:
        return None
    return Diagnostic(
        "error",
        "INIT_PATH_COLLISION",
        f"Planned init paths collide: {'; '.join(collisions)}",
    )


def _planned_path_conflict(
    repository_root: Path,
    planned: list[tuple[str, str, Path]],
    *,
    ignore_existing: set[Path],
) -> Diagnostic | None:
    conflicts: list[str] = []
    for role, relative, target in planned:
        if target not in ignore_existing and target.exists():
            conflicts.append(f"{relative} ({role}) already exists")
        for parent in target.parents:
            if parent == repository_root:
                break
            if parent.exists() and not parent.is_dir():
                parent_name = parent.relative_to(repository_root).as_posix()
                conflicts.append(
                    f"{relative} ({role}) is blocked by non-directory ancestor {parent_name}"
                )
                break
    if not conflicts:
        return None
    return Diagnostic(
        "error",
        "FILE_CONFLICT",
        f"Existing paths would conflict: {'; '.join(conflicts)}",
    )


def run(
    repository_root: Path,
    config_path: str,
    *,
    apply: bool,
    toolchain_revision: str,
    profiles: list[str],
    project_policy_files: list[str] | None = None,
    verification_command: str | None = DEFAULT_VERIFICATION_COMMAND,
    agents_output_enabled: bool = True,
    agents_output_path: str = DEFAULT_AGENTS_OUTPUT_PATH,
    enabled_skills: list[str] | None = None,
) -> list[Diagnostic]:
    repository_root = repository_root.resolve()
    policies = (
        DEFAULT_PROJECT_POLICY_FILES if project_policy_files is None else project_policy_files
    )
    skills = DEFAULT_ENABLED_SKILLS if enabled_skills is None else enabled_skills
    if len(policies) != 1:
        return [
            Diagnostic(
                "error",
                "INIT_PROJECT_POLICY_COUNT",
                "init requires exactly one project policy scaffold",
            )
        ]

    config_target = resolve_inside(repository_root, config_path)
    if config_target.exists():
        return [Diagnostic("error", "ALREADY_INITIALIZED", f"{config_path} already exists")]

    project_targets = [resolve_inside(repository_root, relative) for relative in policies]
    try:
        generated_skill_outputs = _generated_skill_outputs(skills)
    except Exception as exc:
        return [Diagnostic("error", "INIT_SKILL", str(exc))]

    planned = [("configuration", config_path, config_target)]
    planned.extend(
        ("project policy", relative, target)
        for relative, target in zip(policies, project_targets, strict=True)
    )
    if agents_output_enabled:
        agents_target = resolve_inside(repository_root, agents_output_path)
        planned.append(("agent output", agents_output_path, agents_target))
    for role, relative in generated_skill_outputs:
        planned.append((role, relative, resolve_inside(repository_root, relative)))
    lock_target = resolve_inside(repository_root, LOCK_PATH)
    planned.append(("lock", LOCK_PATH, lock_target))

    collision = _planned_path_collision(repository_root, planned)
    if collision is not None:
        return [collision]

    conflict = _planned_path_conflict(
        repository_root,
        planned,
        ignore_existing={config_target},
    )
    if conflict is not None:
        return [conflict]

    generated_skills = [relative for _role, relative in generated_skill_outputs]
    if not apply:
        diagnostics = [Diagnostic("info", "CREATE", config_path)]
        diagnostics.extend(Diagnostic("info", "CREATE", relative) for relative in policies)
        if agents_output_enabled:
            diagnostics.append(Diagnostic("info", "GENERATE", agents_output_path))
        diagnostics.extend(
            Diagnostic("info", "GENERATE", relative) for relative in generated_skills
        )
        diagnostics.append(Diagnostic("info", "GENERATE", LOCK_PATH))
        return diagnostics

    manifest = proposed_manifest(
        toolchain_revision,
        profiles,
        project_policy_files=policies,
        verification_command=verification_command,
        agents_output_enabled=agents_output_enabled,
        agents_output_path=agents_output_path,
        enabled_skills=skills,
    )
    config_target.parent.mkdir(parents=True, exist_ok=True)
    config_target.write_text(dump_yaml(manifest), encoding="utf-8")

    project_template = (package_root() / "templates" / "project-policy.md.j2").read_text(
        encoding="utf-8"
    )
    for project_target in project_targets:
        project_target.parent.mkdir(parents=True, exist_ok=True)
        project_target.write_text(project_template, encoding="utf-8")
    return render_run(repository_root, config_path)
