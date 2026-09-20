from __future__ import annotations

import copy
import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT / "repository-skills" / "land-templates-stack" / "scripts" / "plan_review_scope.py"
)
SPEC = importlib.util.spec_from_file_location("plan_review_scope", MODULE_PATH)
assert SPEC and SPEC.loader
planner = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(planner)


def _sha(letter: str) -> str:
    return letter * 40


def _packet(**overrides: object) -> dict[str, object]:
    packet: dict[str, object] = {
        "schema_version": 2,
        "objective": "adaptive review routing",
        "purpose": "whole_stack_diagnostic",
        "contract": {"revision": "review-contract-1"},
        "candidate": {
            "repository": "TakashiSasaki/templates",
            "authority": "policy",
            "base_sha": _sha("a"),
            "effective_base_sha": _sha("a"),
            "integration_base_tree_sha": _sha("e"),
            "head_sha": _sha("b"),
            "members": [
                {
                    "id": "policy-p1",
                    "authority": "policy",
                    "base_sha": _sha("a"),
                    "head_sha": _sha("b"),
                },
                {
                    "id": "composition-c",
                    "authority": "composition",
                    "base_sha": _sha("c"),
                    "head_sha": _sha("d"),
                },
            ],
        },
        "change": {
            "impact": "bounded",
            "invariants": ["review-scope"],
            "affected_members": ["policy-p1"],
            "contract_changed": False,
            "trust_boundary_changed": False,
            "topology_changed": False,
            "cross_member_interaction_changed": False,
        },
        "input_binding": {
            "provider": "codex",
            "contract_revision": "review-contract-1",
            "evidence": {"ci": ["run-1"], "findings": []},
        },
        "preflight": {"status": "ready", "missing": []},
        "reviews": [],
        "requests": [],
        "discovery": {"requests_complete": True, "reviews_complete": True},
        "options": {},
        "review_readiness": {
            "state": "ready",
            "known_material_findings_complete": True,
            "finding_families": [],
            "planned_candidate_mutations": [],
            "remaining_material_gaps": [],
            "reasons": [],
            "exception": None,
            "review_acquisition_allowed": True,
        },
    }
    packet.update(overrides)
    return packet


def _binding(packet: dict[str, object]) -> dict[str, object]:
    candidate = packet["candidate"]
    assert isinstance(candidate, dict)
    binding = {
        "repository": candidate["repository"],
        "authority": candidate["authority"],
        "base_sha": candidate["base_sha"],
        "effective_base_sha": candidate["effective_base_sha"],
        "head_sha": candidate["head_sha"],
        "members": candidate["members"],
    }
    if "integration_base_tree_sha" in candidate:
        binding["integration_base_tree_sha"] = candidate["integration_base_tree_sha"]
    return binding


def _key(packet: dict[str, object]) -> str:
    initial = planner.plan(packet)
    return initial["request_key"]


@pytest.mark.parametrize(
    "authority,invariant",
    [
        ("policy", "normative-routing"),
        ("composition", "transaction-ownership"),
        ("integration", "bundle-transport"),
        ("modeling", "record-provenance"),
        ("site", "browser-artifact"),
    ],
)
def test_each_authority_routes_bounded_expanded_and_reusable_scope(
    authority: str, invariant: str
) -> None:
    member_id = f"{authority}-maintenance"
    packet = _packet(purpose="fix_verification")
    candidate = packet["candidate"]
    assert isinstance(candidate, dict)
    candidate["authority"] = authority
    candidate["members"] = [
        {
            "id": member_id,
            "authority": authority,
            "base_sha": _sha("a"),
            "head_sha": _sha("b"),
        }
    ]
    packet["change"] = {
        "impact": "bounded",
        "invariants": [invariant],
        "affected_members": [member_id],
        "contract_changed": False,
        "trust_boundary_changed": False,
        "topology_changed": False,
        "cross_member_interaction_changed": False,
    }

    bounded = planner.plan(packet)
    assert bounded["action"] == planner.ACTION_DELTA
    assert bounded["selected_scope"]["members"] == [member_id]

    binding = _binding(packet)
    packet["reviews"] = [
        {
            "key": bounded["request_key"],
            "status": "completed",
            **_record_binding(packet),
            "purpose": packet["purpose"],
            "reviewed_scope": planner.plan(packet)["selected_scope"],
            "candidate_binding": binding,
            "candidate_binding_digest": planner._digest(binding),
            "input_binding": packet["input_binding"],
            "input_binding_digest": planner._digest(packet["input_binding"]),
            "independent": True,
            "metadata_complete": True,
            "pagination_complete": True,
            "coverage": {
                "purposes": [packet["purpose"]],
                "members": [member_id],
                "invariants": [invariant],
                "limitations": [],
            },
            "locator": f"{authority}-review",
        }
    ]
    reused = planner.plan(packet)
    assert reused["action"] == planner.ACTION_REUSE
    assert reused["reusable_evidence"] == [f"{authority}-review"]

    packet["change"] = {
        "impact": "bounded",
        "invariants": [invariant, "shared-contract"],
        "affected_members": [member_id],
        "contract_changed": True,
        "trust_boundary_changed": False,
        "topology_changed": False,
        "cross_member_interaction_changed": False,
    }
    expanded = planner.plan(packet)
    assert expanded["action"] == planner.ACTION_STACK
    assert expanded["selected_scope"]["kind"] == "whole-stack"


def test_bounded_change_selects_independent_delta_scope() -> None:
    packet = _packet(purpose="fix_verification")
    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_DELTA
    assert result["selected_scope"]["kind"] == "delta"
    assert result["selected_scope"]["members"] == ["policy-p1"]
    assert result["merge_authorization"] == "not_established"


@pytest.mark.parametrize(
    "flag",
    [
        "contract_changed",
        "trust_boundary_changed",
        "topology_changed",
        "cross_member_interaction_changed",
    ],
)
def test_prior_delta_cannot_cover_semantic_expansion(flag: str) -> None:
    prior = planner.plan(_packet())["selected_scope"]
    current = dict(prior, kind="whole-stack", **{flag: True})
    assert not planner._scope_dominates(prior, current)
    # Even a whole-stack result needs the particular expansion property.
    assert not planner._scope_dominates(dict(prior, kind="whole-stack"), current)
    assert planner._scope_dominates(current, prior)


@pytest.mark.parametrize("prior", [None, {}, {"kind": []}, {"kind": "whole-stack"}])
def test_unknown_prior_scope_fails_closed(prior: object) -> None:
    assert not planner._scope_dominates(prior, planner.plan(_packet())["selected_scope"])


def test_duplicate_candidate_ids_fail_closed() -> None:
    packet = _packet()
    packet["candidate"]["members"][1]["id"] = "policy-p1"
    with pytest.raises(planner.RoutingInputError, match="unique"):
        planner.plan(packet)


def test_impact_expansion_requires_applicable_prior_scope() -> None:
    prior = planner.plan(_packet())["selected_scope"]
    for impact in ("unknown", "unbounded"):
        assert not planner._scope_dominates(prior, dict(prior, kind="whole-stack", impact=impact))


@pytest.mark.parametrize(
    "change",
    [
        {"impact": "unbounded", "contract_changed": False},
        {"impact": "unknown", "contract_changed": False},
        {"impact": "bounded", "contract_changed": True},
        {"impact": "bounded", "trust_boundary_changed": True},
        {"impact": "bounded", "topology_changed": True},
    ],
)
def test_shared_or_unknown_impact_expands_related_stack(change: dict[str, object]) -> None:
    packet = _packet(
        change={
            "invariants": ["review-scope"],
            "affected_members": ["policy-p1"],
            "contract_changed": False,
            "trust_boundary_changed": False,
            "topology_changed": False,
            "cross_member_interaction_changed": False,
            **change,
        }
    )
    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_STACK
    assert result["selected_scope"]["kind"] == "whole-stack"
    assert result["selected_scope"]["members"] == ["policy-p1", "composition-c"]


def _record_binding(packet):
    binding = planner._request_binding(packet, _binding(packet), packet["input_binding"])
    return {
        "request_binding": copy.deepcopy(binding),
        "request_binding_digest": planner._digest(binding),
    }


def _active_request(packet, key, status, **locator):
    binding = _binding(packet)
    scope = planner.plan(packet)["selected_scope"]
    packet["discovery"]["latest_request_cycle"] = "cycle-1"
    return {
        "key": key,
        "cycle_id": "cycle-1",
        "status": status,
        **_record_binding(packet),
        "requested_scope": scope,
        **locator,
        "candidate_binding": binding,
        "candidate_binding_digest": planner._digest(binding),
        "input_binding": packet["input_binding"],
        "input_binding_digest": planner._digest(packet["input_binding"]),
    }


def test_existing_inflight_request_is_reconciled_without_resubmission() -> None:
    packet = _packet()
    key = _key(packet)
    packet["requests"] = [_active_request(packet, key, "in_progress", handle="review-42")]

    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_RECONCILE
    assert result["reusable_evidence"] == ["review-42"]


def test_submission_unknown_is_reconciled_before_retry() -> None:
    packet = _packet()
    key = _key(packet)
    packet["requests"] = [_active_request(packet, key, "submission_unknown", locator="comment-9")]

    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_RECONCILE
    assert result["request_state"] == "submission_unknown"


def test_explicit_coverage_reuses_completed_independent_result() -> None:
    packet = _packet()
    initial = planner.plan(packet)
    binding = _binding(packet)
    packet["reviews"] = [
        {
            "key": initial["request_key"],
            "status": "completed",
            **_record_binding(packet),
            "purpose": "whole_stack_diagnostic",
            "reviewed_scope": planner.plan(packet)["selected_scope"],
            "candidate_binding": binding,
            "candidate_binding_digest": planner._digest(binding),
            "input_binding": packet["input_binding"],
            "input_binding_digest": planner._digest(packet["input_binding"]),
            "independent": True,
            "metadata_complete": True,
            "pagination_complete": True,
            "coverage": {
                "purposes": ["whole_stack_diagnostic"],
                "members": ["policy-p1"],
                "invariants": ["review-scope"],
                "limitations": [],
            },
            "locator": "review-17",
        }
    ]

    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_REUSE
    assert result["reusable_evidence"] == ["review-17"]


def test_broader_completed_coverage_reuses_for_narrower_scope() -> None:
    packet = _packet(purpose="merge_acceptance")
    broad = _packet(
        purpose="merge_acceptance",
        change={
            "impact": "bounded",
            "invariants": ["review-scope", "shared-contract"],
            "affected_members": ["policy-p1", "composition-c"],
            "contract_changed": True,
            "trust_boundary_changed": False,
            "topology_changed": False,
            "cross_member_interaction_changed": False,
        },
    )
    broad_result = planner.plan(broad)
    binding = _binding(broad)
    packet["reviews"] = [
        {
            "key": broad_result["request_key"],
            "binding_key": broad_result["binding_key"],
            "status": "completed",
            **_record_binding(packet),
            "purpose": "merge_acceptance",
            "reviewed_scope": broad_result["selected_scope"],
            "candidate_binding": binding,
            "candidate_binding_digest": planner._digest(binding),
            "input_binding": broad["input_binding"],
            "input_binding_digest": planner._digest(broad["input_binding"]),
            "independent": True,
            "metadata_complete": True,
            "pagination_complete": True,
            "coverage": {
                "purposes": ["merge_acceptance"],
                "members": ["policy-p1", "composition-c"],
                "invariants": ["review-scope", "shared-contract"],
                "limitations": [],
            },
            "locator": "broad-review-18",
        }
    ]

    result = planner.plan(packet)

    assert result["selected_scope"]["kind"] == "delta"
    assert result["action"] == planner.ACTION_REUSE
    assert result["reusable_evidence"] == ["broad-review-18"]


@pytest.mark.parametrize("status", ["partial", "failed", "applicability_unknown", "stale"])
def test_incomplete_review_result_does_not_establish_coverage(status: str) -> None:
    packet = _packet()
    initial = planner.plan(packet)
    packet["reviews"] = [{"key": initial["request_key"], "status": status}]

    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_DELTA
    assert result["reusable_evidence"] == []


def test_missing_or_unknown_preflight_stops_before_review_acquisition() -> None:
    packet = _packet(preflight={"status": "unknown", "missing": ["ordered-members"]})

    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_MISSING
    assert "ordered-members" in result["unknowns"]


def test_omitted_preflight_or_status_stops_before_review_acquisition() -> None:
    for preflight, expected in (
        (None, "preflight_missing"),
        ({"missing": []}, "preflight_status_missing"),
    ):
        packet = _packet()
        if preflight is None:
            packet.pop("preflight")
        else:
            packet["preflight"] = preflight

        result = planner.plan(packet)

        assert result["action"] == planner.ACTION_MISSING
        assert expected in result["unknowns"]


def test_early_diagnostic_requires_explicit_selection() -> None:
    packet = _packet(options={"early_diagnostic": True})

    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_EARLY


def _open_family_readiness(*, family_id: str = "revision-bound-evidence") -> dict[str, object]:
    return {
        "state": "not_ready",
        "known_material_findings_complete": True,
        "finding_families": [
            {
                "id": family_id,
                "finding_refs": [f"finding://{family_id}"],
                "status": "gap",
                "sibling_audit_complete": False,
                "remaining_material_gaps": ["pending-review-stale-base"],
            }
        ],
        "planned_candidate_mutations": [],
        "exception": None,
    }


def test_open_finding_family_blocks_new_expensive_review_request() -> None:
    packet = _packet(review_readiness=_open_family_readiness())

    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_MISSING
    assert "review_readiness_incomplete" in result["reason"]
    assert "sibling_audit_incomplete:revision-bound-evidence" in result["reason"]
    assert result["review_acquisition_allowed"] is False


def test_closed_finding_family_allows_normally_selected_review() -> None:
    packet = _packet(
        review_readiness={
            "state": "ready",
            "known_material_findings_complete": True,
            "finding_families": [
                {
                    "id": "revision-bound-evidence",
                    "finding_refs": ["finding://revision-bound-evidence"],
                    "status": "closed",
                    "sibling_audit_complete": True,
                    "remaining_material_gaps": [],
                }
            ],
            "planned_candidate_mutations": [],
            "exception": None,
        }
    )

    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_DELTA
    assert result["review_acquisition_allowed"] is True


def test_reopening_one_family_preserves_unrelated_closed_family() -> None:
    packet = _packet(
        review_readiness={
            "state": "not_ready",
            "known_material_findings_complete": True,
            "finding_families": [
                {
                    "id": "family-a",
                    "finding_refs": ["finding://a"],
                    "status": "gap",
                    "sibling_audit_complete": False,
                    "remaining_material_gaps": ["new-sibling"],
                },
                {
                    "id": "family-b",
                    "finding_refs": ["finding://b"],
                    "status": "closed",
                    "sibling_audit_complete": True,
                    "remaining_material_gaps": [],
                },
            ],
            "planned_candidate_mutations": [],
            "exception": None,
        }
    )

    result = planner.plan(packet)
    families = {item["id"]: item for item in result["review_readiness"]["finding_families"]}

    assert result["action"] == planner.ACTION_MISSING
    assert families["family-a"]["sibling_audit_complete"] is False
    assert families["family-b"]["sibling_audit_complete"] is True


def test_incomplete_readiness_does_not_block_reuse_of_applicable_completed_result() -> None:
    packet = _packet(review_readiness=_open_family_readiness())
    initial = planner.plan(packet)
    binding = _binding(packet)
    packet["reviews"] = [
        {
            "key": initial["request_key"],
            "status": "completed",
            **_record_binding(packet),
            "purpose": packet["purpose"],
            "reviewed_scope": initial["selected_scope"],
            "candidate_binding": binding,
            "candidate_binding_digest": planner._digest(binding),
            "input_binding": packet["input_binding"],
            "input_binding_digest": planner._digest(packet["input_binding"]),
            "independent": True,
            "metadata_complete": True,
            "pagination_complete": True,
            "coverage": {
                "purposes": [packet["purpose"]],
                "members": ["policy-p1"],
                "invariants": ["review-scope"],
                "limitations": [],
            },
            "locator": "review-existing",
        }
    ]

    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_REUSE
    assert result["reusable_evidence"] == ["review-existing"]


def test_explicit_review_exception_allows_new_request_without_erasing_gap() -> None:
    packet = _packet(
        review_readiness={
            **_open_family_readiness(),
            "exception": {
                "allow_new_review": True,
                "authority_ref": "incident://urgent-integrity-boundary",
                "reason": "urgent integrity boundary requires current evidence",
            },
        }
    )

    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_DELTA
    assert result["review_readiness"]["state"] == "not_ready"
    assert result["review_acquisition_allowed"] is True
    assert "material_gap:revision-bound-evidence:pending-review-stale-base" in result[
        "review_readiness"
    ]["reasons"]


def test_readiness_changes_review_request_identity_but_not_checkpoint_identity() -> None:
    ready = _packet()
    blocked = _packet(review_readiness=_open_family_readiness())

    assert planner.plan(ready)["request_key"] != planner.plan(blocked)["request_key"]


def test_legacy_v2_packet_without_readiness_requires_regeneration_before_request() -> None:
    packet = _packet()
    packet.pop("review_readiness")

    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_MISSING
    assert "review_readiness_not_supplied" in result["reason"]


def test_planned_candidate_mutation_blocks_new_request_until_candidate_is_stable() -> None:
    packet = _packet(
        review_readiness={
            "state": "not_ready",
            "known_material_findings_complete": True,
            "finding_families": [],
            "planned_candidate_mutations": ["restack upper member"],
            "exception": None,
        }
    )

    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_MISSING
    assert "planned_candidate_mutation" in result["reason"]


def test_request_key_is_not_head_only() -> None:
    packet = _packet()
    changed = _packet(objective="different objective")

    assert _key(packet) != _key(changed)


def test_request_key_includes_validated_input_binding() -> None:
    packet = _packet()
    changed = _packet(
        input_binding={
            "provider": "codex",
            "contract_revision": "review-contract-1",
            "evidence": {"ci": ["run-2"], "findings": []},
        }
    )

    assert _key(packet) != _key(changed)


def test_completed_review_with_stale_candidate_binding_is_not_reused() -> None:
    packet = _packet()
    initial = planner.plan(packet)
    stale_binding = _binding(packet)
    stale_binding["head_sha"] = _sha("c")
    packet["reviews"] = [
        {
            "key": initial["request_key"],
            "status": "completed",
            **_record_binding(packet),
            "purpose": packet["purpose"],
            "candidate_binding": stale_binding,
            "candidate_binding_digest": planner._digest(stale_binding),
            "input_binding": packet["input_binding"],
            "input_binding_digest": planner._digest(packet["input_binding"]),
            "independent": True,
            "metadata_complete": True,
            "pagination_complete": True,
            "coverage": {
                "purposes": [packet["purpose"]],
                "members": ["policy-p1"],
                "invariants": ["review-scope"],
                "limitations": [],
            },
        }
    ]

    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_DELTA


def test_completed_review_with_changed_input_binding_is_not_reused() -> None:
    packet = _packet()
    initial = planner.plan(packet)
    old_input_binding = packet["input_binding"]
    packet["input_binding"] = {
        "provider": "codex",
        "contract_revision": "review-contract-1",
        "evidence": {"ci": ["run-2"], "findings": []},
    }
    packet["reviews"] = [
        {
            "key": initial["request_key"],
            "status": "completed",
            **_record_binding(packet),
            "purpose": packet["purpose"],
            "candidate_binding": _binding(packet),
            "candidate_binding_digest": planner._digest(_binding(packet)),
            "input_binding": old_input_binding,
            "input_binding_digest": planner._digest(old_input_binding),
            "independent": True,
            "metadata_complete": True,
            "pagination_complete": True,
            "coverage": {
                "purposes": [packet["purpose"]],
                "members": ["policy-p1"],
                "invariants": ["review-scope"],
                "limitations": [],
            },
        }
    ]

    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_DELTA


def test_completed_review_with_json_type_distinct_input_is_not_reused() -> None:
    packet = _packet(
        input_binding={
            "provider": "codex",
            "flag": True,
        }
    )
    initial = planner.plan(packet)
    old_input_binding = {"provider": "codex", "flag": 1}
    packet["reviews"] = [
        {
            "key": initial["request_key"],
            "status": "completed",
            **_record_binding(packet),
            "purpose": packet["purpose"],
            "candidate_binding": _binding(packet),
            "candidate_binding_digest": planner._digest(_binding(packet)),
            "input_binding": old_input_binding,
            "input_binding_digest": planner._digest(old_input_binding),
            "independent": True,
            "metadata_complete": True,
            "pagination_complete": True,
            "coverage": {
                "purposes": [packet["purpose"]],
                "members": ["policy-p1"],
                "invariants": ["review-scope"],
                "limitations": [],
            },
        }
    ]

    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_DELTA


def test_same_head_new_contract_evidence_allows_additional_related_scope() -> None:
    packet = _packet()
    previous = planner.plan(packet)
    packet["reviews"] = [
        {
            "key": previous["request_key"],
            "status": "completed",
            **_record_binding(packet),
            "independent": True,
            "metadata_complete": True,
            "pagination_complete": True,
        }
    ]
    packet["change"] = {
        "impact": "bounded",
        "invariants": ["review-scope", "shared-contract"],
        "affected_members": ["policy-p1"],
        "contract_changed": True,
        "trust_boundary_changed": False,
        "topology_changed": False,
        "cross_member_interaction_changed": False,
    }

    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_STACK
    assert result["selected_scope"]["kind"] == "whole-stack"
    assert result["request_key"] != previous["request_key"]


def test_multiple_prior_whole_stack_results_do_not_create_a_numeric_cap() -> None:
    packet = _packet(
        change={
            "impact": "bounded",
            "invariants": ["shared-contract"],
            "affected_members": ["policy-p1"],
            "contract_changed": True,
            "trust_boundary_changed": False,
            "topology_changed": False,
            "cross_member_interaction_changed": False,
        }
    )
    initial = planner.plan(packet)
    packet["reviews"] = [
        {"key": "old-whole-stack-1", "status": "completed"},
        {"key": "old-whole-stack-2", "status": "completed"},
    ]

    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_STACK
    assert result["selected_scope"]["kind"] == "whole-stack"
    assert result["request_key"] == initial["request_key"]


@pytest.mark.parametrize(
    "field",
    [
        "contract_changed",
        "trust_boundary_changed",
        "topology_changed",
        "cross_member_interaction_changed",
    ],
)
@pytest.mark.parametrize("value", [1, "true", None])
def test_non_boolean_scope_flag_fails_closed(field: str, value: object) -> None:
    change = _packet()["change"]
    assert isinstance(change, dict)
    change[field] = value

    with pytest.raises(planner.RoutingInputError, match="must be a boolean"):
        planner.plan(_packet(change=change))


def test_invalid_candidate_binding_fails_closed() -> None:
    packet = _packet()
    candidate = packet["candidate"]
    assert isinstance(candidate, dict)
    candidate["head_sha"] = "main"

    with pytest.raises(planner.RoutingInputError, match="full Git SHA"):
        planner.plan(packet)


def test_missing_input_binding_fails_closed() -> None:
    packet = _packet()
    del packet["input_binding"]

    with pytest.raises(planner.RoutingInputError, match="input_binding must be an object"):
        planner.plan(packet)


def test_empty_invariant_scope_fails_closed() -> None:
    change = _packet()["change"]
    assert isinstance(change, dict)
    change["invariants"] = []

    with pytest.raises(planner.RoutingInputError, match="must not be empty"):
        planner.plan(_packet(change=change))


@pytest.mark.parametrize("field", ["purposes", "members", "invariants", "limitations"])
def test_malformed_coverage_lists_are_not_reused(field: str) -> None:
    packet = _packet()
    initial = planner.plan(packet)
    binding = _binding(packet)
    coverage: dict[str, object] = {
        "purposes": [packet["purpose"]],
        "members": ["policy-p1"],
        "invariants": ["review-scope"],
        "limitations": [],
    }
    coverage[field] = {"policy-p1": False}
    packet["reviews"] = [
        {
            "key": initial["request_key"],
            "status": "completed",
            **_record_binding(packet),
            "purpose": packet["purpose"],
            "reviewed_scope": planner.plan(packet)["selected_scope"],
            "candidate_binding": binding,
            "candidate_binding_digest": planner._digest(binding),
            "input_binding": packet["input_binding"],
            "input_binding_digest": planner._digest(packet["input_binding"]),
            "independent": True,
            "metadata_complete": True,
            "pagination_complete": True,
            "coverage": coverage,
        }
    ]

    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_DELTA


@pytest.mark.parametrize("field", planner.EXPANSION_FLAGS)
def test_missing_scope_expansion_flag_fails_closed(field: str) -> None:
    packet = _packet()
    del packet["change"][field]
    with pytest.raises(planner.RoutingInputError, match="must be a boolean"):
        planner.plan(packet)


def test_cross_member_interaction_expands_and_invalidates_delta_scope() -> None:
    packet = _packet()
    prior = planner.plan(packet)
    packet["change"]["cross_member_interaction_changed"] = True
    current = planner.plan(packet)
    assert current["action"] == planner.ACTION_STACK
    assert current["selected_scope"]["members"] == ["policy-p1", "composition-c"]
    assert not planner._scope_dominates(prior["selected_scope"], current["selected_scope"])


def test_set_like_scope_order_and_duplicates_do_not_duplicate_active_request() -> None:
    packet = _packet()
    packet["change"]["invariants"] = ["first", "second"]
    packet["change"]["affected_members"] = ["policy-p1", "composition-c"]
    initial = planner.plan(packet)
    packet["requests"] = [
        _active_request(packet, initial["request_key"], "in_progress", handle="review-42")
    ]
    packet["change"]["invariants"] = ["second", "first", "second"]
    packet["change"]["affected_members"] = ["composition-c", "policy-p1", "policy-p1"]
    result = planner.plan(packet)
    assert result["request_key"] == initial["request_key"]
    assert result["action"] == planner.ACTION_RECONCILE
    # Ordered candidate topology is not a set and must remain binding material.
    packet["candidate"]["members"].reverse()
    assert planner.plan(packet)["request_key"] != initial["request_key"]


@pytest.mark.parametrize("field", ["requests", "reviews", "discovery"])
def test_missing_observed_provider_state_blocks_acquisition(field: str) -> None:
    packet = _packet()
    del packet[field]
    assert planner.plan(packet)["action"] == planner.ACTION_MISSING


@pytest.mark.parametrize("field", ["requests_complete", "reviews_complete"])
@pytest.mark.parametrize("value", [None, False, 1, "true", [], {}])
def test_incomplete_or_malformed_discovery_blocks_acquisition(field: str, value: object) -> None:
    packet = _packet()
    packet["discovery"][field] = value
    assert planner.plan(packet)["action"] == planner.ACTION_MISSING


@pytest.mark.parametrize("status", ["in_progress", "submission_unknown"])
@pytest.mark.parametrize("field", ["candidate_binding", "input_binding"])
def test_active_request_misassociated_metadata_cannot_suppress_current_review(
    status: str, field: str
) -> None:
    packet = _packet()
    active = copy.deepcopy(_active_request(packet, _key(packet), status, handle="old-review"))
    if field == "candidate_binding":
        active[field]["head_sha"] = _sha("c")
    else:
        active[field]["provider"] = "different-provider"
    active[field + "_digest"] = planner._digest(active[field])
    packet["requests"] = [active]
    result = planner.plan(packet)
    assert result["action"] == planner.ACTION_MISSING
    assert not result["reusable_evidence"]


@pytest.mark.parametrize("value", [None, {}, {"flag": True}])
def test_active_request_requires_exact_json_input_binding(value: object) -> None:
    packet = _packet(input_binding={"flag": 1})
    active = _active_request(packet, _key(packet), "in_progress", handle="review")
    active["input_binding"] = value
    active["input_binding_digest"] = planner._digest(value)
    packet["requests"] = [active]
    assert planner.plan(packet)["action"] == planner.ACTION_MISSING


@pytest.mark.parametrize("locator", [{}, {"handle": ""}, {"locator": " "}, {"handle": 1}])
def test_active_request_requires_actionable_provider_locator(locator: dict) -> None:
    packet = _packet()
    packet["requests"] = [_active_request(packet, _key(packet), "submission_unknown", **locator)]
    assert planner.plan(packet)["action"] == planner.ACTION_MISSING


def _complete_review(packet):
    initial = planner.plan(packet)
    binding = _binding(packet)
    return {
        "key": initial["request_key"],
        "binding_key": initial["binding_key"],
        "status": "completed",
        **_record_binding(packet),
        "candidate_binding": binding,
        "candidate_binding_digest": planner._digest(binding),
        "input_binding": packet["input_binding"],
        "input_binding_digest": planner._digest(packet["input_binding"]),
        "reviewed_scope": initial["selected_scope"],
        "independent": True,
        "metadata_complete": True,
        "pagination_complete": True,
        "coverage": {
            "purposes": [packet["purpose"]],
            "members": initial["selected_scope"]["members"],
            "invariants": initial["selected_scope"]["invariants"],
            "limitations": [],
        },
        "locator": "provider-result",
    }


@pytest.mark.parametrize("value", [True, 1, "true", None])
def test_acceptance_cannot_be_acquired_as_early_diagnostic(value):
    packet = _packet(purpose="merge_acceptance", options={"early_diagnostic": value})
    with pytest.raises(planner.RoutingInputError):
        planner.plan(packet)


@pytest.mark.parametrize("locator", [None, "", " ", 42])
def test_requestless_reuse_requires_result_source(locator):
    packet = _packet()
    review = _complete_review(packet)
    review["locator"] = locator
    packet["reviews"] = [review]
    assert planner.plan(packet)["action"] != planner.ACTION_REUSE


@pytest.mark.parametrize("status", ["failed", "partial", "applicability_unknown", "stale"])
def test_latest_unresolved_cycle_prevents_old_completed_reuse(status):
    packet = _packet()
    review = _complete_review(packet)
    review["cycle_id"] = "old"
    request = _active_request(packet, _key(packet), status, handle="latest-request")
    packet["requests"] = [request]
    packet["reviews"] = [review]
    assert planner.plan(packet)["action"] == planner.ACTION_MISSING


def test_explicit_latest_completed_cycle_can_supersede_failed_history():
    packet = _packet()
    review = _complete_review(packet)
    review["cycle_id"] = "cycle-1"
    request = _active_request(packet, _key(packet), "completed", handle="latest-request")
    old = {**request, "cycle_id": "old", "status": "failed"}
    packet["requests"] = [request, old]
    packet["reviews"] = [review]
    assert planner.plan(packet)["action"] == planner.ACTION_REUSE
    review["cycle_id"] = "old"
    assert planner.plan(packet)["action"] == planner.ACTION_MISSING


@pytest.mark.parametrize("latest", [None, "", "unknown", 1, []])
def test_unknown_latest_cycle_cannot_reuse_or_resubmit(latest):
    packet = _packet()
    review = _complete_review(packet)
    request = _active_request(packet, _key(packet), "completed", handle="request")
    packet["requests"] = [request]
    packet["reviews"] = [review]
    packet["discovery"]["latest_request_cycle"] = latest
    assert planner.plan(packet)["action"] == planner.ACTION_MISSING


def test_duplicate_cycle_identity_is_ambiguous():
    packet = _packet()
    request = _active_request(packet, _key(packet), "in_progress", handle="request")
    packet["requests"] = [request, copy.deepcopy(request)]
    assert planner.plan(packet)["action"] == planner.ACTION_MISSING


@pytest.mark.parametrize(
    "status",
    [
        "failed",
        "partial",
        "stale",
        "applicability_unknown",
        "submission_unknown",
        "in_progress",
        "completed",
    ],
)
def test_broader_request_participates_in_latest_cycle_selection(status):
    packet = _packet()
    review = _complete_review(packet)
    broad = copy.deepcopy(packet)
    broad["change"]["trust_boundary_changed"] = True
    request = _active_request(broad, _key(broad), status, handle="broad-request")
    assert request["key"] != _key(packet)
    packet["requests"] = [request]
    packet["reviews"] = [review]
    assert planner.plan(packet)["action"] == planner.ACTION_MISSING
    packet["discovery"]["latest_request_cycle"] = "cycle-1"
    expected = (
        planner.ACTION_RECONCILE
        if status in {"in_progress", "submission_unknown"}
        else planner.ACTION_MISSING
    )
    assert planner.plan(packet)["action"] == expected
    if status == "completed":
        result = _complete_review(broad)
        result["cycle_id"] = "cycle-1"
        packet["reviews"].append(result)
        assert planner.plan(packet)["action"] == planner.ACTION_REUSE


def test_narrower_request_does_not_supersede_broader_coverage():
    narrow = _packet()
    request = _active_request(narrow, _key(narrow), "failed", handle="narrow")
    broad = _packet()
    broad["change"]["trust_boundary_changed"] = True
    review = _complete_review(broad)
    broad["reviews"] = [review]
    broad["requests"] = [request]
    assert planner.plan(broad)["action"] == planner.ACTION_REUSE


@pytest.mark.parametrize("state", ["in_progress", "submission_unknown", "completed"])
@pytest.mark.parametrize(
    "field", ["repository", "objective", "purpose", "contract", "candidate", "input_binding"]
)
def test_full_recorded_request_binding_rejects_misassociated_key(state: str, field: str) -> None:
    packet = _packet()
    record = (
        _complete_review(packet)
        if state == "completed"
        else _active_request(packet, _key(packet), state, handle="request")
    )
    record["request_binding"][field] = {"different": True}
    record["request_binding_digest"] = planner._digest(record["request_binding"])
    packet["reviews" if state == "completed" else "requests"] = [record]
    result = planner.plan(packet)
    assert result["action"] == (
        planner.ACTION_DELTA if state == "completed" else planner.ACTION_MISSING
    )
    assert not result["reusable_evidence"]


@pytest.mark.parametrize("state", ["in_progress", "completed"])
@pytest.mark.parametrize("value", [None, {}, {"contract": float("nan")}])
def test_missing_or_malformed_complete_record_binding_is_not_evidence(
    state: str, value: object
) -> None:
    packet = _packet()
    record = (
        _complete_review(packet)
        if state == "completed"
        else _active_request(packet, _key(packet), state, handle="request")
    )
    record["request_binding"] = value
    packet["reviews" if state == "completed" else "requests"] = [record]
    assert planner.plan(packet)["action"] not in {planner.ACTION_RECONCILE, planner.ACTION_REUSE}


@pytest.mark.parametrize("field", ["objective", "purpose", "contract"])
def test_contradictory_flat_request_metadata_does_not_override_full_binding(field: str) -> None:
    packet = _packet()
    record = _active_request(packet, _key(packet), "in_progress", handle="request")
    record[field] = {"revision": "old"}
    packet["requests"] = [record]
    assert planner.plan(packet)["action"] == planner.ACTION_MISSING


@pytest.mark.parametrize("scope", [None, {}, {"kind": "delta"}])
def test_active_record_requires_full_requested_scope(scope: object) -> None:
    packet = _packet()
    record = _active_request(packet, _key(packet), "in_progress", handle="request")
    record["requested_scope"] = scope
    packet["requests"] = [record]
    assert planner.plan(packet)["action"] == planner.ACTION_MISSING


@pytest.mark.parametrize("field", ["candidate_binding", "input_binding"])
def test_nonfinite_completed_binding_is_rejected_without_digest_exception(field: str) -> None:
    packet = _packet()
    record = _complete_review(packet)
    record[field] = {"invalid": float("nan")}
    packet["reviews"] = [record]
    assert planner.plan(packet)["action"] == planner.ACTION_DELTA


@pytest.mark.parametrize("field,value", [("head_sha", "c" * 40), ("authority", "absent")])
def test_top_level_candidate_matches_its_ordered_authority_tip(field: str, value: str) -> None:
    packet = _packet()
    packet["candidate"][field] = value
    with pytest.raises(planner.RoutingInputError, match="ordered tip"):
        planner.plan(packet)


@pytest.mark.parametrize("contract", [None, {}, []])
def test_current_review_contract_is_explicit(contract: object) -> None:
    with pytest.raises(planner.RoutingInputError, match="contract"):
        planner.plan(_packet(contract=contract))


@pytest.mark.parametrize("field", ["preflight", "reviews", "requests"])
@pytest.mark.parametrize("status", [None, [], {}])
def test_malformed_status_reports_controlled_input_error(field: str, status: object) -> None:
    packet = _packet()
    packet[field] = {"status": status} if field == "preflight" else [{"status": status}]
    with pytest.raises(planner.RoutingInputError, match="status"):
        planner.plan(packet)


@pytest.mark.parametrize("schema", [True, 2.0, "2"])
def test_packet_schema_requires_integer_version(schema: object) -> None:
    with pytest.raises(planner.RoutingInputError, match="schema"):
        planner.plan(_packet(schema_version=schema))


def test_cumulative_acceptance_requires_explicit_integration_base_tree() -> None:
    packet = _packet(purpose="merge_acceptance")
    packet["change"]["affected_members"] = []
    del packet["candidate"]["integration_base_tree_sha"]
    result = planner.plan(packet)
    assert result["action"] == planner.ACTION_MISSING
    assert "cumulative_integration_base_tree_missing" in result["missing_confirmation"]
    packet["reviews"] = [_complete_review(packet)]
    assert planner.plan(packet)["action"] == planner.ACTION_MISSING
    packet["candidate"]["integration_base_tree_sha"] = _sha("e")
    packet["reviews"] = [_complete_review(packet)]
    assert planner.plan(packet)["action"] == planner.ACTION_REUSE


def test_narrow_request_cannot_reuse_tree_unbound_cumulative_result() -> None:
    packet = _packet(purpose="merge_acceptance")
    del packet["candidate"]["integration_base_tree_sha"]
    record = _complete_review(packet)
    record["reviewed_scope"]["members"] = ["policy-p1", "composition-c"]
    record["coverage"]["members"] = ["policy-p1", "composition-c"]
    packet["reviews"] = [record]
    assert planner.plan(packet)["action"] == planner.ACTION_DELTA


def test_changed_integration_tree_invalidates_record_binding() -> None:
    packet = _packet(purpose="merge_acceptance")
    packet["change"]["affected_members"] = []
    record = _complete_review(packet)
    packet["candidate"]["integration_base_tree_sha"] = _sha("f")
    # A misassociated current key does not make the old tree current.
    record["key"] = _key(packet)
    packet["reviews"] = [record]
    assert planner.plan(packet)["action"] == planner.ACTION_DELTA


def test_completed_coverage_requires_explicit_limitations() -> None:
    packet = _packet()
    record = _complete_review(packet)
    del record["coverage"]["limitations"]
    packet["reviews"] = [record]
    assert planner.plan(packet)["action"] == planner.ACTION_DELTA
