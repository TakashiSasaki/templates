from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MKDOCS = ROOT / "mkdocs.yml"
SUPERSEDED_ADR = ROOT / "docs" / "adr" / "0004-integrated-bootstrap-skill.md"
RESULT_BOUNDARY_ADR = ROOT / "docs" / "adr" / "0009-review-result-representation-boundary.md"


def test_mkdocs_separates_current_and_superseded_adrs() -> None:
    text = MKDOCS.read_text(encoding="utf-8")

    current = "          - Current decisions:"
    superseded = "          - Superseded decisions:"
    adr7 = (
        "              - ADR-0007 Single agent-policy skill runtime cache: "
        "adr/0007-single-agent-policy-skill-runtime-cache.md"
    )
    adr8 = (
        "              - ADR-0008 Review authority and GitHub runtime boundary: "
        "adr/0008-review-authority-and-github-runtime-boundary.md"
    )
    adr9 = (
        "              - ADR-0009 Review-result representation boundary: "
        "adr/0009-review-result-representation-boundary.md"
    )
    adr4 = (
        "              - ADR-0004 Integrated bootstrap skill (superseded): "
        "adr/0004-integrated-bootstrap-skill.md"
    )

    assert current in text
    assert superseded in text
    assert adr7 in text
    assert adr8 in text
    assert adr9 in text
    assert adr4 in text
    assert (
        text.index(current)
        < text.index(adr7)
        < text.index(adr8)
        < text.index(adr9)
        < text.index(superseded)
        < text.index(adr4)
    )


def test_result_representation_adr_supersedes_only_adapter_coupling() -> None:
    text = RESULT_BOUNDARY_ADR.read_text(encoding="utf-8")

    assert "Supersedes in part: ADR-0008" in text
    assert "two explicit semantic/adapter output bindings" in text
    assert "adapter projection identity in final review stability" in text
    assert "All other ADR-0008 trust machinery remains in force" in text
    assert "review-versus-merge separation" in text


def test_superseded_adr_warns_before_historical_detail() -> None:
    text = SUPERSEDED_ADR.read_text(encoding="utf-8")

    marker = "> Historical record. This decision is superseded by ADR-0007"
    assert marker in text
    assert text.index(marker) < text.index("## Context")
    assert "must not be used as the current Policy architecture" in text
