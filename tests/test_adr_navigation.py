from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MKDOCS = ROOT / "mkdocs.yml"
ADR_INDEX = ROOT / "docs" / "adr" / "index.md"
SUPERSEDED_ADR = ROOT / "docs" / "adr" / "0004-integrated-bootstrap-skill.md"


def test_mkdocs_separates_current_and_superseded_adrs() -> None:
    text = MKDOCS.read_text(encoding="utf-8")

    current = "          - Current decisions:"
    superseded = "          - Superseded decisions:"
    adr7 = (
        "              - ADR-0007 Single agent-policy skill runtime cache: "
        "adr/0007-single-agent-policy-skill-runtime-cache.md"
    )
    adr4 = (
        "              - ADR-0004 Integrated bootstrap skill (superseded): "
        "adr/0004-integrated-bootstrap-skill.md"
    )

    assert current in text
    assert superseded in text
    assert adr7 in text
    assert adr4 in text
    assert text.index(current) < text.index(adr7) < text.index(superseded) < text.index(adr4)


def test_adr_index_marks_current_and_superseded_authority() -> None:
    text = ADR_INDEX.read_text(encoding="utf-8")

    assert "## Current decisions" in text
    assert "## Superseded decisions" in text
    assert text.index("ADR-0007") < text.index("## Superseded decisions") < text.index("ADR-0004")
    assert "retained only as historical rationale" in text


def test_superseded_adr_warns_before_historical_detail() -> None:
    text = SUPERSEDED_ADR.read_text(encoding="utf-8")

    marker = "> Historical record. This decision is superseded by ADR-0007"
    assert marker in text
    assert text.index(marker) < text.index("## Context")
    assert "must not be used as the current Policy architecture" in text
