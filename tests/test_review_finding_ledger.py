from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "skills" / "pr-merge-gate" / "references" / "review-finding-ledger.md"
DISPOSITION = ROOT / "skills" / "pr-merge-gate" / "references" / "review-feedback-disposition.md"
BATCHING = ROOT / "skills" / "pr-merge-gate" / "references" / "head-mutation-batching.md"


def _text(path: Path) -> str:
    return path.read_text(encoding="utf-8").lower()


def test_logical_finding_ledger_tracks_required_state_without_file_schema() -> None:
    text = _text(LEDGER)
    for phrase in (
        "stable locator / identity",
        "source review",
        "reviewed head",
        "current applicability",
        "primary disposition",
        "decisive evidence",
        "mutation required?",
        "repair / action",
        "repair/current head",
        "validation evidence",
        "closure evidence / surface",
        "final state",
    ):
        assert phrase in text

    for transport in (
        "inline review thread",
        "reply to a review",
        "pull-request issue comment",
        "pull-request body",
        "agent execution state",
    ):
        assert transport in text

    assert "not a mandatory json/yaml artifact" in text
    assert "do not create a repository file solely" in text
    assert "transport representation must not redefine" in text


def test_ledger_keeps_body_only_findings_in_the_same_backlog() -> None:
    text = _text(LEDGER)
    for phrase in (
        "top-level review-body findings",
        "zero unresolved threads does not imply an empty finding backlog",
        "body-only findings",
        "independently identifiable finding locator",
    ):
        assert phrase in text


def test_ledger_supports_no_change_disposition_without_appeasement_mutation() -> None:
    text = _text(LEDGER)
    for phrase in (
        "evidence-backed no-change disposition",
        "do not create an appeasement mutation",
        "falsified finding",
        "do not force an unrelated suggestion into scope",
    ):
        assert phrase in text


def test_falsified_finding_remains_unresolved_until_validated_no_change_closure() -> None:
    text = _text(LEDGER)
    assert "current applicability is evidence used to choose the disposition" in text
    assert "not by itself permission to drop a known finding" in text
    assert "current applicability is `falsified` remains in the unresolved backlog" in text
    assert "captured as an evidence-backed no-change disposition" in text
    assert "validated for the current proposed head" in text
    assert "closure evidence is recorded" in text


def test_disposition_reuses_existing_taxonomy_and_ledger() -> None:
    text = _text(DISPOSITION)
    for category in (
        "actual-defect",
        "invariant-gap",
        "regression-test-gap",
        "documentation-ambiguity",
        "reviewer-misunderstanding",
        "unrelated-suggestion",
    ):
        assert category in text
    assert "review-finding-ledger.md" in text
    assert "transport representation" in text
    assert "entire known-finding backlog" in text


def test_batching_avoids_one_finding_head_churn_without_time_gate() -> None:
    text = _text(BATCHING)
    for phrase in (
        "currently known backlog",
        "group only compatible repairs",
        "one coherent mutation batch",
        "one-finding-at-a-time review/head churn",
        "do not manufacture a no-op or cosmetic commit",
        "do not wait an arbitrary amount of time",
        "hypothetical future findings",
        "different authority decisions",
        "materially unrelated work",
    ):
        assert phrase in text


def test_head_change_selectively_invalidates_evidence_not_ledger_identity() -> None:
    text = _text(BATCHING) + "\n" + _text(LEDGER)
    for phrase in (
        "according to its actual bindings",
        "finding identity",
        "source review",
        "survive a head change",
        "invalidate and reacquire only the exact-head evidence whose actual binding changed",
    ):
        assert phrase in text
    assert (
        "exact-head ci or review evidence bound to the former proposed commit becomes stale"
        in text
    )
