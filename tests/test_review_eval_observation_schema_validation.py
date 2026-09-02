from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CASE_ROOT = ROOT / "review-evals" / "cases"
VALIDATOR = ROOT / "scripts" / "validate_review_eval_observation.py"


@pytest.mark.parametrize(
    ("schema_option", "label"),
    (
        ("--case-schema", "case"),
        ("--observation-schema", "observation"),
    ),
)
def test_validator_rejects_invalid_schema_without_traceback(
    tmp_path: Path,
    schema_option: str,
    label: str,
) -> None:
    case_path = sorted(CASE_ROOT.rglob("*.json"))[0]
    observation_path = tmp_path / "observation.json"
    observation_path.write_text("{}\n", encoding="utf-8")

    invalid_schema_path = tmp_path / "invalid-schema.json"
    invalid_schema_path.write_text(
        json.dumps(
            {
                "$schema": "https://json-schema.org/draft/2020-12/schema",
                "type": 17,
            }
        )
        + "\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--case",
            str(case_path),
            "--observation",
            str(observation_path),
            schema_option,
            str(invalid_schema_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 1
    assert f"{label} schema invalid" in result.stderr
    assert result.stdout == ""
    assert "Traceback" not in result.stderr
