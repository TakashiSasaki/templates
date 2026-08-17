from __future__ import annotations

from pathlib import Path
from typing import Any

from ..adoption import inspect_repository
from ..diagnostics import Diagnostic
from . import adopt as adopt_command
from . import init as init_command

UNSET: Any = object()


def prepare_run(
    repository_root: Path,
    config_path: str,
    *,
    apply: bool,
    toolchain_revision: str,
    profiles: list[str],
    primary_instructions: str | None = None,
    state_path: str = adopt_command.DEFAULT_STATE_PATH,
    project_policy_files: list[str] | None = None,
    verification_command: str | None | Any = UNSET,
    preview_output_path: str = adopt_command.DEFAULT_PREVIEW_OUTPUT_PATH,
    enabled_skills: list[str] | None = None,
) -> list[Diagnostic]:
    """Prepare adoption using a state-selected internal strategy.

    `unmanaged-empty` delegates to the existing initialization primitive and
    completes fresh adoption directly. `unmanaged-existing` delegates to the
    staged migration-adoption transaction.
    """

    try:
        inspection = inspect_repository(
            repository_root,
            config_path=config_path,
            state_path=state_path,
        )
    except Exception as exc:
        return [Diagnostic("error", "ADOPT_PREPARE", str(exc))]

    if inspection.state == "unmanaged-empty":
        if primary_instructions is not None:
            return [
                Diagnostic(
                    "error",
                    "PRIMARY_INSTRUCTIONS",
                    "Fresh adoption has no existing primary instructions",
                    primary_instructions,
                )
            ]
        verification = (
            init_command.DEFAULT_VERIFICATION_COMMAND
            if verification_command is UNSET
            else verification_command
        )
        policies = project_policy_files
        if policies is not None and len(policies) != 1:
            return [
                Diagnostic(
                    "error",
                    "INIT_PROJECT_POLICY_COUNT",
                    "Fresh adoption requires exactly one project policy scaffold",
                )
            ]
        return init_command.run(
            repository_root,
            config_path,
            apply=apply,
            toolchain_revision=toolchain_revision,
            profiles=profiles,
            project_policy_files=policies,
            verification_command=verification,
            agents_output_enabled=True,
            agents_output_path=init_command.DEFAULT_AGENTS_OUTPUT_PATH,
            enabled_skills=enabled_skills,
        )

    if inspection.state == "unmanaged-existing":
        verification = None if verification_command is UNSET else verification_command
        primary = primary_instructions or adopt_command.DEFAULT_PRIMARY_INSTRUCTIONS
        return adopt_command.prepare_run(
            repository_root,
            config_path,
            apply=apply,
            toolchain_revision=toolchain_revision,
            profiles=profiles,
            primary_instructions=primary,
            state_path=state_path,
            project_policy_files=project_policy_files,
            verification_command=verification,
            preview_output_path=preview_output_path,
            enabled_skills=enabled_skills,
        )

    if inspection.state == "managed":
        return [
            Diagnostic(
                "error",
                "ALREADY_MANAGED",
                "Repository already contains an agent-policy configuration",
            )
        ]
    if inspection.state == "inconsistent":
        return [
            Diagnostic(
                "error",
                "ADOPTION_INCONSISTENT",
                "Repository contains partial or generated agent-policy artifacts",
            )
        ]
    return [
        Diagnostic(
            "error",
            "ADOPTION_STATE",
            f"Unknown repository adoption state: {inspection.state}",
        )
    ]
