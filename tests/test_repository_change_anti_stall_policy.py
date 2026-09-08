import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
POLICY = ROOT / "policy" / "core" / "repository-change-anti-stall.md"
PROFILE = ROOT / "profiles" / "core.yml"
CASES = ROOT / "tests" / "fixtures" / "repository-change-anti-stall" / "cases.json"


def _policy() -> str:
    return POLICY.read_text(encoding="utf-8").lower()


def test_policy_has_required_core_metadata() -> None:
    text = POLICY.read_text(encoding="utf-8")
    assert text.startswith("---\n")
    for token in (
        "id: changes.prevent-diagnostic-stall",
        "severity: mandatory",
        "overridable: false",
        "order: 520",
    ):
        assert token in text


def test_core_profile_includes_anti_stall_policy() -> None:
    assert "policy/core/repository-change-anti-stall.md" in PROFILE.read_text(encoding="utf-8")


def test_progress_is_material_state_delta_not_tool_activity() -> None:
    text = _policy()
    for token in (
        "material progress",
        "knowledge-state",
        "repository-state",
        "tool calls",
        "last_material_progress",
        "progress_frontier",
    ):
        assert token in text


def test_bounded_retries_use_failure_classification_and_strategy_identity() -> None:
    text = _policy()
    for token in (
        "two failures",
        "third identical retrieval",
        "cheap deterministic retry",
        "transient failure",
        "authentication failure",
        "capability unavailable",
        "evidence unavailable",
        "semantic failure",
        "strategy switch",
    ):
        assert token in text


def test_invalidated_paths_require_evidenced_context_change() -> None:
    text = _policy()
    for token in (
        "invalidated path",
        "retry_condition",
        "applicability",
        "changed runtime",
        "network recovery",
    ):
        assert token in text


def test_stagnation_and_reporting_have_bounded_baselines() -> None:
    text = _policy()
    for token in (
        "about 3 calls",
        "about 2 consecutive reports",
        "stagnation signal",
        "what remains unknown",
        "next safe action",
        "tool discovery",
    ):
        assert token in text


def test_wait_stall_blocked_and_parallel_work_are_distinct() -> None:
    text = _policy()
    for token in (
        "external_wait",
        "diagnostic_stall",
        "blocked",
        "productive_parallel_work",
        "completion frontier",
    ):
        assert token in text


def test_resume_state_is_compact_and_separate_from_review_findings() -> None:
    text = _policy()
    for token in (
        "current failure scope",
        "current evidence gap",
        "attempted paths",
        "exhausted strategies",
        "diagnostic budget state",
        "must not record `call 1`",
        "review finding ledger remains authoritative",
    ):
        assert token in text


def test_regression_matrix_contains_cases_a_through_h() -> None:
    cases = json.loads(CASES.read_text(encoding="utf-8"))
    assert [case["id"][0] for case in cases] == list("ABCDEFGH")
    joined = json.dumps(cases).lower()
    for token in (
        "third identical retrieval is prohibited",
        "gh-cli",
        "direct-github-network",
        "not material progress",
        "stagnation signal",
        "external_wait",
        "do not restart investigation",
        "review finding ledger remains authoritative",
    ):
        assert token in joined
