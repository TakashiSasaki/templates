from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/site-compatibility.yml"
PINNED_SITE_SHA = "f79eaa9e90197da0bb0c7eefaa039f265ad4b347"


def test_policy_workflow_uses_reviewed_immutable_site_revision() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")
    assert \
        f"uses: TakashiSasaki/templates/.github/workflows/build-pages.yml@{PINNED_SITE_SHA}" \
        in text
    assert f"site_ref: {PINNED_SITE_SHA}" in text
    assert "policy_ref: ${{ github.sha }}" in text
    assert "publication_staging_id: ${{ matrix.staging_id }}" in text
    assert "build-pages.yml@site" not in text
    assert "policy_ref: policy" not in text
    assert "PR #848 Site merge commit" in text
    assert "maintainer documentation staging mapping" in text
    assert "pristine Site tests before" in text
    assert "publication-sources lock" in text
    assert "build-only" in text
    assert "cannot deploy Pages" in text
    assert "skill_ref:" not in text
    assert "webapp_ref:" not in text
    assert len(PINNED_SITE_SHA) == 40
