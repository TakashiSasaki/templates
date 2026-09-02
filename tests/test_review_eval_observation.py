from __future__ import annotations

import copy
import hashlib
import json
import subprocess
import sys
from pathlib import Path

from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]
EVAL_ROOT = ROOT / "review-evals"
CASE_ROOT = EVAL_ROOT / "cases"
OBSERVATION_SCHEMA = EVAL_ROOT / "review-eval-observation.schema.json"
VALIDATOR = ROOT / "scripts" / "validate_review_eval_observation.py"
RUN_PROTOCOL = EVAL_ROOT / "run-protocol.md"


def _case_paths() -> list[Path]:
    return sorted(CASE_ROOT.rglob("*.json"))


def _observation_for(case_path: Path, trial_index: int = 1) -> dict[str, object]:
    case_bytes = case_path.read_bytes()
    case = json.loads(case_bytes.decode("utf-8"))
    expected = case["expected_review"]
    disposition = expected["disposition"]
    finding_count = 1 if disposition == "blocking-finding" else 0

    return {
        "schema_version": 1,
        "authority": "non-authoritative-evaluation-observation",
        "case": {
            "id": case["id"],
            "sha256": hashlib.sha256(case_bytes).hexdigest(),
        },
        "run": {
            "run_id": "synthetic-test-run",
            "trial_index": trial_index,
            "procedure_bundle_identity": "procedure-bundle:test",
            "semantic_policy_identity": "semantic-policy:test",
            "fixture_identity": "fixture:test",
            "evaluated_reviewer_configuration_identity": "reviewer-config:test",
            "execution_evidence_identity": "execution-evidence:test",
            "evaluator_identity": "evaluator:test",
        },
        "observations": {
            "evaluation_completed": True,
            "reported_disposition": disposition,
            "substantive_analysis_completed": True,
            "task_substitution_observed": False,
            "risk_domain_indices_dispositioned": list(range(len(case["risk_domains"]))),
            "candidate_generation_observed": True,
            "candidate_falsification_observed": True,
            "must_investigate_indices_observed": list(
                range(len(expected["must_investigate"]))
            ),
            "must_identify_indices_observed": list(
                range(len(expected["must_identify"]))
            ),
            "must_not_claim_indices_violated": [],
            "reported_finding_count": finding_count,
            "unsupported_finding_count": 0,
            "limitations_preserved": True,
        },
    }


def _run_validator(
    tmp_path: Path, case_path: Path, observation: dict[str, object]
) -> subprocess.CompletedProcess[str]:
    observation_path = tmp_path / "observation.json"
    observation_path.write_text(
        json.dumps(observation, indent=2) + "\n",
        encoding="utf-8",
    )
    return subprocess.run(
        [
            sys.executable,
            str(VALIDATOR),
            "--case",
            str(case_path),
            "--observation",
            str(observation_path),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_review_eval_observation_schema_is_valid_and_non_authoritative() -> None:
    schema = json.loads(OBSERVATION_SCHEMA.read_text(encoding="utf-8"))
    Draft202012Validator.check_schema(schema)
    assert schema["properties"]["authority"]["const"] == (
        "non-authoritative-evaluation-observation"
    )

    protocol = RUN_PROTOCOL.read_text(encoding="utf-8")
    assert "evaluation data only" in protocol
    assert "does not require the reviewed system to emit JSON" in protocol
    assert "repository-owned review-result wire format" in protocol
    assert "must preserve what the reviewer actually emitted" in protocol


def test_valid_observation_can_be_bound_to_every_current_case(tmp_path: Path) -> None:
    for trial_index, case_path in enumerate(_case_paths(), start=1):
        result = _run_validator(
            tmp_path,
            case_path,
            _observation_for(case_path, trial_index),
        )
        assert result.returncode == 0, result.stdout + result.stderr


def test_observation_validator_rejects_wrong_case_identity(tmp_path: Path) -> None:
    case_path = _case_paths()[0]
    observation = _observation_for(case_path)
    observation["case"]["id"] = "different-case"  # type: ignore[index]

    result = _run_validator(tmp_path, case_path, observation)
    assert result.returncode == 1
    assert "case.id does not match frozen case" in result.stdout


def test_observation_validator_rejects_wrong_case_digest(tmp_path: Path) -> None:
    case_path = _case_paths()[0]
    observation = _observation_for(case_path)
    observation["case"]["sha256"] = "0" * 64  # type: ignore[index]

    result = _run_validator(tmp_path, case_path, observation)
    assert result.returncode == 1
    assert "case.sha256 does not match frozen case bytes" in result.stdout


def test_observation_validator_rejects_case_relative_index_overflow(
    tmp_path: Path,
) -> None:
    case_path = _case_paths()[0]
    case = json.loads(case_path.read_text(encoding="utf-8"))
    observation = _observation_for(case_path)
    observation["observations"]["must_identify_indices_observed"] = [  # type: ignore[index]
        len(case["expected_review"]["must_identify"])
    ]

    result = _run_validator(tmp_path, case_path, observation)
    assert result.returncode == 1
    assert "indices outside frozen case range" in result.stdout


def test_observation_validator_rejects_unsorted_indices(tmp_path: Path) -> None:
    case_path = next(
        path
        for path in _case_paths()
        if len(json.loads(path.read_text(encoding="utf-8"))["risk_domains"]) >= 2
    )
    observation = _observation_for(case_path)
    observation["observations"]["risk_domain_indices_dispositioned"] = [1, 0]  # type: ignore[index]

    result = _run_validator(tmp_path, case_path, observation)
    assert result.returncode == 1
    assert "indices must be sorted" in result.stdout


def test_observation_validator_rejects_impossible_unsupported_count(
    tmp_path: Path,
) -> None:
    case_path = next(
        path
        for path in _case_paths()
        if json.loads(path.read_text(encoding="utf-8"))["expected_review"][
            "disposition"
        ]
        == "blocking-finding"
    )
    observation = _observation_for(case_path)
    observation["observations"]["reported_finding_count"] = 1  # type: ignore[index]
    observation["observations"]["unsupported_finding_count"] = 2  # type: ignore[index]

    result = _run_validator(tmp_path, case_path, observation)
    assert result.returncode == 1
    assert "cannot exceed reported_finding_count" in result.stdout


def test_schema_can_record_false_completion_instead_of_censoring_it() -> None:
    schema = json.loads(OBSERVATION_SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    control_path = next(CASE_ROOT.glob("control/*.json"))
    observation = _observation_for(control_path)
    observation["observations"]["substantive_analysis_completed"] = False  # type: ignore[index]
    observation["observations"]["task_substitution_observed"] = True  # type: ignore[index]

    assert not list(validator.iter_errors(observation))


def test_schema_can_record_missing_review_output() -> None:
    schema = json.loads(OBSERVATION_SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    observation = _observation_for(_case_paths()[0])
    observed = observation["observations"]  # type: ignore[assignment]
    observed["reported_disposition"] = "not-reported"  # type: ignore[index]
    observed["reported_finding_count"] = None  # type: ignore[index]
    observed["unsupported_finding_count"] = None  # type: ignore[index]
    observed["substantive_analysis_completed"] = False  # type: ignore[index]
    observed["candidate_generation_observed"] = False  # type: ignore[index]
    observed["candidate_falsification_observed"] = False  # type: ignore[index]

    assert not list(validator.iter_errors(observation))


def test_not_reported_disposition_requires_null_finding_counts() -> None:
    schema = json.loads(OBSERVATION_SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    observation = _observation_for(_case_paths()[0])
    observed = observation["observations"]  # type: ignore[assignment]
    observed["reported_disposition"] = "not-reported"  # type: ignore[index]
    observed["reported_finding_count"] = 0  # type: ignore[index]
    observed["unsupported_finding_count"] = 0  # type: ignore[index]

    assert list(validator.iter_errors(observation))


def test_observation_schema_does_not_accept_review_wire_fields() -> None:
    schema = json.loads(OBSERVATION_SCHEMA.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema)
    observation = _observation_for(_case_paths()[0])

    for field in ("provider_event", "review_body", "comments", "confidence"):
        invalid = copy.deepcopy(observation)
        invalid[field] = "not part of the evaluation observation contract"
        assert list(validator.iter_errors(invalid)), field
