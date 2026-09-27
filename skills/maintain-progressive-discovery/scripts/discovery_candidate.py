# agent-policy-generated: true
# source-skill: maintain-progressive-discovery
# DO NOT EDIT DIRECTLY
"""Stage A adapter v2. Explicitly selected; never replaces the adopted runtime."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any
from urllib.parse import unquote, urlsplit

ADAPTER_SCHEMA_JSON = "{{ canonical_discovery_adapter_schema_json }}"
PROJECTION_SCHEMA_JSON = "{{ canonical_discovery_projection_schema_json }}"


def schema(name: str) -> dict[str, Any]:
    embedded = ADAPTER_SCHEMA_JSON if name == "adapter" else PROJECTION_SCHEMA_JSON
    if embedded.startswith("{{"):
        filename = "progressive-discovery-adapter" if name == "adapter" else "discovery-projection"
        return json.loads(
            (Path(__file__).resolve().parents[3] / f"schemas/{filename}.schema.json").read_text()
        )
    return json.loads(embedded)


def under(path: str, prefix: str) -> bool:
    return path == prefix or path.startswith(prefix + "/")


def select(value: Any, tokens: list[str]) -> list[str]:
    """Object keys and array expansion only; no implicit traversal or coercion."""
    if not tokens:
        if not isinstance(value, str) or not value.strip():
            raise ValueError("selector must resolve to nonempty strings")
        return [value]
    key, *rest = tokens
    if key == "*":
        if not isinstance(value, list):
            raise ValueError("selector * requires an array")
        return [leaf for item in value for leaf in select(item, rest)]
    if not isinstance(value, dict) or key not in value:
        raise ValueError(f"selector missing object key: {key}")
    return select(value[key], rest)


def inputs(engine, root: Path, relative: str):
    from jsonschema import Draft202012Validator

    if problem := engine._repository_path_error(root, relative):
        raise ValueError(problem)
    adapter = engine._read_json(root / relative)
    Draft202012Validator(schema("adapter")).validate(adapter)
    expected: dict[str, str] = {"index.md": "index"}
    protected: set[str] = {"index.md"}
    references: list[dict[str, str]] = []
    inventories: list[str] = []

    def add(path: str, kind: str, *, required=False):
        if problem := engine._repository_path_error(root, path):
            raise ValueError(problem)
        if kind == "index" and Path(path).name != "index.md":
            raise ValueError(f"index entry must name index.md: {path}")
        previous = expected.get(path)
        if previous and previous != kind and {previous, kind} != {"file", "index"}:
            raise ValueError(f"conflicting member kinds: {path}")
        expected[path] = "index" if previous == "index" else kind
        if required:
            protected.add(path)

    for entry in adapter["entries"]:
        add(entry["path"], entry["kind"], required=True)
    for inv in adapter.get("inventories", []):
        source = inv["path"]
        add(source, "file", required=True)
        inventories.append(source)
        if Path(source).suffix.lower() not in (
            (".json",) if inv["format"] == "json" else (".yaml", ".yml")
        ):
            raise ValueError(f"inventory format/extension mismatch: {source}")
        data = (engine._read_json if inv["format"] == "json" else engine._read_yaml)(root / source)
        for selector in inv["select"]:
            for member in select(data, selector["at"]):
                namespace = selector["namespace"]
                if namespace == "local":
                    add(member, selector["kind"])
                else:
                    parsed = urlsplit(member)
                    if namespace == "external":
                        valid = (
                            parsed.scheme in {"http", "https"}
                            and bool(parsed.netloc)
                            or not parsed.scheme
                            and engine._safe_relative(member) == member
                        )
                    else:
                        valid = (
                            parsed.scheme in {"http", "https"}
                            and bool(parsed.netloc)
                            or member.startswith("/")
                            and not member.startswith("//")
                        )
                    if not valid:
                        raise ValueError(f"invalid {namespace} reference: {member}")
                    references.append({"source": source, "namespace": namespace, "value": member})
    for projection in adapter.get("projections", []):
        path = projection["path"]
        add(path, "file", required=True)
        inventories.append(path)
        data = engine._read_json(root / path)
        Draft202012Validator(schema("projection")).validate(data)
        declared = [source["path"] for source in data["sources"]]
        if len(declared) != len(set(declared)) or set(declared) != set(projection["sources"]):
            raise ValueError(f"projection source closure mismatch: {path}")
        for source in data["sources"]:
            add(source["path"], "file", required=True)
            actual = hashlib.sha256((root / source["path"]).read_bytes()).hexdigest()
            if actual != source["sha256"]:
                raise ValueError(f"stale projection: {path}: {source['path']}")
        for entry in data["members"]:
            add(entry["path"], entry["kind"])
    generated = {}
    for item in adapter.get("generated", []):
        path = item["path"]
        add(path, "index", required=True)
        if path in generated:
            raise ValueError(f"duplicate generated target: {path}")
        for scope in item["members"]:
            if problem := engine._repository_path_error(root, scope):
                raise ValueError(problem)
            if not any(under(p, scope) and p != path for p in expected):
                raise ValueError(f"generated scope has no expected members: {scope}")
        generated[path] = {
            "title": item["title"],
            "section": item["section"],
            "inventory": item["members"],
        }
    retired = [item["path"] for item in adapter.get("retire", [])]
    if len(set(retired)) != len(retired):
        raise ValueError("duplicate retirement target")
    for path in retired:
        if (
            path in expected
            or Path(path).name != "index.md"
            or engine._repository_path_error(root, path)
        ):
            raise ValueError(f"invalid or active retirement target: {path}")
    for item in adapter.get("delegate", []):
        if problem := engine._repository_path_error(root, item["path"]):
            raise ValueError(problem)
        if not (root / item["path"]).is_dir():
            raise ValueError(f"delegated subtree missing: {item['path']}")
        add(item["entry"]["path"], item["entry"]["kind"], required=True)
    for item in adapter.get("exclude", []):
        path = item["path"]
        if problem := engine._repository_path_error(root, path):
            raise ValueError(problem)
        if any(under(p, path) for p in protected | set(retired)):
            raise ValueError(f"required/excluded conflict: {path}")
        expected = {p: kind for p, kind in expected.items() if not under(p, path)}
    for path, spec in generated.items():
        for scope in spec["inventory"]:
            if not any(under(p, scope) and p != path for p in expected):
                raise ValueError(f"generated scope empty after exclusions: {scope}")
    for item in adapter.get("delegate", []):
        for path, kind in expected.items():
            if kind == "index" and under(path, item["path"]) and path != item["path"] + "/index.md":
                raise ValueError(f"required index hidden by delegation: {path}")
    for omission in adapter.get("omit_from", []):
        path = omission["index"]
        if (
            path == "index.md"
            or Path(path).name != "index.md"
            or engine._repository_path_error(root, path)
            or not (root / path).is_file()
        ):
            raise ValueError(f"invalid scoped omission index: {path}")
        if any(p not in expected for p in omission["paths"]):
            raise ValueError(f"scoped omission of unknown member: {path}")
    return adapter, expected, generated, sorted(set(inventories)), references


def indexes_for(engine, root, adapter):
    excluded = [item["path"] for item in adapter.get("exclude", [])]
    delegated = [item["path"] for item in adapter.get("delegate", [])]
    return sorted(
        engine._relative(p, root)
        for p in engine._walk_files(root)
        if p.name == "index.md"
        and not any(under(engine._relative(p, root), x) for x in excluded)
        and not any(
            under(engine._relative(p, root), x) and engine._relative(p, root) != x + "/index.md"
            for x in delegated
        )
    )


def graph(engine, root, indexes, expected, adapter, generated):
    errors = []
    edges: dict[str, set[str]] = {}
    for index in indexes:
        links, notes = engine._read_index_links(root, index, prose=True)
        errors.extend(notes)
        targets = edges[index] = set()
        for link in links:
            resolved, issue = engine._resolve_link(root, index, link["target"], prose=True)
            if issue:
                errors.append(issue)
            if not resolved or issue:
                continue
            targets.add(resolved)
            if (root / resolved).is_dir():
                nested = resolved.rstrip("/") + "/index.md"
                fragment = urlsplit(link["target"]).fragment
                if fragment:
                    if nested not in indexes or unquote(fragment) not in engine._headings(
                        root / nested
                    ) | engine._anchors(root / nested, prose=True):
                        errors.append(f"{index}: missing directory fragment: {link['target']}")
                if nested in indexes:
                    targets.add(nested)
        if index != "index.md":
            targets.add(str(Path(index).parent))

    def reachable(start):
        seen = set()
        queue = [start] if start in indexes else []
        while queue:
            item = queue.pop()
            if item in seen:
                continue
            seen.add(item)
            queue.extend(edges.get(item, set()) - seen)
        return seen

    reached = reachable("index.md")
    for path, kind in expected.items():
        target = root / path
        exists = target.is_dir() if kind == "directory" else target.is_file()
        if not exists:
            errors.append(f"expected {kind} missing: {path}")
        if path not in reached:
            errors.append(f"root coverage missing: {path}")
    for index in set(indexes) - reached:
        errors.append(f"orphan index: {index}")
    omitted = {}
    for item in adapter.get("omit_from", []):
        omitted.setdefault(item["index"], set()).update(item["paths"])
    for index in indexes:
        if index == "index.md":
            continue
        local = reachable(index)
        prefix = str(Path(index).parent)
        for path in expected:
            if under(path, prefix) and path not in local and path not in omitted.get(index, set()):
                errors.append(f"index coverage missing: {index}: {path}")
        for path in edges.get(index, set()) & omitted.get(index, set()):
            errors.append(f"scoped omission is linked: {index}: {path}")
    for path, spec in generated.items():
        members = [
            p for p in expected if p != path and any(under(p, scope) for scope in spec["inventory"])
        ]
        content = engine._render_generated(root, path, spec, members)
        try:
            if (root / path).read_bytes() != content.encode():
                errors.append(f"generated freshness: stale {path}")
        except OSError:
            errors.append(f"generated freshness: missing {path}")
    return {
        "valid": not errors,
        "errors": sorted(set(errors)),
        "warnings": [],
        "reachable": sorted(reached),
    }


def run(engine, root, *, adapter_path, policy_path, apply=False):
    root = root.resolve()
    policy_raw, policy_errors = engine._yaml_policy(root, policy_path)
    policy = engine._policy_state(policy_raw)
    selected = policy["profile_selected"] and policy["skill_selected"]
    errors = list(policy_errors)
    adapter, expected, generated, inventories, references = {}, {}, {}, [], []
    try:
        adapter, expected, generated, inventories, references = inputs(engine, root, adapter_path)
    except Exception as exc:
        errors.append(f"candidate input: {exc}")
    indexes = indexes_for(engine, root, adapter) if not errors else []
    planning_adapter = {"remove_generated_indexes": [x["path"] for x in adapter.get("retire", [])]}
    plan = (
        []
        if errors
        else engine._plan(
            root,
            planning_adapter,
            indexes,
            sorted(expected),
            generated,
            policy,
            generation_only=True,
        )
    )
    requested = plan
    applied, apply_errors = [], []
    if apply:
        if errors or not selected:
            apply_errors = errors or ["candidate policy/profile not selected"]
        else:
            applied, apply_errors = engine._apply(root, plan, policy)
            indexes = indexes_for(engine, root, adapter)
            plan = engine._plan(
                root,
                planning_adapter,
                indexes,
                sorted(expected),
                generated,
                policy,
                generation_only=True,
            )
    validation = (
        graph(engine, root, indexes, expected, adapter, generated)
        if not errors
        else {"valid": False, "errors": [], "warnings": [], "reachable": []}
    )
    validation["errors"] = sorted(set(validation["errors"] + errors + apply_errors))
    validation["valid"] = not validation["errors"]
    authority = bool(errors or apply_errors or any(p["action"] == "authority-needed" for p in plan))
    actionable = any(p["action"] != "none" for p in plan)
    result = (
        "AUTHORITY_NEEDED"
        if authority
        else "NOT_APPLICABLE"
        if not selected
        else "UPDATE_REQUIRED"
        if actionable or not validation["valid"]
        else "NO_UPDATE_REQUIRED"
    )
    return {
        "schema_version": 2,
        "contract": "candidate-v2",
        "repository": str(root),
        "revision": engine._git_revision(root),
        "dirty": engine._git_dirty(root),
        "policy": policy,
        "policy_selected": selected,
        "adapter": adapter_path,
        "schema_sha256": hashlib.sha256(
            json.dumps(schema("adapter"), sort_keys=True).encode()
        ).hexdigest(),
        "inventories": inventories,
        "expected_documents": sorted(expected),
        "expected_entries": [{"path": p, "kind": k} for p, k in sorted(expected.items())],
        "references": sorted(references, key=lambda x: (x["source"], x["namespace"], x["value"])),
        "indexes": indexes,
        "classification": [
            {
                "index": p,
                "classification": "generated-index-needed"
                if p in generated
                else "authored-index-needed",
                "reason": "explicit or existing navigation boundary",
            }
            for p in sorted(set(indexes) | {p for p, k in expected.items() if k == "index"})
        ],
        "plan": [{k: v for k, v in p.items() if k != "content"} for p in plan],
        "requested_plan": requested if apply else [],
        "applied": applied,
        "apply_errors": apply_errors,
        "validation": validation,
        "notes": errors,
        "exclusions": adapter.get("exclude", []),
        "result": result,
    }
