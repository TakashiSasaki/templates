from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "plan_policy_release_chain.py"
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location(
        "plan_policy_release_chain",
        SCRIPT,
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


planner = _load_script()


def _stage(plan: dict, name: str) -> dict:
    return next(stage for stage in plan["stages"] if stage["name"] == name)


def test_current_release_chain_inventory_is_complete_and_immutable() -> None:
    plan = planner.build_plan(ROOT)
    assert set(plan["current"]) == {"T", "S", "I"}
    for value in plan["current"].values():
        assert FULL_SHA.fullmatch(value)
    assert planner.check_current_inventory(plan) == []
    assert plan["awaiting_release_evidence"] == []
    assert plan["invariants"] == {
        "full_sha_only": True,
        "predict_future_commit_sha": False,
        "self_referential_release": False,
        "site_is_policy_super_authority": False,
        "runtime_lock_digest_required": True,
    }


def test_toolchain_change_stales_full_downstream_chain() -> None:
    plan = planner.build_plan(ROOT, toolchain_revision="a" * 40)
    assert plan["changed"] == {"T": True, "S": False, "I": False}
    assert plan["stale_stages"] == [
        "T-self-host-input",
        "T-self-host-projection",
        "T-promotion",
        "S-installer-candidate",
        "I-policy-publication",
        "policy-to-site-projection",
    ]
    assert plan["awaiting_immutable_identity_materialization"] == ["S", "I"]
    assert plan["awaiting_release_evidence"] == ["runtime-lock-sha256"]
    assert plan["runtime_lock"]["available"] is False


def test_current_identities_cannot_masquerade_as_fresh_materialization() -> None:
    current = planner.current_identities(ROOT)
    plan = planner.build_plan(
        ROOT,
        toolchain_revision="a" * 40,
        skill_source_revision=current["S"],
        installer_revision=current["I"],
    )
    assert plan["fresh_materialized"] == {
        "T": True,
        "S": False,
        "I": False,
    }
    assert plan["awaiting_immutable_identity_materialization"] == ["S", "I"]


def test_installer_cannot_be_fresh_when_new_toolchain_lacks_new_skill() -> None:
    current = planner.current_identities(ROOT)
    plan = planner.build_plan(
        ROOT,
        toolchain_revision="a" * 40,
        skill_source_revision=current["S"],
        installer_revision="c" * 40,
    )
    assert plan["fresh_materialized"]["S"] is False
    assert plan["fresh_materialized"]["I"] is False
    assert plan["awaiting_immutable_identity_materialization"] == ["S", "I"]


def test_new_toolchain_and_skill_still_wait_for_new_installer() -> None:
    plan = planner.build_plan(
        ROOT,
        toolchain_revision="a" * 40,
        skill_source_revision="b" * 40,
    )
    assert plan["fresh_materialized"]["S"] is True
    assert plan["fresh_materialized"]["I"] is False
    assert plan["awaiting_immutable_identity_materialization"] == ["I"]


def test_new_skill_with_current_installer_keeps_publication_waiting() -> None:
    current = planner.current_identities(ROOT)
    plan = planner.build_plan(
        ROOT,
        skill_source_revision="b" * 40,
        installer_revision=current["I"],
    )
    assert plan["awaiting_immutable_identity_materialization"] == ["I"]
    candidate_paths = {
        surface["path"]
        for surface in _stage(plan, "S-installer-candidate")[
            "direct_surfaces"
        ]
    }
    assert "release/skill-installer.json" not in candidate_paths


def test_new_skill_and_installer_make_publication_surfaces_actionable() -> None:
    plan = planner.build_plan(
        ROOT,
        skill_source_revision="b" * 40,
        installer_revision="c" * 40,
    )
    assert plan["awaiting_immutable_identity_materialization"] == []
    descriptor_records = [
        surface
        for surface in _stage(plan, "I-policy-publication")[
            "direct_surfaces"
        ]
        if surface["path"] == "release/skill-installer.json"
    ]
    assert {record["identity"] for record in descriptor_records} == {"S", "I"}
    assert all(record["requires_change"] for record in descriptor_records)


def test_installer_only_change_does_not_regenerate_toolchain_or_skill() -> None:
    plan = planner.build_plan(ROOT, installer_revision="c" * 40)
    assert plan["stale_stages"] == [
        "I-policy-publication",
        "policy-to-site-projection",
    ]
    assert plan["awaiting_immutable_identity_materialization"] == []


def test_self_host_input_and_generated_outputs_are_distinct() -> None:
    plan = planner.build_plan(ROOT)
    input_stage = _stage(plan, "T-self-host-input")
    generated = _stage(plan, "T-self-host-projection")[
        "generated_surfaces"
    ]
    assert input_stage["input_mutations"] == [".agent-policy.yml"]
    assert ".agent-policy.yml" not in generated
    assert ".agent-policy.lock" in generated
    assert ".agents/skills/pr-review/" in generated


def test_changed_toolchain_requires_explicit_runtime_lock_digest() -> None:
    plan = planner.build_plan(ROOT, toolchain_revision="a" * 40)
    assert plan["runtime_lock"] == {
        "available": False,
        "status": "runtime lock digest unavailable / awaiting",
    }
    digest = "d" * 64
    plan = planner.build_plan(
        ROOT,
        toolchain_revision="a" * 40,
        runtime_lock_sha256=digest,
    )
    assert plan["runtime_lock"]["available"] is True
    assert plan["runtime_lock"]["sha256"] == digest
    assert plan["awaiting_release_evidence"] == []


def test_invalid_runtime_lock_digest_fails_closed() -> None:
    with pytest.raises(ValueError, match="runtime lock digest"):
        planner.build_plan(
            ROOT,
            toolchain_revision="a" * 40,
            runtime_lock_sha256="not-a-digest",
        )


def test_surface_inventory_reports_deterministic_replacement_counts() -> None:
    plan = planner.build_plan(
        ROOT,
        skill_source_revision="b" * 40,
        installer_revision="c" * 40,
    )
    skill_surfaces = _stage(plan, "S-installer-candidate")[
        "direct_surfaces"
    ]
    publication_surfaces = _stage(plan, "I-policy-publication")[
        "direct_surfaces"
    ]
    assert all(
        surface["current_identity_occurrences"] >= 1
        for surface in skill_surfaces
    )
    assert all(
        surface["current_identity_occurrences"] >= 1
        for surface in publication_surfaces
    )


def test_site_projection_preserves_authority_boundary() -> None:
    plan = planner.build_plan(ROOT, installer_revision="d" * 40)
    site = _stage(plan, "policy-to-site-projection")
    assert site["external_authority"] == "site"
    assert "publication-sources.json" in site["generated_surfaces"]
    assert plan["invariants"]["site_is_policy_super_authority"] is False
