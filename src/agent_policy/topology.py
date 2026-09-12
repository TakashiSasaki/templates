"""Operational ingestion of the pinned, Composition-owned topology contract."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path

from ._topology_contract import validator

TOPOLOGY_CONTRACT_RELATIVE = validator.TOPOLOGY_CONTRACT
TOPOLOGY_SCHEMA_RELATIVE = validator.TOPOLOGY_SCHEMA
CONTRACT_SOURCE_ROOT = Path(validator.__file__).parent


class TopologyDiscoveryError(RuntimeError):
    """Topology is unreadable or invalid; mutation must not proceed."""

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
    components: Mapping[str, ComponentTopology] = field(default_factory=dict)

    @property
    def is_hub_and_orphan(self) -> bool:
        return self.kind == "hub-and-orphan"

    @property
    def is_single_worktree(self) -> bool:
        return self.kind == "single-worktree"

    def component_by_branch(self, branch: str) -> ComponentTopology | None:
        return next((c for c in self.components.values() if c.branch == branch), None)

    def component_by_mount_path(self, path: str) -> ComponentTopology | None:
        return next((c for c in self.components.values() if c.mount_path == path.strip("/")), None)


def discover_repository_topology(root: Path) -> RepositoryTopology:
    """Read a declaration, not Git graph evidence or authorization to mutate.

    The bundled schema and validator are an immutable upstream snapshot. Consumer
    schemas cannot weaken validation. Absence never overrides repository-local
    authority instructions or proves that all branch histories are related.
    """
    root = root.resolve()
    contract_path = root / TOPOLOGY_CONTRACT_RELATIVE
    if (root / "contracts").is_symlink() or contract_path.is_symlink():
        raise TopologyDiscoveryError("TOPOLOGY_PATH_UNSAFE", "contract path contains a symlink")
    if not contract_path.exists():
        return RepositoryTopology(kind="single-worktree")
    try:
        data = validator.load_json(root, TOPOLOGY_CONTRACT_RELATIVE)
        schema = validator.load_json(CONTRACT_SOURCE_ROOT, TOPOLOGY_SCHEMA_RELATIVE)
        errors = validator.validate_contract(data, schema)
    except validator.TopologyValidationError as exc:
        raise TopologyDiscoveryError("TOPOLOGY_CONTRACT_INVALID", str(exc)) from exc
    if errors:
        raise TopologyDiscoveryError("TOPOLOGY_CONTRACT_INVALID", "; ".join(errors))
    return RepositoryTopology(
        kind=data["topologyKind"],
        hub_branch=data["hub"]["branch"],
        components={
            item["name"]: ComponentTopology(
                name=item["name"], branch=item["branch"], mount_path=item["mountPath"],
                role=item["role"], summary=item.get("summary"),
            )
            for item in data["components"]
        },
    )
