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
    documents = {
        "README.md": read_doc("README.md"),
        "docs/getting-started.md": read_doc("docs/getting-started.md"),
        "docs/bootstrap.md": read_doc("docs/bootstrap.md"),
        "docs/cli.md": read_doc("docs/cli.md"),
        "docs/adoption.md": read_doc("docs/adoption.md"),
    }
    path_statement = (
        "Installing the skill does not by itself install an `agent-policy` "
        "executable globally on `PATH`."
    )

    assert "repository-development installation path" in documents["README.md"]
    assert "not necessarily byte-for-byte identical" in documents["README.md"]

    for relative, text in documents.items():
        assert path_statement in text, relative

    assert "From the installed skill directory" in documents["docs/getting-started.md"]
    assert "Run from the installed skill directory" in documents["docs/bootstrap.md"]
    assert "canonical toolchain CLI" in documents["docs/cli.md"]
    assert "canonical toolchain CLI" in documents["docs/adoption.md"]
    assert "scripts/bootstrap.py" in documents["docs/adoption.md"]
    assert "scripts/run.py" in documents["docs/adoption.md"]


def test_getting_started_surfaces_profile_selection_for_first_time_consumers() -> None:
    getting_started = read_doc("docs/getting-started.md")
    japanese = read_doc("translations/ja/docs/getting-started.md")

    for text in [getting_started, japanese]:
        assert "`core`" in text
        assert "`security-baseline`" in text
        assert "`pull-request`" in text
        assert "`review`" in text
        assert "`external-artifact-intake`" in text
        assert "[Policy profiles](shared-policy/profiles.md)" in text

    assert "normal bootstrap path uses exactly that pair" in getting_started
    assert "通常のbootstrap path" in japanese


def test_migration_docs_cover_zero_one_and_multiple_primary_instructions() -> None:
    getting_started = read_doc("docs/getting-started.md")
    bootstrap_doc = read_doc("docs/bootstrap.md")
    adoption = read_doc("docs/adoption.md")
    skill = read_doc("skills/agent-policy/SKILL.md")
    zero_case = "If no supported instruction files are discovered"

    assert "a single supported instruction" in getting_started.lower()
    assert "If multiple supported instruction files are discovered" in getting_started
    assert zero_case in getting_started

    assert "exactly one supported instruction file" in bootstrap_doc
    assert "multiple supported instruction files" in bootstrap_doc
    assert zero_case in bootstrap_doc

    assert "A single discovered supported instruction file is selected automatically" in adoption
    assert "If multiple supported instruction files are discovered" in adoption
    assert zero_case in adoption

    assert zero_case in skill
    assert "exactly one supported instruction file is discovered" in skill
    assert "If multiple supported instruction files are discovered" in skill
    assert "zero or multiple supported primary instruction files" not in skill


def test_readiness_audit_marks_legacy_route_names_as_historical() -> None:
    audit = read_doc("docs/policy-readiness-audit.md")
    assert "At this frozen candidate" in audit
    assert "historical candidate evidence" in audit
    assert "not the current bootstrap route naming" in audit
