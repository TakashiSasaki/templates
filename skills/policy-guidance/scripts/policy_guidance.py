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


def _lock_digest(lock_path: Path, relative: str) -> str:
    if not lock_path.is_file():
        raise ValueError(".agent-policy.lock is missing")
    lines = lock_path.read_text(encoding="utf-8").splitlines()
    marker = f"  {relative}:"
    for index, line in enumerate(lines):
        if line != marker:
            continue
        for nested in lines[index + 1 :]:
            if nested and not nested.startswith("    "):
                break
            if nested.startswith("    sha256: "):
                digest = nested.removeprefix("    sha256: ").strip()
                if SHA256_RE.fullmatch(digest):
                    return digest
                break
    raise ValueError(f"lock has no valid output digest for {relative}")


def _load_bundle(root: Path, bundle_relative: str) -> dict[str, Any]:
    bundle_path = _safe_path(root, bundle_relative)
    actual = bundle_path.read_bytes()
    expected = _lock_digest(_safe_path(root, ".agent-policy.lock"), bundle_relative)
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
    routes = presentation.get("routes")
    if not isinstance(routes, list):
        raise ValueError("detail bundle routes are missing")
    route_ids = [route.get("id") for route in routes if isinstance(route, dict)]
    if route_ids != [rule["id"] for rule in rules]:
        raise ValueError("detail bundle routes do not match selected rules")
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
