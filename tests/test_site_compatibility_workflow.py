from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/site-compatibility.yml"
PINNED_SITE_SHA = "7776f174e116d8ade9eb0f481d3f8b9bd743c792"
STAGING_IDS = (
    "contributing",
    "maintainer-workflow",
    "adr-review-authority-and-github-runtime-boundary",
    "adr-review-result-representation-boundary",
)
STAGING_IDS_CSV = ",".join(STAGING_IDS)


def test_policy_workflow_uses_reviewed_immutable_site_revision() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert 'branches:\n      - policy\n      - "policy-*"\n    paths:' in text
    for required_path in (
        "- CONTRIBUTING.md",
        "- docs/**",
        "- .github/workflows/pages.yml",
        "- .github/workflows/site-compatibility.yml",
        "- tests/test_publication_protocol_consumption.py",
        "- tests/test_site_compatibility_workflow.py",
    ):
        assert required_path in text
    assert "permissions:\n  contents: read" in text
    assert (
        f"uses: TakashiSasaki/templates/.github/workflows/build-pages.yml@{PINNED_SITE_SHA}"
        in text
    )
    assert f"site_ref: {PINNED_SITE_SHA}" in text
    assert "policy_ref: ${{ github.sha }}" in text
    assert "publication_staging_ids: >-" in text
    assert f"        {STAGING_IDS_CSV}" in text
    assert "publication_staging_id:" not in text
    assert "matrix.staging_id" not in text
    assert "strategy:" not in text
    assert "      actions: read" in text
    assert "build-pages.yml@site" not in text
    assert "policy_ref: policy" not in text
    assert "PR #850 Site merge commit" in text
    assert "PR #848 Site-owned" in text
    assert "maintainer documentation staging mappings" in text
    assert "immutable site_ref" in text
    assert "atomically stages the complete mapping set" in text
    assert "Partial one-ID staging is intentionally not used" in text
    assert "pristine Site tests before" in text
    assert "publication-sources lock" in text
    assert "build-only" in text
    assert "cannot deploy" in text
    assert "exact-input artifact" in text
    assert "skill_ref:" not in text
    assert "webapp_ref:" not in text
    assert len(PINNED_SITE_SHA) == 40
    assert all(character in "0123456789abcdef" for character in PINNED_SITE_SHA)
