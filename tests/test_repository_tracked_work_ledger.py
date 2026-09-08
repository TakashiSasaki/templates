from pathlib import Path

from agent_policy.renderer import render_skill

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/orchestrate-repository-change"
REFERENCE = SKILL / "references/repository-tracked-work-ledger.md"


def test_top_level_skill_selects_the_explicitly_adopted_storage_backend():
    rendered = render_skill("orchestrate-repository-change")
    installed_skill = rendered["SKILL.md"].lower()

    for required in (
        "select the adopted work-ledger storage strategy",
        "use the explicitly adopted repository-tracked operational ref",
        "otherwise use the canonical provider-side checkpoint",
        "always resolve the live operational-ref head",
        "including under serialized ownership",
        (
            "establish exclusive action ownership through authoritative serialized "
            "action ownership or an atomic/cas checkpoint transition"
        ),
        "a worker that loses the claim must reload and must not execute the action",
        "checkpoint material transitions on the selected canonical operational surface",
    ):
        assert required in installed_skill


def test_repository_tracked_strategy_requires_explicit_adoption_and_candidate_isolation():
    text = REFERENCE.read_text().lower()
    for required in (
        "do not create a repository-tracked work ledger merely because this procedure exists",
        "absence of a prohibition is not adoption",
        "provider-side pr/issue checkpoints remain the default",
        "updating operational state does not move a pr head",
        (
            "a commit that adds or refreshes a progress file on the implementation "
            "candidate itself is not isolated"
        ),
        "not an acceptable substitute for isolation",
        "does not reserve those names",
        "no json/yaml schema is mandatory",
    ):
        assert required in text


def test_repository_tracked_strategy_uses_guarded_shared_state():
    text = REFERENCE.read_text().lower()
    for required in (
        "current operational ref head",
        "publish only if the operational ref still has the expected predecessor/head",
        "do not force or blindly overwrite",
        "serialized single writer",
        "append immutable successor checkpoints",
        "competing successors are a conflict",
        "do not use `force` ref movement",
    ):
        assert required in text


def test_resume_binds_checkpoint_selection_to_the_live_operational_head():
    text = REFERENCE.read_text().lower()
    for required in (
        "read-side freshness of the shared operational ref is part of concurrency safety",
        (
            "always resolve the current **live operational ref head before selecting or "
            "loading the checkpoint**"
        ),
        "including when serialized writer ownership has already been established",
        "load the latest valid current checkpoint from that live immutable binding",
        "restart phase 1 from the new live head",
        "checkpoint read is bound to the returned immutable ref head",
        "never eliminates the initial live-head resolution",
    ):
        assert required in text


def test_recovered_non_idempotent_action_requires_pre_execution_ownership():
    text = REFERENCE.read_text().lower()
    for required in (
        "action ownership before non-idempotent effects",
        "checkpoint-write cas does not by itself prevent two workers",
        "before executing a recovered `next_safe_action`",
        "authoritative serialized-owner mechanism",
        "atomic/cas checkpoint transition",
        "records the specific action as claimed/in-progress",
        "worker that loses the claim cas must not execute the action",
        "do not infer action ownership from merely having loaded the checkpoint",
        "preflight checkpoint must also establish the exclusive action claim",
    ):
        assert required in text


def test_interrupted_action_claim_cannot_be_cleared_or_stolen_before_reconciliation():
    text = REFERENCE.read_text().lower()
    for required in (
        (
            "preserve that claim as `claimed/in-progress` or "
            "`uncertain-after-interruption` while checking provider effects"
        ),
        "do not clear or steal the claim merely because the original worker is no longer active",
        (
            "transfer or expire action ownership only under an authoritative "
            "repository/provider mechanism"
        ),
        "preserves the possibility that the external effect already occurred",
    ):
        assert required in text


def test_resume_is_minimal_frontier_refresh_then_selective_reconciliation():
    text = REFERENCE.read_text().lower()
    for required in (
        "resume is a cache-validation operation, not a complete rediscovery by default",
        "phase 1 — checkpoint recovery",
        "phase 2 — minimal frontier refresh",
        "smallest live frontier needed",
        "binding-valid / unchanged",
        "changed",
        "stale",
        "unknown",
        "not relevant to the next safe action",
        "only then retrieve deeper ci run details",
        "freshness is required; exhaustive rediscovery is not",
        "round-trip depth",
    ):
        assert required in text


def test_cached_evidence_never_overrides_provider_truth_or_applicability():
    text = REFERENCE.read_text().lower()
    for required in (
        "repository-tracked storage does not relax exact-head",
        "live head is still `a`",
        "live head moved to `b`",
        "head is unchanged but a relevant base",
        "never substitutes for the provider evidence locator",
        (
            "the ledger determines **what must be refreshed**; the provider "
            "determines **what is true**"
        ),
        "inspect the provider effect before retrying",
        "do not create duplicate branches, prs, review requests, comments, merges, deployments",
    ):
        assert required in text


def test_operational_state_does_not_gain_product_or_review_authority():
    text = REFERENCE.read_text().lower()
    for required in (
        "not a new acceptance authority",
        "not interpreted as product semantic state",
        "validated lifecycle history",
        "review-finding authority",
        "merge evidence",
        "work ledger is not product lifecycle authority",
    ):
        assert required in text
