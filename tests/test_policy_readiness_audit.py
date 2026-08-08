from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT / "docs/policy-readiness-audit.md"
MKDOCS = ROOT / "mkdocs.yml"
FULL_SHA = re.compile(r"^[0-9a-f]{40}$")
CANDIDATE = "7caad06497f061e507afc6df7b600c62b443bf2a"
STABLE = "5de32547e68fa15e24ff3b8affadf12e9d730a41"
EXPECTED_GATES = {
    "scope",
    "configuration",
    "generation",
    "validation",
    "adoption",
    "bootstrap",
    "release-model",
    "identity",
    "ci",
    "documentation",
    "consistency",
    "release-alignment",
}


def audit_text() -> str:
    return AUDIT.read_text(encoding="utf-8")


def gate_results() -> dict[str, tuple[str, str]]:
    results: dict[str, tuple[str, str]] = {}
    for line in audit_text().splitlines():
        if not line.startswith("| `"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        assert len(cells) == 4
        gate = cells[0].removeprefix("`").removesuffix("`")
        results[gate] = (cells[1], cells[2])
    return results


def test_audit_names_one_immutable_candidate_and_stable_revision() -> None:
    audit = audit_text()

    assert FULL_SHA.fullmatch(CANDIDATE)
    assert FULL_SHA.fullmatch(STABLE)
    assert CANDIDATE != STABLE
    assert f"Frozen candidate commit: `{CANDIDATE}`" in audit
    assert f"Stable toolchain revision at audit time: `{STABLE}`" in audit
    assert "identified only by its immutable 40-character commit SHA" in audit


def test_audit_records_every_gate_as_passed_at_the_declared_point() -> None:
    results = gate_results()

    assert set(results) == EXPECTED_GATES
    for gate, (evaluation_point, result) in results.items():
        assert result == "PASS", gate
        if gate == "release-alignment":
            assert evaluation_point == "`completion sequence`"
        else:
            assert evaluation_point == "`candidate commit`"


def test_audit_records_required_candidate_evidence() -> None:
    audit = audit_text()

    required_fragments = (
        "run #604, run ID `31236767746`, `success`",
        "run #261, run ID `31236767751`, `success`",
        "review ID `4888015772`, state `COMMENTED`",
        "Candidate unresolved review threads: `0`",
        "281 passed in 7.96s",
        "No exception or waiver is accepted or required.",
    )
    for fragment in required_fragments:
        assert fragment in audit


def test_audit_records_explicit_no_promotion_release_alignment() -> None:
    audit = audit_text()

    assert "No promotion is required." in audit
    assert f"stable channel remains at `{STABLE}`" in audit
    assert "stable verifier dependency lock is therefore retained unchanged" in audit
    assert "adds no shared executable policy-toolchain capability" in audit


def test_audit_preserves_completion_and_ecosystem_boundaries() -> None:
    audit = audit_text()

    assert "does not itself pre-declare toolkit completion" in audit
    assert (
        "may be declared only after the commit containing this audit record itself has passed"
        in audit
    )
    assert "Ecosystem migration remains a separate state." in audit
    assert "former repository has been archived" in audit


def test_audit_record_is_in_documentation_navigation() -> None:
    navigation = MKDOCS.read_text(encoding="utf-8")

    assert "Policy readiness audit: policy-readiness-audit.md" in navigation
