from __future__ import annotations

import re
from pathlib import Path

import yaml

from agent_policy.policy_loader import parse_policy

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "pr-merge-gate" / "SKILL.md"
PROFILE = ROOT / "profiles" / "pull-request.yml"


def _profile_rule_ids() -> list[str]:
    profile = yaml.safe_load(PROFILE.read_text(encoding="utf-8"))
    return [
        parse_policy(ROOT / path, path, "toolchain").id
        for path in profile["policy_files"]
    ]


def test_adapter_has_stable_agent_skill_identity() -> None:
    text = SKILL.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    _, frontmatter, body = text.split("---\n", 2)
    metadata = yaml.safe_load(frontmatter)
    assert metadata["name"] == "pr-merge-gate"
    assert isinstance(metadata["description"], str) and metadata["description"]
    assert re.fullmatch(r"[a-z0-9-]+", SKILL.parent.name)
    assert body.lstrip().startswith("# Pull Request Merge Gate\n")


def test_adapter_references_every_canonical_pull_request_rule() -> None:
    text = SKILL.read_text(encoding="utf-8")
    rule_ids = _profile_rule_ids()
    assert rule_ids
    for rule_id in rule_ids:
        assert f"`{rule_id}`" in text


def test_adapter_declares_policy_authority_boundary() -> None:
    text = SKILL.read_text(encoding="utf-8").lower()
    for invariant in (
        "not a second authority for shared pull-request semantics",
        "the rules under `policy/pull-request/` are canonical",
        "this skill owns github-specific execution details, not shared policy meaning",
        "if this skill conflicts with those canonical rules, follow the canonical rules",
        "if the `pull-request` profile changes, this adapter must be reviewed",
    ):
        assert invariant in text


def test_adapter_keeps_provider_mechanics_outside_atomic_policy() -> None:
    adapter = SKILL.read_text(encoding="utf-8")
    policy_corpus = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (ROOT / "policy" / "pull-request").glob("*.md")
    )

    adapter_terms = (
        "GitHub connector",
        "expected_head_sha",
        "check-run",
        "check-suite",
        "CI_DISCOVERY_MIN_OBSERVATION_MINUTES = 10",
        "@hermes review",
    )
    for term in adapter_terms:
        assert term in adapter
        assert term not in policy_corpus


def test_adapter_ci_discovery_is_fail_closed_and_read_only() -> None:
    text = SKILL.read_text(encoding="utf-8").lower()
    for invariant in (
        "`ci_discovery_pending`",
        "`ci_confirmed_absent`",
        "use read-only discovery",
        "at least two independently indexed github views",
        "a single zero-result view",
        "elapsed time alone is insufficient",
        "do not close/reopen the pr",
        "create a no-op commit",
        "solely to retrigger ci",
    ):
        assert invariant in text


def test_adapter_requires_exact_head_review_and_guarded_merge() -> None:
    text = SKILL.read_text(encoding="utf-8").lower()
    for invariant in (
        "request review for the exact current head",
        "the request must name the exact sha",
        "a request, pending review, empty review list, or absence of findings is not completed review evidence",
        "include the literal string `@hermes review`",
        "current pr head equals the exact accepted head",
        "never omit `expected_head_sha`",
        "do not retry blindly",
    ):
        assert invariant in text


def test_adapter_separates_merge_from_post_merge_readiness() -> None:
    text = SKILL.read_text(encoding="utf-8").lower()
    for invariant in (
        "confirm the pr is actually merged",
        "record the merge commit sha",
        "treat release, publication, deployment, and other post-merge readiness as separate boundaries",
    ):
        assert invariant in text
