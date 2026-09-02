#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator
from jsonschema.exceptions import SchemaError

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CASE_SCHEMA = ROOT / "review-evals" / "review-eval-case.schema.json"
DEFAULT_OBSERVATION_SCHEMA = (
    ROOT / "review-evals" / "review-eval-observation.schema.json"
)


class ObservationValidationError(ValueError):
    pass


def _load_json(path: Path) -> dict[str, Any]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ObservationValidationError(f"{path}: expected one JSON object")
    return data


def _validate_schema(
    instance: dict[str, Any], schema: dict[str, Any], label: str
) -> None:
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError as exc:
        raise ObservationValidationError(
            f"{label} schema invalid: {exc.message}"
        ) from exc

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(instance), key=lambda item: list(item.path))
    if errors:
        messages = "; ".join(error.message for error in errors)
        raise ObservationValidationError(f"{label}: {messages}")


def _require_valid_indices(
    observation: dict[str, Any], field: str, source: list[Any]
) -> None:
    indices = observation["observations"][field]
    if indices != sorted(indices):
        raise ObservationValidationError(f"{field}: indices must be sorted")
    invalid = [index for index in indices if index < 0 or index >= len(source)]
    if invalid:
        raise ObservationValidationError(
            f"{field}: indices outside frozen case range: {invalid}"
        )


def validate_observation(
    case_path: Path,
    observation_path: Path,
    case_schema_path: Path = DEFAULT_CASE_SCHEMA,
    observation_schema_path: Path = DEFAULT_OBSERVATION_SCHEMA,
) -> None:
    case_bytes = case_path.read_bytes()
    case_data = json.loads(case_bytes.decode("utf-8"))
    if not isinstance(case_data, dict):
        raise ObservationValidationError(f"{case_path}: expected one JSON object")
    case = case_data

    observation = _load_json(observation_path)
    case_schema = _load_json(case_schema_path)
    observation_schema = _load_json(observation_schema_path)

    _validate_schema(case, case_schema, "case")
    _validate_schema(observation, observation_schema, "observation")

    expected_digest = hashlib.sha256(case_bytes).hexdigest()
    if observation["case"]["id"] != case["id"]:
        raise ObservationValidationError("case.id does not match frozen case")
    if observation["case"]["sha256"] != expected_digest:
        raise ObservationValidationError("case.sha256 does not match frozen case bytes")

    _require_valid_indices(
        observation,
        "risk_domain_indices_dispositioned",
        case["risk_domains"],
    )
    for field, case_field in (
        ("must_investigate_indices_observed", "must_investigate"),
        ("must_identify_indices_observed", "must_identify"),
        ("must_not_claim_indices_violated", "must_not_claim"),
    ):
        _require_valid_indices(
            observation,
            field,
            case["expected_review"][case_field],
        )

    reported = observation["observations"]["reported_finding_count"]
    unsupported = observation["observations"]["unsupported_finding_count"]
    if isinstance(reported, int) and isinstance(unsupported, int):
        if unsupported > reported:
            raise ObservationValidationError(
                "unsupported_finding_count cannot exceed reported_finding_count"
            )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate one non-authoritative reviewer-evaluation observation."
    )
    parser.add_argument("--case", type=Path, required=True)
    parser.add_argument("--observation", type=Path, required=True)
    parser.add_argument("--case-schema", type=Path, default=DEFAULT_CASE_SCHEMA)
    parser.add_argument(
        "--observation-schema",
        type=Path,
        default=DEFAULT_OBSERVATION_SCHEMA,
    )
    args = parser.parse_args()

    try:
        validate_observation(
            args.case,
            args.observation,
            args.case_schema,
            args.observation_schema,
        )
    except (ObservationValidationError, OSError, UnicodeError, json.JSONDecodeError) as exc:
        print(f"review evaluation observation invalid: {exc}", file=sys.stderr)
        return 1

    print("review evaluation observation valid")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
