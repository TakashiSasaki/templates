from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
ROADMAP = ROOT / "docs/policy-readiness.md"
MIGRATION = ROOT / "docs/migration-from-agent-policy.md"
PUBLICATION = ROOT / "docs/documentation-publication.md"
MKDOCS = ROOT / "mkdocs.yml"


def normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


def test_readiness_separates_toolkit_and_ecosystem_completion() -> None:
    roadmap = normalized(ROADMAP)

    assert "## Policy toolkit completion" in roadmap
    assert "## Ecosystem migration completion" in roadmap
    assert (
        "A policy-toolkit-complete declaration does not imply ecosystem migration completion."
        in roadmap
    )


def test_readiness_covers_every_cross_cutting_gate() -> None:
    roadmap = ROADMAP.read_text(encoding="utf-8")

    for gate in (
        "`scope`",
        "`configuration`",
        "`generation`",
        "`adoption`",
        "`bootstrap`",
        "`release`",
        "`identity`",
        "`ci`",
        "`documentation`",
        "`consistency`",
    ):
        assert f"| {gate} |" in roadmap


def test_completion_requires_one_full_sha_and_an_audit_record() -> None:
    roadmap = normalized(ROADMAP)

    assert "same 40-character lowercase Git commit SHA" in roadmap
    assert "`docs/policy-readiness-audit.md`" in roadmap
    assert "successful `Policy CI` and `Policy documentation build` run identifiers" in roadmap
    assert "unresolved review-thread count" in roadmap
    assert "mutable branch or tag" in roadmap


def test_primary_documentation_links_the_readiness_contract() -> None:
    readme = README.read_text(encoding="utf-8")
    mkdocs = MKDOCS.read_text(encoding="utf-8")

    assert "docs/policy-readiness.md" in readme
    assert "policy-readiness.md" in mkdocs


def test_migration_cannot_reintroduce_policy_pages_deployment() -> None:
    migration = normalized(MIGRATION)
    publication = normalized(PUBLICATION)
    roadmap = normalized(ROADMAP)

    assert "whether and when to enable Pages deployment" not in migration
    assert "belongs exclusively to the unrelated `site` branch" in publication
    assert "The `policy` workflow remains build-only." in migration
    assert "The `policy` workflow remains build-only." in roadmap
