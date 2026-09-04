from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SELECTION = (
    ROOT
    / "skills"
    / "orchestrate-repository-change"
    / "references"
    / "pr-workflow-selection.md"
)
SERIAL = (
    ROOT
    / "skills"
    / "orchestrate-repository-change"
    / "references"
    / "serial-pr-workflow.md"
)


def _strategy_matrix() -> dict[tuple[str, str], tuple[str, str, str]]:
    lines = SELECTION.read_text(encoding="utf-8").splitlines()
    marker = lines.index("## Strategy matrix")
    rows = [line for line in lines[marker + 1 :] if line.startswith("|")]
    header, separator, *data = rows
    assert [cell.strip() for cell in header.strip("|").split("|")] == [
        "Progression",
        "Completion",
        "Construction",
        "Review acquisition",
        "Merge boundary",
    ]
    assert not separator.replace("|", "").replace("-", "").replace(" ", "")

    matrix: dict[tuple[str, str], tuple[str, str, str]] = {}
    for row in data:
        cells = tuple(cell.strip() for cell in row.strip("|").split("|"))
        assert len(cells) == 5
        progression, completion, construction, review, merge = cells
        matrix[(progression, completion)] = (construction, review, merge)
    return matrix


def test_strategy_matrix_covers_exactly_the_two_by_two_product() -> None:
    matrix = _strategy_matrix()
    assert set(matrix) == {
        ("serial-pr", "agent-review-and-merge"),
        ("serial-pr", "human-handoff"),
        ("stacked-pr", "agent-review-and-merge"),
        ("stacked-pr", "human-handoff"),
    }


def test_strategy_matrix_encodes_expected_behavior_for_all_four_combinations() -> None:
    serial_construction = (
        "implement and validate one member, then open its pull request without "
        "review acquisition"
    )
    assert _strategy_matrix() == {
        ("serial-pr", "agent-review-and-merge"): (
            serial_construction,
            "establish completed independent exact-head review for the member",
            "guarded merge, then begin the next member",
        ),
        ("serial-pr", "human-handoff"): (
            "implement and validate the current member, then open its pull request "
            "without merge-acceptance review acquisition",
            "no merge-acceptance review by default; an explicit task may authorize "
            "one final diagnostic whole-stack audit when a stack exists",
            "stop at HANDOFF_READY; leave the member open and unmerged",
        ),
        ("stacked-pr", "agent-review-and-merge"): (
            "construct and validate dependent members without review latency "
            "blocking construction",
            "establish individual independent exact-head review per member, or "
            "explicit cumulative stack coverage satisfying canonical bindings",
            "guarded bottom-up merge after applicability evaluation",
        ),
        ("stacked-pr", "human-handoff"): (
            "construct and validate the ordered stack",
            "no merge-acceptance review by default; an explicit task may authorize "
            "one final diagnostic whole-stack audit after the complete stack is stable",
            "stop at HANDOFF_READY; leave the whole stack open and unmerged",
        ),
    }


def test_serial_procedure_materializes_pr_before_completion_branch() -> None:
    text = SERIAL.read_text(encoding="utf-8").lower()
    create_marker = "create or ensure an open pull request for the exact validated member"
    completion_marker = "then apply the selected completion strategy"
    assert create_marker in text
    assert "without initiating review acquisition" in text
    assert "non-review-triggering state such as draft" in text
    assert text.index(create_marker) < text.index(completion_marker)


def test_serial_handoff_preserves_preexisting_completed_review_state() -> None:
    text = SERIAL.read_text(encoding="utf-8").lower()
    assert "report the observed review state truthfully" in text
    assert "when no applicable pre-existing evidence establishes another state" in text
    assert "preserve review_complete" in text


def test_stacked_tip_only_approval_differs_from_individual_exact_head_review() -> None:
    text = SELECTION.read_text(encoding="utf-8").lower()
    assert (
        "a stacked member may instead rely on its own completed independent "
        "exact-head review"
    ) in text
    assert (
        "a tip-only review or approval event is not cumulative coverage for lower "
        "members"
    ) in text
