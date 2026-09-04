from __future__ import annotations

import hashlib
import importlib.util
import json
import re
import shutil
from pathlib import Path
from types import ModuleType

import pytest

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


def _stage(plan: dict, name: str) -> dict:
    return next(stage for stage in plan["stages"] if stage["name"] == name)


def _reader(mapping: dict[tuple[str, str], bytes]):
    def read(revision: str, path: str) -> bytes | None:
        return mapping.get((revision, path))

    return read


def _verified_reader(
    *,
    toolchain: str | None = None,
    skill_source: str | None = None,
    installer: str | None = None,
    skill_toolchain: str | None = None,
    installer_skill: str | None = None,
    lock_bytes: bytes = b"candidate runtime lock\n",
):
    current = planner.current_identities(ROOT)
    mapping: dict[tuple[str, str], bytes] = {}
    if toolchain is not None:
        mapping[(toolchain, planner.RUNTIME_LOCK)] = lock_bytes
        runtime_digest = hashlib.sha256(lock_bytes).hexdigest()
    else:
        runtime_digest = planner._current_runtime_lock_evidence(ROOT)["sha256"]
    if skill_source is not None:
        manifest = {
            "schema_version": 1,
            "toolchain": {
                "repository": planner.REPOSITORY,
                "revision": skill_toolchain or toolchain or current["T"],
            },
            "runtime_lock": {
                "path": planner.RUNTIME_LOCK,
                "sha256": runtime_digest,
            },
        }
        mapping[(skill_source, planner.SKILL_RUNTIME_MANIFEST)] = json.dumps(manifest).encode()
    if installer is not None:
        source = installer_skill or skill_source or current["S"]
        script = (
            f'TOOLCHAIN_REPOSITORY = "{planner.REPOSITORY}"\n'
            f'INSTALLER_PATH = "{planner.INSTALLER_SCRIPT}"\n'
            f'SKILL_SOURCE_REVISION = "{source}"\n'
            'SKILL_SOURCE_PATH = "skills/agent-policy"\n'
        )
        mapping[(installer, planner.INSTALLER_SCRIPT)] = script.encode()
    return _reader(mapping)


def test_current_release_chain_inventory_is_complete_and_immutable() -> None:
    plan = planner.build_plan(ROOT)
    assert set(plan["current"]) == {"T", "S", "I"}
    for value in plan["current"].values():
        assert FULL_SHA.fullmatch(value)
    assert planner.check_current_inventory(plan) == []
    assert plan["awaiting_immutable_identity_materialization"] == []
    assert plan["awaiting_release_evidence"] == []
    assert plan["invariants"] == {
        "full_sha_only": True,
        "predict_future_commit_sha": False,
        "self_referential_release": False,
        "site_is_policy_super_authority": False,
        "runtime_lock_digest_required": True,
    }


def test_toolchain_change_verifies_lock_but_still_awaits_new_skill_and_installer() -> None:
    toolchain = "a" * 40
    plan = planner.build_plan(
        ROOT,
        toolchain_revision=toolchain,
        revision_reader=_verified_reader(toolchain=toolchain),
    )
    assert plan["fresh_materialized"] == {"T": True, "S": False, "I": False}
    assert plan["awaiting_immutable_identity_materialization"] == ["S", "I"]
    assert plan["runtime_lock"]["verified"] is True
    assert plan["runtime_lock"]["revision"] == toolchain
    assert plan["awaiting_release_evidence"] == []


def test_unresolvable_toolchain_keeps_runtime_evidence_and_chain_awaiting() -> None:
    plan = planner.build_plan(
        ROOT,
        toolchain_revision="a" * 40,
        revision_reader=_reader({}),
    )
    assert plan["fresh_materialized"] == {"T": False, "S": False, "I": False}
    assert plan["awaiting_immutable_identity_materialization"] == ["T", "S", "I"]
    assert plan["awaiting_release_evidence"] == ["runtime-lock-sha256"]
    assert plan["runtime_lock"]["verified"] is False


def test_current_downstream_identities_cannot_masquerade_as_fresh() -> None:
    current = planner.current_identities(ROOT)
    toolchain = "a" * 40
    plan = planner.build_plan(
        ROOT,
        toolchain_revision=toolchain,
        skill_source_revision=current["S"],
        installer_revision=current["I"],
        revision_reader=_verified_reader(toolchain=toolchain),
    )
    assert plan["fresh_materialized"] == {"T": True, "S": False, "I": False}
    assert plan["awaiting_immutable_identity_materialization"] == ["S", "I"]


def test_new_toolchain_and_verified_skill_still_wait_for_installer() -> None:
    toolchain = "a" * 40
    skill = "b" * 40
    plan = planner.build_plan(
        ROOT,
        toolchain_revision=toolchain,
        skill_source_revision=skill,
        revision_reader=_verified_reader(toolchain=toolchain, skill_source=skill),
    )
    assert plan["fresh_materialized"] == {"T": True, "S": True, "I": False}
    assert plan["awaiting_immutable_identity_materialization"] == ["I"]


def test_new_skill_with_current_installer_keeps_publication_waiting() -> None:
    current = planner.current_identities(ROOT)
    skill = "b" * 40
    plan = planner.build_plan(
        ROOT,
        skill_source_revision=skill,
        installer_revision=current["I"],
        revision_reader=_verified_reader(skill_source=skill),
    )
    assert plan["fresh_materialized"]["S"] is True
    assert plan["fresh_materialized"]["I"] is False
    assert plan["awaiting_immutable_identity_materialization"] == ["I"]
    candidate_paths = {
        surface["path"] for surface in _stage(plan, "S-installer-candidate")["direct_surfaces"]
    }
    assert set(planner.S_PUBLICATION_SURFACES).isdisjoint(candidate_paths)


def test_verified_skill_and_installer_publish_every_s_and_i_reference_together() -> None:
    skill = "b" * 40
    installer = "c" * 40
    plan = planner.build_plan(
        ROOT,
        skill_source_revision=skill,
        installer_revision=installer,
        revision_reader=_verified_reader(skill_source=skill, installer=installer),
    )
    assert plan["awaiting_immutable_identity_materialization"] == []
    publication = _stage(plan, "I-policy-publication")["direct_surfaces"]
    by_identity = {
        identity: {record["path"] for record in publication if record["identity"] == identity}
        for identity in ("S", "I")
    }
    assert by_identity["S"] == set(planner.S_PUBLICATION_SURFACES)
    assert by_identity["I"] == set(planner.DIRECT_SURFACES["I"])
    descriptor = [record for record in publication if record["path"] == planner.INSTALLER_DESCRIPTOR]
    assert {record["identity"] for record in descriptor} == {"S", "I"}
    assert all(record["requires_change"] for record in descriptor)


def test_installer_only_change_requires_verified_binding_to_current_skill() -> None:
    installer = "c" * 40
    plan = planner.build_plan(
        ROOT,
        installer_revision=installer,
        revision_reader=_verified_reader(installer=installer),
    )
    assert plan["fresh_materialized"]["I"] is True
    assert plan["awaiting_immutable_identity_materialization"] == []
    assert plan["stale_stages"] == ["I-policy-publication", "policy-to-site-projection"]


def test_unverified_or_wrongly_bound_downstream_shas_remain_awaiting() -> None:
    current = planner.current_identities(ROOT)
    skill = "b" * 40
    installer = "c" * 40
    unresolved = planner.build_plan(
        ROOT,
        skill_source_revision=skill,
        installer_revision=installer,
        revision_reader=_reader({}),
    )
    assert unresolved["fresh_materialized"]["S"] is False
    assert unresolved["fresh_materialized"]["I"] is False
    assert unresolved["awaiting_immutable_identity_materialization"] == ["S", "I"]

    wrong_skill = planner.build_plan(
        ROOT,
        skill_source_revision=skill,
        revision_reader=_verified_reader(skill_source=skill, skill_toolchain="d" * 40),
    )
    assert wrong_skill["fresh_materialized"]["S"] is False
    assert "requested T" in wrong_skill["verification"]["S"]["reason"]

    wrong_installer = planner.build_plan(
        ROOT,
        installer_revision=installer,
        revision_reader=_verified_reader(installer=installer, installer_skill="e" * 40),
    )
    assert wrong_installer["fresh_materialized"]["I"] is False
    assert "requested S" in wrong_installer["verification"]["I"]["reason"]
    assert current["S"] != "e" * 40


def test_runtime_lock_digest_is_computed_from_requested_toolchain_and_compared() -> None:
    toolchain = "a" * 40
    lock_bytes = b"verified lock bytes\n"
    digest = hashlib.sha256(lock_bytes).hexdigest()
    reader = _verified_reader(toolchain=toolchain, lock_bytes=lock_bytes)
    plan = planner.build_plan(
        ROOT,
        toolchain_revision=toolchain,
        runtime_lock_sha256=digest,
        revision_reader=reader,
    )
    assert plan["runtime_lock"]["sha256"] == digest
    assert plan["runtime_lock"]["source"] == "verified-requested-toolchain-git-object"
    with pytest.raises(ValueError, match="does not match the requested toolchain"):
        planner.build_plan(
            ROOT,
            toolchain_revision=toolchain,
            runtime_lock_sha256="d" * 64,
            revision_reader=reader,
        )


def test_supplied_digest_does_not_make_unresolvable_toolchain_verified() -> None:
    plan = planner.build_plan(
        ROOT,
        toolchain_revision="a" * 40,
        runtime_lock_sha256="d" * 64,
        revision_reader=_reader({}),
    )
    assert plan["runtime_lock"]["verified"] is False
    assert plan["runtime_lock"]["supplied_sha256"] == "d" * 64
    assert plan["awaiting_release_evidence"] == ["runtime-lock-sha256"]


def test_self_host_input_validation_does_not_require_generated_coherence() -> None:
    plan = planner.build_plan(ROOT)
    input_stage = _stage(plan, "T-self-host-input")
    projection = _stage(plan, "T-self-host-projection")
    assert input_stage["input_mutations"] == [".agent-policy.yml"]
    assert input_stage["generated_surfaces"] == []
    assert "tests/test_policy_self_hosting.py" not in input_stage["validation"]
    assert "tests/test_policy_self_hosting.py" in projection["validation"]
    assert ".agent-policy.lock" in projection["generated_surfaces"]
    assert ".agents/skills/pr-review/" in projection["generated_surfaces"]


def test_invalid_runtime_lock_digest_fails_closed() -> None:
    with pytest.raises(ValueError, match="runtime lock digest"):
        planner.build_plan(
            ROOT,
            toolchain_revision="a" * 40,
            runtime_lock_sha256="not-a-digest",
            revision_reader=_reader({}),
        )


def _copy_identity_inputs(destination: Path) -> None:
    for relative in (
        planner.TOOLCHAIN_DESCRIPTOR,
        planner.INSTALLER_DESCRIPTOR,
        planner.TOOLCHAIN_SCHEMA,
        planner.INSTALLER_SCHEMA,
    ):
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(ROOT / relative, target)


def test_release_descriptors_are_schema_validated_without_string_coercion(tmp_path: Path) -> None:
    _copy_identity_inputs(tmp_path)
    toolchain_path = tmp_path / planner.TOOLCHAIN_DESCRIPTOR
    value = json.loads(toolchain_path.read_text())
    value["toolchain"]["revision"] = int("1" * 40)
    toolchain_path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="schema validation"):
        planner.current_identities(tmp_path)


def test_release_descriptor_authority_fields_are_validated(tmp_path: Path) -> None:
    _copy_identity_inputs(tmp_path)
    installer_path = tmp_path / planner.INSTALLER_DESCRIPTOR
    value = json.loads(installer_path.read_text())
    value["installer"]["repository"] = "example/other"
    installer_path.write_text(json.dumps(value), encoding="utf-8")
    with pytest.raises(ValueError, match="schema validation"):
        planner.current_identities(tmp_path)


def test_repository_inputs_reject_symlink_escape(tmp_path: Path) -> None:
    _copy_identity_inputs(tmp_path)
    outside = tmp_path / "outside.json"
    outside.write_text((tmp_path / planner.TOOLCHAIN_DESCRIPTOR).read_text(), encoding="utf-8")
    toolchain_path = tmp_path / planner.TOOLCHAIN_DESCRIPTOR
    toolchain_path.unlink()
    toolchain_path.symlink_to(outside)
    with pytest.raises(ValueError, match="must not contain symlinks"):
        planner.current_identities(tmp_path)


def test_direct_surface_inventory_rejects_symlink_escape(tmp_path: Path) -> None:
    outside = tmp_path / "outside.txt"
    outside.write_text("a" * 40, encoding="utf-8")
    surface = tmp_path / "surface.txt"
    surface.symlink_to(outside)
    with pytest.raises(ValueError, match="must not contain symlinks"):
        planner._surface_inventory(
            tmp_path,
            "S",
            "a" * 40,
            "b" * 40,
            paths=("surface.txt",),
        )


def test_site_projection_preserves_authority_boundary() -> None:
    installer = "d" * 40
    plan = planner.build_plan(
        ROOT,
        installer_revision=installer,
        revision_reader=_verified_reader(installer=installer),
    )
    site = _stage(plan, "policy-to-site-projection")
    assert site["external_authority"] == "site"
    assert "publication-sources.json" in site["generated_surfaces"]
    assert plan["invariants"]["site_is_policy_super_authority"] is False
