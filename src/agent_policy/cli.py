from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .commands import adopt as adopt_command
from .commands import check as check_command
from .commands import init as init_command
from .commands import onboard as onboard_command
from .commands import render as render_command
from .commands import review_bundle as review_bundle_command
from .commands import validate as validate_command
from .diagnostics import print_diagnostics
from .identity import immutable_toolchain_reference, resolve_toolchain_revision
from .paths import find_repository_root, find_trusted_snapshot_root


def immutable_revision_argument(value: str) -> str:
    try:
        return immutable_toolchain_reference(value)["revision"]
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def _add_review_bundle_bindings(item: argparse.ArgumentParser) -> None:
    item.add_argument("--semantic-output", required=True)
    item.add_argument("--adapter-output", required=True)
    item.add_argument("--adapter-renderer", required=True)


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="agent-policy")
    root.add_argument("--repository", type=Path, default=None)
    root.add_argument("--format", choices=["text", "json"], default="text")
    root.add_argument(
        "--trusted-review-snapshot",
        action="store_true",
        help=argparse.SUPPRESS,
    )
    sub = root.add_subparsers(dest="command", required=True)
    for name in ["validate", "render", "check"]:
        item = sub.add_parser(name)
        item.add_argument("--config", default=".agent-policy.yml")

    # Internal primitive retained for the pinned bootstrap trust seed and direct
    # tests. New onboarding documentation and bootstrap UX expose only adopt.
    init = sub.add_parser("init", help=argparse.SUPPRESS)
    init.add_argument("--config", default=".agent-policy.yml")
    init.add_argument("--apply", action="store_true")
    init.add_argument("--toolchain-revision", type=immutable_revision_argument)
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
    prepare.add_argument("--toolchain-revision", type=immutable_revision_argument)
    prepare.add_argument("--profile", action="append", dest="profiles")
    prepare.add_argument("--primary-instructions", default=None)
    prepare.add_argument("--project-policy", action="append", dest="project_policy_files")
    adopt_verification = prepare.add_mutually_exclusive_group()
    adopt_verification.add_argument(
        "--verification-command",
        default=onboard_command.UNSET,
    )
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

    preview = adopt_sub.add_parser("preview")
    preview.add_argument("--state", default=adopt_command.DEFAULT_STATE_PATH)

    finalize = adopt_sub.add_parser("finalize")
    finalize.add_argument("--state", default=adopt_command.DEFAULT_STATE_PATH)
    finalize.add_argument("--backup-path", default=adopt_command.DEFAULT_BACKUP_PATH)
    finalize.add_argument("--apply", action="store_true")

    # Internal trusted-review artifact handoff. This command does not establish
    # OS/deployment immutability; the dispatcher freezes the candidate between
    # materialize and verify.
    review_bundle = sub.add_parser("review-bundle", help=argparse.SUPPRESS)
    review_bundle_sub = review_bundle.add_subparsers(
        dest="review_bundle_command",
        required=True,
    )
    bundle_materialize = review_bundle_sub.add_parser("materialize")
    bundle_materialize.add_argument("--config", default=".agent-policy.yml")
    bundle_materialize.add_argument("--destination", type=Path, required=True)
    _add_review_bundle_bindings(bundle_materialize)
    bundle_verify = review_bundle_sub.add_parser("verify")
    bundle_verify.add_argument("--config", default=".agent-policy.yml")
    bundle_verify.add_argument("--bundle", type=Path, required=True)
    _add_review_bundle_bindings(bundle_verify)
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    if args.trusted_review_snapshot and args.command not in {
        "validate",
        "check",
        "review-bundle",
    }:
        print(
            "ERROR REPOSITORY: trusted review snapshot mode is read-only",
            file=sys.stderr,
        )
        return 2
    try:
        if args.trusted_review_snapshot:
            repository_root = find_trusted_snapshot_root(args.repository)
        else:
            repository_root = find_repository_root(args.repository)
    except Exception as exc:
        print(f"ERROR REPOSITORY: {exc}", file=sys.stderr)
        return 2

    needs_revision = args.command == "init" or (
        args.command == "adopt" and args.adopt_command == "prepare"
    )
    toolchain_revision: str | None = None
    if needs_revision:
        try:
            toolchain_revision = resolve_toolchain_revision(args.toolchain_revision)
        except ValueError as exc:
            print(f"ERROR TOOLCHAIN: {exc}", file=sys.stderr)
            return 2

    if args.command == "validate":
        diagnostics = validate_command.run(repository_root, args.config)
    elif args.command == "render":
        diagnostics = render_command.run(repository_root, args.config)
    elif args.command == "check":
        diagnostics = check_command.run(repository_root, args.config)
    elif args.command == "review-bundle":
        if args.review_bundle_command == "materialize":
            diagnostics = review_bundle_command.materialize(
                repository_root,
                args.config,
                args.destination,
                args.semantic_output,
                args.adapter_output,
                args.adapter_renderer,
            )
        else:
            diagnostics = review_bundle_command.verify(
                repository_root,
                args.config,
                args.bundle,
                args.semantic_output,
                args.adapter_output,
                args.adapter_renderer,
            )
    elif args.command == "adopt":
        if args.adopt_command == "inspect":
            diagnostics = adopt_command.inspect_run(
                repository_root,
                args.config,
                state_path=args.state,
            )
        elif args.adopt_command == "prepare":
            assert toolchain_revision is not None
            diagnostics = onboard_command.prepare_run(
                repository_root,
                args.config,
                apply=args.apply,
                toolchain_revision=toolchain_revision,
                profiles=args.profiles or ["core", "security-baseline"],
                primary_instructions=args.primary_instructions,
                state_path=args.state,
                project_policy_files=args.project_policy_files,
                verification_command=args.verification_command,
                preview_output_path=args.preview_output_path,
                enabled_skills=args.enabled_skills,
            )
        elif args.adopt_command == "preview":
            diagnostics = adopt_command.preview_run(
                repository_root,
                state_path=args.state,
            )
        else:
            diagnostics = adopt_command.finalize_run(
                repository_root,
                state_path=args.state,
                backup_path=args.backup_path,
                apply=args.apply,
            )
    else:
        assert toolchain_revision is not None
        project_policy_files = [args.project_policy] if args.project_policy else None
        diagnostics = init_command.run(
            repository_root,
            args.config,
            apply=args.apply,
            toolchain_revision=toolchain_revision,
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
