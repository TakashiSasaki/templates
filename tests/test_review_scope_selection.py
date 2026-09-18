from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    ROOT
    / "repository-skills"
    / "land-templates-stack"
    / "scripts"
    / "plan_review_scope.py"
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
        "candidate": {
            "repository": "TakashiSasaki/templates",
            "authority": "policy",
            "base_sha": _sha("a"),
            "effective_base_sha": _sha("a"),
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
        },
        "input_binding": {
            "provider": "codex",
            "contract_revision": "review-contract-1",
            "evidence": {"ci": ["run-1"], "findings": []},
        },
        "preflight": {"status": "ready", "missing": []},
        "reviews": [],
        "requests": [],
        "options": {},
    }
    packet.update(overrides)
    return packet


def _binding(packet: dict[str, object]) -> dict[str, object]:
    candidate = packet["candidate"]
    assert isinstance(candidate, dict)
    return {
        "repository": candidate["repository"],
        "authority": candidate["authority"],
        "base_sha": candidate["base_sha"],
        "effective_base_sha": candidate["effective_base_sha"],
        "head_sha": candidate["head_sha"],
        "members": candidate["members"],
    }


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
    }

    bounded = planner.plan(packet)
    assert bounded["action"] == planner.ACTION_DELTA
    assert bounded["selected_scope"]["members"] == [member_id]

    binding = _binding(packet)
    packet["reviews"] = [
        {
            "key": bounded["request_key"],
            "status": "completed",
            "purpose": packet["purpose"],
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
            **change,
        }
    )
    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_STACK
    assert result["selected_scope"]["kind"] == "whole-stack"
    assert result["selected_scope"]["members"] == ["policy-p1", "composition-c"]


def test_existing_inflight_request_is_reconciled_without_resubmission() -> None:
    packet = _packet()
    key = _key(packet)
    packet["requests"] = [{"key": key, "status": "in_progress", "handle": "review-42"}]

    result = planner.plan(packet)

    assert result["action"] == planner.ACTION_RECONCILE
    assert result["reusable_evidence"] == ["review-42"]


def test_submission_unknown_is_reconciled_before_retry() -> None:
    packet = _packet()
    key = _key(packet)
    packet["requests"] = [{"key": key, "status": "submission_unknown", "locator": "comment-9"}]

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
            "purpose": "whole_stack_diagnostic",
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
    packet = _packet(input_binding={"provider": "codex", "flag": True})
    initial = planner.plan(packet)
    old_input_binding = {"provider": "codex", "flag": 1}
    packet["reviews"] = [
        {
            "key": initial["request_key"],
            "status": "completed",
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


@pytest.mark.parametrize(
    "field", ["contract_changed", "trust_boundary_changed", "topology_changed"]
)
@pytest.mark.parametrize("value", [1, "true", None])
def test_non_boolean_scope_flag_fails_closed(field: str, value: object) -> None:
    change = _packet()["change"]
    assert isinstance(change, dict)
    change[field] = value

    with pytest.raises(planner.RoutingInputError, match="must be a boolean"):
        planner.plan(_packet(change=change))


def test_missing_input_binding_fails_closed() -> None:
    packet = _packet()
    del packet["input_binding"]

    with pytest.raises(planner.RoutingInputError, match="input_binding must be an object"):
        planner.plan(packet)


def test_invalid_candidate_binding_fails_closed() -> None:
    packet = _packet()
    candidate = packet["candidate"]
    assert isinstance(candidate, dict)
    candidate["head_sha"] = "main"

    with pytest.raises(planner.RoutingInputError, match="full Git SHA"):
        planner.plan(packet)
