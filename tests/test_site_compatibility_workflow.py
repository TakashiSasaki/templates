from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/site-compatibility.yml"
PINNED_SITE_SHA = "76db390476b2b6fd2fb49c90fd4b9fbcf0c65f94"


def test_policy_workflow_uses_reviewed_immutable_site_revision() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "branches:\n      - policy" in text
    for required_path in (
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
    assert "publication_staging_id: policy-concepts" in text
    assert "build-pages.yml@site" not in text
    assert "policy_ref: policy" not in text
    assert "PR #643 Site merge commit" in text
    assert "policy-concepts staging mapping" in text
    assert "pristine Site tests before" in text
    assert "publication-sources lock" in text
    assert "build-only" in text
    assert "cannot deploy Pages" in text
    assert "skill_ref:" not in text
    assert "webapp_ref:" not in text
    assert len(PINNED_SITE_SHA) == 40
    assert all(character in "0123456789abcdef" for character in PINNED_SITE_SHA)
