from __future__ import annotations

import argparse
import subprocess
import sys
from pathlib import Path

from .commands import adopt as adopt_command
from .commands import check as check_command
from .commands import init as init_command
from .commands import render as render_command
from .commands import validate as validate_command
from .diagnostics import print_diagnostics
from .paths import find_repository_root


def current_revision() -> str:
    try:
        return subprocess.check_output(
            ["git", "rev-parse", "HEAD"],
            cwd=Path(__file__).resolve().parents[2],
            text=True,
            stderr=subprocess.DEVNULL,
        ).strip()
    except (OSError, subprocess.CalledProcessError):
        return "LOCAL-DEVELOPMENT"


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="agent-policy")
    root.add_argument("--repository", type=Path, default=None)
    root.add_argument("--format", choices=["text", "json"], default="text")
    sub = root.add_subparsers(dest="command", required=True)
    for name in ["validate", "render", "check"]:
        item = sub.add_parser(name)
        item.add_argument("--config", default=".agent-policy.yml")

    init = sub.add_parser("init")
    init.add_argument("--config", default=".agent-policy.yml")
    init.add_argument("--apply", action="store_true")
    init.add_argument("--toolchain-revision", default=current_revision())
    init.add_argument("--profile", action="append", dest="profiles")
    init.add_argument("--project-policy")
    verification = init.add_mutually_exclusive_group()
    verification.add_argument(
        "--verification-command",
        default=init_command.DEFAULT_VERIFICATION_COMMAND,
    )
    verification.add_argument(
        "--no-verification",
        action="store_const",
        dest="verification_command",
        const=None,
    )
    init.add_argument(
        "--agents-output-path",
        default=init_command.DEFAULT_AGENTS_OUTPUT_PATH,
    )
    init.add_argument("--disable-agents-output", action="store_true")
    init.add_argument("--skill", action="append", dest="enabled_skills")

    adopt = sub.add_parser("adopt")
    adopt_sub = adopt.add_subparsers(dest="adopt_command", required=True)
    inspect = adopt_sub.add_parser("inspect")
    inspect.add_argument("--config", default=".agent-policy.yml")
    inspect.add_argument("--state", default=adopt_command.DEFAULT_STATE_PATH)

    prepare = adopt_sub.add_parser("prepare")
    prepare.add_argument("--config", default=".agent-policy.yml")
    prepare.add_argument("--state", default=adopt_command.DEFAULT_STATE_PATH)
    prepare.add_argument("--apply", action="store_true")
    prepare.add_argument("--toolchain-revision", default=current_revision())
    prepare.add_argument("--profile", action="append", dest="profiles")
    prepare.add_argument(
        "--primary-instructions",
        default=adopt_command.DEFAULT_PRIMARY_INSTRUCTIONS,
    )
    prepare.add_argument("--project-policy", action="append", dest="project_policy_files")
    adopt_verification = prepare.add_mutually_exclusive_group()
    adopt_verification.add_argument("--verification-command", default=None)
    adopt_verification.add_argument(
        "--no-verification",
        action="store_const",
        dest="verification_command",
        const=None,
    )
    prepare.add_argument(
        "--preview-output-path",
        default=adopt_command.DEFAULT_PREVIEW_OUTPUT_PATH,
    )
    adopt_skills = prepare.add_mutually_exclusive_group()
    adopt_skills.add_argument("--skill", action="append", dest="enabled_skills")
    adopt_skills.add_argument(
        "--no-skills",
        action="store_const",
        dest="enabled_skills",
        const=[],
    )
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    try:
        repository_root = find_repository_root(args.repository)
    except Exception as exc:
        print(f"ERROR REPOSITORY: {exc}", file=sys.stderr)
        return 2
    if args.command == "validate":
        diagnostics = validate_command.run(repository_root, args.config)
    elif args.command == "render":
        diagnostics = render_command.run(repository_root, args.config)
    elif args.command == "check":
        diagnostics = check_command.run(repository_root, args.config)
    elif args.command == "adopt":
        if args.adopt_command == "inspect":
            diagnostics = adopt_command.inspect_run(
                repository_root,
                args.config,
                state_path=args.state,
            )
        else:
            diagnostics = adopt_command.prepare_run(
                repository_root,
                args.config,
                apply=args.apply,
                toolchain_revision=args.toolchain_revision,
                profiles=args.profiles or ["core", "security-baseline"],
                primary_instructions=args.primary_instructions,
                state_path=args.state,
                project_policy_files=args.project_policy_files,
                verification_command=args.verification_command,
                preview_output_path=args.preview_output_path,
                enabled_skills=args.enabled_skills,
            )
    else:
        project_policy_files = [args.project_policy] if args.project_policy else None
        diagnostics = init_command.run(
            repository_root,
            args.config,
            apply=args.apply,
            toolchain_revision=args.toolchain_revision,
            profiles=args.profiles or ["core", "security-baseline"],
            project_policy_files=project_policy_files,
            verification_command=args.verification_command,
            agents_output_enabled=not args.disable_agents_output,
            agents_output_path=args.agents_output_path,
            enabled_skills=args.enabled_skills,
        )
    print_diagnostics(diagnostics, args.format)
    return 1 if any(item.level == "error" for item in diagnostics) else 0


if __name__ == "__main__":
    raise SystemExit(main())
