from __future__ import annotations


def build_manifest(
    *,
    toolchain_revision: str,
    profiles: list[str],
    project_policy_files: list[str],
    verification_command: str | None,
    agents_output_enabled: bool,
    agents_output_path: str,
    enabled_skills: list[str],
) -> dict[str, object]:
    manifest: dict[str, object] = {
        "schema_version": 1,
        "toolchain": {
            "repository": "TakashiSasaki/agent-policy",
            "revision": toolchain_revision,
        },
        "profiles": list(profiles),
        "project_policy": {"files": list(project_policy_files)},
        "outputs": {
            "agents": {
                "enabled": agents_output_enabled,
                "path": agents_output_path,
            }
        },
        "skills": {"enabled": list(enabled_skills)},
    }
    if verification_command is not None:
        manifest["verification"] = {"command": verification_command}
    return manifest
