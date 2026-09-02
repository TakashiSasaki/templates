from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "pr-merge-gate" / "SKILL.md"
REFERENCE = (
    ROOT
    / "skills"
    / "pr-merge-gate"
    / "references"
    / "head-mutation-batching.md"
)


def test_merge_gate_wires_stable_candidate_mutation_batching() -> None:
    skill = SKILL.read_text(encoding="utf-8").lower()

    for invariant in (
        "references/head-mutation-batching.md",
        "keep the current candidate sha stable",
        "one coherent mutation batch",
        "known material defect blocks merge immediately",
        "do not wait an arbitrary interval for hypothetical future findings",
        "concrete operational or safety risk",
        "invalidate and reacquire only the evidence actually bound to the former sha",
        "intentionally partial intermediate heads",
    ):
        assert invariant in skill


def test_mutation_batching_is_efficiency_procedure_not_acceptance_authority() -> None:
    text = REFERENCE.read_text(encoding="utf-8").lower()

    for invariant in (
        "does not create a new acceptance gate",
        "waiting period",
        "continue read-only investigation",
        "keeping the sha stable for batching never makes a known-defective head acceptable",
        "batch only work that is already known and justified",
        "do not wait an arbitrary amount of time for hypothetical future findings",
        "coherence is more important than minimizing commit count",
        "immediate-mutation exceptions",
        (
            "request or collect new exact-head ci/review evidence only after the "
            "coherent replacement candidate is ready"
        ),
        "mutation batching is an efficiency discipline, not acceptance evidence",
    ):
        assert invariant in text


def test_mutation_batching_preserves_selective_evidence_invalidation() -> None:
    text = REFERENCE.read_text(encoding="utf-8").lower()

    for invariant in (
        "exact-head ci, exact-head review, and head-bound scope evidence",
        "target-branch evidence is affected only when its own binding changed",
        "evidence independent of the changed head remains reusable",
        "reacquire every exact-head gate invalidated by the mutation",
    ):
        assert invariant in text
