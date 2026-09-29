#!/usr/bin/env python3
"""Build and validate the versioned Integration-to-Site dispatch request."""

from __future__ import annotations

import argparse
import json
import os
import re
from pathlib import Path


EVENT_TYPE = "publication.integration-promoted"
BOUNDARY = "integration-to-site"
MAX_REQUEST_BYTES = 16 * 1024


def required_text(environment: dict[str, str], name: str) -> str:
    value = environment.get(name, "")
    if not value or value.strip() != value:
        raise ValueError(f"{name} must be a non-empty string")
    if any(ord(character) < 32 or ord(character) == 127 for character in value):
        raise ValueError(f"{name} contains a control character")
    return value


def require_pattern(value: str, pattern: str, name: str) -> str:
    if re.fullmatch(pattern, value) is None:
        raise ValueError(f"{name} has an invalid identity format")
    return value


def artifact(environment: dict[str, str], prefix: str) -> dict[str, str]:
    return {
        "id": require_pattern(required_text(environment, f"{prefix}_ID"), r"[1-9][0-9]*", f"{prefix}_ID"),
        "digest": require_pattern(required_text(environment, f"{prefix}_DIGEST"), r"sha256:[0-9a-f]{64}", f"{prefix}_DIGEST"),
        "name": required_text(environment, f"{prefix}_NAME"),
    }


def build_request(environment: dict[str, str]) -> dict[str, object]:
    bundle = {
        "schema": require_pattern(required_text(environment, "BUNDLE_SCHEMA"), r"[1-9][0-9]*", "BUNDLE_SCHEMA"),
        "identity": require_pattern(required_text(environment, "BUNDLE_IDENTITY"), r"[0-9a-f]{64}", "BUNDLE_IDENTITY"),
        "content_digest": require_pattern(required_text(environment, "CONTENT_DIGEST"), r"[0-9a-f]{64}", "CONTENT_DIGEST"),
        "artifact": artifact(environment, "ARTIFACT"),
    }
    workflow = {
        "run_id": require_pattern(required_text(environment, "RUN_ID"), r"[1-9][0-9]*", "RUN_ID"),
        "attempt": require_pattern(required_text(environment, "ATTEMPT"), r"[1-9][0-9]*", "ATTEMPT"),
        "head": require_pattern(required_text(environment, "WORKFLOW_HEAD"), r"[0-9a-f]{40}", "WORKFLOW_HEAD"),
        "name": required_text(environment, "WORKFLOW_NAME"),
        "event": required_text(environment, "WORKFLOW_EVENT"),
    }
    if workflow["name"] != "Notify Site after Integration adoption" or workflow["event"] != "pull_request":
        raise ValueError("workflow provenance is not the trusted promoted-release run")

    release = {
        "integration_revision": require_pattern(required_text(environment, "PRODUCER_SHA"), r"[0-9a-f]{40}", "PRODUCER_SHA"),
        "bundle": bundle,
        "workflow": workflow,
        "qualification_artifact": artifact(environment, "QUALIFICATION_ARTIFACT"),
        "verified_receipt": {
            "digest": require_pattern(required_text(environment, "VERIFIED_RECEIPT_DIGEST"), r"[0-9a-f]{64}", "VERIFIED_RECEIPT_DIGEST"),
            "artifact": artifact(environment, "VERIFIED_RECEIPT_ARTIFACT"),
        },
        "source_pr": require_pattern(required_text(environment, "PR_NUMBER"), r"[1-9][0-9]*", "PR_NUMBER"),
    }
    return {
        "event_type": EVENT_TYPE,
        "client_payload": {
            "schema_version": 1,
            "boundary": BOUNDARY,
            "release": release,
        },
    }


def serialize_request(request: dict[str, object]) -> bytes:
    if set(request) != {"event_type", "client_payload"} or request["event_type"] != EVENT_TYPE:
        raise ValueError("request envelope is malformed")
    payload = request["client_payload"]
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "boundary", "release"}:
        raise ValueError("client_payload must have exactly the three versioned envelope fields")
    if type(payload["schema_version"]) is not int or payload["schema_version"] != 1:
        raise ValueError("client_payload.schema_version must be integer 1")
    if payload["boundary"] != BOUNDARY or not isinstance(payload["release"], dict):
        raise ValueError("client_payload boundary or release object is invalid")

    body = (json.dumps(request, sort_keys=True, separators=(",", ":")) + "\n").encode("utf-8")
    if len(body) > MAX_REQUEST_BYTES:
        raise ValueError("serialized dispatch body exceeds the conservative 16 KiB limit")
    return body


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    body = serialize_request(build_request(dict(os.environ)))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(body)


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError) as error:
        raise SystemExit(f"Integration-to-Site dispatch payload rejected: {error}") from error
