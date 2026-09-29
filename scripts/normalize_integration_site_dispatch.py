#!/usr/bin/env python3
"""Validate Integration promotion events and normalize Site workflow inputs."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path
from typing import Any


EVENT_TYPE = "publication.integration-promoted"
BOUNDARY = "integration-to-site"
OUTPUT_FIELDS = {
    "integration_revision": "integration_revision",
    "bundle_schema": "bundle_schema",
    "bundle_identity": "bundle_identity",
    "content_digest": "content_digest",
    "artifact_id": "artifact_id",
    "artifact_digest": "artifact_digest",
    "artifact_name": "artifact_name",
    "run_id": "run_id",
    "attempt": "attempt",
    "workflow_head": "workflow_head",
    "workflow_name": "workflow_name",
    "workflow_event": "workflow_event",
    "qualification_artifact_id": "qualification_artifact_id",
    "qualification_artifact_digest": "qualification_artifact_digest",
    "qualification_artifact_name": "qualification_artifact_name",
    "verified_receipt_digest": "verified_receipt_digest",
    "verified_receipt_artifact_id": "verified_receipt_artifact_id",
    "verified_receipt_artifact_digest": "verified_receipt_artifact_digest",
    "verified_receipt_artifact_name": "verified_receipt_artifact_name",
    "source_pr": "source_pr",
}


def exact_object(value: Any, expected: set[str], label: str) -> dict[str, Any]:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"{label} has unsupported or missing fields")
    return value


def text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value or value.strip() != value:
        raise ValueError(f"{label} must be a non-empty string")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError(f"{label} contains a control character")
    return value


def full_sha(value: Any, label: str) -> str:
    result = text(value, label)
    if re.fullmatch(r"[0-9a-f]{40}", result) is None:
        raise ValueError(f"{label} must be a full lowercase commit SHA")
    return result


def digest(value: Any, label: str, *, prefixed: bool = False) -> str:
    result = text(value, label)
    pattern = r"sha256:[0-9a-f]{64}" if prefixed else r"[0-9a-f]{64}"
    if re.fullmatch(pattern, result) is None:
        raise ValueError(f"{label} has an invalid SHA-256 form")
    return result


def positive_decimal(value: Any, label: str) -> str:
    result = text(value, label)
    if re.fullmatch(r"[1-9][0-9]*", result) is None:
        raise ValueError(f"{label} must be a positive decimal identity")
    return result


def artifact(value: Any, label: str) -> dict[str, str]:
    record = exact_object(value, {"id", "digest", "name"}, label)
    return {
        "id": positive_decimal(record["id"], f"{label}.id"),
        "digest": digest(record["digest"], f"{label}.digest", prefixed=True),
        "name": text(record["name"], f"{label}.name"),
    }


def normalize_repository_dispatch(event: Any) -> dict[str, str]:
    if not isinstance(event, dict) or event.get("action") != EVENT_TYPE:
        raise ValueError("repository dispatch action is not the supported promotion event")

    payload = exact_object(
        event.get("client_payload"),
        {"schema_version", "boundary", "release"},
        "client_payload",
    )
    if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
        raise ValueError("client_payload.schema_version must be integer 1")
    if payload["boundary"] != BOUNDARY:
        raise ValueError("client_payload.boundary is unsupported")

    release = exact_object(
        payload["release"],
        {
            "integration_revision",
            "bundle",
            "workflow",
            "qualification_artifact",
            "verified_receipt",
            "source_pr",
        },
        "client_payload.release",
    )
    bundle = exact_object(
        release["bundle"],
        {"schema", "identity", "content_digest", "artifact"},
        "release.bundle",
    )
    workflow = exact_object(
        release["workflow"],
        {"run_id", "attempt", "head", "name", "event"},
        "release.workflow",
    )
    receipt = exact_object(
        release["verified_receipt"],
        {"digest", "artifact"},
        "release.verified_receipt",
    )

    schema = text(bundle["schema"], "release.bundle.schema")
    if re.fullmatch(r"[1-9][0-9]*", schema) is None:
        raise ValueError("release.bundle.schema must be a positive decimal string")
    if text(workflow["name"], "release.workflow.name") != "Notify Site after Integration adoption":
        raise ValueError("release.workflow.name is not the trusted promotion workflow")
    if text(workflow["event"], "release.workflow.event") != "pull_request":
        raise ValueError("release.workflow.event is not the trusted pull_request event")

    bundle_artifact = artifact(bundle["artifact"], "release.bundle.artifact")
    qualification = artifact(
        release["qualification_artifact"], "release.qualification_artifact"
    )
    receipt_artifact = artifact(receipt["artifact"], "release.verified_receipt.artifact")

    return {
        "integration_revision": full_sha(release["integration_revision"], "release.integration_revision"),
        "bundle_schema": schema,
        "bundle_identity": digest(bundle["identity"], "release.bundle.identity"),
        "content_digest": digest(bundle["content_digest"], "release.bundle.content_digest"),
        "artifact_id": bundle_artifact["id"],
        "artifact_digest": bundle_artifact["digest"],
        "artifact_name": bundle_artifact["name"],
        "run_id": positive_decimal(workflow["run_id"], "release.workflow.run_id"),
        "attempt": positive_decimal(workflow["attempt"], "release.workflow.attempt"),
        "workflow_head": full_sha(workflow["head"], "release.workflow.head"),
        "workflow_name": workflow["name"],
        "workflow_event": workflow["event"],
        "qualification_artifact_id": qualification["id"],
        "qualification_artifact_digest": qualification["digest"],
        "qualification_artifact_name": qualification["name"],
        "verified_receipt_digest": digest(receipt["digest"], "release.verified_receipt.digest"),
        "verified_receipt_artifact_id": receipt_artifact["id"],
        "verified_receipt_artifact_digest": receipt_artifact["digest"],
        "verified_receipt_artifact_name": receipt_artifact["name"],
        "source_pr": positive_decimal(release["source_pr"], "release.source_pr"),
    }


def normalize_manual_dispatch(environment: dict[str, str]) -> dict[str, str]:
    values = {
        output: environment.get(f"MANUAL_{input_name.upper()}", "")
        for output, input_name in OUTPUT_FIELDS.items()
        if output != "source_pr"
    }
    values["source_pr"] = ""
    for name, value in values.items():
        if not isinstance(value, str):
            raise ValueError(f"manual input {name} is not a string")
        if any(ord(character) < 32 or ord(character) == 127 for character in value):
            raise ValueError(f"manual input {name} contains a control character")
    return values


def write_outputs(path: str, values: dict[str, str]) -> None:
    if not path:
        raise ValueError("GITHUB_OUTPUT is required")
    Path(path).write_text(
        "".join(f"{OUTPUT_FIELDS[name]}={value}\n" for name, value in values.items()),
        encoding="utf-8",
    )


def main() -> None:
    event_name = os.environ.get("GITHUB_EVENT_NAME", "")
    if event_name == "repository_dispatch":
        event = json.loads(Path(os.environ["GITHUB_EVENT_PATH"]).read_text(encoding="utf-8"))
        values = normalize_repository_dispatch(event)
    elif event_name == "workflow_dispatch":
        values = normalize_manual_dispatch(dict(os.environ))
    else:
        raise ValueError("unsupported Site reconciliation event")
    write_outputs(os.environ.get("GITHUB_OUTPUT", ""), values)


if __name__ == "__main__":
    try:
        main()
    except (KeyError, OSError, json.JSONDecodeError, ValueError) as error:
        raise SystemExit(f"Integration-to-Site event rejected: {error}") from error
