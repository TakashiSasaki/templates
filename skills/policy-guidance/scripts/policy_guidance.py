#!/usr/bin/env python3
# agent-policy-generated: true
# source-skill: policy-guidance
# DO NOT EDIT DIRECTLY
"""Validate and retrieve an opt-in staged Policy detail bundle."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from typing import Any

DEFAULT_BUNDLE_PATH = "{{ policy_delivery_bundle_path_python }}"
SCHEMA_VERSION = 1
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _safe_path(root: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"path is outside repository root: {relative}")
    resolved_root = root.resolve()
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"path is outside repository root: {relative}") from exc
    if any(part.is_symlink() for part in (root / candidate).parents if part != root):
        raise ValueError(f"path contains a symbolic-link component: {relative}")
    if (root / candidate).is_symlink():
        raise ValueError(f"path must not be a symbolic link: {relative}")
    return resolved


def _safe_package_path(package: Path, relative: str) -> Path:
    candidate = Path(relative)
    if candidate.is_absolute() or ".." in candidate.parts:
        raise ValueError(f"package source path is unsafe: {relative}")
    resolved_root = package.resolve()
    resolved = (package / candidate).resolve()
    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise ValueError(f"package source path is outside package data: {relative}") from exc
    return resolved


def _load_lock(lock_path: Path) -> dict[str, Any]:
    if not lock_path.is_file():
        raise ValueError(".agent-policy.lock is missing")
    try:
        from agent_policy.lockfile import load_lock
    except ImportError as exc:
        raise ValueError(
            "the installed agent-policy package is required for strict lock parsing"
        ) from exc
    try:
        return load_lock(lock_path)
    except (OSError, ValueError) as exc:
        raise ValueError(f"lock file is invalid: {exc}") from exc


def _validate_digest_map(value: Any, label: str) -> dict[str, str]:
    if not isinstance(value, dict) or not value:
        raise ValueError(f"detail bundle {label} bindings are missing")
    result: dict[str, str] = {}
    for relative, digest in value.items():
        if (
            not isinstance(relative, str)
            or not relative
            or not isinstance(digest, str)
            or SHA256_RE.fullmatch(digest) is None
        ):
            raise ValueError(f"detail bundle {label} binding is invalid")
        if relative in result:
            raise ValueError(f"detail bundle {label} bindings contain duplicates")
        result[relative] = digest
    return dict(sorted(result.items()))


def _validate_route_metadata(
    presentation: dict[str, Any], rules: list[dict[str, Any]]
) -> None:
    presentation_map = presentation.get("map")
    if not isinstance(presentation_map, dict):
        raise ValueError("detail bundle presentation map is missing")
    mapped_rules = presentation_map.get("rules")
    fallback = presentation_map.get("fallback")
    if not isinstance(mapped_rules, dict) or not isinstance(fallback, dict):
        raise ValueError("detail bundle presentation map is invalid")
    if (
        fallback.get("mode") != "detail-only"
        or not isinstance(fallback.get("operations"), list)
        or not fallback["operations"]
        or not all(
            isinstance(operation, str) and operation
            for operation in fallback["operations"]
        )
        or len(fallback["operations"]) != len(set(fallback["operations"]))
        or not isinstance(fallback.get("reason"), str)
        or not fallback["reason"]
    ):
        raise ValueError("detail bundle fallback metadata is invalid")
    routes = presentation.get("routes")
    if not isinstance(routes, list):
        raise ValueError("detail bundle routes are missing")
    rule_ids = [rule["id"] for rule in rules]
    rules_by_id = {rule["id"]: rule for rule in rules}
    route_ids: list[str] = []
    expected_operation_routes: dict[str, list[str]] = {}
    expected_unmapped: list[str] = []
    for route in routes:
        if not isinstance(route, dict):
            raise ValueError("detail bundle contains an invalid presentation route")
        rule_id = route.get("id")
        operations = route.get("operations")
        mode = route.get("mode")
        startup = route.get("startup")
        if (
            not isinstance(rule_id, str)
            or rule_id in route_ids
            or not isinstance(operations, list)
            or not all(isinstance(operation, str) and operation for operation in operations)
            or len(operations) != len(set(operations))
            or mode not in {"startup", "detail-only"}
            or not isinstance(startup, bool)
            or startup != (mode == "startup")
        ):
            raise ValueError("detail bundle presentation route is invalid")
        rule = rules_by_id.get(rule_id)
        if rule is None:
            raise ValueError("detail bundle presentation route names an unknown rule")
        entry = mapped_rules.get(rule_id, fallback)
        if not isinstance(entry, dict):
            raise ValueError("detail bundle presentation route is inconsistent")
        expected_startup = entry.get("startup", False)
        if (
            entry.get("operations") != operations
            or expected_startup != startup
            or route.get("origin") != rule.get("origin")
            or route.get("source") != rule.get("source")
        ):
            raise ValueError("detail bundle presentation route is inconsistent")
        if rule_id not in mapped_rules:
            expected_unmapped.append(rule_id)
        route_ids.append(rule_id)
        for operation in operations:
            expected_operation_routes.setdefault(operation, []).append(rule_id)
    if route_ids != rule_ids:
        raise ValueError("detail bundle routes do not match selected rules")

    operation_routes = presentation.get("operation_routes")
    if not isinstance(operation_routes, dict):
        raise ValueError("detail bundle operation routes are missing")
    for operation, selected_ids in operation_routes.items():
        if (
            not isinstance(operation, str)
            or not operation
            or not isinstance(selected_ids, list)
            or len(selected_ids) != len(set(selected_ids))
            or not all(rule_id in rule_ids for rule_id in selected_ids)
            or selected_ids != expected_operation_routes.get(operation, [])
        ):
            raise ValueError("detail bundle operation routes are inconsistent")
    if set(operation_routes) != set(expected_operation_routes):
        raise ValueError("detail bundle operation routes omit or add a route")

    unmapped = presentation.get("unmapped_rule_ids")
    if (
        not isinstance(unmapped, list)
        or len(unmapped) != len(set(unmapped))
        or not all(rule_id in rule_ids for rule_id in unmapped)
        or unmapped != expected_unmapped
    ):
        raise ValueError("detail bundle unmapped rule metadata is invalid")


def _validate_current_bindings(
    root: Path,
    bundle: dict[str, Any],
    lock: dict[str, Any],
) -> None:
    try:
        from agent_policy.config import load_config, package_root, validate_config
        from agent_policy.delivery import load_presentation_map
        from agent_policy.policy_loader import load_rules
    except ImportError as exc:
        raise ValueError(
            "the installed agent-policy package is required for current binding validation"
        ) from exc

    bindings = bundle["bindings"]
    expected_inputs = _validate_digest_map(bindings.get("inputs"), "input")
    if lock["inputs"] != expected_inputs:
        raise ValueError("lock input bindings do not match the detail bundle")
    if lock["toolchain"] != bundle["toolchain"]:
        raise ValueError("lock toolchain identity does not match the detail bundle")

    config_path = bundle.get("config_path")
    context_name = bundle.get("context")
    expected_context = bindings.get("context")
    if (
        not isinstance(config_path, str)
        or not isinstance(context_name, str)
        or not isinstance(expected_context, dict)
        or expected_context.get("name") != context_name
    ):
        raise ValueError("detail bundle context binding is invalid")
    config = load_config(root, config_path)
    diagnostics = validate_config(root, config)
    if diagnostics:
        raise ValueError("current policy configuration is invalid")
    if config.data.get("toolchain") != bundle["toolchain"]:
        raise ValueError("current configuration toolchain differs from detail bundle")
    context = config.contexts.get(context_name)
    if context is None:
        raise ValueError("current policy configuration lacks the selected context")
    actual_context = {
        "name": context.name,
        "profiles": list(context.profiles),
        "project_policy_files": list(context.project_policy_files),
        "overrides": context.override_reasons,
    }
    if actual_context != expected_context:
        raise ValueError("current policy context differs from detail bundle")

    current_inputs = {config.relative_path: config.path}
    current_inputs.update(
        {
            relative: _safe_path(root, relative)
            for relative in config.project_policy_files
        }
    )
    if set(current_inputs) != set(expected_inputs):
        raise ValueError("current policy input set differs from detail bundle")
    for relative, expected_digest in expected_inputs.items():
        path = current_inputs[relative]
        if _digest(path.read_bytes()) != expected_digest:
            raise ValueError(f"current policy input changed: {relative}")

    rules = load_rules(
        root,
        list(context.profiles),
        list(context.project_policy_files),
        declared_overrides=context.override_reasons,
        require_explicit_overrides=True,
    )
    package = package_root()
    bundled_rules = bundle["rules"]
    if [rule.id for rule in rules] != [item["id"] for item in bundled_rules]:
        raise ValueError("current selected rules differ from detail bundle")
    for actual, bundled in zip(rules, bundled_rules, strict=True):
        source_path = (
            _safe_package_path(package, actual.source)
            if actual.origin == "toolchain"
            else _safe_path(root, actual.source)
        )
        if (
            actual.origin != bundled.get("origin")
            or actual.source != bundled.get("source")
            or _digest(source_path.read_bytes()) != bundled.get("source_sha256")
            or _digest(actual.body.encode("utf-8")) != bundled.get("body_sha256")
        ):
            raise ValueError(f"current rule source changed: {actual.id}")

    presentation = bundle["presentation"]
    source = presentation.get("source")
    source_digest = presentation.get("source_sha256")
    if (
        source != "delivery/presentation-map.yml"
        or SHA256_RE.fullmatch(str(source_digest)) is None
    ):
        raise ValueError("detail bundle presentation source identity is invalid")
    actual_map, actual_digest = load_presentation_map()
    if (
        actual_digest != source_digest
        or actual_map != presentation.get("map")
        or _digest(_safe_package_path(package, source).read_bytes()) != source_digest
    ):
        raise ValueError("installed presentation map differs from detail bundle")


def _load_bundle(root: Path, bundle_relative: str) -> dict[str, Any]:
    bundle_path = _safe_path(root, bundle_relative)
    actual = bundle_path.read_bytes()
    lock = _load_lock(_safe_path(root, ".agent-policy.lock"))
    expected = lock["outputs"].get(bundle_relative)
    if not isinstance(expected, str) or SHA256_RE.fullmatch(expected) is None:
        raise ValueError(f"lock has no valid output digest for {bundle_relative}")
    if _digest(actual) != expected:
        raise ValueError("detail bundle does not match .agent-policy.lock")
    try:
        bundle = json.loads(actual.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("detail bundle is not valid UTF-8 JSON") from exc
    if not isinstance(bundle, dict):
        raise ValueError("detail bundle root must be an object")
    if bundle.get("agent-policy-generated") is not True:
        raise ValueError("detail bundle is not an authenticated generated output")
    if bundle.get("schema_version") != SCHEMA_VERSION:
        raise ValueError("unsupported detail bundle schema")
    if bundle.get("bundle_path") != bundle_relative:
        raise ValueError("detail bundle path binding does not match the selected file")
    toolchain = bundle.get("toolchain")
    if (
        not isinstance(toolchain, dict)
        or toolchain.get("repository") != "TakashiSasaki/templates"
        or not isinstance(toolchain.get("revision"), str)
        or re.fullmatch(r"[0-9a-f]{40}", toolchain["revision"]) is None
    ):
        raise ValueError("detail bundle toolchain identity is invalid")
    rules = bundle.get("rules")
    if not isinstance(rules, list) or not rules:
        raise ValueError("detail bundle has no selected rules")
    seen: set[str] = set()
    for rule in rules:
        if not isinstance(rule, dict):
            raise ValueError("detail bundle contains an invalid rule")
        rule_id = rule.get("id")
        body = rule.get("body")
        body_digest = rule.get("body_sha256")
        source_digest = rule.get("source_sha256")
        if (
            not isinstance(rule_id, str)
            or not rule_id
            or rule_id in seen
            or not isinstance(body, str)
            or not isinstance(body_digest, str)
            or SHA256_RE.fullmatch(body_digest) is None
            or _digest(body.encode("utf-8")) != body_digest
            or not isinstance(source_digest, str)
            or SHA256_RE.fullmatch(source_digest) is None
        ):
            raise ValueError("detail bundle rule identity or body is invalid")
        seen.add(rule_id)
    presentation = bundle.get("presentation")
    if not isinstance(presentation, dict):
        raise ValueError("detail bundle presentation metadata is missing")
    bindings = bundle.get("bindings")
    if not isinstance(bindings, dict):
        raise ValueError("detail bundle input bindings are missing")
    selected_ids = bindings.get("selected_rule_ids")
    if selected_ids != [rule["id"] for rule in rules]:
        raise ValueError("detail bundle selected-rule binding is inconsistent")
    _validate_route_metadata(presentation, rules)
    _validate_current_bindings(root, bundle, lock)
    return bundle


def _select(
    bundle: dict[str, Any],
    operation: str | None,
    rule_id: str | None,
    all_rules: bool,
) -> list[dict[str, Any]]:
    rules = bundle["rules"]
    if all_rules:
        return rules
    if rule_id is not None:
        selected = [rule for rule in rules if rule["id"] == rule_id]
        if not selected:
            raise ValueError(f"unknown selected rule: {rule_id}")
        return selected
    if operation is None:
        raise ValueError("choose --operation, --rule-id, or --all")
    unmapped = bundle["presentation"].get("unmapped_rule_ids")
    if isinstance(unmapped, list) and unmapped:
        raise ValueError(
            "operation route is incomplete for selected rules; rerun with --all"
        )
    routes = bundle["presentation"]["operation_routes"].get(operation)
    if routes is None:
        routes = bundle["presentation"]["operation_routes"].get("all")
    if not isinstance(routes, list) or not routes:
        raise ValueError(f"operation has no validated route: {operation}")
    return [rule for rule in rules if rule["id"] in routes]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("."))
    parser.add_argument("--bundle", default=DEFAULT_BUNDLE_PATH)
    parser.add_argument("--operation")
    parser.add_argument("--rule-id")
    parser.add_argument("--all", action="store_true", dest="all_rules")
    parser.add_argument("--format", choices=("text", "json"), default="text")
    args = parser.parse_args()
    try:
        bundle = _load_bundle(args.root, args.bundle)
        selected = _select(bundle, args.operation, args.rule_id, args.all_rules)
    except (OSError, ValueError, KeyError) as exc:
        print(f"policy-guidance error: {exc}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(selected, indent=2, sort_keys=True, ensure_ascii=False))
        return 0
    for index, rule in enumerate(selected):
        if index:
            print("\n---\n")
        print(f"## {rule['title']}\n\n{rule['body']}\n")
        print(
            f"Source: {rule['source']} | rule ID: {rule['id']} | "
            f"severity: {rule['severity']}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
