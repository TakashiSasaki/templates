from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Iterable

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .config import Config, package_root
from .policy_loader import Rule

GENERATED_MARKER = "agent-policy-generated: true"


def sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(package_root() / "templates"),
        undefined=StrictUndefined,
        autoescape=False,
        keep_trailing_newline=True,
    )


def render_agents(config: Config, rules: Iterable[Rule]) -> str:
    template = environment().get_template("AGENTS.md.j2")
    return template.render(config=config.data, rules=list(rules))


def render_skill(skill_name: str) -> dict[str, str]:
    skill_root = package_root() / "skills" / skill_name
    if not skill_root.is_dir():
        raise ValueError(f"Unknown skill: {skill_name}")
    return {
        str(path.relative_to(skill_root)): path.read_text(encoding="utf-8")
        for path in skill_root.rglob("*")
        if path.is_file()
    }
