from __future__ import annotations

import hashlib
from collections.abc import Iterable

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .config import Config, package_root
from .policy_loader import Rule

GENERATED_MARKER = "agent-policy-generated: true"


def environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(package_root() / "templates"),
        undefined=StrictUndefined,
        autoescape=False,
        keep_trailing_newline=True,
    )


def render_agents(config: Config, rules: Iterable[Rule]) -> str:
    template = environment().get_template("AGENTS.md.j2")
    return template.render(config=config, rules=list(rules))


def render_skill(skill_name: str) -> dict[str, str]:
    skill_root = package_root() / "skills" / skill_name
    if not skill_root.is_dir():
        raise ValueError(f"Unknown generated skill: {skill_name}")
    result: dict[str, str] = {}
    for path in sorted(skill_root.rglob("*")):
        if path.is_file():
            relative = str(path.relative_to(skill_root))
            result[relative] = path.read_text(encoding="utf-8")
    return result


def content_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
