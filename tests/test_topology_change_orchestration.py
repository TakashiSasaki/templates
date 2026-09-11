from __future__ import annotations

from pathlib import Path

from agent_policy.topology import (
    ComponentTopology,
    RepositoryTopology,
)

ROOT = Path(__file__).resolve().parents[1]
WORK_LEDGER = ROOT / "skills" / "orchestrate-repository-change" / "references" / "work-ledger.md"
TRACKED_LEDGER = (
    ROOT / "skills" / "orchestrate-repository-change" / "references" / "repository-tracked-work-ledger.md"
)
STACKED_WORKFLOW = (
    ROOT / "skills" / "orchestrate-repository-change" / "references" / "stacked-pr-workflow.md"
)


def test_work_ledger_guidance_specifies_hub_and_orphan_invariants() -> None:
    text = WORK_LEDGER.read_text(encoding="utf-8")
    assert "## Hub-and-Orphan topology tracking" in text
    assert "hub projection branch (`hub.branch`)" in text
    assert "Direct mutation of component files on the hub projection branch is prohibited" in text
    assert "authority-to-hub" in text
    assert "reconcile component authority state before scheduling hub projection updates" in text.lower()


def test_repository_tracked_work_ledger_enforces_orphan_ref_isolation() -> None:
    text = TRACKED_LEDGER.read_text(encoding="utf-8")
    assert "in repositories using Hub-and-Orphan topology" in text
    assert "independent orphan ref" in text
    assert "does not collide with component authority branch names" in text
    assert "never registered or projected as a submodule in the hub" in text


def test_stacked_pr_workflow_enforces_intra_authority_stacking() -> None:
    text = STACKED_WORKFLOW.read_text(encoding="utf-8")
    assert "## Stacked PRs under Hub-and-Orphan topology" in text
    assert "Intra-authority stacking" in text
    assert "Cross-component independence" in text
    assert (
        "never create a single pr or git commit branch that spans multiple component orphan histories"
        in text.lower()
    )
    assert "Landing and projection advance" in text
    assert (
        "The hub branch is never mutated to land intermediate, unmerged component candidate commits"
        in text
    )


def test_mutation_plan_validation_under_hub_and_orphan() -> None:
    # Verify the operational view; Git mutation authorization remains procedural.
    topology = RepositoryTopology(
        kind="hub-and-orphan",
        hub_branch="main",
        components={
            "policy": ComponentTopology(
                name="policy",
                branch="policy",
                mount_path="policy",
                role="component-authority",
            ),
            "composition": ComponentTopology(
                name="composition",
                branch="composition",
                mount_path="composition",
                role="component-authority",
            ),
        },
    )

    # Valid mutation plan unit targeting component authority branch
    valid_unit = {
        "target_authority": "policy",
        "branch": "feat/policy-feature",
        "base": "policy",
        "files": ["src/agent_policy/cli.py"],
    }
    assert valid_unit["base"] == topology.components["policy"].branch

    # Invalid: direct mutation of component files on hub branch
    invalid_hub_direct_mutation = {
        "target_authority": "hub",
        "branch": "feat/hub-change",
        "base": "main",
        "files": ["policy/src/agent_policy/cli.py"],
    }
    for f in invalid_hub_direct_mutation["files"]:
        mount = f.split("/")[0]
        if mount in topology.components:
            # Component file direct mutation on hub is forbidden
            is_forbidden = True
            break
    assert is_forbidden

    # Operational ref collision check
    operational_ref = "work-ledger"
    assert operational_ref != topology.hub_branch
    assert operational_ref not in topology.components
    assert operational_ref not in [c.branch for c in topology.components.values()]
