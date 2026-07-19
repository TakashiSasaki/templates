from __future__ import annotations

import hashlib
import json
import re
import shlex
from collections.abc import Iterable

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .config import Config, package_root
from .policy_loader import Rule

GENERATED_MARKER = "agent-policy-generated: true"
SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
SKILL_CONFIG_PATH_TOKEN = "{{ config_path }}"
SKILL_CONFIG_PATH_SHELL_TOKEN = "{{ config_path_shell }}"
SKILL_CONFIG_PATH_YAML_TOKEN = "{{ config_path_yaml }}"


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


def render_skill(
    skill_name: str,
    *,
    config_path: str = ".agent-policy.yml",
) -> dict[str, str]:
    if SKILL_NAME_PATTERN.fullmatch(skill_name) is None:
        raise ValueError(f"Invalid generated skill name: {skill_name}")
    skill_root = package_root() / "skills" / skill_name
    if not skill_root.is_dir():
        raise ValueError(f"Unknown generated skill: {skill_name}")
    replacements = {
        SKILL_CONFIG_PATH_SHELL_TOKEN: shlex.quote(config_path),
        SKILL_CONFIG_PATH_YAML_TOKEN: json.dumps(config_path),
        SKILL_CONFIG_PATH_TOKEN: config_path,
    }
    result: dict[str, str] = {}
    for path in sorted(skill_root.rglob("*")):
        if path.is_file():
            relative = str(path.relative_to(skill_root))
            content = path.read_text(encoding="utf-8")
            for token, value in replacements.items():
                content = content.replace(token, value)
            result[relative] = content
    return result


def content_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
