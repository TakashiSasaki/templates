#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

# The installed Skill tree can be deployment-attested trust material. Prevent
# importing sibling modules from creating __pycache__ entries inside that tree.
sys.dont_write_bytecode = True

# This import intentionally follows the bytecode-write guard because runtime.py
# is inside the deployment-attested Skill tree.
from runtime import (  # noqa: E402
    cli_command,
    ensure_runtime,
    load_manifest,
    pin_from_manifest,
    sanitized_environment,
)

EXPECTED_ROUTES = {
    "inspect": ["adopt", "inspect"],
    "fresh_prepare": ["init"],
    "migration_prepare": ["adopt", "prepare"],
    "migration_preview": ["adopt", "preview"],
    "validate": ["validate"],
    "check": ["check"],
}
KNOWN_INSTRUCTION_FILES = (
    "AGENTS.md",
    "CLAUDE.md",
    "GEMINI.md",
    ".github/copilot-instructions.md",
)


@dataclass(frozen=True)
class Inspection:
    state: str
    sources: tuple[str, ...]


class Toolchain:
    def __init__(self, command: list[str], cwd: Path) -> None:
        self.command = tuple(command)
        self.cwd = cwd

    def run(
        self,
        arguments: list[str],
        *,
        capture_output: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [*self.command, *arguments],
            cwd=self.cwd,
            env=sanitized_environment(),
            text=True,
            capture_output=capture_output,
        )


def validated_manifest() -> dict[str, Any]:
    manifest = load_manifest()
    if manifest.get("routes") != EXPECTED_ROUTES:
        raise ValueError("Unexpected runtime manifest routes")
    return manifest


def repository_root(raw: Path) -> Path:
    path = raw.expanduser().resolve()
    if not (path / ".git").exists():
        raise ValueError(
            "The supplied --repository path must be a Git repository root; "
            "parent repositories are not searched"
        )
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        check=True,
        text=True,
        capture_output=True,
    )
    discovered = Path(result.stdout.strip()).resolve()
    if discovered != path:
        raise ValueError(
            "The supplied --repository path is not the Git repository root; "
            "parent repositories are not searched"
        )
    return discovered


def root_arguments(root: Path) -> list[str]:
    return ["--repository", str(root)]


def inspect_arguments(manifest: dict[str, Any], root: Path) -> list[str]:
    return [*root_arguments(root), "--format", "json", *manifest["routes"]["inspect"]]


def adoption_strategy(state: str) -> str:
    if state == "unmanaged-empty":
        return "fresh"
    if state == "unmanaged-existing":
        return "migration"
    if state == "managed":
        raise ValueError("Repository is already managed by agent-policy")
    if state == "inconsistent":
        raise ValueError("Repository contains inconsistent agent-policy artifacts")
    raise ValueError(f"Unknown repository adoption state: {state}")


def available_primary_instructions(inspection: Inspection) -> tuple[str, ...]:
    return tuple(path for path in inspection.sources if path in KNOWN_INSTRUCTION_FILES)


def select_primary_instructions(
    inspection: Inspection,
    requested: str | None,
    *,
    apply: bool,
) -> str | None:
    strategy = adoption_strategy(inspection.state)
    if strategy == "fresh":
        if requested is not None:
            raise ValueError("Fresh adoption has no existing primary instructions")
        return None

    available = available_primary_instructions(inspection)
    if requested is not None:
        if requested not in available:
            detail = ", ".join(available) if available else "none"
            raise ValueError(
                "Adoption primary instructions must be a discovered instruction file; "
                f"available: {detail}"
            )
        return requested
    if len(available) == 1:
        return available[0]
    if apply:
        if not available:
            raise ValueError(
                "Migration adoption requires a supported primary instruction file; "
                "create one supported instruction file before applying"
            )
        detail = ", ".join(available)
        raise ValueError(
            "Migration adoption requires --primary-instructions when multiple "
            f"supported instruction files are discovered; available: {detail}"
        )
    return None


def primary_selection_guidance(available: tuple[str, ...]) -> str:
    if not available:
        supported = ", ".join(KNOWN_INSTRUCTION_FILES)
        return (
            "No supported primary instruction file was discovered. "
            f"Create one supported instruction file ({supported}), then re-run bootstrap."
        )
    return (
        "Multiple supported primary instruction files were discovered. "
        "Re-run with --primary-instructions <path> after review."
    )


def action_arguments(
    manifest: dict[str, Any],
    root: Path,
    strategy: str,
    revision: str,
    *,
    apply: bool,
    primary_instructions: str | None,
) -> list[str]:
    route_key = "fresh_prepare" if strategy == "fresh" else "migration_prepare"
    arguments = [
        *root_arguments(root),
        *manifest["routes"][route_key],
        "--toolchain-revision",
        revision,
    ]
    if strategy == "migration":
        if primary_instructions is None:
            raise ValueError(
                "Migration adoption requires explicit or unambiguous primary instructions"
            )
        arguments.extend(["--primary-instructions", primary_instructions])
    if apply:
        arguments.append("--apply")
    return arguments


def post_apply_arguments(
    manifest: dict[str, Any], root: Path, strategy: str
) -> list[list[str]]:
    if strategy == "fresh":
        return [
            [*root_arguments(root), *manifest["routes"]["validate"]],
            [*root_arguments(root), *manifest["routes"]["check"]],
        ]
    return [[*root_arguments(root), *manifest["routes"]["migration_preview"]]]


def parse_inspection(output: str) -> Inspection:
    value = json.loads(output)
    if not isinstance(value, list):
        raise ValueError("Inspection output must be a diagnostic list")
    states = [
        item.get("message")
        for item in value
        if isinstance(item, dict) and item.get("code") == "ADOPTION_STATE"
    ]
    if len(states) != 1 or not isinstance(states[0], str):
        raise ValueError("Inspection output must contain one ADOPTION_STATE diagnostic")
    sources = tuple(
        sorted(
            item["path"]
            for item in value
            if isinstance(item, dict)
            and item.get("code") == "ADOPTION_SOURCE"
            and isinstance(item.get("path"), str)
        )
    )
    return Inspection(state=states[0], sources=sources)


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Adopt the pinned TakashiSasaki/templates agent-policy toolchain"
    )
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--primary-instructions")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the inspected adoption strategy after dry-run review",
    )
    return parser.parse_args(argv)


def _relay_completed(result: subprocess.CompletedProcess[str]) -> None:
    if result.stdout:
        print(result.stdout, end="" if result.stdout.endswith("\n") else "\n")
    if result.stderr:
        print(
            result.stderr,
            end="" if result.stderr.endswith("\n") else "\n",
            file=sys.stderr,
        )


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    try:
        manifest = validated_manifest()
        root = repository_root(args.repository)
        pin = pin_from_manifest(manifest)
        runtime = ensure_runtime(pin)
        runner = Toolchain(cli_command(runtime), root)

        print(f"Toolchain: {pin.repository}@{pin.revision}")
        print(f"Repository: {root}")
        print(f"Mode: {'apply' if args.apply else 'dry-run'}")

        inspection_result = runner.run(inspect_arguments(manifest, root), capture_output=True)
        if inspection_result.returncode:
            _relay_completed(inspection_result)
            return inspection_result.returncode
        inspection = parse_inspection(inspection_result.stdout)
        print(f"State: {inspection.state}")
        if inspection.sources:
            print("Sources:")
            for source in inspection.sources:
                print(f"- {source}")

        strategy = adoption_strategy(inspection.state)
        print(f"Adoption strategy: {strategy}")
        primary_instructions = select_primary_instructions(
            inspection,
            args.primary_instructions,
            apply=args.apply,
        )
        if strategy == "migration" and primary_instructions is None:
            available = available_primary_instructions(inspection)
            print(primary_selection_guidance(available))
            detail = ", ".join(available) if available else "none"
            print(f"Available primary instructions: {detail}")
            return 0
        if primary_instructions is not None:
            print(f"Primary instructions: {primary_instructions}")

        result = runner.run(
            action_arguments(
                manifest,
                root,
                strategy,
                pin.revision,
                apply=args.apply,
                primary_instructions=primary_instructions,
            )
        )
        if result.returncode:
            return result.returncode
        if not args.apply:
            return 0

        for arguments in post_apply_arguments(manifest, root, strategy):
            result = runner.run(arguments)
            if result.returncode:
                return result.returncode

        if strategy == "migration":
            print("Adoption preparation and preview completed.")
            print("Finalization was not run and requires a separate explicit instruction.")
        else:
            print("Fresh adoption completed and managed validation succeeded.")
        return 0
    except (OSError, ValueError, RuntimeError, subprocess.CalledProcessError) as exc:
        print(f"agent-policy skill error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
