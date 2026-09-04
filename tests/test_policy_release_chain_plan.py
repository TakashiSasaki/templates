from __future__ import annotations

import importlib.util
import re
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "plan_policy_release_chain.py"
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")


def _load_script() -> ModuleType:
    spec = importlib.util.spec_from_file_location("plan_policy_release_chain", SCRIPT)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


planner = _load_script()


def test_current_release_chain_inventory_is_complete_and_immutable() -> None:
    plan = planner.build_plan(ROOT)
    assert set(plan["current"]) == {"T", "S", "I"}
    for value in plan["current"].values():
        assert FULL_SHA.fullmatch(value)
    assert planner.check_current_inventory(plan) == []
    assert plan["invariants"] == {
        "full_sha_only": True,
        "predict_future_commit_sha": False,
        "self_referential_release": False,
        "site_is_policy_super_authority": False,
    }


def test_toolchain_change_marks_downstream_materialization_stale_without_inventing_shas() -> None:
    plan = planner.build_plan(ROOT, toolchain_revision="a" * 40)
    assert plan["changed"] == {"T": True, "S": False, "I": False}
    assert plan["stale_stages"] == [
        "T-self-host-projection",
        "T-promotion",
        "S-installer-candidate",
        "I-policy-publication",
        "policy-to-site-projection",
    ]
    assert plan["awaiting_immutable_identity_materialization"] == ["S", "I"]
    assert plan["requested"]["S"] == plan["current"]["S"]
    assert plan["requested"]["I"] == plan["current"]["I"]


def test_surface_inventory_reports_deterministic_replacement_counts() -> None:
    plan = planner.build_plan(
        ROOT,
        skill_source_revision="b" * 40,
        installer_revision="c" * 40,
    )
    by_name = {stage["name"]: stage for stage in plan["stages"]}
    skill_surfaces = by_name["S-installer-candidate"]["direct_surfaces"]
    installer_surfaces = by_name["I-policy-publication"]["direct_surfaces"]
    assert all(
        surface["current_identity_occurrences"] >= 1 for surface in skill_surfaces
    )
    assert all(
        surface["expected_replacements"]
        == surface["current_identity_occurrences"]
        for surface in skill_surfaces
    )
    assert all(
        surface["current_identity_occurrences"] >= 1
        for surface in installer_surfaces
    )
    assert all(
        surface["expected_replacements"]
        == surface["current_identity_occurrences"]
        for surface in installer_surfaces
    )


def test_site_projection_is_inventory_only_and_preserves_authority_boundary() -> None:
    plan = planner.build_plan(ROOT, installer_revision="d" * 40)
    site = next(
        stage
        for stage in plan["stages"]
        if stage["name"] == "policy-to-site-projection"
    )
    assert site["external_authority"] == "site"
    assert "publication-sources.json" in site["generated_surfaces"]
    assert plan["invariants"]["site_is_policy_super_authority"] is False
