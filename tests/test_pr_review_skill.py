from __future__ import annotations

from pathlib import Path

from agent_policy.renderer import render_skill

ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills/pr-review"
AGENT_POLICY_SKILL = ROOT / "skills/agent-policy/SKILL.md"


def test_pr_review_skill_layout_and_config_path_rendering() -> None:
    rendered = render_skill("pr-review", config_path="config/agent-policy.yml")

    assert set(rendered) == {
        "SKILL.md",
        "references/canonical-github-pr-review-prompt.md",
    }
    assert "{{ config_path }}" not in rendered["SKILL.md"]
    assert "{{ config_path }}" not in rendered[
        "references/canonical-github-pr-review-prompt.md"
    ]
    assert "config/agent-policy.yml" in rendered["SKILL.md"]
    assert "config/agent-policy.yml" in rendered[
        "references/canonical-github-pr-review-prompt.md"
    ]


def test_pr_review_skill_is_the_sole_review_execution_procedure_authority() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert "sole procedural authority" in skill
    assert "read-only" in skill
    assert "stable repository identity" in skill
    assert "provider-neutral policy projection" in skill
    assert "platform output adapter" in skill
    assert "stability loop" in skill
    assert "Do not merge the pull request" in skill
    assert "separate merge-gate procedure" in skill


def test_agent_policy_skill_owns_trusted_review_bootstrap() -> None:
    bootstrap = AGENT_POLICY_SKILL.read_text(encoding="utf-8")

    assert "## Trusted `pr-review` bootstrap" in bootstrap
    assert "before `pr-review` executes" in bootstrap
    assert "must not perform pull-request review analysis" in bootstrap
    assert "installed immutable `agent-policy` Skill" in bootstrap
    assert "The proposed head is never an authority input to bootstrap" in bootstrap
    assert "before consulting the candidate override" in bootstrap
    assert "candidate override and proposed head must not authorize themselves" in bootstrap
    assert (
        "python scripts/run.py --repository <trusted-snapshot> check --config <config-path>"
        in bootstrap
    )
    assert "select the managed runtime from that snapshot's `.agent-policy.lock`" in bootstrap
    assert ".agents/skills/pr-review/SKILL.md" in bootstrap
    assert "regular non-symlink files" in bootstrap
    assert "verified generated-output set" in bootstrap
    assert "lock-selected full-SHA toolchain revision" in bootstrap
    assert "Hand only those verified generated Skill bytes" in bootstrap
    assert "may bypass repository `skills.enabled`" in bootstrap
    assert "does not replace the active repository lock" in bootstrap
    assert "immutable bootstrap evidence record" in bootstrap
    assert "Reauthorize **every** active override" in bootstrap
    assert "changed procedure revision or Skill digest requires a full restart" in bootstrap


def test_pr_review_skill_consumes_bootstrap_evidence_without_self_bootstrapping() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert "## Trusted bootstrap precondition" in skill
    assert "does **not** select or verify its own executable authority" in skill
    assert "bootstrap evidence produced by the **Trusted `pr-review` bootstrap** section" in skill
    assert "stable repository identity" in skill
    assert "exact prior base authorization anchor" in skill
    assert "verified `pr-review` procedure revision" in skill
    assert "verified Skill-file digests/provenance" in skill
    assert "currently executing Skill bytes correspond" in skill
    assert "do not begin review analysis" in skill
    assert "Never fall back" in skill

    # Procedure authority must not regress into a circular self-loader.
    forbidden = (
        "derive the procedure revision from the validated lock",
        "Resolve `pr-review` only from that exact procedure revision",
        "verify the Skill source/generated provenance before execution",
        "This is the only path that may bypass repository `skills.enabled` selection",
    )
    for term in forbidden:
        assert term not in skill


def test_pr_review_skill_binds_repository_and_policy_authority_to_bootstrap() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert "repository identity matching bootstrap evidence" in skill
    assert "pull-request identity matching bootstrap evidence" in skill
    assert "active trusted repository-policy revision" in skill
    assert "validated lock identity" in skill
    assert "procedure revision" in skill
    assert "override identities" in skill
    assert "self-authorized by proposed-head content" in skill
    proposed_head_data = (
        "`.agent-policy.yml`, `.agent-policy.lock`, policy files, generated "
        "instructions, adapters, Skills"
    )
    assert proposed_head_data in skill
    assert "as evidence and claims to verify" in skill


def test_pr_review_skill_rejects_unsafe_projection_paths_before_loading() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert "Validate the active trusted configuration with the schema" in skill
    assert "Resolve `{{ config_path }}`, `.agent-policy.lock`" in skill
    assert "repository-relative non-empty paths" in skill
    assert "without parent traversal" in skill
    assert "do not enter `.git` or another reserved namespace" in skill
    assert "contain no symlink component" in skill
    assert "Reject absolute paths" in skill
    assert "missing projection files, and non-regular projection files" in skill
    assert "Do not load bytes through a path until these checks succeed" in skill


def test_pr_review_skill_requires_explicit_output_and_renderer_binding() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert "repository-relative path of the provider-neutral semantic review projection" in skill
    assert "repository-relative path of the required platform adapter projection" in skill
    assert "adapter renderer identifier" in skill
    assert "configured paths exactly match the supplied" in skill
    assert "Require both outputs to be enabled" in skill
    assert "require both to reference the same context" in skill
    assert "semantic output renderer to be exactly `policy-context-md`" in skill
    assert "adapter output renderer to equal the supplied adapter renderer identifier" in skill
    assert "github-review-json-adapter-v1" in skill
    assert "do not guess from names" in skill


def test_pr_review_skill_verifies_projection_bytes_before_use() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert "Verify the bound semantic and adapter projections before consuming them" in skill
    assert "matching input and output digests" in skill
    assert "deterministic check/regeneration" in skill
    assert "toolchain revision pinned by that active trusted lock" in skill
    assert "procedure/toolchain override governs only the verified `pr-review` Skill bytes" in skill
    assert "byte-for-byte identical" in skill
    assert "A stale, manually altered, unverifiable, or non-reproducible projection" in skill
    assert "a lock digest alone is not proof" in skill


def test_canonical_prompt_is_a_thin_non_normative_invocation() -> None:
    prompt = (
        SKILL_ROOT / "references/canonical-github-pr-review-prompt.md"
    ).read_text(encoding="utf-8")

    assert "non-normative invocation template" in prompt
    assert "not a bootstrap contract" in prompt
    assert "immutable `agent-policy` Skill bootstrap establishes executable provenance" in prompt
    assert "verified `pr-review` Skill is the sole review-execution procedural authority" in prompt
    assert "Semantic review projection: `<repository-relative-semantic-output-path>`" in prompt
    assert "GitHub adapter projection: `<repository-relative-github-adapter-output-path>`" in prompt
    assert "Adapter renderer: `github-review-json-adapter-v1`" in prompt
    assert "Trusted repository-policy revision request:" in prompt
    assert "Trusted procedure/toolchain revision request:" in prompt
    assert "Pass the repository/PR identity and any optional override requests" in prompt
    assert "Do not select, authorize, discover, or verify a procedure from this prompt" in prompt
    assert "After bootstrap returns valid immutable handoff evidence" in prompt
    assert "invoke the verified `pr-review` Skill" in prompt

    # Bootstrap, procedure, semantic definitions, and GitHub transport vocabulary
    # must stay in their authorities instead of being copied here.
    forbidden = (
        "Perform the review in this order",
        "realistic trigger or state",
        "reachable failure path",
        "Pending, skipped, stale",
        "REQUEST_CHANGES",
        "APPROVE",
        "COMMENT",
        '"schema_version"',
        '"analysis_status"',
        "LEFT",
        "RIGHT",
        "confidence >=",
        "confidence at least",
        "run `python scripts/run.py",
        "Reauthorize **every** active override",
        "complete set of best common ancestors",
    )
    for term in forbidden:
        assert term not in prompt


def test_pr_review_skill_defers_ci_classification_to_semantic_policy() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert "record the exact revision and state each item covers" in skill
    ci_classification = (
        "Do not classify pending, skipped, stale, inaccessible, missing, "
        "successful, or failed evidence"
    )
    semantic_handoff = (
        "pass the observed evidence to the bound semantic review policy "
        "for classification"
    )
    assert ci_classification in skill
    assert semantic_handoff in skill
    assert "is not by itself a code defect" not in skill
    assert "is not a pass" not in skill


def test_pr_review_skill_requires_one_unique_merge_base() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert "complete set of best common ancestors" in skill
    assert "Require that set to contain exactly one revision" in skill
    assert "Unrelated histories or multiple best merge bases" in skill
    assert "criss-cross histories" in skill
    assert "do not choose an arbitrary merge base" in skill
    assert "unique merge-base→head surface" in skill


def test_pr_review_skill_rechecks_repository_base_head_and_authority_until_stable() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert "Immediately before serialization, enter a stability loop" in skill
    assert "Re-resolve the stable repository identity" in skill
    assert "Require the repository identity to remain the one bound by bootstrap evidence" in skill
    assert "Require the ancestor set to still contain exactly one revision" in skill
    assert "If repository identity changes, fail closed" in skill
    assert "return control to trusted bootstrap" in skill
    assert "replacement exact base as the new prior authorization anchor" in skill
    assert "reauthorize **every** active out-of-band policy/procedure override" in skill
    assert "override authorized only by the old base cannot be carried forward" in skill
    assert "old Skill must not continue" in skill
    assert "recompute the unique merge-base→head changed surface" in skill
    stable = (
        "immediately pre-serialization observation reproduces the fully analyzed "
        "repository identity, base, head, unique merge-base, and current bootstrap authority"
    )
    assert stable in skill
