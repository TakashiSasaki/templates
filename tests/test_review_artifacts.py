from __future__ import annotations

import copy
import importlib.util
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT / "repository-skills" / "land-templates-stack" / "scripts" / "render_review_artifacts.py"
)
SPEC = importlib.util.spec_from_file_location("render_review_artifacts", MODULE_PATH)
assert SPEC and SPEC.loader
artifacts = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(artifacts)


def _sha(letter: str) -> str:
    return letter * 40


def _trusted_planner_source() -> dict[str, object]:
    revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
    ).strip()
    blob_sha = subprocess.check_output(
        ["git", "rev-parse", f"{revision}:{artifacts.PLANNER_PATH}"],
        cwd=ROOT,
        text=True,
    ).strip()
    return {
        "repository": "TakashiSasaki/templates",
        "authority": "policy",
        "revision": revision,
        "path": artifacts.PLANNER_PATH,
        "blob_sha": blob_sha,
        "trusted": True,
    }


def _source() -> dict[str, object]:
    trusted_planner = _trusted_planner_source()
    candidate = {
        "repository": "TakashiSasaki/templates",
        "authority": "policy",
        "branch": "codex/review-artifacts-source",
        "base_sha": _sha("a"),
        "effective_base_sha": _sha("a"),
        "head_sha": _sha("b"),
        "members": [
            {
                "id": "policy-review-artifacts",
                "authority": "policy",
                "base_sha": _sha("a"),
                "head_sha": _sha("b"),
                "pull_request": {
                    "number": 123,
                    "provider_identity": {
                        "provider": "github",
                        "repository_id": "9",
                        "resource_id": "123",
                    },
                },
            }
        ],
        "pull_request": {
            "id": "PR_node_123",
            "number": 123,
            "url": "https://github.com/TakashiSasaki/templates/pull/123",
            "base_sha": _sha("a"),
            "head_sha": _sha("b"),
        },
    }
    source: dict[str, object] = {
        "schema_version": 1,
        "kind": "repository-change-review-artifacts",
        "repository": "TakashiSasaki/templates",
        "objective": "bind review projections",
        "purpose": "fix_verification",
        "contract": {"revision": "contract-1", "scope": "review-artifacts"},
        "candidate": candidate,
        "change": {
            "impact": "bounded",
            "invariants": ["one-source-of-truth"],
            "affected_members": ["policy-review-artifacts"],
            "contract_changed": False,
            "trust_boundary_changed": False,
            "topology_changed": False,
            "cross_member_interaction_changed": False,
        },
        "input_binding": {"evidence_set": "evidence-1"},
        "revision_bindings": [
            {
                "role": "consumer_actual_toolchain",
                "status": "bound",
                "label": "Consumer actual toolchain revision",
                "revision": _sha("c"),
                "source": {
                    "locator": "policy@b:.agent-policy.yml#toolchain.revision",
                    "candidate_head_sha": _sha("b"),
                    "worktree_head_sha": _sha("b"),
                    "path": ".agent-policy.yml",
                    "field": "toolchain.revision",
                },
            },
            {
                "role": "prospective_canonical_candidate",
                "status": "bound",
                "label": "Prospective canonical candidate",
                "revision": _sha("d"),
                "source": {
                    "locator": "policy-candidate@d",
                    "candidate_head_sha": _sha("d"),
                },
            },
            {
                "role": "trusted_maintainer_source",
                "status": "bound",
                "label": "Trusted maintainer source",
                "revision": trusted_planner["revision"],
                "source": {
                    "locator": "policy-source@trusted-planner",
                    **copy.deepcopy(trusted_planner),
                },
            },
            {
                "role": "publication_provider",
                "status": "not_applicable",
                "label": "Publication provider revision",
                "reason": "render-only candidate",
            },
            {
                "role": "site_integration_lock",
                "status": "unknown",
                "label": "Site Integration lock",
                "reason": "not consulted for this Policy-local change",
            },
        ],
        "planner": {
            "source": {
                **copy.deepcopy(trusted_planner),
                "authority": "policy",
            },
            "preflight": {"status": "ready", "missing": []},
            "reviews": [],
            "requests": [],
            "discovery": {"requests_complete": True, "reviews_complete": True},
            "options": {},
        },
        "observed": {
            "complete": True,
            "source": "fixture-observer",
            "observed_at": "2026-09-20T02:00:00Z",
            "facts": {
                "ci": {
                    "status": "success",
                    "head_sha": _sha("b"),
                    "applicable_to": {"head_sha": _sha("b"), "base_sha": _sha("a")},
                    "workflow": "policy-ci",
                    "run_id": 7,
                    "attempt": 1,
                },
                "review": {"status": "pending"},
            },
        },
        "judgments": [],
        "work": {
            "objective_ref": "bind review projections",
            "blockers": [],
            "unresolved_finding_refs": ["finding://review/1"],
            "next_safe_action": "run the focused tests",
            "stopping_boundary": "stop after the whole-stack Codex review request",
        },
    }
    normalized_candidate = artifacts._normalize_candidate(source)
    _, revision_digest = artifacts._normalize_revision_bindings(source, normalized_candidate)
    planner_source = source["planner"]["source"]
    planner_binding = {
        **source["input_binding"],
        "artifact_binding": artifacts._artifact_binding(
            source, normalized_candidate, revision_digest, planner_source
        ),
        "planner_source": copy.deepcopy(planner_source),
    }
    packet = {
        "schema_version": 2,
        "objective": source["objective"],
        "purpose": source["purpose"],
        "contract": source["contract"],
        "candidate": artifacts._planner_candidate(normalized_candidate),
        "change": source["change"],
        "input_binding": planner_binding,
        "preflight": source["planner"]["preflight"],
        "reviews": [],
        "requests": [],
        "discovery": source["planner"]["discovery"],
        "options": {},
    }
    planner_result = artifacts.execute_bound_planner(
        source["planner"]["source"], packet
    )
    gate_binding = {
        "repository": "TakashiSasaki/templates",
        "pull_request_id": "PR_node_123",
        "candidate_head_sha": _sha("b"),
        "base_sha": _sha("a"),
        "effective_base_sha": _sha("a"),
        "revision_bindings_digest": revision_digest,
        "planner_input_digest": artifacts.semantic_digest(packet),
        "planner_result_digest": artifacts.semantic_digest(planner_result),
    }
    source["gate"] = {
        "status": "passed",
        "source": {
            "repository": "TakashiSasaki/templates",
            "authority": "policy",
            "revision": _sha("1"),
            "path": "skills/pr-merge-gate/SKILL.md",
            "trusted": True,
        },
        "input_binding": gate_binding,
        "input_binding_digest": artifacts.semantic_digest(gate_binding),
        "evidence": {"exact_head": _sha("b")},
    }
    return source


def test_divergent_revision_roles_survive_normalization_and_rendering() -> None:
    normalized = artifacts.normalize(_source())
    bindings = {item["role"]: item for item in normalized.data["revision_bindings"]}

    assert bindings["consumer_actual_toolchain"]["revision"] == _sha("c")
    assert bindings["prospective_canonical_candidate"]["revision"] == _sha("d")
    assert (
        bindings["consumer_actual_toolchain"]["revision"]
        != bindings["prospective_canonical_candidate"]["revision"]
    )
    rendered = artifacts.render(normalized)
    assert _sha("c") in rendered.files["pr-generated-region.md"]
    assert _sha("d") in rendered.files["pr-generated-region.md"]


def test_consumer_pin_must_be_read_at_target_head_not_another_worktree() -> None:
    source = _source()
    actual = source["revision_bindings"][0]
    actual["source"]["worktree_head_sha"] = _sha("9")

    with pytest.raises(artifacts.ArtifactInputError, match="unrelated worktree"):
        artifacts.normalize(source)


def test_same_semantic_input_renders_identical_projections() -> None:
    first = artifacts.render(artifacts.normalize(_source()))
    second = artifacts.render(artifacts.normalize(_source()))

    assert first.files == second.files
    assert first.manifest["semantic_digest"] == second.manifest["semantic_digest"]


@pytest.mark.parametrize(
    "field,value,pattern",
    [
        ("head_sha", _sha("9"), "consumer_actual_toolchain"),
        ("base_sha", _sha("9"), "target member base|gate.input_binding.base_sha"),
    ],
)
def test_candidate_binding_changes_refuse_stale_gate_input(
    field: str, value: str, pattern: str
) -> None:
    source = _source()
    source["candidate"][field] = value
    if field == "head_sha":
        source["candidate"]["members"][0]["head_sha"] = value
        source["candidate"]["pull_request"]["head_sha"] = value
    else:
        source["candidate"]["pull_request"]["base_sha"] = value
    with pytest.raises(artifacts.ArtifactInputError, match=pattern):
        artifacts.normalize(source)


def test_dependency_change_refuses_gate_bound_to_earlier_dependency_set() -> None:
    source = _source()
    source["revision_bindings"][1]["revision"] = _sha("8")

    with pytest.raises(artifacts.ArtifactInputError, match="revision_bindings_digest"):
        artifacts.normalize(source)


def test_stale_declared_planner_result_is_rejected() -> None:
    source = _source()
    normalized_candidate = artifacts._normalize_candidate(source)
    bindings, revision_digest = artifacts._normalize_revision_bindings(source, normalized_candidate)
    planner_source = source["planner"]["source"]
    planner_binding = {
        **source["input_binding"],
        "artifact_binding": artifacts._artifact_binding(
            source, normalized_candidate, revision_digest, planner_source
        ),
        "planner_source": copy.deepcopy(planner_source),
    }
    _, _, planner_result = artifacts._planner_packet(source, normalized_candidate, planner_binding)
    source["planner"]["result"] = planner_result
    source["planner"]["result"]["request_key"] = _sha("9")

    with pytest.raises(artifacts.ArtifactInputError, match="planner.result"):
        artifacts.normalize(source)


def test_older_ci_success_is_rendered_as_stale_not_success() -> None:
    source = _source()
    source["observed"]["facts"]["ci"]["head_sha"] = _sha("8")
    source["observed"]["facts"]["ci"]["applicable_to"]["head_sha"] = _sha("8")

    normalized = artifacts.normalize(source)
    region = artifacts.render(normalized).files["pr-generated-region.md"]
    assert "CI: `stale`" in region
    assert "CI: `success`" not in region
    assert "ci_stale" in normalized.blockers


def test_ci_success_on_an_older_base_is_rendered_as_stale() -> None:
    source = _source()
    source["observed"]["facts"]["ci"]["applicable_to"]["base_sha"] = _sha("c")

    normalized = artifacts.normalize(source)
    region = artifacts.render(normalized).files["pr-generated-region.md"]

    assert "CI: `stale`" in region
    assert "CI: `success`" not in region
    assert "ci_stale" in normalized.blockers


def test_planner_source_must_match_independent_trusted_maintainer_binding() -> None:
    source = _source()
    source["planner"]["source"]["revision"] = _sha("f")
    source["planner"]["source"]["blob_sha"] = _sha("f")

    with pytest.raises(artifacts.ArtifactInputError, match="trusted_maintainer_source"):
        artifacts.normalize(source)


@pytest.mark.parametrize(
    "ci,expected",
    [
        ({"status": "not_configured"}, "not_configured"),
        (None, "unobserved"),
        ({"status": "pending"}, "pending"),
    ],
)
def test_ci_absent_unobserved_and_pending_states_stay_distinct(
    ci: dict[str, object] | None, expected: str
) -> None:
    source = _source()
    if ci is None:
        del source["observed"]["facts"]["ci"]
    else:
        source["observed"]["facts"]["ci"] = ci

    region = artifacts.render(artifacts.normalize(source)).files["pr-generated-region.md"]
    assert f"CI: `{expected}`" in region


def test_clean_prose_without_bound_judgment_does_not_become_resolution() -> None:
    source = _source()
    source["observed"]["facts"]["prose"] = "clean; all findings look resolved"
    source["judgments"] = []
    source["gate"]["status"] = "unknown"

    normalized = artifacts.normalize(source)
    assert normalized.data["judgments"] == []
    assert normalized.data["gate"]["status"] == "unknown"
    assert "gate_unknown" in normalized.blockers


def test_timestamp_only_change_keeps_rendered_content_identity_stable() -> None:
    first_source = _source()
    second_source = copy.deepcopy(first_source)
    second_source["observed"]["observed_at"] = "2026-09-20T02:30:00Z"
    first = artifacts.render(artifacts.normalize(first_source))
    second = artifacts.render(artifacts.normalize(second_source))

    assert first.manifest["semantic_digest"] == second.manifest["semantic_digest"]
    for filename in ("review-request.md", "pr-generated-region.md", "work-ledger-checkpoint.md"):
        assert first.files[filename] == second.files[filename]


def test_human_pr_text_is_preserved_and_owned_region_is_fail_closed() -> None:
    source = _source()
    source["observed"]["pr_body"] = {
        "revision": "body-1",
        "body": "Human introduction\n\nDo not rewrite this paragraph.\n",
    }
    normalized = artifacts.normalize(source)
    region = artifacts.render(normalized).files["pr-generated-region.md"]
    body = artifacts.replace_generated_region(
        source["observed"]["pr_body"]["body"], region, initialize=True
    )
    assert "Do not rewrite this paragraph." in body
    updated = artifacts.replace_generated_region(body, region)
    assert updated.count(artifacts.GENERATED_REGION_START) == 1
    assert updated.count(artifacts.GENERATED_REGION_END) == 1

    with pytest.raises(artifacts.RegionOwnershipError, match="missing"):
        artifacts.replace_generated_region("human-only", region)
    with pytest.raises(artifacts.RegionOwnershipError, match="duplicated"):
        artifacts.replace_generated_region(
            f"{artifacts.GENERATED_REGION_START}\n{artifacts.GENERATED_REGION_START}\n{artifacts.GENERATED_REGION_END}",
            region,
        )


def test_special_multiline_checkpoint_values_are_escaped() -> None:
    source = _source()
    source["work"]["next_safe_action"] = "inspect line 1\n* [unsafe] <url>"
    checkpoint = artifacts.render(artifacts.normalize(source)).files["work-ledger-checkpoint.md"]

    assert "inspect line 1<br>\\* \\[unsafe\\] \\<url\\>" in checkpoint


def test_planner_missing_information_is_returned_not_fabricated() -> None:
    source = _source()
    source["planner"]["discovery"]["reviews_complete"] = False
    source["gate"]["status"] = "pending"
    candidate = artifacts._normalize_candidate(source)
    _, revision_digest = artifacts._normalize_revision_bindings(source, candidate)
    planner_source = source["planner"]["source"]
    planner_binding = {
        **source["input_binding"],
        "artifact_binding": artifacts._artifact_binding(
            source, candidate, revision_digest, planner_source
        ),
        "planner_source": copy.deepcopy(planner_source),
    }
    _, planner_packet, planner_result = artifacts._planner_packet(
        source, candidate, planner_binding
    )
    source["gate"]["input_binding"]["planner_input_digest"] = artifacts.semantic_digest(
        planner_packet
    )
    source["gate"]["input_binding"]["planner_result_digest"] = artifacts.semantic_digest(
        planner_result
    )
    source["gate"]["input_binding_digest"] = artifacts.semantic_digest(
        source["gate"]["input_binding"]
    )
    normalized = artifacts.normalize(source)
    request = artifacts.render(normalized).files["review-request.md"]

    assert normalized.planner_result["action"] == "acquire_missing_input_or_handoff"
    assert "Not ready for a new request" in request
    assert "planner_reviews_complete_not_established" in request


def test_incomplete_observation_cannot_render_success() -> None:
    source = _source()
    source["observed"]["complete"] = False
    source["observed"]["retrieval"] = {"complete": False, "reason": "pagination interrupted"}
    normalized = artifacts.normalize(source)

    assert "observation_incomplete" in normalized.blockers
    assert "observation_retrieval_incomplete" in normalized.blockers
    assert "CI: `success`" in artifacts.render(normalized).files["pr-generated-region.md"]
    assert (
        "observation_incomplete" in artifacts.render(normalized).files["work-ledger-checkpoint.md"]
    )


def test_all_projections_share_one_source_identity_and_checkpoint_uses_refs() -> None:
    normalized = artifacts.normalize(_source())
    rendered = artifacts.render(normalized)

    for filename in (
        "review-request.md",
        "pr-generated-region.md",
        "work-ledger-checkpoint.md",
    ):
        assert normalized.semantic_digest in rendered.files[filename]
    assert "finding://review/1" in rendered.files["work-ledger-checkpoint.md"]
    assert "full_findings" not in rendered.files["work-ledger-checkpoint.md"]


def test_candidate_topology_requires_one_target_and_unique_provider_bindings() -> None:
    duplicate_target = _source()
    duplicate_target["candidate"]["members"].append(copy.deepcopy(
        duplicate_target["candidate"]["members"][0]
    ))
    duplicate_target["candidate"]["members"][1]["id"] = "duplicate-target"
    with pytest.raises(artifacts.ArtifactInputError, match="pull-request numbers"):
        artifacts.normalize(duplicate_target)

    duplicate_provider = _source()
    duplicate_provider["candidate"]["members"].append({
        "id": "another-member",
        "authority": "policy",
        "base_sha": _sha("a"),
        "head_sha": _sha("c"),
        "pull_request": {
            "number": 124,
            "provider_identity": {
                "provider": "github",
                "repository_id": "9",
                "resource_id": "123",
            },
        },
    })
    with pytest.raises(artifacts.ArtifactInputError, match="provider identities"):
        artifacts.normalize(duplicate_provider)

    missing_target = _source()
    member = missing_target["candidate"]["members"][0]
    member["id"] = "other-member"
    member["pull_request"]["number"] = 124
    member["pull_request"]["provider_identity"]["resource_id"] = "124"
    with pytest.raises(artifacts.ArtifactInputError, match="target pull request"):
        artifacts.normalize(missing_target)


def test_bound_planner_uses_trusted_commit_not_modified_checkout(tmp_path: Path) -> None:
    planner_path = tmp_path / artifacts.PLANNER_PATH
    planner_path.parent.mkdir(parents=True)
    planner_path.write_text(
        "def plan(packet):\n    return {'action': 'trusted-planner'}\n",
        encoding="utf-8",
    )
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(
        ["git", "add", artifacts.PLANNER_PATH], cwd=tmp_path, check=True
    )
    subprocess.run(
        [
            "git",
            "-c",
            "user.name=review-test",
            "-c",
            "user.email=review-test@example.invalid",
            "commit",
            "-qm",
            "trusted planner",
        ],
        cwd=tmp_path,
        check=True,
    )
    trusted_revision = subprocess.check_output(
        ["git", "rev-parse", "HEAD"], cwd=tmp_path, text=True
    ).strip()
    trusted_blob = subprocess.check_output(
        ["git", "rev-parse", f"HEAD:{artifacts.PLANNER_PATH}"],
        cwd=tmp_path,
        text=True,
    ).strip()
    planner_path.write_text(
        "def plan(packet):\n    return {'action': 'candidate-planner'}\n",
        encoding="utf-8",
    )

    result = artifacts.execute_bound_planner(
        {
            "repository": "TakashiSasaki/templates",
            "revision": trusted_revision,
            "path": artifacts.PLANNER_PATH,
            "blob_sha": trusted_blob,
            "trusted": True,
        },
        {"candidate": {"head_sha": _sha("b")}},
        repository_root=tmp_path,
    )

    assert result == {"action": "trusted-planner"}


def test_bound_planner_does_not_import_mutable_source_verifier(monkeypatch) -> None:
    original_loader = artifacts.importlib.util.spec_from_file_location

    def forbidden_verifier_loader(name, location, *args, **kwargs):
        if str(location).endswith("verify_maintainer_source_reference.py"):
            raise AssertionError("mutable source verifier was imported")
        return original_loader(name, location, *args, **kwargs)

    monkeypatch.setattr(
        artifacts.importlib.util,
        "spec_from_file_location",
        forbidden_verifier_loader,
    )

    normalized = artifacts.normalize(_source())

    assert isinstance(normalized.planner_result.get("action"), str)
