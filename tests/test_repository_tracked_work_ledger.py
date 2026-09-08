from pathlib import Path

from agent_policy.renderer import render_skill

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills/orchestrate-repository-change"
REFERENCE = SKILL / "references/repository-tracked-work-ledger.md"


def test_repository_tracked_work_ledger_is_discoverable_and_distributed():
    rendered = render_skill("orchestrate-repository-change")
    ledger = (SKILL / "references/work-ledger.md").read_text().lower()

    assert "repository-tracked-work-ledger.md" in ledger
    assert "references/repository-tracked-work-ledger.md" in rendered
    installed = rendered["references/repository-tracked-work-ledger.md"].lower()
    assert "isolated repository-tracked work ledger" in installed
    assert "provider-side pr/issue checkpoints remain the default" in installed


def test_top_level_skill_selects_the_explicitly_adopted_storage_backend():
    rendered = render_skill("orchestrate-repository-change")
    installed_skill = rendered["SKILL.md"].lower()

    for required in (
        "select the adopted work-ledger storage strategy",
        "use the explicitly adopted repository-tracked operational ref",
        "otherwise use the canonical provider-side checkpoint",
        (
            "resolve the live operational-ref head before selecting/loading the checkpoint "
            "unless serialized ownership is positively established"
        ),
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
        "serialized ownership is positively established",
        "live operational ref head before selecting or loading the checkpoint",
        "load the latest valid current checkpoint from that live immutable binding",
        "restart phase 1 from the new live head",
        "checkpoint read is bound to the returned immutable ref head",
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
