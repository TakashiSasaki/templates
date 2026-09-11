"""Generic repository topology discovery and fail-closed operational validation."""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping

TOPOLOGY_CONTRACT_RELATIVE = Path("contracts/repository-topology.json")
TOPOLOGY_SCHEMA_RELATIVE = Path("schemas/repository-topology.schema.json")


class TopologyDiscoveryError(RuntimeError):
    """Raised when repository topology discovery encounters invalid or contradictory state."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(f"[{code}] {message}")
        self.code = code
        self.message = message


@dataclass(frozen=True)
class ComponentTopology:
    name: str
    branch: str
    mount_path: str
    role: str
    summary: str | None = None


@dataclass(frozen=True)
class RepositoryTopology:
    kind: str
    hub_branch: str | None = None
    components: Mapping[str, ComponentTopology] = ()

    @property
    def is_hub_and_orphan(self) -> bool:
        return self.kind == "hub-and-orphan"

    @property
    def is_single_worktree(self) -> bool:
        return self.kind == "single-worktree"

    def component_by_branch(self, branch: str) -> ComponentTopology | None:
        for comp in self.components.values():
            if comp.branch == branch:
                return comp
        return None

    def component_by_mount_path(self, path: str) -> ComponentTopology | None:
        normalized = path.strip("/")
        for comp in self.components.values():
            if comp.mount_path.strip("/") == normalized:
                return comp
        return None


def discover_repository_topology(root: Path) -> RepositoryTopology:
    """Discover the repository topology from contracts/repository-topology.json.

    Fails closed if the contract exists but is malformed, unparseable, or violates
    topological invariants.
    """
    root = root.resolve()
    contract_path = root / TOPOLOGY_CONTRACT_RELATIVE
    if not contract_path.is_file():
        # Conventional single-worktree default
        return RepositoryTopology(kind="single-worktree")

    try:
        raw_text = contract_path.read_text(encoding="utf-8")
    except Exception as exc:
        raise TopologyDiscoveryError(
            "TOPOLOGY_READ_FAILED", f"unable to read {TOPOLOGY_CONTRACT_RELATIVE}: {exc}"
        ) from exc

    try:
        data = json.loads(raw_text)
    except Exception as exc:
        raise TopologyDiscoveryError(
            "TOPOLOGY_JSON_INVALID", f"invalid JSON in {TOPOLOGY_CONTRACT_RELATIVE}: {exc}"
        ) from exc

    if not isinstance(data, dict):
        raise TopologyDiscoveryError(
            "TOPOLOGY_SHAPE_INVALID", f"{TOPOLOGY_CONTRACT_RELATIVE} must contain a JSON object"
        )

    # Validate against schema if available
    schema_path = root / TOPOLOGY_SCHEMA_RELATIVE
    if not schema_path.is_file():
        # Fallback to internal policy schema
        internal_schema = Path(__file__).resolve().parents[2] / TOPOLOGY_SCHEMA_RELATIVE
        if internal_schema.is_file():
            schema_path = internal_schema

    if schema_path.is_file():
        try:
            import jsonschema

            schema = json.loads(schema_path.read_text(encoding="utf-8"))
            jsonschema.validate(instance=data, schema=schema)
        except ImportError:
            pass
        except Exception as exc:
            raise TopologyDiscoveryError(
                "TOPOLOGY_SCHEMA_VIOLATION",
                f"{TOPOLOGY_CONTRACT_RELATIVE} violates schema {schema_path.name}: {exc}",
            ) from exc

    topology_kind = data.get("topologyKind")
    if topology_kind != "hub-and-orphan":
        raise TopologyDiscoveryError(
            "UNSUPPORTED_TOPOLOGY_KIND", f"unsupported topologyKind: {topology_kind!r}"
        )

    hub = data.get("hub")
    if not isinstance(hub, dict):
        raise TopologyDiscoveryError("TOPOLOGY_HUB_MISSING", "hub configuration object is required")

    hub_branch = hub.get("branch")
    if not isinstance(hub_branch, str) or not hub_branch.strip():
        raise TopologyDiscoveryError(
            "TOPOLOGY_HUB_BRANCH_INVALID", "hub.branch must be a non-empty string"
        )

    if hub.get("role") != "discovery-projection":
        raise TopologyDiscoveryError(
            "TOPOLOGY_HUB_ROLE_INVALID", "hub.role must be 'discovery-projection'"
        )

    if hub.get("directMutationForbidden") is not True:
        raise TopologyDiscoveryError(
            "TOPOLOGY_HUB_MUTATION_ALLOWED", "hub.directMutationForbidden must be true"
        )

    submodule = data.get("submoduleProjection")
    if not isinstance(submodule, dict):
        raise TopologyDiscoveryError(
            "TOPOLOGY_SUBMODULE_MISSING", "submoduleProjection configuration object is required"
        )
    if submodule.get("selfReferencing") is not True:
        raise TopologyDiscoveryError(
            "TOPOLOGY_SUBMODULE_NOT_SELF_REFERENCING",
            "submoduleProjection.selfReferencing must be true",
        )
    if submodule.get("mountRule") != "branch-name-equals-mount-path":
        raise TopologyDiscoveryError(
            "TOPOLOGY_MOUNT_RULE_INVALID",
            "submoduleProjection.mountRule must be 'branch-name-equals-mount-path'",
        )

    sync = data.get("synchronization")
    if not isinstance(sync, dict):
        raise TopologyDiscoveryError(
            "TOPOLOGY_SYNCHRONIZATION_MISSING", "synchronization configuration object is required"
        )
    if sync.get("direction") != "authority-to-hub":
        raise TopologyDiscoveryError(
            "TOPOLOGY_SYNC_DIRECTION_INVALID",
            "synchronization.direction must be 'authority-to-hub'",
        )
    if sync.get("authorityMustAdvanceBeforeProjection") is not True:
        raise TopologyDiscoveryError(
            "TOPOLOGY_SYNC_ORDER_INVALID",
            "synchronization.authorityMustAdvanceBeforeProjection must be true",
        )

    raw_components = data.get("components")
    if not isinstance(raw_components, list):
        raise TopologyDiscoveryError(
            "TOPOLOGY_COMPONENTS_INVALID", "components must be an array"
        )

    components: dict[str, ComponentTopology] = {}
    seen_branches: set[str] = set()
    seen_mount_paths: list[str] = []

    for index, item in enumerate(raw_components):
        if not isinstance(item, dict):
            raise TopologyDiscoveryError(
                "TOPOLOGY_COMPONENT_INVALID", f"components[{index}] must be an object"
            )
        name = item.get("name")
        branch = item.get("branch")
        mount_path = item.get("mountPath")
        role = item.get("role")
        summary = item.get("summary")

        if not isinstance(name, str) or not name.strip():
            raise TopologyDiscoveryError(
                "TOPOLOGY_COMPONENT_NAME_INVALID", f"components[{index}].name must be a non-empty string"
            )
        if name in components:
            raise TopologyDiscoveryError(
                "DUPLICATE_COMPONENT_NAME", f"duplicate component name: {name}"
            )

        if not isinstance(branch, str) or not branch.strip():
            raise TopologyDiscoveryError(
                "TOPOLOGY_COMPONENT_BRANCH_INVALID", f"components[{index}].branch must be a non-empty string"
            )
        if branch in seen_branches:
            raise TopologyDiscoveryError(
                "DUPLICATE_COMPONENT_BRANCH", f"duplicate component branch: {branch}"
            )
        seen_branches.add(branch)

        if branch == hub_branch:
            raise TopologyDiscoveryError(
                "COMPONENT_BRANCH_IS_HUB", f"component branch {branch!r} cannot be the Hub branch"
            )

        if not isinstance(mount_path, str) or not mount_path.strip():
            raise TopologyDiscoveryError(
                "TOPOLOGY_COMPONENT_MOUNT_INVALID", f"components[{index}].mountPath must be a non-empty string"
            )

        # Invariant 1: branch-name == mount-path rule
        if branch != mount_path:
            raise TopologyDiscoveryError(
                "BRANCH_NAME_MOUNT_PATH_MISMATCH",
                f"component {name!r}: branch {branch!r} does not equal mountPath {mount_path!r}",
            )

        # Invariant 2: leaf-only namespace rule (no nesting or prefix collision)
        normalized_path = mount_path.strip("/")
        for existing in seen_mount_paths:
            if (
                normalized_path == existing
                or normalized_path.startswith(existing + "/")
                or existing.startswith(normalized_path + "/")
            ):
                raise TopologyDiscoveryError(
                    "LEAF_NAMESPACE_VIOLATION",
                    f"component {name!r}: mountPath {mount_path!r} collides or nests with "
                    f"existing mountPath {existing!r} (leaf-only namespace violation)",
                )
        seen_mount_paths.append(normalized_path)

        if role != "component-authority":
            raise TopologyDiscoveryError(
                "TOPOLOGY_COMPONENT_ROLE_INVALID",
                f"components[{index}].role must be 'component-authority'",
            )

        components[name] = ComponentTopology(
            name=name,
            branch=branch,
            mount_path=mount_path,
            role=role,
            summary=summary if isinstance(summary, str) else None,
        )

    return RepositoryTopology(
        kind=topology_kind,
        hub_branch=hub_branch,
        components=components,
    )
