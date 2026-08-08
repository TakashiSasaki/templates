from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
ROADMAP = ROOT / "docs/policy-readiness.md"
PUBLICATION = ROOT / "docs/documentation-publication.md"
MKDOCS = ROOT / "mkdocs.yml"


def normalized(path: Path) -> str:
    return " ".join(path.read_text(encoding="utf-8").split())


def readiness_gates() -> dict[str, tuple[str, str]]:
    gates: dict[str, tuple[str, str]] = {}
    for line in ROADMAP.read_text(encoding="utf-8").splitlines():
        if not line.startswith("| `"):
            continue
        cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
        assert len(cells) == 4
        gate = cells[0].removeprefix("`").removesuffix("`")
        assert gate not in gates
        gates[gate] = (cells[1], cells[2])
    return gates


def test_readiness_defines_templates_local_completion_states() -> None:
    roadmap = normalized(ROADMAP)

    assert "## Policy toolkit completion" in roadmap
    for state in (
        "Development baseline",
        "Frozen audit candidate",
        "Candidate verified",
        "Release aligned",
        "Policy toolkit complete",
    ):
        assert state in roadmap
    assert "entirely within `TakashiSasaki/templates`" in roadmap


def test_readiness_enforces_gate_conditions_and_evaluation_points() -> None:
    gates = readiness_gates()
    required = {
        "scope": (
            "`candidate commit`",
            ("application-type independent", "excludes product architecture"),
        ),
        "configuration": (
            "`candidate commit`",
            (
                "`.agent-policy.yml`",
                "sole semantic configuration entry point",
                "validates deterministically",
            ),
        ),
        "generation": (
            "`candidate commit`",
            (
                "`init --apply`",
                "`render`",
                "deterministically write",
                "dry-run `init`",
                "without mutation",
            ),
        ),
        "validation": (
            "`candidate commit`",
            (
                "`validate` is read-only",
                "`check` is read-only",
                "stale or modified generated artifacts",
                "without changing the repository",
            ),
        ),
        "adoption": (
            "`candidate commit`",
            (
                "Inspection, preparation, preview",
                "explicit transactional finalization",
                "safety boundary",
            ),
        ),
        "bootstrap": (
            "`candidate commit`",
            ("executes only the stable full SHA", "no adoption-finalization route"),
        ),
        "release-model": (
            "`candidate commit`",
            (
                "schema-validated stable descriptor",
                "synchronization verifier",
                "separate candidate-and-promotion lifecycle",
                "free of mutable release references",
            ),
        ),
        "identity": ("`candidate commit`", ("TakashiSasaki/templates", "policy")),
        "ci": (
            "`candidate commit`",
            (
                "fixed baseline",
                "neutralizes external Python and pip inputs",
                "verifies the installed distribution set",
            ),
        ),
        "documentation": (
            "`candidate commit`",
            ("builds strictly", "without any Pages upload or deployment authority on `policy`"),
        ),
        "consistency": (
            "`candidate commit`",
            ("README, architecture, ADRs", "in the candidate do not contradict one another"),
        ),
        "release-alignment": (
            "`completion sequence`",
            (
                "remains on its current full SHA with an explicit no-promotion rationale",
                "separate promotion commit synchronizes",
                "to the frozen candidate",
                "retaining the existing verifier lock when compatible",
                "updating it when the candidate requires a different probe environment",
            ),
        ),
    }

    assert set(gates) == set(required)
    for gate, (expected_point, fragments) in required.items():
        point, condition = gates[gate]
        assert point == expected_point
        for fragment in fragments:
            assert fragment in condition


def test_candidate_verification_excludes_release_alignment() -> None:
    roadmap = normalized(ROADMAP)

    assert "every gate whose evaluation point is `candidate commit`" in roadmap
    assert "`release-alignment` gate is evaluated later across the completion sequence" in roadmap
    assert "it is not a candidate-local gate" in roadmap
    assert "without marking that sequence gate passed" in roadmap
    assert "Mark `release-alignment` passed only after" in roadmap


def test_verifier_lock_promotion_is_conditional() -> None:
    roadmap = normalized(ROADMAP)

    assert "updates the verifier lock only when the candidate requires" in roadmap
    assert "otherwise it retains and verifies the existing compatible lock" in roadmap
    assert "Update the stable verifier lock in that promotion commit only when" in roadmap
    assert "otherwise retain and verify the existing compatible lock" in roadmap


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


def test_policy_documentation_keeps_pages_deployment_outside_policy() -> None:
    publication = normalized(PUBLICATION)
    roadmap = normalized(ROADMAP)

    assert "belongs exclusively to the unrelated `site` branch" in publication
    assert "a Pages deployment path on `policy`" in roadmap
