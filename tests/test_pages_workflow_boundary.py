from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BUILD_WORKFLOW = ROOT / ".github/workflows/build-pages.yml"
DEPLOY_WORKFLOW = ROOT / ".github/workflows/deploy-pages.yml"


def test_reusable_workflow_is_build_only() -> None:
    workflow = BUILD_WORKFLOW.read_text(encoding="utf-8")
    trigger_block = workflow.split("\npermissions:\n", maxsplit=1)[0]

    assert "  pull_request:\n    branches:\n      - site" in trigger_block
    assert "  workflow_call:" in trigger_block
    assert "\n  push:\n" not in trigger_block
    assert "Deprecated compatibility input; ignored" in workflow
    assert "actions/upload-pages-artifact@" in workflow
    assert "actions/configure-pages@" not in workflow
    assert "actions/deploy-pages@" not in workflow
    assert "pages: write" not in workflow
    assert "id-token: write" not in workflow
    assert "name: github-pages" not in workflow
    assert "\n  deploy:\n" not in workflow


def test_deployment_workflow_accepts_only_site_pushes() -> None:
    workflow = DEPLOY_WORKFLOW.read_text(encoding="utf-8")
    trigger_block = workflow.split("\npermissions:\n", maxsplit=1)[0]

    assert "  push:\n    branches:\n      - site" in trigger_block
    assert "pull_request:" not in trigger_block
    assert "workflow_call:" not in trigger_block
    assert "workflow_dispatch:" not in trigger_block
    assert "uses: ./.github/workflows/build-pages.yml" in workflow
    assert "site_ref: ${{ github.sha }}" in workflow
    assert "source_ref: main" in workflow
    assert "github.event_name == 'push'" in workflow
    assert "github.ref == 'refs/heads/site'" in workflow
    assert "github.event.repository.default_branch" not in workflow
    assert "actions/configure-pages@" in workflow
    assert "actions/deploy-pages@" in workflow
    assert "pages: write" in workflow
    assert "id-token: write" in workflow
    assert "name: github-pages" in workflow
