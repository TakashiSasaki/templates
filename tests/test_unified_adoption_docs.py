from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_doc(relative: str) -> str:
    return (ROOT / relative).read_text(encoding="utf-8")


def test_current_onboarding_docs_use_state_derived_adoption() -> None:
    for relative in [
        "docs/adoption.md",
        "docs/architecture.md",
        "docs/bootstrap-model.md",
        "docs/repository-structure.md",
    ]:
        text = read_doc(relative)
        assert "--route init" not in text
        assert "--route adopt" not in text
        assert "fresh adoption" in text.lower()
        assert "migration adoption" in text.lower()


def test_readiness_audit_marks_legacy_route_names_as_historical() -> None:
    audit = read_doc("docs/policy-readiness-audit.md")
    assert "At this frozen candidate" in audit
    assert "historical candidate evidence" in audit
    assert "not the current bootstrap route naming" in audit
