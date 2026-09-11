#!/usr/bin/env python3
"""Validate Hub-and-Orphan repository topology contract and structural invariants."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

TOPOLOGY_CONTRACT = Path("contracts/repository-topology.json")
TOPOLOGY_SCHEMA = Path("schemas/repository-topology.schema.json")


class TopologyValidationError(RuntimeError):
    """Raised when the repository topology contract violates repository invariants."""


def load_json(root: Path, relative: Path) -> dict[str, Any]:
    target = root / relative
    current = root
    for part in relative.parts:
        current = current / part
        if current.is_symlink():
            raise TopologyValidationError(f"symbolic link is not allowed: {relative}")
    if not target.is_file():
        raise TopologyValidationError(f"required contract file does not exist: {relative}")
    try:
        data = json.loads(target.read_text(encoding="utf-8"))
    except Exception as exc:
        raise TopologyValidationError(f"cannot parse JSON from {relative}: {exc}") from exc
    if not isinstance(data, dict):
        raise TopologyValidationError(f"{relative} must contain a JSON object")
    return data


def valid_branch_path(value: object) -> bool:
    """Portable relative path that is also a valid Git branch name."""
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*", value):
        return False
    return (
        value != "HEAD" and not value.startswith("-") and ".." not in value
        and not value.endswith(".")
        and all(not part.startswith(".") and not part.endswith(".lock") for part in value.split("/"))
    )


def validate_topology(root: Path) -> list[str]:
    contract = load_json(root, TOPOLOGY_CONTRACT)
    schema = load_json(root, TOPOLOGY_SCHEMA)
    return validate_contract(contract, schema)


def validate_contract(contract: dict[str, Any], schema: dict[str, Any]) -> list[str]:
    """Validate one in-memory declaration against the Composition-owned contract."""
    try:
        import jsonschema

        jsonschema.validate(instance=contract, schema=schema)
    except ImportError as exc:
        raise TopologyValidationError("jsonschema is required; validation cannot be skipped") from exc
    except Exception as exc:
        raise TopologyValidationError(f"contract failed schema validation: {exc}") from exc

    errors: list[str] = []

    # Topology kind invariant
    if contract.get("topologyKind") != "hub-and-orphan":
        errors.append(f"unsupported topology kind: {contract.get('topologyKind')}")

    # Hub projection role invariant
    hub = contract.get("hub")
    if not isinstance(hub, dict):
        errors.append("hub configuration is required")
        return errors

    hub_branch = hub.get("branch")
    if not valid_branch_path(hub_branch):
        errors.append("hub.branch must be a valid Git branch and safe relative path")
    if hub.get("role") != "discovery-projection":
        errors.append("hub.role must be 'discovery-projection'")
    if hub.get("directMutationForbidden") is not True:
        errors.append("hub.directMutationForbidden must be true")

    # Submodule projection invariant
    submodule = contract.get("submoduleProjection")
    if not isinstance(submodule, dict):
        errors.append("submoduleProjection configuration is required")
    else:
        if submodule.get("selfReferencing") is not True:
            errors.append("submoduleProjection.selfReferencing must be true")
        if submodule.get("mountRule") != "branch-name-equals-mount-path":
            errors.append("submoduleProjection.mountRule must be 'branch-name-equals-mount-path'")

    # Synchronization direction invariant
    synchronization = contract.get("synchronization")
    if not isinstance(synchronization, dict):
        errors.append("synchronization configuration is required")
    else:
        if synchronization.get("direction") != "authority-to-hub":
            errors.append("synchronization.direction must be 'authority-to-hub'")
        if synchronization.get("authorityMustAdvanceBeforeProjection") is not True:
            errors.append("synchronization.authorityMustAdvanceBeforeProjection must be true")

    # Components invariants
    components = contract.get("components")
    if not isinstance(components, list):
        errors.append("components must be an array")
        return errors

    seen_names: set[str] = set()
    seen_branches: set[str] = set()
    seen_mount_paths: list[str] = []

    for index, comp in enumerate(components):
        if not isinstance(comp, dict):
            errors.append(f"components[{index}] must be an object")
            continue

        name = comp.get("name")
        branch = comp.get("branch")
        mount_path = comp.get("mountPath")
        role = comp.get("role")

        if not isinstance(name, str) or not name:
            errors.append(f"components[{index}].name must be a non-empty string")
        elif name in seen_names:
            errors.append(f"duplicate component name: {name}")
        else:
            seen_names.add(name)

        if not isinstance(branch, str) or not branch:
            errors.append(f"components[{index}].branch must be a non-empty string")
        elif not valid_branch_path(branch):
            errors.append(f"invalid component branch/path: {branch!r}")
        elif branch in seen_branches:
            errors.append(f"duplicate component branch: {branch}")
        else:
            seen_branches.add(branch)

        if isinstance(branch, str) and isinstance(hub_branch, str) and (
            branch == hub_branch or branch.startswith(hub_branch + "/")
            or hub_branch.startswith(branch + "/")
        ):
            errors.append(f"component branch cannot be the Hub branch: {branch}")

        if not isinstance(mount_path, str) or not mount_path:
            errors.append(f"components[{index}].mountPath must be a non-empty string")
        else:
            # Rule: branch-name == mount-path
            if branch != mount_path:
                errors.append(
                    f"component {name!r}: branch {branch!r} does not equal mountPath {mount_path!r} "
                    "(violates branch-name == mount-path rule)"
                )

            # Rule: leaf-only disjoint namespace
            normalized_path = mount_path.strip("/")
            for existing in seen_mount_paths:
                if (
                    normalized_path == existing
                    or normalized_path.startswith(existing + "/")
                    or existing.startswith(normalized_path + "/")
                ):
                    errors.append(
                        f"component {name!r}: mountPath {mount_path!r} collides or nests with "
                        f"existing mountPath {existing!r} (violates leaf-only namespace rule)"
                    )
            seen_mount_paths.append(normalized_path)

        if role != "component-authority":
            errors.append(f"components[{index}].role must be 'component-authority'")

    return errors


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", default=".", help="Repository root path")
    args = parser.parse_args()

    root = Path(args.root).resolve()
    try:
        errors = validate_topology(root)
    except TopologyValidationError as exc:
        print(f"validate_repository_topology.py: {exc}", file=sys.stderr)
        return 1

    if errors:
        for err in errors:
            print(f"validate_repository_topology.py: ERROR: {err}", file=sys.stderr)
        return 1

    print("validate_repository_topology.py: OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
