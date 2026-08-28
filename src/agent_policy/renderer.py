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
NON_GENERATED_SKILLS = frozenset({"agent-policy", "pr-merge-gate"})
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


def render_output(
    renderer: str,
    config: Config,
    rules: Iterable[Rule],
    *,
    context_name: str,
    project_policy_files: Iterable[str],
) -> str:
    if renderer == "agents-md":
        return render_agents(
            config,
            rules,
            context_name=context_name,
            project_policy_files=project_policy_files,
        )
    if renderer == "policy-context-md":
        return render_policy_context(
            config,
            rules,
            context_name=context_name,
            project_policy_files=project_policy_files,
        )
    if renderer == "github-review-json-v1":
        return render_github_review_json(
            config,
            rules,
            context_name=context_name,
            project_policy_files=project_policy_files,
        )
    raise ValueError(f"Unknown output renderer: {renderer}")


def render_consumer_workflow(toolchain_revision: str) -> str:
    toolchain = toolchain_reference(toolchain_revision)
    template = environment().get_template("workflows/check-agent-policy.yml.j2")
    return template.render(revision=toolchain["revision"])


def render_skill(
    skill_name: str,
    *,
    config_path: str = ".agent-policy.yml",
) -> dict[str, str]:
    if SKILL_NAME_PATTERN.fullmatch(skill_name) is None:
        raise ValueError(f"Invalid generated skill name: {skill_name}")
    if skill_name in NON_GENERATED_SKILLS:
        raise ValueError(f"Unknown generated skill: {skill_name}")
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
