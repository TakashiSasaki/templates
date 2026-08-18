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


def test_consumer_and_cli_docs_distinguish_execution_context() -> None:
    getting_started = read_doc("docs/getting-started.md")
    bootstrap = read_doc("docs/bootstrap.md")
    cli = read_doc("docs/cli.md")
    adoption = read_doc("docs/adoption.md")

    assert "From the installed skill directory" in getting_started
    assert "Run from the installed skill directory" in bootstrap
    assert "canonical toolchain CLI" in cli
    assert "canonical toolchain CLI" in adoption
    assert "globally on `PATH`" in cli
    assert "globally on `PATH`" in adoption


def test_migration_docs_cover_zero_one_and_multiple_primary_instructions() -> None:
    getting_started = read_doc("docs/getting-started.md")
    bootstrap = read_doc("docs/bootstrap.md")
    adoption = read_doc("docs/adoption.md")

    assert "A single supported instruction" in getting_started
    assert "If multiple supported instruction files are discovered" in getting_started
    assert "If none are discovered, create one supported instruction file first" in getting_started

    assert "exactly one supported instruction file" in bootstrap
    assert "multiple supported instruction files" in bootstrap
    assert "When it finds none, create a supported" in bootstrap

    assert "A single discovered supported instruction file is selected automatically" in adoption
    assert "If multiple supported instruction files are discovered" in adoption
    assert "If zero supported instruction files are discovered" in adoption


def test_readiness_audit_marks_legacy_route_names_as_historical() -> None:
    audit = read_doc("docs/policy-readiness-audit.md")
    assert "At this frozen candidate" in audit
    assert "historical candidate evidence" in audit
    assert "not the current bootstrap route naming" in audit
