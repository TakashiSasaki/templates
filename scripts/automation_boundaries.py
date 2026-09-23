#!/usr/bin/env python3
"""Canonical automation boundaries and operation taxonomy for templates maintainer tooling.

Enforces the non-negotiable architectural boundary:
«Automate mechanical fact acquisition, state comparison, deterministic routing, and
guarded execution; do not automate semantic judgment or authorization merely because
automation is convenient.»

Defines explicit operation classes:
1. MECHANICAL_READ_OR_LOCAL: Pure fact collection, local validation, deterministic calculation.
2. GUARDED_MUTATION: Reversible or bounded mutation requiring explicit authorization and guards.
3. SEMANTIC_JUDGMENT: Correctness, finding validity, or acceptance contracts.
4. AUTHORITY_CONTROLLED_DECISION: Merge authorization, self-host adoption, publication cutover.
"""
from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any


class AutomationBoundaryError(PermissionError):
    """Raised when an automated process attempts to cross an authorization or judgment boundary."""


class OperationCategory(StrEnum):
    MECHANICAL_READ_OR_LOCAL = "mechanical_read_or_local"
    GUARDED_MUTATION = "guarded_mutation"
    SEMANTIC_JUDGMENT = "semantic_judgment"
    AUTHORITY_CONTROLLED_DECISION = "authority_controlled_decision"


@dataclass(frozen=True)
class OperationContract:
    name: str
    category: OperationCategory
    description: str
    requires_authorization: bool = False
    requires_concurrency_guard: bool = False
    may_establish_acceptance: bool = False
    may_authorize_merge: bool = False
    may_authorize_adoption: bool = False
    may_mutate_repository: bool = False


# Canonical registry of maintainer toolchain operations
CANONICAL_OPERATION_REGISTRY: dict[str, OperationContract] = {
    # 1. Mechanical / read-only operations
    "observe_pr_state": OperationContract(
        name="observe_pr_state",
        category=OperationCategory.MECHANICAL_READ_OR_LOCAL,
        description="Acquire read-only snapshot of provider PR, checks, reviews, and threads",
        requires_authorization=False,
        may_establish_acceptance=False,
    ),
    "orchestrate_preflights": OperationContract(
        name="orchestrate_preflights",
        category=OperationCategory.MECHANICAL_READ_OR_LOCAL,
        description="Execute canonical local preflights across authorities with exact head binding",
        requires_authorization=False,
        may_establish_acceptance=False,
    ),
    "sequence_qualification": OperationContract(
        name="sequence_qualification",
        category=OperationCategory.MECHANICAL_READ_OR_LOCAL,
        description="Determine qualification frontier and routing plan from supplied facts",
        requires_authorization=False,
        may_establish_acceptance=False,
    ),
    "plan_review_scope": OperationContract(
        name="plan_review_scope",
        category=OperationCategory.MECHANICAL_READ_OR_LOCAL,
        description="Adaptively select review scope from immutable source and topology facts",
        requires_authorization=False,
        may_establish_acceptance=False,
        may_authorize_merge=False,
    ),
    "render_review_artifacts": OperationContract(
        name="render_review_artifacts",
        category=OperationCategory.MECHANICAL_READ_OR_LOCAL,
        description="Render normalized review artifacts and markdown summaries locally",
        requires_authorization=False,
        may_establish_acceptance=False,
    ),
    "preview_maintainer_stack": OperationContract(
        name="preview_maintainer_stack",
        category=OperationCategory.MECHANICAL_READ_OR_LOCAL,
        description="Assemble inputs and preview stack artifacts locally without side effects",
        requires_authorization=False,
        may_mutate_repository=False,
    ),
    # 2. Guarded mutations
    "execute_guarded_repin": OperationContract(
        name="execute_guarded_repin",
        category=OperationCategory.GUARDED_MUTATION,
        description="Update downstream pin file with authorization and expected-old-pin match",
        requires_authorization=True,
        requires_concurrency_guard=True,
        may_mutate_repository=True,
    ),
    "publish_review_artifacts": OperationContract(
        name="publish_review_artifacts",
        category=OperationCategory.GUARDED_MUTATION,
        description="Publish generated PR regions and markers under explicit human authorization",
        requires_authorization=True,
        requires_concurrency_guard=True,
        may_mutate_repository=True,
    ),
    # 3. Semantic judgments (cannot be automated by mechanical helpers)
    "judge_finding_validity": OperationContract(
        name="judge_finding_validity",
        category=OperationCategory.SEMANTIC_JUDGMENT,
        description="Assess whether a reviewer finding represents a valid invariant violation",
        may_establish_acceptance=False,
    ),
    "evaluate_acceptance_contract": OperationContract(
        name="evaluate_acceptance_contract",
        category=OperationCategory.SEMANTIC_JUDGMENT,
        description="Determine whether evidence satisfies acceptance contract (pr-merge-gate)",
        may_establish_acceptance=True,
    ),
    # 4. Authority-controlled decisions (strictly human-controlled)
    "authorize_merge": OperationContract(
        name="authorize_merge",
        category=OperationCategory.AUTHORITY_CONTROLLED_DECISION,
        description="Authorize landing and merging of a stack member commit",
        requires_authorization=True,
        may_authorize_merge=True,
    ),
    "authorize_self_host_adoption": OperationContract(
        name="authorize_self_host_adoption",
        category=OperationCategory.AUTHORITY_CONTROLLED_DECISION,
        description="Authorize updating Policy B1 self-host toolchain pin",
        requires_authorization=True,
        may_authorize_adoption=True,
    ),
    "authorize_publication_cutover": OperationContract(
        name="authorize_publication_cutover",
        category=OperationCategory.AUTHORITY_CONTROLLED_DECISION,
        description="Authorize release and publication cutover across distribution channels",
        requires_authorization=True,
    ),
}


def enforce_operation_permission(
    operation: str,
    *,
    authorized: bool = False,
    caller_is_automated_helper: bool = True,
    expected_guard: Any = None,
    actual_guard: Any = None,
) -> OperationContract:
    """Enforce operation permissions against canonical taxonomy contracts.

    Raises AutomationBoundaryError if an automated helper attempts to execute
    an authority-controlled decision, synthesize a semantic judgment, or perform
    an unauthorized guarded mutation.
    """
    contract = CANONICAL_OPERATION_REGISTRY.get(operation)
    if contract is None:
        raise AutomationBoundaryError(
            f"unknown operation '{operation}'; unclassified operations fail closed"
        )

    # 1. Authority-controlled decisions can never be autonomously executed by automated helpers
    if contract.category == OperationCategory.AUTHORITY_CONTROLLED_DECISION:
        if caller_is_automated_helper and not authorized:
            raise AutomationBoundaryError(
                f"operation '{operation}' is an authority-controlled decision; "
                f"automated helpers cannot manufacture authorization"
            )

    # 2. Semantic judgments cannot be fabricated by mechanical tools
    if contract.category == OperationCategory.SEMANTIC_JUDGMENT:
        if caller_is_automated_helper:
            raise AutomationBoundaryError(
                f"operation '{operation}' is a semantic judgment; "
                f"mechanical helpers cannot synthesize semantic evaluation"
            )

    # 3. Guarded mutations require explicit authorization and guard equality
    if contract.category == OperationCategory.GUARDED_MUTATION:
        if not authorized:
            raise AutomationBoundaryError(
                f"guarded mutation '{operation}' refused: explicit authorization is required"
            )
        if contract.requires_concurrency_guard and expected_guard is not None:
            if expected_guard != actual_guard:
                raise AutomationBoundaryError(
                    f"guarded mutation '{operation}' blocked by guard mismatch: "
                    f"expected {expected_guard!r}, observed {actual_guard!r}"
                )

    return contract


def enforce_acceptance_separation(
    validation_status: str,
    acceptance_state: str,
    *,
    has_external_acceptance_evidence: bool = False,
) -> None:
    """Ensure that validation PASS is never automatically treated as review acceptance."""
    if (
        validation_status == "passed"
        and acceptance_state == "accepted"
        and not has_external_acceptance_evidence
    ):
        raise AutomationBoundaryError(
            "acceptance separation violation: validation PASS cannot synthesize "
            "review acceptance without external acceptance authority evidence"
        )
