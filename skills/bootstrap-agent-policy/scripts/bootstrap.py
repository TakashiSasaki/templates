#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
EXPECTED_REPOSITORY = "TakashiSasaki/templates"
EXPECTED_EXECUTABLE = "agent-policy"
EXPECTED_ROUTES = {
    "inspect": ["adopt", "inspect"],
    "init": ["init"],
    "adopt_prepare": ["adopt", "prepare"],
    "adopt_preview": ["adopt", "preview"],
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


def skill_root() -> Path:
    return Path(__file__).resolve().parents[1]


def load_manifest() -> dict[str, Any]:
    path = skill_root() / "bootstrap-manifest.yml"
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or value.get("schema_version") != 2:
        raise ValueError("Manifest schema_version must be 2")

    toolchain = value.get("toolchain")
    if not isinstance(toolchain, dict):
        raise ValueError("Manifest toolchain must be an object")
    revision = toolchain.get("revision")
    if not isinstance(revision, str) or not FULL_SHA.fullmatch(revision):
        raise ValueError("Manifest revision must be a full lowercase Git commit SHA")
    if toolchain.get("repository") != EXPECTED_REPOSITORY:
        raise ValueError("Unexpected toolchain repository")

    entrypoint = value.get("entrypoint")
    if entrypoint != {"executable": EXPECTED_EXECUTABLE}:
        raise ValueError("Unexpected manifest entrypoint")
    if value.get("routes") != EXPECTED_ROUTES:
        raise ValueError("Unexpected manifest routes")
    return value


def repository_root(raw: Path) -> Path:
    path = raw.expanduser().resolve()
    result = subprocess.run(
        ["git", "-C", str(path), "rev-parse", "--show-toplevel"],
        check=True,
        text=True,
        capture_output=True,
    )
    return Path(result.stdout.strip()).resolve()


def git_requirement(repository: str, revision: str) -> str:
    return f"git+https://github.com/{repository}.git@{revision}"


class Toolchain:
    def __init__(self, requirement: str, executable: str, cwd: Path) -> None:
        self.requirement = requirement
        self.executable = executable
        self.cwd = cwd
        self._temporary: tempfile.TemporaryDirectory[str] | None = None
        self._prefix: list[str] | None = None

    def __enter__(self) -> Toolchain:
        if shutil.which("uvx"):
            self._prefix = [
                "uvx",
                "--from",
                self.requirement,
                self.executable,
            ]
            return self

        self._temporary = tempfile.TemporaryDirectory(prefix="bootstrap-agent-policy-")
        venv = Path(self._temporary.name) / "venv"
        subprocess.run([sys.executable, "-m", "venv", str(venv)], check=True)
        if sys.platform == "win32":
            python = venv / "Scripts" / "python.exe"
            executable = venv / "Scripts" / f"{self.executable}.exe"
        else:
            python = venv / "bin" / "python"
            executable = venv / "bin" / self.executable
        subprocess.run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                self.requirement,
            ],
            check=True,
        )
        self._prefix = [str(executable)]
        return self

    def __exit__(self, exc_type: object, exc: object, traceback: object) -> None:
        if self._temporary is not None:
            self._temporary.cleanup()

    def run(
        self,
        arguments: list[str],
        *,
        capture_output: bool = False,
    ) -> subprocess.CompletedProcess[str]:
        if self._prefix is None:
            raise RuntimeError("Toolchain is not active")
        return subprocess.run(
            [*self._prefix, *arguments],
            cwd=self.cwd,
            text=True,
            capture_output=capture_output,
        )


def root_arguments(root: Path) -> list[str]:
    return ["--repository", str(root)]


def inspect_arguments(manifest: dict[str, Any], root: Path) -> list[str]:
    return [
        *root_arguments(root),
        "--format",
        "json",
        *manifest["routes"]["inspect"],
    ]


def action_arguments(
    manifest: dict[str, Any],
    root: Path,
    route: str,
    revision: str,
    *,
    apply: bool,
    primary_instructions: str | None,
) -> list[str]:
    route_key = "init" if route == "init" else "adopt_prepare"
    arguments = [
        *root_arguments(root),
        *manifest["routes"][route_key],
        "--toolchain-revision",
        revision,
    ]
    if route == "adopt":
        if primary_instructions is None:
            raise ValueError("Adoption requires explicit or unambiguous primary instructions")
        arguments.extend(["--primary-instructions", primary_instructions])
    if apply:
        arguments.append("--apply")
    return arguments


def post_apply_arguments(
    manifest: dict[str, Any],
    root: Path,
    route: str,
) -> list[list[str]]:
    if route == "init":
        return [
            [*root_arguments(root), *manifest["routes"]["validate"]],
            [*root_arguments(root), *manifest["routes"]["check"]],
        ]
    return [[*root_arguments(root), *manifest["routes"]["adopt_preview"]]]


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


def recommended_route(state: str) -> str:
    if state == "unmanaged-empty":
        return "init"
    if state == "unmanaged-existing":
        return "adopt"
    if state == "managed":
        raise ValueError("Repository is already managed by agent-policy")
    if state == "inconsistent":
        raise ValueError("Repository contains inconsistent agent-policy artifacts")
    raise ValueError(f"Unknown repository adoption state: {state}")


def select_route(state: str, requested: str, *, apply: bool) -> str:
    recommended = recommended_route(state)
    if requested == "auto":
        if apply:
            raise ValueError("--apply requires an explicit --route init or --route adopt")
        return recommended
    if requested != recommended:
        raise ValueError(
            f"Requested route {requested} does not match repository state; "
            f"recommended route is {recommended}"
        )
    return requested


def available_primary_instructions(inspection: Inspection) -> tuple[str, ...]:
    return tuple(path for path in inspection.sources if path in KNOWN_INSTRUCTION_FILES)


def select_primary_instructions(
    inspection: Inspection,
    route: str,
    requested: str | None,
    *,
    apply: bool,
) -> str | None:
    if route != "adopt":
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
        detail = ", ".join(available) if available else "none"
        raise ValueError(
            "Adoption requires --primary-instructions when discovery is ambiguous; "
            f"available: {detail}"
        )
    return None


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Bootstrap the TakashiSasaki/templates policy toolchain"
    )
    parser.add_argument("--repository", type=Path, default=Path.cwd())
    parser.add_argument("--route", choices=["auto", "init", "adopt"], default="auto")
    parser.add_argument("--primary-instructions")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Apply the explicitly selected route after dry-run inspection",
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
        manifest = load_manifest()
        root = repository_root(args.repository)
        toolchain = manifest["toolchain"]
        entrypoint = manifest["entrypoint"]
        assert isinstance(toolchain, dict)
        assert isinstance(entrypoint, dict)
        repository = str(toolchain["repository"])
        revision = str(toolchain["revision"])
        executable = str(entrypoint["executable"])
        requirement = git_requirement(repository, revision)

        print(f"Toolchain: {repository}@{revision}")
        print(f"Repository: {root}")
        print(f"Mode: {'apply' if args.apply else 'dry-run'}")

        with Toolchain(requirement, executable, root) as runner:
            inspection_result = runner.run(
                inspect_arguments(manifest, root),
                capture_output=True,
            )
            if inspection_result.returncode:
                _relay_completed(inspection_result)
                return inspection_result.returncode
            inspection = parse_inspection(inspection_result.stdout)
            print(f"State: {inspection.state}")
            if inspection.sources:
                print("Sources:")
                for source in inspection.sources:
                    print(f"- {source}")

            recommended = recommended_route(inspection.state)
            print(f"Recommended route: {recommended}")
            route = select_route(inspection.state, args.route, apply=args.apply)
            primary_instructions = select_primary_instructions(
                inspection,
                route,
                args.primary_instructions,
                apply=args.apply,
            )
            print(f"Selected route: {route}")
            if route == "adopt" and primary_instructions is None:
                available = available_primary_instructions(inspection)
                detail = ", ".join(available) if available else "none"
                print(
                    "No unique primary instruction was selected. "
                    "Re-run with --primary-instructions after review."
                )
                print(f"Available primary instructions: {detail}")
                return 0
            if primary_instructions is not None:
                print(f"Primary instructions: {primary_instructions}")

            result = runner.run(
                action_arguments(
                    manifest,
                    root,
                    route,
                    revision,
                    apply=args.apply,
                    primary_instructions=primary_instructions,
                )
            )
            if result.returncode:
                return result.returncode
            if not args.apply:
                return 0

            for arguments in post_apply_arguments(manifest, root, route):
                result = runner.run(arguments)
                if result.returncode:
                    return result.returncode

            if route == "adopt":
                print("Adoption preparation and preview completed.")
                print("Finalization was not run and requires a separate explicit instruction.")
            return 0
    except (OSError, ValueError, subprocess.CalledProcessError, json.JSONDecodeError) as exc:
        print(f"bootstrap error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
