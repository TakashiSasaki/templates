from __future__ import annotations

import hashlib
import json
import re
import shlex
from collections.abc import Iterable

from jinja2 import Environment, FileSystemLoader, StrictUndefined

from .config import Config, package_root
from .identity import toolchain_reference
from .policy_loader import Rule

GENERATED_MARKER = "agent-policy-generated: true"
SKILL_NAME_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]*$")
NON_GENERATED_SKILLS = frozenset({"agent-policy"})
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


def render_agents(
    config: Config,
    rules: Iterable[Rule],
    *,
    context_name: str = "default",
    project_policy_files: Iterable[str] | None = None,
) -> str:
    template = environment().get_template("AGENTS.md.j2")
    policy_files = (
        list(config.project_policy_files)
        if project_policy_files is None
        else list(project_policy_files)
    )
    return template.render(
        config=config,
        rules=list(rules),
        context_name=context_name,
        project_policy_files=policy_files,
    )


def render_policy_context(
    config: Config,
    rules: Iterable[Rule],
    *,
    context_name: str,
    project_policy_files: Iterable[str],
) -> str:
    template = environment().get_template("policy-context.md.j2")
    return template.render(
        config=config,
        rules=list(rules),
        context_name=context_name,
        project_policy_files=list(project_policy_files),
    )


def render_github_review_json(
    config: Config,
    rules: Iterable[Rule],
    *,
    context_name: str,
    project_policy_files: Iterable[str],
) -> str:
    template = environment().get_template("github-review-json-v1.md.j2")
    return template.render(
        config=config,
        rules=list(rules),
        context_name=context_name,
        project_policy_files=list(project_policy_files),
    )


def render_consumer_workflow(revision: str) -> str:
    template = environment().get_template("workflows/check-agent-policy.yml.j2")
    return template.render(revision=revision)


def render_skill(name: str, config_path: str = ".agent-policy.yml") -> str:
    if not SKILL_NAME_PATTERN.fullmatch(name):
        raise ValueError(f"Invalid generated skill name: {name}")
    if name in NON_GENERATED_SKILLS:
        raise ValueError(f"Unknown generated skill: {name}")
    root = package_root() / "skills"
    skill_path = root / name / "SKILL.md"
    if not skill_path.is_file():
        raise ValueError(f"Unknown generated skill: {name}")
    content = skill_path.read_text(encoding="utf-8")
    if GENERATED_MARKER in content:
        raise ValueError(f"Generated skill source must not contain generated marker: {name}")
    shell_path = shlex.quote(config_path)
    yaml_path = json.dumps(config_path)
    content = content.replace(SKILL_CONFIG_PATH_TOKEN, config_path)
    content = content.replace(SKILL_CONFIG_PATH_SHELL_TOKEN, shell_path)
    content = content.replace(SKILL_CONFIG_PATH_YAML_TOKEN, yaml_path)
    return content.rstrip() + f"\n\n<!-- {GENERATED_MARKER} -->\n"


def hash_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def render_toolchain_reference(revision: str) -> str:
    return toolchain_reference(revision)
