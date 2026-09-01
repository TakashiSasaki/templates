from __future__ import annotations

from pathlib import Path

from agent_policy.renderer import render_skill

ROOT = Path(__file__).resolve().parents[1]
SKILL_ROOT = ROOT / "skills/pr-review"
AGENT_POLICY_SKILL = ROOT / "skills/agent-policy/SKILL.md"
AGENT_POLICY_RUN = ROOT / "skills/agent-policy/scripts/run.py"
AGENT_POLICY_BOOTSTRAP = ROOT / "skills/agent-policy/scripts/bootstrap.py"


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


def test_agent_policy_skill_owns_one_trusted_review_bootstrap_path() -> None:
    bootstrap = AGENT_POLICY_SKILL.read_text(encoding="utf-8")

    assert "## Trusted `pr-review` bootstrap" in bootstrap
    assert "only repository-facing bootstrap authority" in bootstrap
    assert "before `pr-review` executes" in bootstrap
    assert "must not perform pull-request review analysis" in bootstrap
    assert "No alternate bootstrap loader" in bootstrap
    assert "repository-policy-root override" in bootstrap
    assert "procedure/toolchain override" in bootstrap
    assert "future alternate authority path requires" in bootstrap
    assert "The proposed head is never an authority input to bootstrap" in bootstrap
    assert (
        "python -B scripts/run.py --repository <trusted-base-snapshot> check "
        "--config <config-path>"
    ) in bootstrap
    assert "select the managed runtime from that snapshot's `.agent-policy.lock`" in bootstrap
    assert "Require the trusted configuration to enable `pr-review`" in bootstrap
    assert ".agents/skills/pr-review/SKILL.md" in bootstrap
    assert "lock-selected full-SHA toolchain revision" in bootstrap
    assert "Hand only those verified generated Skill bytes" in bootstrap
    assert "immutable bootstrap evidence record" in bootstrap
    assert "If stable repository identity changes, fail closed" in bootstrap
    assert "return to this already authenticated bootstrap" in bootstrap


def test_agent_policy_bootstrap_requires_external_installation_authentication() -> None:
    bootstrap = AGENT_POLICY_SKILL.read_text(encoding="utf-8")

    assert "### Installed bootstrap authentication precondition" in bootstrap
    assert "does **not** authenticate the Skill-source bytes" in bootstrap
    assert "deployment-managed installation attestation" in bootstrap
    assert "outside both the installed Skill tree and the repository under review" in bootstrap
    assert "full-SHA installer revision" in bootstrap
    assert "immutable Skill-source revision" in bootstrap
    assert "closed path/type inventory for the complete installed Skill tree" in bootstrap
    assert "SHA-256 for every regular file" in bootstrap
    assert "Verification requires exact inventory equality" in bootstrap
    assert "additional files or directories" in bootstrap
    assert "--attestation <path> --installer-revision <trusted-installer-sha>" in bootstrap
    assert "--verify-only" in bootstrap
    assert "authenticate the installer script itself" in bootstrap
    assert "Never substitute `runtime-manifest.json`" in bootstrap
    assert "authenticated bootstrap installer and Skill-source revisions" in bootstrap
    assert "installation-attestation digest" in bootstrap


def test_agent_policy_bootstrap_execution_cannot_mutate_attested_tree() -> None:
    bootstrap = AGENT_POLICY_SKILL.read_text(encoding="utf-8")
    run_source = AGENT_POLICY_RUN.read_text(encoding="utf-8")
    bootstrap_source = AGENT_POLICY_BOOTSTRAP.read_text(encoding="utf-8")

    assert "immutable trust material" in bootstrap
    assert "must not create `__pycache__`" in bootstrap
    assert "sys.dont_write_bytecode" in bootstrap
    assert "python -B" in bootstrap
    assert "Runtime/cache state belongs outside the attested Skill root" in bootstrap

    for source in (run_source, bootstrap_source):
        assert "sys.dont_write_bytecode = True" in source
        assert source.index("sys.dont_write_bytecode = True") < source.index("from runtime import")


def test_agent_policy_bootstrap_allows_only_verified_base_generated_review_skill() -> None:
    bootstrap = AGENT_POLICY_SKILL.read_text(encoding="utf-8")

    assert "sole repository-local review-procedure bytes permitted" in bootstrap
    assert "trusted-base generated `pr-review` Skill and declared references" in bootstrap
    assert "passed steps 6-8" in bootstrap
    assert "another unverified repository-local Skill" in bootstrap
    assert "any `agent-policy`/`pr-review` bytes from the proposed head" in bootstrap


def test_agent_policy_bootstrap_rejects_symlinked_generated_skill_paths() -> None:
    bootstrap = AGENT_POLICY_SKILL.read_text(encoding="utf-8")

    assert "Resolve `.agents/skills/pr-review/SKILL.md`" in bootstrap
    assert "remain inside the generated `pr-review` tree" in bootstrap
    assert "without parent traversal or reserved-namespace entry" in bootstrap
    assert "every existing path component" in bootstrap
    assert "non-symlink" in bootstrap
    assert "final path to be a regular file" in bootstrap


def test_pr_review_skill_consumes_bootstrap_evidence_without_self_bootstrapping() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert "## Trusted bootstrap precondition" in skill
    assert "does **not** select or verify its own executable authority" in skill
    assert "deployment-authenticated installed `agent-policy` Skill" in skill
    assert "supports no alternate loader" in skill
    assert "authenticated bootstrap installer and Skill-source revisions" in skill
    assert "exact trusted base revision" in skill
    assert "verified `pr-review` procedure revision" in skill
    assert "verified Skill-file digests/provenance" in skill
    assert "currently executing Skill bytes correspond" in skill
    assert "do not begin review analysis" in skill
    assert "Never fall back" in skill

    forbidden = (
        "derive the procedure revision from the validated lock",
        "Resolve `pr-review` only from that exact procedure revision",
        "verify the Skill source/generated provenance before execution",
        "authorized out-of-band procedure",
    )
    for term in forbidden:
        assert term not in skill


def test_pr_review_contract_rejects_authority_override_inputs() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")
    prompt = (
        SKILL_ROOT / "references/canonical-github-pr-review-prompt.md"
    ).read_text(encoding="utf-8")

    assert "Do not accept caller-supplied policy-root" in skill
    assert "procedure-revision" in skill
    assert "alternate-loader" in skill
    assert "current contract has no caller-selectable repository-policy root" in prompt
    assert "procedure/toolchain revision" in prompt
    assert "alternate loader" in prompt
    assert "other authority override" in prompt
    assert "Trusted repository-policy revision request:" not in prompt
    assert "Trusted procedure/toolchain revision request:" not in prompt


def test_pr_review_skill_binds_pr_repository_and_policy_authority_to_bootstrap() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert "repository identity matching bootstrap evidence" in skill
    assert "pull-request identity matching bootstrap evidence" in skill
    assert "Require both the stable repository identity **and pull-request identity**" in skill
    assert "exact current base tip to match the trusted repository-policy root" in skill
    assert "validated lock identity" in skill
    assert "procedure revision" in skill
    proposed_head_data = (
        "`.agent-policy.yml`, `.agent-policy.lock`, policy files, generated "
        "instructions, adapters, Skills"
    )
    assert proposed_head_data in skill
    assert "as evidence and claims to verify" in skill


def test_pr_review_skill_rejects_unsafe_projection_paths_before_loading() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert "Validate the trusted-base configuration with the schema" in skill
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


def test_pr_review_skill_verifies_and_pins_projection_bytes_for_serialization() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert "Verify the bound semantic and adapter projections before consuming them" in skill
    assert "matching input and output digests" in skill
    assert "deterministic check/regeneration" in skill
    assert "toolchain revision pinned by that trusted base lock" in skill
    assert "byte-for-byte identical" in skill
    assert "A stale, manually altered, unverifiable, or non-reproducible projection" in skill
    assert "a lock digest alone is not proof" in skill
    assert "Bind the exact verified semantic and adapter bytes to this review run" in skill
    assert "immutable in-memory/content-addressed copies" in skill
    assert "reverify the source bytes immediately before every later consumption" in skill
    assert "Do not silently reopen mutable projection paths after verification" in skill
    assert "exact run-bound platform adapter bytes" in skill


def test_pr_review_skill_discards_semantic_result_after_base_change() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert "If the base tip changes" in skill
    assert "Discard **all** review evidence classifications, semantic analysis" in skill
    assert "candidate serialized result produced under the old trusted root" in skill
    assert "execute the complete review procedure again from step 1" in skill
    assert "mandatory even when bootstrap returns the same verified procedure revision" in skill


def test_canonical_prompt_is_a_thin_non_normative_invocation() -> None:
    prompt = (
        SKILL_ROOT / "references/canonical-github-pr-review-prompt.md"
    ).read_text(encoding="utf-8")

    assert "non-normative invocation template" in prompt
    assert "not a bootstrap contract" in prompt
    assert "Deployment authentication first establishes" in prompt
    assert "installed `agent-policy` Skill-source provenance" in prompt
    assert "verified `pr-review` Skill is the sole review-execution procedural authority" in prompt
    assert "Semantic review projection: `<repository-relative-semantic-output-path>`" in prompt
    assert "GitHub adapter projection: `<repository-relative-github-adapter-output-path>`" in prompt
    assert "Adapter renderer: `github-review-json-adapter-v1`" in prompt
    assert "Pass the repository/PR identity" in prompt
    assert "Do not select, authorize, discover, or verify a procedure from this prompt" in prompt
    assert "After bootstrap returns valid immutable handoff evidence" in prompt
    assert "invoke the verified `pr-review` Skill" in prompt

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


def test_pr_review_skill_rechecks_pr_repository_base_head_until_stable() -> None:
    skill = (SKILL_ROOT / "SKILL.md").read_text(encoding="utf-8")

    assert "Immediately before serialization, enter a stability loop" in skill
    assert "Re-resolve the **pull-request identity**, stable repository identity" in skill
    assert "pull-request identity and repository identity" in skill
    assert "identities bound by bootstrap evidence" in skill
    assert "ancestor set to still contain exactly one revision" in skill
    assert "If pull-request identity or repository identity changes, fail closed" in skill
    assert "deployment-authenticated installed `agent-policy` bootstrap" in skill
    assert "replacement exact base becomes the new active trusted repository-policy root" in skill
    assert "old Skill must not continue" in skill
    assert "recompute the unique merge-base→head changed surface" in skill
    stable = (
        "immediately pre-serialization observation reproduces the fully analyzed "
        "pull-request identity, repository identity, base, head, unique merge-base, "
        "current bootstrap/procedure identity, and exact semantic/adapter projection "
        "identities used by the analysis"
    )
    assert stable in skill
