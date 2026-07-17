from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from .config import package_root
from .paths import resolve_inside
from .yamlutil import load_yaml


@dataclass(frozen=True)
class Rule:
    id: str
    title: str
    severity: str
    overridable: bool
    order: int
    source: str
    body: str


def parse_policy(path: Path, source_label: str) -> Rule:
    text = path.read_text(encoding="utf-8")
    if not text.startswith("---\n"):
        raise ValueError(f"Policy file lacks YAML front matter: {source_label}")
    _, front, body = text.split("---\n", 2)
    metadata = yaml.safe_load(front)
    if not isinstance(metadata, dict):
        raise ValueError(f"Invalid policy metadata: {source_label}")
    required = {"id", "severity", "overridable", "order"}
    missing = required.difference(metadata)
    if missing:
        raise ValueError(f"Missing policy metadata {sorted(missing)}: {source_label}")
    title = body.strip().splitlines()[0].lstrip("# ").strip() if body.strip() else metadata["id"]
    return Rule(
        id=str(metadata["id"]),
        title=title,
        severity=str(metadata["severity"]),
        overridable=bool(metadata["overridable"]),
        order=int(metadata["order"]),
        source=source_label,
        body=body.strip(),
    )


def profile_policy_paths(profile: str) -> list[Path]:
    profile_file = package_root() / "profiles" / f"{profile}.yml"
    data: Any = load_yaml(profile_file)
    if not isinstance(data, dict) or not isinstance(data.get("policy_files"), list):
        raise ValueError(f"Invalid profile definition: {profile}")
    return [package_root() / str(item) for item in data["policy_files"]]


def load_rules(repository_root: Path, profiles: list[str], local_files: list[str]) -> list[Rule]:
    rules: list[Rule] = []
    seen: dict[str, Rule] = {}
    for profile in profiles:
        for path in profile_policy_paths(profile):
            rule = parse_policy(path, str(path.relative_to(package_root())))
            if rule.id in seen:
                raise ValueError(f"Duplicate rule ID: {rule.id}")
            seen[rule.id] = rule
            rules.append(rule)
    for relative in local_files:
        path = resolve_inside(repository_root, relative, allow_missing=False)
        rule = parse_policy(path, relative)
        previous = seen.get(rule.id)
        if previous is not None and not previous.overridable:
            raise ValueError(f"Rule {rule.id} is not overridable (defined in {previous.source})")
        if previous is not None:
            rules.remove(previous)
        seen[rule.id] = rule
        rules.append(rule)
    return sorted(rules, key=lambda item: (item.order, item.id))
