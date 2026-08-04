from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = ROOT / ".github/workflows"


def test_webapp_workflows_have_no_github_pages_deployment_route() -> None:
    workflow_files = sorted(
        path
        for path in WORKFLOWS.iterdir()
        if path.is_file() and path.suffix in {".yml", ".yaml"}
    )
    assert workflow_files, "expected at least one webapp validation workflow"

    forbidden = (
        "actions/upload-pages-artifact@",
        "actions/configure-pages@",
        "actions/deploy-pages@",
        "pages: write",
        "name: github-pages",
        "deploy: true",
    )
    for workflow_file in workflow_files:
        workflow = workflow_file.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in workflow, (
                f"{workflow_file.relative_to(ROOT)} contains forbidden Pages "
                f"deployment token {token!r}"
            )

    assert not (WORKFLOWS / "pages.yml").exists()
    assert not (WORKFLOWS / "deploy-pages.yml").exists()
