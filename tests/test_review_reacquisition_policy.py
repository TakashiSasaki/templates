from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RULE = ROOT / "policy" / "pull-request" / "review-reacquisition-after-disposition.md"
THREAD_RULE = ROOT / "policy" / "pull-request" / "review-thread-closure.md"
INDEPENDENT_RULE = ROOT / "policy" / "pull-request" / "independent-exact-head-review.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def test_reacquisition_gate_requires_disposition_of_known_material_findings() -> None:
    text = _text(RULE)
    for phrase in (
        "before intentionally starting a new merge-acceptance review acquisition cycle",
        "every material actionable finding already known",
        "repair validated for the current proposed head",
        "evidence-backed no-change disposition",
        "finding-level closure evidence",
        "unresolved or deferred material findings",
        "required current-head validated outcome or the required closure evidence",
        "top-level review body",
        "provider thread resolution is bookkeeping",
        "closure evidence records the validated disposition for auditability",
        "defect hypothesis rather than authority",
        "appeasement edit",
        "unrelated suggestion",
    ):
        assert phrase in text


def test_reacquisition_gate_preserves_handoff_and_urgent_repair_semantics() -> None:
    text = _text(RULE)
    for phrase in (
        "urgent operational, security, or data-integrity repair",
        "naturally triggered ci or review-provider behavior",
        "does not require waiting for hypothetical future findings",
        "explicit human-handoff procedure",
        "one final diagnostic whole-stack audit",
        "validated dispositions and recorded closure evidence required above",
        "distinct from merge-acceptance evidence",
        "does not satisfy or waive the independent exact-head review requirements",
    ):
        assert phrase in text


def test_reacquisition_gate_has_distinct_boundary_from_merge_thread_closure() -> None:
    reacquisition = _text(RULE)
    closure = _text(THREAD_RULE)
    independent = _text(INDEPENDENT_RULE)

    assert (
        "before intentionally starting a new merge-acceptance review acquisition cycle"
        in reacquisition
    )
    assert "finding-level closure evidence" in reacquisition
    assert "before merge" in closure
    assert "before merging" in independent
    assert "review acquisition cycle" not in closure
    assert "completed review" in independent
