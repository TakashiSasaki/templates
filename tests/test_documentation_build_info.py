from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/pages.yml"
PUBLICATION_GUIDE = ROOT / "docs/documentation-publication.md"
BUILD_INFO_GENERATOR = ROOT / "scripts/generate_docs_build_info.py"


def test_workflow_and_local_reproduction_share_build_info_generator() -> None:
    workflow = WORKFLOW.read_text(encoding="utf-8")
    guide = PUBLICATION_GUIDE.read_text(encoding="utf-8")

    assert BUILD_INFO_GENERATOR.is_file()
    assert ".venv/bin/python scripts/generate_docs_build_info.py" in workflow
    assert '--commit "$BUILD_COMMIT"' in workflow
    assert '--repository "$BUILD_REPOSITORY"' in workflow
    assert '--run-id "$BUILD_RUN_ID"' in workflow
    assert '--run-number "$BUILD_RUN_NUMBER"' in workflow
    assert "from datetime import datetime, timezone" not in workflow

    assert "python scripts/generate_docs_build_info.py" in guide
    assert '--commit "$(git rev-parse HEAD)"' in guide
    assert "--repository TakashiSasaki/templates" in guide
    assert "python -m mkdocs build --strict --clean" in guide
    assert guide.index("python scripts/generate_docs_build_info.py") < guide.index(
        "python -m mkdocs build --strict --clean"
    )
