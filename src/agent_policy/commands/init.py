from __future__ import annotations

from pathlib import Path

from ..config import package_root
from ..diagnostics import Diagnostic
from ..manifest import build_manifest
from ..paths import resolve_inside
from ..yamlutil import dump_yaml
from .render import run as render_run


DEFAULT_PROJECT_POLICY_FILES = ["policy/project.md"]
DEFAULT_VERIFICATION_COMMAND = "./scripts/verify.sh"
DEFAULT_AGENTS_OUTPUT_PATH = "AGENTS.md"
DEFAULT_ENABLED_SKILLS = ["validate-agent-policy"]


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
    policies = DEFAULT_PROJECT_POLICY_FILES if project_policy_files is None else project_policy_files
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
    policies = DEFAULT_PROJECT_POLICY_FILES if project_policy_files is None else project_policy_files
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
    agents_target = (
        resolve_inside(repository_root, agents_output_path) if agents_output_enabled else None
    )
    conflict_targets = [*project_targets]
    if agents_target is not None:
        conflict_targets.append(agents_target)
    conflicts = [
        str(path.relative_to(repository_root)) for path in conflict_targets if path.exists()
    ]
    if conflicts:
        return [
            Diagnostic(
                "error",
                "FILE_CONFLICT",
                f"Existing files would conflict: {', '.join(conflicts)}",
            )
        ]

    generated_skills = [f".agents/skills/{skill}/SKILL.md" for skill in skills]
    if not apply:
        diagnostics = [Diagnostic("info", "CREATE", config_path)]
        diagnostics.extend(Diagnostic("info", "CREATE", relative) for relative in policies)
        if agents_output_enabled:
            diagnostics.append(Diagnostic("info", "GENERATE", agents_output_path))
        diagnostics.extend(Diagnostic("info", "GENERATE", relative) for relative in generated_skills)
        diagnostics.append(Diagnostic("info", "GENERATE", ".agent-policy.lock"))
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
