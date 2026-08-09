#!/usr/bin/env python3
"""Regression tests for MCP extension and MCP Apps activation rules."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from pathlib import Path


REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = (
    REPOSITORY_ROOT
    / "template"
    / ".github"
    / "scripts"
    / "validate_mcp_extensions.py"
)

VALID_APPS = """# MCP Apps extension contract

## Status and authority

Selection status: SELECTED
Extension identifier: io.modelcontextprotocol/ui
Extension specification revision: 2026-01-26
Core MCP revision: see RUNTIME.md

## Host capability and fallback

Host support is optional; a non-App Host receives the same core tool result.

## UI resource inventory

The View is `ui://example/result` with `text/html;profile=mcp-app`.

## Tool-to-UI linkage

The tool uses `_meta.ui.resourceUri` and the resource must resolve.

## Tool visibility and invocation

The tool is model-and-app visible; no app-only helper is selected.

## Result and presentation data

Core content remains meaningful and structuredContent contains display data.

## View and Host bridge lifecycle

The View uses Apps `ui/initialize` over the Host bridge; this is not core MCP initialize.

## Sandbox and browser security

The View is sandboxed, requests no browser permissions, and declares no external origin.

## Failure and degradation behavior

A View failure leaves the core tool result intact and is reported separately.

## Standalone Web interface boundary

MCP Apps does not select browser-interface and does not require WEB_INTERFACE.md.

## Required tests

Tests cover extension selection, resource linkage, fallback, bridge lifecycle, and denied authority.

## Decision rationale

The small View improves structured-result presentation without changing core tool semantics.
"""


def skill(profiles: str) -> str:
    return f"""---
name: extension-test
description: Test MCP extension selection.
---

# Extension test

Selected profiles: {profiles}
"""


def runtime(extensions: str) -> str:
    return f"""# Runtime

## MCP protocol support

| Item | Selected value |
|---|---|
| Optional MCP extensions | {extensions} |
"""


def run_case(
    *,
    name: str,
    profiles: str,
    extensions: str | None,
    apps_contract: str | None,
    app_file: bool = False,
    expected_success: bool,
) -> str | None:
    with tempfile.TemporaryDirectory(prefix="mcp-extension-contract-") as directory:
        root = Path(directory)
        (root / "SKILL.md").write_text(skill(profiles), encoding="utf-8")
        if extensions is not None:
            (root / "RUNTIME.md").write_text(runtime(extensions), encoding="utf-8")
        if apps_contract is not None:
            (root / "MCP_APPS.md").write_text(apps_contract, encoding="utf-8")
        if app_file:
            implementation = root / "mcp" / "apps"
            implementation.mkdir(parents=True)
            (implementation / "view.html").write_text("<p>fixture</p>\n", encoding="utf-8")

        environment = os.environ.copy()
        environment.pop("RUBYOPT", None)
        completed = subprocess.run(
            [sys.executable, str(VALIDATOR)],
            cwd=root,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        success = completed.returncode == 0
        if success != expected_success:
            return (
                f"{name}: expected success={expected_success}, got {success}; "
                f"stdout={completed.stdout.strip()!r}; stderr={completed.stderr.strip()!r}"
            )
    return None


def run() -> int:
    cases = [
        dict(
            name="mcp without extensions",
            profiles="mcp-enabled",
            extensions="NONE",
            apps_contract=None,
            expected_success=True,
        ),
        dict(
            name="unselected Apps contract retained",
            profiles="mcp-enabled",
            extensions="NONE",
            apps_contract=VALID_APPS,
            expected_success=False,
        ),
        dict(
            name="Apps selected but contract missing",
            profiles="mcp-enabled",
            extensions="io.modelcontextprotocol/ui",
            apps_contract=None,
            expected_success=False,
        ),
        dict(
            name="Apps selected without browser profile",
            profiles="mcp-enabled",
            extensions="io.modelcontextprotocol/ui",
            apps_contract=VALID_APPS,
            expected_success=True,
        ),
        dict(
            name="Apps implementation retained with Apps selected",
            profiles="mcp-enabled",
            extensions="io.modelcontextprotocol/ui",
            apps_contract=VALID_APPS,
            app_file=True,
            expected_success=True,
        ),
        dict(
            name="Apps implementation retained without Apps selection",
            profiles="mcp-enabled",
            extensions="NONE",
            apps_contract=None,
            app_file=True,
            expected_success=False,
        ),
        dict(
            name="malformed extension identifier",
            profiles="mcp-enabled",
            extensions="mcp-apps",
            apps_contract=None,
            expected_success=False,
        ),
        dict(
            name="NONE mixed with extension",
            profiles="mcp-enabled",
            extensions="NONE, io.modelcontextprotocol/ui",
            apps_contract=VALID_APPS,
            expected_success=False,
        ),
        dict(
            name="non-MCP skill retains Apps contract",
            profiles="script-assisted",
            extensions=None,
            apps_contract=VALID_APPS,
            expected_success=False,
        ),
    ]

    failures = [
        failure
        for case in cases
        if (failure := run_case(**case)) is not None
    ]
    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1

    print(f"MCP extension contract regression tests passed ({len(cases)} cases).")
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
