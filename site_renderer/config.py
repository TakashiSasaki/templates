"""Translate semantic navigation to Zensical presentation configuration."""
from __future__ import annotations
import json
from typing import Any

def render_nav(nodes: list[dict[str, Any]], indent: int = 0) -> str:
    prefix = " " * indent
    entry = " " * (indent + 2)
    values = []
    for node in nodes:
        title = json.dumps(node["title"], ensure_ascii=False)
        if "children" in node:
            values.append(
                f"{entry}{{{title} = {render_nav(node['children'], indent + 2)}}}"
            )
        else:
            destination = json.dumps(
                node["destination"].as_posix(),
                ensure_ascii=False,
            )
            values.append(f"{entry}{{{title} = {destination}}}")
    return "[\n" + ",\n".join(values) + f"\n{prefix}]"

