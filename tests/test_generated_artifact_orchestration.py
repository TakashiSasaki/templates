from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "orchestrate-repository-change" / "SKILL.md"
REFERENCE = (
    ROOT
    / "skills"
    / "orchestrate-repository-change"
    / "references"
    / "generated-artifact-transport.md"
)


def test_orchestration_requires_transport_classification_before_mutation() -> None:
    text = SKILL.read_text(encoding="utf-8").lower()
    for invariant in (
        "before selecting a transport or mutation mechanism",
        "git-tracked authority source",
        "generated build product",
        "external artifact",
        "generated-artifact-transport.md",
        "prefer deterministic provider-owned generation/materialization",
        "do not promote a generated projection to authority source",
        "fail closed",
    ):
        assert invariant in text


def test_transport_planning_remains_provider_neutral() -> None:
    skill = SKILL.read_text(encoding="utf-8").lower()
    reference = REFERENCE.read_text(encoding="utf-8").lower()
    combined = skill + "\n" + reference
    for product_specific in ("webmcp", "composition playground"):
        assert product_specific not in combined


def test_handoff_reports_transport_decisions_when_material() -> None:
    text = SKILL.read_text(encoding="utf-8").lower()
    assert (
        "payload classification and chosen transport when transport-sensitive mutation "
        "affected execution or resumption"
    ) in text
