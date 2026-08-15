from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/site-compatibility.yml"
PINNED_SITE_SHA = "e95959f5a47b071fb1178565893ea0d572f4ff97"


def test_policy_workflow_uses_reviewed_immutable_site_revision() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "branches:\n      - policy" in text
    assert "- docs/**" in text
    assert "permissions:\n  contents: read" in text
    assert (
        f"uses: TakashiSasaki/templates/.github/workflows/build-pages.yml@{PINNED_SITE_SHA}"
        in text
    )
    assert f"site_ref: {PINNED_SITE_SHA}" in text
    assert "policy_ref: ${{ github.sha }}" in text
    assert "build-pages.yml@site" not in text
    assert "policy_ref: policy" not in text
    assert len(PINNED_SITE_SHA) == 40
    assert all(character in "0123456789abcdef" for character in PINNED_SITE_SHA)
