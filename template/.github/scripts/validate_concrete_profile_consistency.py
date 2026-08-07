#!/usr/bin/env python3
"""Validate language-neutral implementation signals and concrete profile details."""

from __future__ import annotations

import sys

from lib.profile_contracts import (
    ParseError,
    ProfileSelection,
    RepositorySnapshot,
    SkillDocument,
    ValuePolicy,
)


def run() -> int:
    try:
        skill = SkillDocument.read("SKILL.md")
        selection = ProfileSelection.load("SKILL.md", document=skill)
    except (ParseError, OSError) as exc:
        print(exc, file=sys.stderr)
        return 1

    repository = RepositorySnapshot()
    selected_profiles = set(selection.profiles)
    errors: list[str] = []

    for declaration in skill.declarations("Asset"):
        if declaration.path == "assets/TODO":
            continue
        for field in ("Use when", "Handling"):
            if not ValuePolicy.concrete(declaration.fields.get(field)):
                errors.append(
                    "SKILL.md asset declaration for "
                    f"{declaration.path} must include a concrete '{field}:' value."
                )

    if not selection.template_scaffold():
        executable_profiles = {
            "script-assisted",
            "packaged-cli",
            "mcp-enabled",
            "browser-interface",
            "headless-service",
        }
        general_directories = ("src", "app", "lib", "bin", "server", "client", "tests")
        browser_directories = ("web", "website", "frontend", "ui", "public", "static", "www")

        general_present = any(
            repository.operational_file_present(directory)
            for directory in general_directories
        )
        browser_present = any(
            repository.operational_file_present(directory)
            for directory in browser_directories
        )
        manifest_present = any(
            repository.file(path)
            for path in (
                "package.json",
                "package-lock.json",
                "pnpm-lock.yaml",
                "yarn.lock",
                "bun.lock",
                "bun.lockb",
                "pyproject.toml",
                "requirements.txt",
                "uv.lock",
                "Pipfile",
                "Pipfile.lock",
                "Cargo.toml",
                "Cargo.lock",
                "go.mod",
                "go.sum",
                "Gemfile",
                "Gemfile.lock",
                "pom.xml",
                "build.gradle",
                "build.gradle.kts",
                "composer.json",
                "composer.lock",
            )
        )
        root_present = any(
            repository.file(path)
            for path in (
                "index.html",
                "service-worker.js",
                "sw.js",
                "manifest.webmanifest",
                "Dockerfile",
                "compose.yml",
                "compose.yaml",
                "docker-compose.yml",
                "docker-compose.yaml",
            )
        )

        if (
            general_present or manifest_present or root_present
        ) and selected_profiles.isdisjoint(executable_profiles):
            errors.append(
                "Retained implementation or runtime signals require an executable "
                "or service profile."
            )

        if (
            browser_present
            or repository.file("index.html")
            or repository.file("manifest.webmanifest")
        ) and not selection.selected("browser-interface"):
            errors.append(
                "Retained browser implementation signals require selected profile "
                "'browser-interface'."
            )

    if selection.selected("headless-service"):
        runtime = repository.document("RUNTIME.md")
        if runtime is not None:
            service = runtime.section("## Headless service deployment")
            items = (
                "Supported",
                "Service runtime or entry point",
                "Protocol or API surface",
                "Endpoint or listener model",
                "Default bind address",
                "Port policy",
                "Authentication",
                "Authorization",
                "Exposure and non-loopback policy",
                "Request size and rate limits",
                "Concurrent request policy",
                "State or session model",
                "Readiness check",
                "Liveness check",
                "Timeout and cancellation policy",
                "Graceful shutdown and restart policy",
                "Deployment topology",
                "Security and deployment smoke tests",
            )
            for item in items:
                value = runtime.table_value(item, section=service)
                valid = value == "YES" if item == "Supported" else ValuePolicy.concrete(value)
                if not valid:
                    errors.append(
                        "Selected profile 'headless-service' requires a concrete "
                        f"'{item}' value in RUNTIME.md."
                    )

    if errors:
        for error in dict.fromkeys(errors):
            print(error, file=sys.stderr)
        return 1

    print("Concrete Agent Skill profile consistency is valid.")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
