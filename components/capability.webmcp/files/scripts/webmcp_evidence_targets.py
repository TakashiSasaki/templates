#!/usr/bin/env python3
"""Derive deterministic implementation-evidence targets for WebMCP tools."""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

CONTRACT_PATH = "contracts/webmcp-tools.json"
CONTRACT_ID = "webmcp_tools"


def load_tools(root: Path) -> list[dict[str, Any]]:
    value = json.loads((root / CONTRACT_PATH).read_text(encoding="utf-8"))
    tools = value.get("tools")
    if not isinstance(tools, list):
        raise ValueError("webmcp-tools.json tools must be an array")
    return tools


def target(tool_id: str) -> dict[str, str]:
    return {
        "kind": "contract-item",
        "contractId": CONTRACT_ID,
        "itemKind": "tool",
        "itemId": tool_id,
    }


def expected_targets(root: Path) -> tuple[dict[str, str], ...]:
    tools = load_tools(root.resolve())
    ids: list[str] = []
    for tool in tools:
        tool_id = tool.get("id") if isinstance(tool, dict) else None
        if not isinstance(tool_id, str) or not tool_id:
            raise ValueError("every WebMCP tool must have a stable id")
        ids.append(tool_id)
    if len(ids) != len(set(ids)):
        raise ValueError("WebMCP stable tool ids must be unique")
    return tuple(target(tool_id) for tool_id in sorted(ids))
