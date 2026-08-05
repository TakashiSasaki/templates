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


def readiness_gate_conditions() -> dict[str, str]:
    gates: dict[str, str] = {}
    for line in ROADMAP.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| `"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        assert len(cells) == 3
        gate = cells[0].removeprefix("`").removesuffix("`")
        assert gate not in gates
        gates[gate] = cells[1]
    return gates


def test_readiness_separates_toolkit_and_ecosystem_completion() -> None:
    roadmap = normalized(ROADMAP)

    assert "## Policy toolkit completion" in roadmap
    assert "## Ecosystem migration completion" in roadmap
    assert (
        "A policy-toolkit-complete declaration does not imply ecosystem migration completion."
        in roadmap
    )


def test_readiness_enforces_every_cross_cutting_gate_condition() -> None:
    gates = readiness_gate_conditions()
    required_fragments = {
        "scope": ("application-type independent", "excludes product architecture"),
        "configuration": (
            "`.agent-policy.yml`",
            "sole semantic configuration entry point",
            "validates deterministically",
        ),
        "generation": (
            "`init --apply`",
            "`render`",
            "deterministically write",
            "dry-run `init`",
            "without mutation",
        ),
        "validation": (
            "`validate` is read-only",
            "`check` is read-only",
            "stale or modified generated artifacts",
            "without changing the repository",
        ),
        "adoption": (
            "Inspection, preparation, preview",
            "explicit transactional finalization",
            "safety boundary",
        ),
        "bootstrap": (
            "executes only the stable full SHA",
            "no adoption-finalization route",
        ),
        "release": (
            "stable descriptor",
            "bootstrap manifest",
            "verifier lock",
            "separate candidate and promotion commits",
        ),
        "identity": ("TakashiSasaki/templates", "policy"),
        "ci": (
            "fixed baseline",
            "neutralizes external Python and pip inputs",
            "verifies the installed distribution set",
        ),
        "documentation": (
            "builds strictly",
            "without any Pages upload or deployment authority on `policy`",
        ),
        "consistency": (
            "README, architecture, ADRs",
            "do not contradict one another",
        ),
    }

    assert set(gates) == set(required_fragments)
    for gate, fragments in required_fragments.items():
        for fragment in fragments:
            assert fragment in gates[gate]


def test_completion_uses_distinct_candidate_promotion_and_audit_commits() -> None:
    roadmap = normalized(ROADMAP)

    assert (
        "candidate, any required stable-promotion commit, and the audit-record commit are "
        "different commits"
    ) in roadmap
    assert "audit-record commit must be later than the candidate" in roadmap
    assert "when promotion is required, later than the promotion commit" in roadmap
    assert "record does not contain its own commit SHA" in roadmap
    assert "Do not declare policy-toolkit completion in this phase." in roadmap
    assert "Declare policy-toolkit completion only after those checks pass" in roadmap


def test_completion_requires_one_full_sha_and_a_final_audit_record() -> None:
    roadmap = normalized(ROADMAP)

    assert "same 40-character lowercase Git commit SHA" in roadmap
    assert "`docs/policy-readiness-audit.md`" in roadmap
    assert "successful `Policy CI` and `Policy documentation build` run identifiers" in roadmap
    assert "unresolved review-thread count" in roadmap
    assert "mutable branch or tag" in roadmap
    assert "promotion commit's 40-character lowercase Git SHA" in roadmap
    assert "existing stable pin remains valid" in roadmap


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
