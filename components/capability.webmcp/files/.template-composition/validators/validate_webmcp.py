#!/usr/bin/env python3
"""Validate cross-contract WebMCP invariants after schema validation."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from urllib.parse import urlsplit


def load(root: Path, relative: str) -> dict:
    value = json.loads((root / relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{relative} must be a JSON object")
    return value


def validate(root: Path) -> list[str]:
    interface = load(root, "contracts/webmcp-interface.json")
    inventory = load(root, "contracts/webmcp-tools.json")
    errors: list[str] = []

    if interface.get("profile") != "imperative":
        errors.append("WebMCP v1 profile must be imperative")
    if interface.get("browserContext", {}).get("api") != "document.modelContext":
        errors.append("WebMCP v1 browser API must be document.modelContext")

    exposure = interface.get("exposure", {})
    mode = exposure.get("mode")
    origins = exposure.get("allowOrigins", [])
    if mode == "same-origin" and origins:
        errors.append("same-origin exposure must not declare allowOrigins")
    if mode == "cross-origin-allowlist":
        if not origins:
            errors.append("cross-origin exposure requires a non-empty allowOrigins")
        for origin in origins:
            parsed = urlsplit(origin)
            if parsed.scheme != "https" or not parsed.netloc or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
                errors.append(f"cross-origin allowOrigins entry must be an HTTPS origin: {origin!r}")

    tools = inventory.get("tools", [])
    ids: set[str] = set()
    names: set[str] = set()
    for index, tool in enumerate(tools):
        if not isinstance(tool, dict):
            errors.append(f"tool[{index}] must be an object")
            continue
        tool_id = tool.get("id")
        name = tool.get("name")
        if tool_id in ids:
            errors.append(f"duplicate stable WebMCP tool id: {tool_id}")
        if name in names:
            errors.append(f"duplicate caller-visible WebMCP tool name: {name}")
        if isinstance(tool_id, str):
            ids.add(tool_id)
        if isinstance(name, str):
            names.add(name)
        if tool.get("effect") == "consequential" and tool.get("confirmation") != "required-by-domain-operation":
            errors.append(f"consequential tool {tool_id!r} must retain domain confirmation")
        input_schema = tool.get("inputSchema")
        if not isinstance(input_schema, dict) or input_schema.get("type") not in {None, "object"}:
            errors.append(f"tool {tool_id!r} inputSchema must describe an object input")
    return errors


def main() -> int:
    root = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    try:
        errors = validate(root)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"WebMCP validation failed closed: {exc}", file=sys.stderr)
        return 1
    if errors:
        for error in errors:
            print(error, file=sys.stderr)
        return 1
    print("WebMCP semantic validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
