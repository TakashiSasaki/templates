from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from scripts.generate_docs_build_info import build_metadata, write_build_info

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


def test_build_metadata_preserves_ci_identity_and_jst_timestamp() -> None:
    built_at = datetime(2026, 8, 3, 1, 45, 0, tzinfo=UTC)

    metadata = build_metadata(
        commit="a" * 40,
        repository="TakashiSasaki/templates",
        run_id=123,
        run_number=45,
        built_at=built_at,
    )

    assert metadata == {
        "built_at_utc": "2026-08-03T01:45:00Z",
        "built_at_jst": "2026-08-03T10:45:00+09:00",
        "commit": "a" * 40,
        "repository": "TakashiSasaki/templates",
        "run_id": 123,
        "run_number": 45,
    }


def test_build_metadata_rejects_invalid_identity_values() -> None:
    built_at = datetime(2026, 8, 3, tzinfo=UTC)

    with pytest.raises(ValueError, match="40-character lowercase hexadecimal"):
        build_metadata(
            commit="not-a-commit",
            repository="TakashiSasaki/templates",
            run_id=0,
            run_number=0,
            built_at=built_at,
        )
    with pytest.raises(ValueError, match="owner/repository"):
        build_metadata(
            commit="b" * 40,
            repository="templates",
            run_id=0,
            run_number=0,
            built_at=built_at,
        )
    with pytest.raises(ValueError, match="non-negative"):
        build_metadata(
            commit="b" * 40,
            repository="TakashiSasaki/templates",
            run_id=-1,
            run_number=0,
            built_at=built_at,
        )


def test_write_build_info_creates_the_expected_json(tmp_path: Path) -> None:
    output = tmp_path / "nested/build-info.json"
    metadata = {
        "built_at_utc": "2026-08-03T01:45:00Z",
        "built_at_jst": "2026-08-03T10:45:00+09:00",
        "commit": "c" * 40,
        "repository": "TakashiSasaki/templates",
        "run_id": 0,
        "run_number": 0,
    }

    write_build_info(output, metadata)

    assert json.loads(output.read_text(encoding="utf-8")) == metadata
    assert output.read_text(encoding="utf-8").endswith("\n")
