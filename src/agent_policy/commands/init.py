from __future__ import annotations

from pathlib import Path

from ..config import package_root
from ..diagnostics import Diagnostic
from ..paths import resolve_inside
from ..yamlutil import dump_yaml
from .render import run as render_run


def proposed_manifest(toolchain_revision: str, profiles: list[str]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "toolchain": {
            "repository": "TakashiSasaki/agent-policy",
            "revision": toolchain_revision,
        },
        "profiles": profiles,
        "project_policy": {"files": ["policy/project.md"]},
        "verification": {"command": "./scripts/verify.sh"},
        "outputs": {"agents": {"enabled": True, "path": "AGENTS.md"}},
        "skills": {"enabled": ["validate-agent-policy"]},
    }


def run(
    repository_root: Path,
    config_path: str,
    *,
    apply: bool,
    toolchain_revision: str,
    profiles: list[str],
) -> list[Diagnostic]:
    config_target = resolve_inside(repository_root, config_path)
    if config_target.exists():
        return [Diagnostic("error", "ALREADY_INITIALIZED", f"{config_path} already exists")]
    project_target = resolve_inside(repository_root, "policy/project.md")
    agents_target = resolve_inside(repository_root, "AGENTS.md")
    conflicts = [str(path.relative_to(repository_root)) for path in [project_target, agents_target] if path.exists()]
    if conflicts:
        return [Diagnostic("error", "FILE_CONFLICT", f"Existing files would conflict: {', '.join(conflicts)}")]
    if not apply:
        return [
            Diagnostic("info", "CREATE", config_path),
            Diagnostic("info", "CREATE", "policy/project.md"),
            Diagnostic("info", "GENERATE", "AGENTS.md"),
            Diagnostic("info", "GENERATE", ".agents/skills/validate-agent-policy/SKILL.md"),
            Diagnostic("info", "GENERATE", ".agent-policy.lock"),
        ]
    config_target.parent.mkdir(parents=True, exist_ok=True)
    config_target.write_text(dump_yaml(proposed_manifest(toolchain_revision, profiles)), encoding="utf-8")
    project_target.parent.mkdir(parents=True, exist_ok=True)
    project_template = (package_root() / "templates" / "project-policy.md.j2").read_text(encoding="utf-8")
    project_target.write_text(project_template, encoding="utf-8")
    return render_run(repository_root, config_path)
