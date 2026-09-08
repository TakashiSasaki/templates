from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "orchestrate-repository-change" / "SKILL.md"
LEDGER = ROOT / "skills" / "orchestrate-repository-change" / "references" / "work-ledger.md"
POLICY = ROOT / "policy" / "core" / "repository-change-anti-stall.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def test_orchestrator_projects_policy_without_becoming_authority() -> None:
    skill = _text(SKILL)
    policy = _text(POLICY)
    assert "material progress" in policy
    for token in (
        "anti-stall diagnostic control",
        "material progress",
        "strategy switch",
        "invalidated path",
        "diagnostic budget",
        "external_wait",
        "diagnostic_stall",
    ):
        assert token in skill
    assert "policy/core/repository-change-anti-stall.md" in skill
    assert "does not redefine" in skill


def test_strategy_identity_uses_selected_inputs_not_failure_outcomes() -> None:
    skill = _text(SKILL)
    ledger = _text(LEDGER)
    for text in (skill, ledger):
        assert "objective, evidence source, diagnostic method, and hypothesis" in text
        assert "failure mode per attempt" in text
    assert "do not treat a changed outcome as a new strategy" in skill
    assert "does not create a new strategy" in ledger


def test_no_progress_activity_triggers_bounded_reassessment() -> None:
    skill = _text(SKILL)
    for token in (
        "global no-material-progress budget",
        "successful calls that only reproduce already-known information",
        "two equivalent failures",
        "third identical retrieval",
        "about three no-progress tool calls",
        "two semantically equivalent progress reports",
        "capability-first",
    ):
        assert token in skill


def test_budget_exhaustion_switches_strategy_before_blocking() -> None:
    skill = _text(SKILL)
    assert "switch diagnostic strategy" in skill
    assert "only classify the objective as `blocked`" in skill
    assert "alternate authorized, in-scope strategy" in skill


def test_waiting_parallel_work_and_agent_stall_are_distinct() -> None:
    skill = _text(SKILL)
    ledger = _text(LEDGER)
    for token in (
        "external_wait",
        "diagnostic_stall",
        "productive_parallel_work",
        "completion frontier",
        "unchanged `pending` or `in_progress` status",
        "concrete resume condition",
        "stale/timeout/failure",
    ):
        assert token in skill
    assert "provider progress may be opaque" in skill
    assert "progress is opaque" in ledger


def test_work_ledger_carries_compact_anti_stall_state() -> None:
    ledger = _text(LEDGER)
    for token in (
        "attempted_paths",
        "invalidated_paths",
        "current_hypothesis",
        "evidence_gap",
        "strategy_attempt_count",
        "strategy_switch_reason",
        "progress_frontier",
        "diagnostic_budget",
        "last_material_progress",
        "next_safe_action",
    ):
        assert token in ledger


def test_ledger_negative_capability_memory_is_scoped_and_recoverable() -> None:
    ledger = _text(LEDGER)
    for token in (
        "retry_condition",
        "applicability",
        "restore invalidated paths before retrying",
        "resume is not a restart",
        "strategies already exhausted",
    ):
        assert token in ledger


def test_ledger_is_state_projection_not_diagnostic_transcript() -> None:
    ledger = _text(LEDGER)
    assert "do not record call-by-call diagnostic history" in ledger
    assert "strategy-level summary" in ledger
    assert "review finding ledger remains authoritative" in ledger
    assert "do not duplicate" in ledger


def test_work_ledger_owns_provider_specific_resume_projection() -> None:
    policy = _text(POLICY)
    ledger = _text(LEDGER)
    assert "work ledger" not in policy
    assert "work-ledger projection" in ledger
    assert "minimum logical state" in ledger
    assert "diagnosis and progress" in ledger


def test_progress_reporting_is_knowledge_delta_reporting() -> None:
    skill = _text(SKILL)
    for token in (
        "what changed",
        "what was learned",
        "what remains unknown",
        "why the strategy changed",
        "what comes next",
    ):
        assert token in skill
