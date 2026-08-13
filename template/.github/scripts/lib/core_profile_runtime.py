"""Runtime-backed profile checks for the core Skill validator."""

from __future__ import annotations

import re
import tomllib

from .profile_contracts import ProfileSelection, RepositorySnapshot, ValuePolicy


def _validate_python_packaged_cli_entry_point(
    *,
    runtime,
    primary: str | None,
    commands: str | None,
    repository: RepositorySnapshot,
    errors: list[str],
) -> None:
    """Require a pyproject console script to resolve to a retained module file.

    This closes a gap where the runtime/packaging contracts could remain
    syntactically complete while the module named by ``[project.scripts]`` was
    absent.  Both src-layout and flat-layout Python packages are accepted.
    """

    manifest = runtime.table_value("Project manifest", section=primary)
    runtime_name = runtime.table_value("Runtime", section=primary)
    human_cli = runtime.table_value("Human CLI", section=commands)
    if manifest != "pyproject.toml" or runtime_name != "CPython":
        return

    if not repository.file(manifest):
        errors.append(
            "Selected Python packaged CLI requires the declared project manifest "
            f"to exist: {manifest}"
        )
        return

    try:
        payload = tomllib.loads((repository.root / manifest).read_text(encoding="utf-8"))
    except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
        errors.append(
            f"Selected Python packaged CLI requires a readable valid {manifest}: {exc}"
        )
        return

    project = payload.get("project")
    scripts = project.get("scripts") if isinstance(project, dict) else None
    target = scripts.get(human_cli) if isinstance(scripts, dict) and human_cli else None
    if not isinstance(target, str) or not target.strip():
        errors.append(
            "Selected Python packaged CLI requires [project.scripts] to map the "
            f"declared Human CLI {human_cli!r} to an entry point."
        )
        return

    module_name = target.split(":", 1)[0].strip()
    if not re.fullmatch(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*", module_name):
        errors.append(
            "Selected Python packaged CLI has an invalid module path in its "
            f"[project.scripts] entry point: {target!r}"
        )
        return

    module_path = module_name.replace(".", "/")
    candidates = (
        f"src/{module_path}.py",
        f"src/{module_path}/__init__.py",
        f"{module_path}.py",
        f"{module_path}/__init__.py",
    )
    if not any(repository.file(candidate) for candidate in candidates):
        errors.append(
            "Selected Python packaged CLI entry point "
            f"{target!r} declares missing implementation module {module_name!r}; "
            f"expected one of: {', '.join(candidates)}"
        )


def validate_runtime_contracts(
    *,
    selected_profiles: list[str],
    selection: ProfileSelection,
    repository: RepositorySnapshot,
    errors: list[str],
) -> None:
    runtime_allowed_profiles = {
        "script-assisted",
        "packaged-cli",
        "mcp-enabled",
        "browser-interface",
        "headless-service",
    }
    runtime_selected = bool(
        set(selected_profiles) & runtime_allowed_profiles
    )
    runtime = repository.document("RUNTIME.md")

    if runtime_selected and runtime is not None:
        runtime_status = runtime.field("Selection status")
        if runtime_status != "SELECTED":
            errors.append(
                "Selected runtime-backed profiles require "
                "'Selection status: SELECTED' in RUNTIME.md."
            )

        primary = runtime.section("## Primary implementation")
        for item in (
            "Language",
            "Runtime",
            "Minimum runtime version",
            "Dependency/package manager",
            "Project manifest",
            "Lockfile policy",
            "Source layout",
            "Supported operating systems",
        ):
            if not ValuePolicy.resolved(
                runtime.table_value(item, section=primary)
            ):
                errors.append(
                    f"RUNTIME.md requires a concrete '{item}' value for selected "
                    "runtime-backed profiles."
                )

        commands = runtime.section("## Commands")
        for item in (
            "Install development dependencies",
            "Run in place",
            "Test",
            "Lint/static analysis",
            "Format check",
            "Build/package",
        ):
            if not ValuePolicy.resolved(
                runtime.table_value(item, section=commands)
            ):
                errors.append(
                    f"RUNTIME.md requires a resolved '{item}' command for selected "
                    "runtime-backed profiles."
                )

        distribution = runtime.section("## Distribution")
        for item in ("Skill distribution", "Version source of truth"):
            if not ValuePolicy.resolved(
                runtime.table_value(item, section=distribution)
            ):
                errors.append(
                    f"RUNTIME.md requires a concrete '{item}' value for selected "
                    "runtime-backed profiles."
                )

        environment = runtime.section("## Environment and configuration")
        if environment is None or re.search(
            r"\bTODO\b", environment, re.IGNORECASE
        ):
            errors.append(
                "RUNTIME.md must replace the environment/configuration "
                "placeholder with concrete variables or an explicit NONE record."
            )

        rationale = runtime.section("## Decision rationale")
        if (
            rationale is None
            or not rationale.strip()
            or re.search(r"\bTODO\b", rationale, re.IGNORECASE)
        ):
            errors.append(
                "RUNTIME.md requires a concrete decision rationale for selected "
                "runtime-backed profiles."
            )

        if selection.selected("packaged-cli"):
            if not ValuePolicy.concrete(
                runtime.table_value("Human CLI", section=commands)
            ):
                errors.append(
                    "Selected profile 'packaged-cli' requires a concrete "
                    "'Human CLI' command in RUNTIME.md."
                )
            if not ValuePolicy.resolved(
                runtime.table_value("CLI distribution", section=distribution)
            ):
                errors.append(
                    "Selected profile 'packaged-cli' requires a resolved "
                    "'CLI distribution' value in RUNTIME.md."
                )
            _validate_python_packaged_cli_entry_point(
                runtime=runtime,
                primary=primary,
                commands=commands,
                repository=repository,
                errors=errors,
            )

        if selection.selected("browser-interface"):
            for item in (
                "Start human verification Web UI",
                "Stop human verification Web UI",
                "Check human verification Web UI readiness",
            ):
                if not ValuePolicy.concrete(
                    runtime.table_value(item, section=commands)
                ):
                    errors.append(
                        "Selected profile 'browser-interface' requires a concrete "
                        f"'{item}' command in RUNTIME.md."
                    )

            web_deployment = runtime.section(
                "## Optional human verification Web interface deployment"
            )
            for item in (
                "Supported",
                "Web runtime or entry point",
                "Deployment selection time",
                "Supported topologies",
                "Default topology",
                "Shared-listener support",
                "Separate-listener support",
                "External-origin model",
                "Browser-visible MCP exposure capability",
                "Enablement configuration",
            ):
                if not ValuePolicy.resolved(
                    runtime.table_value(item, section=web_deployment)
                ):
                    errors.append(
                        "Selected profile 'browser-interface' requires a concrete "
                        f"'{item}' value in the RUNTIME.md Web deployment section."
                    )
            if runtime.table_value(
                "Supported", section=web_deployment
            ) != "YES":
                errors.append(
                    "Selected profile 'browser-interface' requires "
                    "'Supported: YES' in the RUNTIME.md Web deployment section."
                )
            if not ValuePolicy.resolved(
                runtime.table_value(
                    "Human Web interface distribution",
                    section=distribution,
                )
            ):
                errors.append(
                    "Selected profile 'browser-interface' requires a resolved "
                    "Web distribution value in RUNTIME.md."
                )

        if selection.selected("headless-service"):
            for item in (
                "Start headless service",
                "Stop headless service",
                "Check headless service readiness",
            ):
                if not ValuePolicy.concrete(
                    runtime.table_value(item, section=commands)
                ):
                    errors.append(
                        "Selected profile 'headless-service' requires a concrete "
                        f"'{item}' command in RUNTIME.md."
                    )

            service = runtime.section("## Headless service deployment")
            for item in (
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
            ):
                if not ValuePolicy.resolved(
                    runtime.table_value(item, section=service)
                ):
                    errors.append(
                        "Selected profile 'headless-service' requires a concrete "
                        f"'{item}' value in the RUNTIME.md service section."
                    )
            if runtime.table_value("Supported", section=service) != "YES":
                errors.append(
                    "Selected profile 'headless-service' requires "
                    "'Supported: YES' in the RUNTIME.md service section."
                )
            if not ValuePolicy.resolved(
                runtime.table_value(
                    "Service integration", section=distribution
                )
            ):
                errors.append(
                    "Selected profile 'headless-service' requires a resolved "
                    "'Service integration' value in RUNTIME.md."
                )

        if selection.selected("mcp-enabled"):
            mcp_protocol = runtime.section("## MCP protocol support")
            for item in (
                "Supported protocol revisions",
                "Supported protocol eras",
                "Default revision or negotiation mode",
                "MCP SDK or protocol library",
                "SDK version",
                "Legacy compatibility policy",
                "JSON Schema dialects",
                "Optional MCP extensions",
                "Deprecated feature policy",
                "Negotiation and compatibility tests",
            ):
                if not ValuePolicy.resolved(
                    runtime.table_value(item, section=mcp_protocol)
                ):
                    errors.append(
                        "Selected profile 'mcp-enabled' requires a concrete "
                        f"'{item}' value in RUNTIME.md."
                    )

            variant_sections = {
                "stdio": runtime.section("### stdio variant"),
                "Streamable HTTP": runtime.section(
                    "### Streamable HTTP variant"
                ),
                "bundled client": runtime.section(
                    "### Bundled ad hoc MCP tool client"
                ),
            }
            variant_support: dict[str, str | None] = {}
            for variant, content in variant_sections.items():
                support = runtime.table_value(
                    "Supported", section=content
                )
                variant_support[variant] = support
                if support not in {"YES", "NO"}:
                    errors.append(
                        "Selected profile 'mcp-enabled' requires "
                        f"'{variant}' Supported to be YES or NO in RUNTIME.md."
                    )
                if content is None or re.search(
                    r"\bTODO\b", content, re.IGNORECASE
                ):
                    errors.append(
                        "Selected profile 'mcp-enabled' must resolve all retained "
                        f"'{variant}' RUNTIME.md fields using concrete or "
                        "NOT SUPPORTED values."
                    )
            if "YES" not in (
                variant_support.get("stdio"),
                variant_support.get("Streamable HTTP"),
            ):
                errors.append(
                    "Selected profile 'mcp-enabled' requires at least one "
                    "supported MCP server transport in RUNTIME.md."
                )
            if not ValuePolicy.resolved(
                runtime.table_value(
                    "MCP distribution", section=distribution
                )
            ):
                errors.append(
                    "Selected profile 'mcp-enabled' requires a resolved "
                    "'MCP distribution' value in RUNTIME.md."
                )
