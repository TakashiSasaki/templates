from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent_policy.policy_loader import load_rules
from agent_policy.topology import (
    TopologyDiscoveryError,
    discover_repository_topology,
)

SAMPLE_VALID_TOPOLOGY = {
    "$schema": "../schemas/repository-topology.schema.json",
    "schemaVersion": 1,
    "topologyKind": "hub-and-orphan",
    "hub": {
        "branch": "main",
        "role": "discovery-projection",
        "directMutationForbidden": True,
    },
    "submoduleProjection": {
        "selfReferencing": True,
        "mountRule": "branch-name-equals-mount-path",
    },
    "synchronization": {
        "direction": "authority-to-hub",
        "authorityMustAdvanceBeforeProjection": True,
    },
    "components": [
        {
            "name": "composition",
            "branch": "composition",
            "mountPath": "composition",
            "role": "component-authority",
            "summary": "Composition authority component.",
        },
        {
            "name": "policy",
            "branch": "policy",
            "mountPath": "policy",
            "role": "component-authority",
            "summary": "Policy authority component.",
        },
        {
            "name": "site",
            "branch": "site",
            "mountPath": "site",
            "role": "component-authority",
            "summary": "Site authority component.",
        },
    ],
}


def test_discover_absent_contract_returns_single_worktree(tmp_path: Path) -> None:
    topology = discover_repository_topology(tmp_path)
    assert topology.kind == "single-worktree"
    assert topology.is_single_worktree
    assert not topology.is_hub_and_orphan
    assert len(topology.components) == 0


def test_discover_valid_contract_returns_hub_and_orphan(tmp_path: Path) -> None:
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir(parents=True)
    contract_file = contracts_dir / "repository-topology.json"
    contract_file.write_text(json.dumps(SAMPLE_VALID_TOPOLOGY), encoding="utf-8")

    # Also place schema
    schemas_dir = tmp_path / "schemas"
    schemas_dir.mkdir(parents=True)
    repo_root = Path(__file__).resolve().parents[1]
    (schemas_dir / "repository-topology.schema.json").write_text(
        (repo_root / "src/agent_policy/_topology_contract/schemas/repository-topology.schema.json").read_text(encoding="utf-8"),
        encoding="utf-8",
    )

    topology = discover_repository_topology(tmp_path)
    assert topology.kind == "hub-and-orphan"
    assert topology.is_hub_and_orphan
    assert topology.hub_branch == "main"
    assert len(topology.components) == 3

    policy_comp = topology.component_by_branch("policy")
    assert policy_comp is not None
    assert policy_comp.name == "policy"
    assert policy_comp.mount_path == "policy"
    assert policy_comp.role == "component-authority"

    comp_by_mount = topology.component_by_mount_path("composition")
    assert comp_by_mount is not None
    assert comp_by_mount.name == "composition"


def test_discover_malformed_json_fails_closed(tmp_path: Path) -> None:
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir(parents=True)
    contract_file = contracts_dir / "repository-topology.json"
    contract_file.write_text("{ unparseable json ...", encoding="utf-8")

    with pytest.raises(TopologyDiscoveryError) as exc_info:
        discover_repository_topology(tmp_path)
    assert exc_info.value.code == "TOPOLOGY_CONTRACT_INVALID"


def test_discover_invalid_shape_fails_closed(tmp_path: Path) -> None:
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir(parents=True)
    contract_file = contracts_dir / "repository-topology.json"
    contract_file.write_text("[\"an array not an object\"]", encoding="utf-8")

    with pytest.raises(TopologyDiscoveryError) as exc_info:
        discover_repository_topology(tmp_path)
    assert exc_info.value.code == "TOPOLOGY_CONTRACT_INVALID"


def test_discover_schema_violation_fails_closed(tmp_path: Path) -> None:
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir(parents=True)
    contract_file = contracts_dir / "repository-topology.json"
    bad_data = dict(SAMPLE_VALID_TOPOLOGY)
    del bad_data["hub"]  # required field missing
    contract_file.write_text(json.dumps(bad_data), encoding="utf-8")

    with pytest.raises(TopologyDiscoveryError) as exc_info:
        discover_repository_topology(tmp_path)
    assert exc_info.value.code == "TOPOLOGY_CONTRACT_INVALID"


def test_discover_unsupported_kind_fails_closed(tmp_path: Path) -> None:
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir(parents=True)
    contract_file = contracts_dir / "repository-topology.json"
    bad_data = dict(SAMPLE_VALID_TOPOLOGY)
    bad_data["topologyKind"] = "unsupported-galaxy"
    contract_file.write_text(json.dumps(bad_data), encoding="utf-8")

    with pytest.raises(TopologyDiscoveryError) as exc_info:
        discover_repository_topology(tmp_path)
    assert exc_info.value.code == "TOPOLOGY_CONTRACT_INVALID"


def test_discover_branch_name_mount_path_mismatch_fails_closed(tmp_path: Path) -> None:
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir(parents=True)
    contract_file = contracts_dir / "repository-topology.json"
    bad_data = dict(SAMPLE_VALID_TOPOLOGY)
    bad_data["components"] = [
        {
            "name": "comp1",
            "branch": "branch-one",
            "mountPath": "different-path",
            "role": "component-authority",
        }
    ]
    contract_file.write_text(json.dumps(bad_data), encoding="utf-8")

    with pytest.raises(TopologyDiscoveryError) as exc_info:
        discover_repository_topology(tmp_path)
    assert exc_info.value.code == "TOPOLOGY_CONTRACT_INVALID"


def test_discover_nested_mount_paths_fails_closed(tmp_path: Path) -> None:
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir(parents=True)
    contract_file = contracts_dir / "repository-topology.json"
    bad_data = dict(SAMPLE_VALID_TOPOLOGY)
    bad_data["components"] = [
        {
            "name": "parent",
            "branch": "shared",
            "mountPath": "shared",
            "role": "component-authority",
        },
        {
            "name": "child",
            "branch": "shared/nested",
            "mountPath": "shared/nested",
            "role": "component-authority",
        },
    ]
    contract_file.write_text(json.dumps(bad_data), encoding="utf-8")

    with pytest.raises(TopologyDiscoveryError) as exc_info:
        discover_repository_topology(tmp_path)
    assert exc_info.value.code == "TOPOLOGY_CONTRACT_INVALID"


def test_discover_hub_direct_mutation_allowed_fails_closed(tmp_path: Path) -> None:
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir(parents=True)
    contract_file = contracts_dir / "repository-topology.json"
    bad_data = dict(SAMPLE_VALID_TOPOLOGY)
    bad_data["hub"] = dict(SAMPLE_VALID_TOPOLOGY["hub"])
    bad_data["hub"]["directMutationForbidden"] = False
    contract_file.write_text(json.dumps(bad_data), encoding="utf-8")

    with pytest.raises(TopologyDiscoveryError) as exc_info:
        discover_repository_topology(tmp_path)
    assert exc_info.value.code == "TOPOLOGY_CONTRACT_INVALID"


def test_discover_invalid_sync_direction_fails_closed(tmp_path: Path) -> None:
    contracts_dir = tmp_path / "contracts"
    contracts_dir.mkdir(parents=True)
    contract_file = contracts_dir / "repository-topology.json"
    bad_data = dict(SAMPLE_VALID_TOPOLOGY)
    bad_data["synchronization"] = dict(SAMPLE_VALID_TOPOLOGY["synchronization"])
    bad_data["synchronization"]["direction"] = "hub-to-authority"
    contract_file.write_text(json.dumps(bad_data), encoding="utf-8")

    with pytest.raises(TopologyDiscoveryError) as exc_info:
        discover_repository_topology(tmp_path)
    assert exc_info.value.code == "TOPOLOGY_CONTRACT_INVALID"


def test_core_profile_loads_repository_topology_discovery_rule() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    rules = list(load_rules(repo_root, ["core"], []))
    rule_ids = [r.id for r in rules]
    assert "core.discover-repository-topology-fail-closed" in rule_ids

    rule = next(r for r in rules if r.id == "core.discover-repository-topology-fail-closed")
    assert rule.severity == "mandatory"
    assert rule.overridable is False
    assert rule.order == 45
    assert "Discover repository topology fail-closed" in rule.title


def test_absent_contract_has_safe_empty_lookups(tmp_path: Path) -> None:
    topology = discover_repository_topology(tmp_path)
    assert topology.component_by_branch("anything") is None
    assert topology.component_by_mount_path("anything") is None


def test_present_directory_and_symlink_fail_closed(tmp_path: Path) -> None:
    contract = tmp_path / "contracts/repository-topology.json"
    contract.parent.mkdir()
    contract.mkdir()
    with pytest.raises(TopologyDiscoveryError):
        discover_repository_topology(tmp_path)
    contract.rmdir()
    contract.symlink_to(tmp_path / "absent")
    with pytest.raises(TopologyDiscoveryError):
        discover_repository_topology(tmp_path)


def test_consumer_schema_cannot_disable_validation(tmp_path: Path) -> None:
    (tmp_path / "contracts").mkdir()
    data = dict(SAMPLE_VALID_TOPOLOGY, schemaVersion=999)
    (tmp_path / "contracts/repository-topology.json").write_text(json.dumps(data))
    (tmp_path / "schemas").mkdir()
    (tmp_path / "schemas/repository-topology.schema.json").write_text("{}")
    with pytest.raises(TopologyDiscoveryError):
        discover_repository_topology(tmp_path)
