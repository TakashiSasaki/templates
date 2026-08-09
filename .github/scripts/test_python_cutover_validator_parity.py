#!/usr/bin/env python3
"""Parity tests for concrete-profile and late-review Python validators."""

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path


SCRIPT_ROOT = Path(__file__).resolve().parent
REPOSITORY_ROOT = SCRIPT_ROOT.parents[1]
TEMPLATE_SCRIPT_ROOT = REPOSITORY_ROOT / "template" / ".github" / "scripts"
VALIDATORS = {
    "concrete": (
        ["ruby", str(SCRIPT_ROOT / "validate-concrete-profile-consistency.rb")],
        [
            sys.executable,
            str(TEMPLATE_SCRIPT_ROOT / "validate_concrete_profile_consistency.py"),
        ],
    ),
    "late-review": (
        ["ruby", str(SCRIPT_ROOT / "validate-late-review-contracts.rb")],
        [
            sys.executable,
            str(TEMPLATE_SCRIPT_ROOT / "validate_late_review_contracts.py"),
        ],
    ),
}


@dataclass(frozen=True)
class Case:
    name: str
    profile: str
    files: dict[str, str] = field(default_factory=dict)
    extra_skill: str = ""
    expected: dict[str, bool] = field(default_factory=dict)


def _skill(profile: str, extra: str = "") -> str:
    name = "agent-skill-template" if profile == "template-scaffold" else "example-skill"
    return f"""---
name: {name}
description: Example Skill
---
# Example Skill

Selected profiles: {profile}

{extra}"""


def _modern_http_runtime(*, post_request_model: str = "one JSON-RPC message per POST") -> str:
    return f"""# Runtime decision record

## MCP protocol support

| Item | Selected value |
|---|---|
| Supported protocol revisions | 2026-07-28 |

### stdio variant

| Item | Selected value |
|---|---|
| Supported | NO |

### Streamable HTTP variant

| Item | Selected value |
|---|---|
| Supported | YES |
| Server entry point | server/http.mjs |
| Endpoint path | /mcp |
| Default bind address | 127.0.0.1 |
| Port | 3000 |
| Supported protocol eras | modern |
| Revision-specific state model | request-scoped Modern state |
| Concurrent-client policy | independent request contexts |
| Authentication | bearer token |
| Host-header validation | validate every request |
| Origin validation granularity | validate every request |
| Allowed origins and absent-Origin policy | allow https://example.test; reject other present origins |
| Connection-reuse security tests | keep-alive requests with distinct origins |
| Readiness check | GET /ready outside MCP endpoint |
| Cancellation behavior | close request SSE to cancel that request |
| Shutdown/restart policy | graceful drain then restart |
| Non-loopback support | disabled by deployment policy |

When Streamable HTTP is supported, complete every Modern requirement below:

| Modern Streamable HTTP requirement | Selected behavior |
|---|---|
| POST request model | {post_request_model} |
| `Accept: application/json, text/event-stream` | require both media types |
| `MCP-Protocol-Version` and request `_meta` consistency | require exact agreement |
| Required `Mcp-Method` and conditional `Mcp-Name` headers | require and validate before dispatch |
| Header value encoding | use the selected specification encoding |
| `x-mcp-header` validation and `Mcp-Param-*` emission | validate definitions before emission |
| JSON and request-scoped SSE response handling | support JSON and request-scoped SSE |
| SSE-stream cancellation | closing the stream cancels the request |
| `Mcp-Session-Id`, GET, DELETE, and resumability | not used in Modern core |
| Initialization-era fallback on the same endpoint | NOT SUPPORTED |

The stdio and Streamable HTTP variants must preserve equivalent domain semantics.
"""


def _run(command: list[str], case: Case) -> tuple[int, str, str]:
    with tempfile.TemporaryDirectory(prefix="python-cutover-parity-") as directory:
        root = Path(directory)
        (root / "SKILL.md").write_text(
            _skill(case.profile, case.extra_skill), encoding="utf-8"
        )
        for relative, content in case.files.items():
            path = root / relative
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(content, encoding="utf-8")

        environment = os.environ.copy()
        environment.pop("RUBYOPT", None)
        completed = subprocess.run(
            command,
            cwd=root,
            env=environment,
            text=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
        return completed.returncode, completed.stdout, completed.stderr


def run() -> int:
    cases = [
        Case(
            name="clean template scaffold",
            profile="template-scaffold",
            expected={"concrete": True, "late-review": True},
        ),
        Case(
            name="template root implementation signal",
            profile="template-scaffold",
            files={"pyproject.toml": "[project]\nname = \"example\"\n"},
            expected={"concrete": True, "late-review": False},
        ),
        Case(
            name="instruction-only root implementation signal",
            profile="instruction-only",
            files={"main.py": "print('example')\n"},
            expected={"concrete": True, "late-review": False},
        ),
        Case(
            name="instruction-only source directory",
            profile="instruction-only",
            files={"src/main.py": "print('example')\n"},
            expected={"concrete": False, "late-review": True},
        ),
        Case(
            name="browser directory without browser profile",
            profile="instruction-only",
            files={"web/app.js": "export const ready = true;\n"},
            expected={"concrete": False, "late-review": True},
        ),
        Case(
            name="browser directory with browser profile",
            profile="browser-interface",
            files={"web/app.js": "export const ready = true;\n"},
            expected={"concrete": True, "late-review": True},
        ),
        Case(
            name="asset declaration missing handling",
            profile="asset-driven",
            extra_skill=(
                "Asset: assets/example.txt\n"
                "Use when: deterministic example output is required\n"
            ),
            files={"assets/example.txt": "example\n"},
            expected={"concrete": False, "late-review": True},
        ),
        Case(
            name="asset declaration complete",
            profile="asset-driven",
            extra_skill=(
                "Asset: assets/example.txt\n"
                "Use when: deterministic example output is required\n"
                "Handling: read-only input\n"
            ),
            files={"assets/example.txt": "example\n"},
            expected={"concrete": True, "late-review": True},
        ),
        Case(
            name="incomplete headless service deployment",
            profile="headless-service",
            files={
                "RUNTIME.md": (
                    "# Runtime decision record\n\n"
                    "## Headless service deployment\n\n"
                    "| Item | Selected value |\n"
                    "|---|---|\n"
                    "| Supported | YES |\n"
                )
            },
            expected={"concrete": False, "late-review": True},
        ),
        Case(
            name="Modern Streamable HTTP table is parsed from the HTTP section",
            profile="mcp-enabled",
            files={"RUNTIME.md": _modern_http_runtime()},
            expected={"concrete": True, "late-review": True},
        ),
        Case(
            name="Modern Streamable HTTP rejects an unresolved required row",
            profile="mcp-enabled",
            files={"RUNTIME.md": _modern_http_runtime(post_request_model="TODO")},
            expected={"concrete": True, "late-review": False},
        ),
    ]

    failures: list[str] = []
    for case in cases:
        for validator, (ruby_command, python_command) in VALIDATORS.items():
            ruby_result = _run(ruby_command, case)
            python_result = _run(python_command, case)
            expected_success = case.expected[validator]

            if ruby_result != python_result:
                failures.append(
                    f"{validator} / {case.name}: Ruby/Python output drift; "
                    f"ruby={ruby_result!r}; python={python_result!r}"
                )
                continue

            actual_success = ruby_result[0] == 0
            if actual_success != expected_success:
                failures.append(
                    f"{validator} / {case.name}: expected success="
                    f"{expected_success}, got {actual_success}; "
                    f"stdout={ruby_result[1].strip()!r}; "
                    f"stderr={ruby_result[2].strip()!r}"
                )

    if failures:
        for failure in failures:
            print(failure, file=sys.stderr)
        return 1

    print(
        "Concrete/late-review Ruby-Python parity tests passed "
        f"({len(cases) * len(VALIDATORS)} validator cases)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(run())
