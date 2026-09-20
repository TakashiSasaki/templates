from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .config import Config, package_root
from .paths import resolve_inside
from .policy_loader import Rule
from .yamlutil import load_yaml

DELIVERY_MAP_RELATIVE = "delivery/presentation-map.yml"
DELIVERY_MAP_PATH = package_root() / DELIVERY_MAP_RELATIVE
DELIVERY_SCHEMA_VERSION = 1
JSON_GENERATED_MARKER = '"agent-policy-generated": true'


@dataclass(frozen=True)
class StagedDelivery:
    startup: str
    bundle: str


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _source_path(repository_root: Path, rule: Rule) -> Path:
    if rule.origin == "toolchain":
        return package_root() / rule.source
    return resolve_inside(repository_root, rule.source, allow_missing=False)


def _validate_string_list(value: Any, label: str) -> list[str]:
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise ValueError(f"Presentation map {label} must be a non-empty string list")
    if len(value) != len(set(value)):
        raise ValueError(f"Presentation map {label} must not contain duplicates")
    return list(value)


def load_presentation_map() -> tuple[dict[str, Any], str]:
    raw = load_yaml(DELIVERY_MAP_PATH)
    if not isinstance(raw, dict) or raw.get("schema_version") != DELIVERY_SCHEMA_VERSION:
        raise ValueError("Unsupported policy-delivery presentation map")
    if raw.get("context") != "coding":
        raise ValueError("Policy-delivery presentation map must target coding context")
    raw_rules = raw.get("rules")
    if not isinstance(raw_rules, dict) or not raw_rules:
        raise ValueError("Policy-delivery presentation map has no rules")
    normalized: dict[str, dict[str, Any]] = {}
    for rule_id, entry in raw_rules.items():
        if not isinstance(rule_id, str) or not rule_id or not isinstance(entry, dict):
            raise ValueError("Policy-delivery presentation map has an invalid rule entry")
        startup = entry.get("startup")
        operations = entry.get("operations")
        if not isinstance(startup, bool):
            raise ValueError(f"Presentation map startup flag is invalid: {rule_id}")
        normalized[rule_id] = {
            "startup": startup,
            "operations": _validate_string_list(operations, f"operations.{rule_id}"),
        }
    fallback = raw.get("fallback")
    if not isinstance(fallback, dict) or fallback.get("mode") != "detail-only":
        raise ValueError("Presentation map must define a detail-only fallback")
    fallback_operations = _validate_string_list(
        fallback.get("operations"), "fallback.operations"
    )
    reason = fallback.get("reason")
    if not isinstance(reason, str) or not reason:
        raise ValueError("Presentation map fallback requires a reason")
    normalized_value = {
        "schema_version": DELIVERY_SCHEMA_VERSION,
        "context": "coding",
        "rules": normalized,
        "fallback": {
            "mode": "detail-only",
            "operations": fallback_operations,
            "reason": reason,
        },
    }
    return normalized_value, _sha256(DELIVERY_MAP_PATH.read_bytes())


def _input_digests(input_paths: dict[str, Path]) -> dict[str, str]:
    return {
        relative: _sha256(path.read_bytes())
        for relative, path in sorted(input_paths.items())
    }


def _route_rows(
    rules: list[Rule], presentation_map: dict[str, Any]
) -> tuple[list[dict[str, Any]], dict[str, list[str]], list[str]]:
    mapped = presentation_map["rules"]
    fallback = presentation_map["fallback"]
    rows: list[dict[str, Any]] = []
    operation_routes: dict[str, list[str]] = {}
    unmapped: list[str] = []
    for rule in rules:
        entry = mapped.get(rule.id)
        if entry is None:
            entry = fallback
            unmapped.append(rule.id)
            mode = "detail-only"
        else:
            mode = "startup" if entry["startup"] else "detail-only"
        operations = list(entry["operations"])
        row = {
            "id": rule.id,
            "origin": rule.origin,
            "source": rule.source,
            "startup": mode == "startup",
            "mode": mode,
            "operations": operations,
        }
        rows.append(row)
        for operation in operations:
            operation_routes.setdefault(operation, []).append(rule.id)
    return rows, {
        operation: ids for operation, ids in sorted(operation_routes.items())
    }, unmapped


def build_detail_bundle(
    config: Config,
    rules: list[Rule],
    *,
    context_name: str,
    project_policy_files: list[str],
    input_paths: dict[str, Path],
    bundle_path: str,
) -> tuple[str, list[dict[str, Any]], dict[str, list[str]]]:
    if not bundle_path:
        raise ValueError("Staged Policy output requires detail_bundle")
    presentation_map, map_digest = load_presentation_map()
    route_rows, operation_routes, unmapped = _route_rows(rules, presentation_map)
    selected_ids = [rule.id for rule in rules]
    rule_values: list[dict[str, Any]] = []
    for rule in rules:
        source_path = _source_path(config.repository_root or Path.cwd(), rule)
        source_bytes = source_path.read_bytes()
        rule_values.append(
            {
                "id": rule.id,
                "title": rule.title,
                "severity": rule.severity,
                "overridable": rule.overridable,
                "order": rule.order,
                "origin": rule.origin,
                "source": rule.source,
                "source_sha256": _sha256(source_bytes),
                "body_sha256": _sha256(rule.body.encode("utf-8")),
                "body": rule.body,
            }
        )
    bundle: dict[str, Any] = {
        "agent-policy-generated": True,
        "schema_version": DELIVERY_SCHEMA_VERSION,
        "context": context_name,
        "renderer": "agents-md-staged",
        "bundle_path": bundle_path,
        "toolchain": dict(config.data["toolchain"]),
        "bindings": {
            "configuration": _input_digests({config.relative_path: config.path}),
            "project_policy": {
                relative: _input_digests({relative: path})[relative]
                for relative, path in sorted(input_paths.items())
                if relative in project_policy_files
            },
            "selected_rule_ids": selected_ids,
        },
        "presentation": {
            "source": DELIVERY_MAP_RELATIVE,
            "source_sha256": map_digest,
            "map": presentation_map,
            "routes": route_rows,
            "operation_routes": operation_routes,
            "unmapped_rule_ids": unmapped,
        },
        "rules": rule_values,
    }
    encoded = json.dumps(bundle, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    startup_rules = [
        {
            "rule": rule,
            "route": route,
        }
        for rule, route in zip(rules, route_rows, strict=True)
        if route["startup"]
    ]
    return encoded, startup_rules, operation_routes


def render_staged_agents(
    config: Config,
    rules: list[Rule],
    *,
    context_name: str,
    project_policy_files: list[str],
    input_paths: dict[str, Path],
    bundle_path: str,
) -> StagedDelivery:
    bundle, startup_rules, operation_routes = build_detail_bundle(
        config,
        rules,
        context_name=context_name,
        project_policy_files=project_policy_files,
        input_paths=input_paths,
        bundle_path=bundle_path,
    )
    from .renderer import environment

    template = environment().get_template("AGENTS-staged.md.j2")
    startup = template.render(
        config=config,
        context_name=context_name,
        project_policy_files=project_policy_files,
        bundle_path=bundle_path,
        startup_rules=startup_rules,
        operation_routes=operation_routes,
        selected_rule_count=len(rules),
    )
    return StagedDelivery(startup=startup, bundle=bundle)
