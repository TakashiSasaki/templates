from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/build-pages.yml"


def test_reusable_build_hashes_the_pinned_site_workflow_definition() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    site_checkout = (
        "- name: Check out site implementation\n"
        "        uses: actions/checkout@v7\n"
        "        with:\n"
        "          ref: ${{ inputs.site_ref || github.event.pull_request.head.sha || github.sha }}"
    )
    workflow_checkout = (
        "- name: Check out executed build workflow definition\n"
        "        uses: actions/checkout@v7\n"
        "        with:\n"
        "          ref: ${{ inputs.site_ref || github.sha }}\n"
        "          path: workflow-source"
    )

    assert site_checkout in text
    assert workflow_checkout in text
    assert "workflow-source/.github/workflows/build-pages.yml" not in text
    assert "run: python site-source/scripts/site_build_artifact.py" in text


def test_reusable_build_keeps_artifact_discovery_read_only() -> None:
    text = WORKFLOW.read_text(encoding="utf-8")

    assert "    permissions:\n      contents: read\n      actions: read" in text
    assert "persist-credentials: false" in text
